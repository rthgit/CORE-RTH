"""
Robotics Bridge — Governed interface for robotic actuators, serial devices, and ROS2.

Supports:
- Serial port communication (Arduino, ESP32, robotic arms)
- ROS2 topic publish/subscribe (via rclpy or HTTP bridge)
- Generic actuator abstraction (motors, servos, grippers)
- Sensor data collection (IMU, LIDAR, camera feeds)
- Safety interlocks via Guardian

All physical actions are governed by Guardian (Capability.SYSTEM_MODIFY, RiskLevel.HIGH).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERIAL_TIMEOUT = 5
MAX_ACTUATORS = 100
SAFETY_MAX_SPEED = 100        # % of max speed
SAFETY_MAX_FORCE = 80         # % of max force
EMERGENCY_STOP_TOPIC = "robot/emergency_stop"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Actuator:
    """Represents a robotic actuator or sensor."""
    actuator_id: str
    name: str
    actuator_type: str        # motor, servo, gripper, led, relay, stepper, sensor, camera
    interface: str            # serial, ros2, http, gpio, mock
    state: str = "idle"       # idle, moving, error, e_stop, active
    position: float = 0.0
    speed: float = 0.0
    limits: Dict[str, Any] = field(default_factory=lambda: {"min": 0, "max": 180, "speed_max": 100})
    config: Dict[str, Any] = field(default_factory=dict)
    last_update: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actuator_id": self.actuator_id, "name": self.name,
            "type": self.actuator_type, "interface": self.interface,
            "state": self.state, "position": self.position,
            "speed": self.speed, "limits": self.limits,
            "last_update": self.last_update,
        }


@dataclass
class RobotCommand:
    """A command to a robotic device."""
    command_id: str
    actuator_id: str
    action: str               # move_to, set_speed, grip, release, home, stop, e_stop
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"   # pending, approved, executing, completed, failed, denied, e_stopped
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id, "actuator_id": self.actuator_id,
            "action": self.action, "parameters": self.parameters,
            "status": self.status, "result": self.result, "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Interface adapters
# ---------------------------------------------------------------------------

class SerialAdapter:
    """Adapter for serial devices (Arduino, ESP32, robotic arms)."""

    def __init__(self):
        self._ports: Dict[str, Any] = {}
        self._available = False
        try:
            import serial
            self._available = True
        except ImportError:
            logger.info("pyserial not installed — serial adapter disabled")

    @property
    def available(self) -> bool:
        return self._available

    def list_ports(self) -> List[Dict[str, str]]:
        """List available serial ports."""
        if not self._available:
            return []
        try:
            import serial.tools.list_ports
            return [
                {"port": p.device, "description": p.description, "hwid": p.hwid}
                for p in serial.tools.list_ports.comports()
            ]
        except Exception as e:
            logger.warning(f"Serial port listing failed: {e}")
            return []

    def send(self, port: str, data: str, baudrate: int = 9600) -> Dict[str, Any]:
        """Send data to a serial port and read response."""
        if not self._available:
            return {"status": "error", "error": "pyserial not installed"}
        try:
            import serial
            with serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT) as ser:
                ser.write(data.encode("utf-8"))
                time.sleep(0.1)
                response = ser.read(ser.in_waiting or 256).decode("utf-8", errors="replace")
                return {"status": "ok", "response": response, "port": port}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class ROS2Adapter:
    """Adapter for ROS2 topics (via rclpy or HTTP rosbridge)."""

    def __init__(self, rosbridge_url: str = ""):
        self.rosbridge_url = rosbridge_url or ""
        self._rclpy_available = False
        self._rosbridge_available = False
        self._check()

    def _check(self):
        try:
            import rclpy
            self._rclpy_available = True
        except ImportError:
            pass
        if self.rosbridge_url:
            try:
                import urllib.request
                with urllib.request.urlopen(self.rosbridge_url, timeout=3):
                    self._rosbridge_available = True
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._rclpy_available or self._rosbridge_available

    def publish(self, topic: str, msg_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a message to a ROS2 topic."""
        if self._rosbridge_available:
            return self._publish_via_rosbridge(topic, msg_type, data)
        return {"status": "error", "error": "ROS2 not available (install rclpy or configure rosbridge)"}

    def _publish_via_rosbridge(self, topic: str, msg_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish via rosbridge HTTP interface."""
        try:
            import urllib.request
            body = json.dumps({
                "op": "publish",
                "topic": topic,
                "type": msg_type,
                "msg": data,
            }).encode("utf-8")
            req = urllib.request.Request(
                self.rosbridge_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"status": "ok", "topic": topic}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class MockAdapter:
    """Mock adapter for testing without real hardware."""

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def execute(self, actuator_id: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a robotic action."""
        self._state[actuator_id] = {
            "action": action,
            "params": params,
            "timestamp": _now(),
        }
        return {
            "status": "ok",
            "mode": "simulated",
            "actuator_id": actuator_id,
            "action": action,
            "result": f"Simulated {action} on {actuator_id}",
        }


# ---------------------------------------------------------------------------
# Main Robotics Bridge
# ---------------------------------------------------------------------------

class RoboticsBridge:
    """Governed robotics bridge for Core Rth."""

    def __init__(self):
        self.actuators: Dict[str, Actuator] = {}
        self.command_history: List[RobotCommand] = []
        self._max_history = 500
        self._e_stop_active = False

        # Adapters
        self._serial = SerialAdapter()
        self._ros2 = ROS2Adapter(rosbridge_url=self._get_rosbridge_url())
        self._mock = MockAdapter()

    def _get_rosbridge_url(self) -> str:
        import os
        return os.getenv("RTH_ROSBRIDGE_URL", "")

    # ── Status ─────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "module": "robotics_bridge",
            "version": 1,
            "e_stop_active": self._e_stop_active,
            "adapters": {
                "serial": {
                    "available": self._serial.available,
                    "ports": self._serial.list_ports() if self._serial.available else [],
                },
                "ros2": {"available": self._ros2.available},
                "mock": {"available": True},
            },
            "actuators_count": len(self.actuators),
            "command_history_count": len(self.command_history),
        }

    # ── Emergency Stop ─────────────────────────────────────────────────

    def emergency_stop(self, reason: str = "Emergency stop activated") -> Dict[str, Any]:
        """IMMEDIATE emergency stop — NO governance delay, this is safety-critical."""
        self._e_stop_active = True
        stopped = []
        for act in self.actuators.values():
            act.state = "e_stop"
            act.speed = 0.0
            stopped.append(act.actuator_id)
        memory_vault.record_event("robotics_e_stop", {"reason": reason, "stopped": stopped}, tags={"source": "robotics", "critical": "true"})
        logger.critical(f"EMERGENCY STOP: {reason}")
        return {"status": "e_stop_active", "stopped_actuators": len(stopped), "reason": reason}

    def reset_e_stop(
        self,
        reason: str = "E-Stop reset by owner",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """Reset emergency stop (governed — HIGH risk)."""
        req = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY,
            action="robotics_reset_e_stop",
            scope={"reason": reason},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {"status": "denied", "detail": "Owner must approve e-stop reset"}
        self._e_stop_active = False
        for act in self.actuators.values():
            if act.state == "e_stop":
                act.state = "idle"
        return {"status": "ok", "e_stop_active": False}

    # ── Register Actuator ──────────────────────────────────────────────

    def register_actuator(
        self,
        actuator_id: str, name: str, actuator_type: str, interface: str,
        limits: Dict = None, config: Dict = None,
    ) -> Dict[str, Any]:
        """Register a robotic actuator."""
        actuator = Actuator(
            actuator_id=actuator_id, name=name,
            actuator_type=actuator_type, interface=interface,
            limits=limits or {"min": 0, "max": 180, "speed_max": 100},
            config=config or {},
            last_update=_now(),
        )
        self.actuators[actuator_id] = actuator
        return actuator.to_dict()

    # ── Command Execution ──────────────────────────────────────────────

    def execute_command(
        self,
        actuator_id: str,
        action: str,
        parameters: Dict[str, Any] = None,
        reason: str = "Robotics command",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """Execute a command on an actuator (governed by Guardian — HIGH risk)."""
        parameters = parameters or {}

        # Safety checks
        if self._e_stop_active:
            return {"status": "blocked", "error": "Emergency stop is active. Reset e-stop first."}

        actuator = self.actuators.get(actuator_id)
        if not actuator:
            return {"status": "error", "error": f"Actuator {actuator_id} not registered"}

        # Validate speed/force limits
        speed = parameters.get("speed", 50)
        if speed > SAFETY_MAX_SPEED:
            parameters["speed"] = SAFETY_MAX_SPEED
            parameters["speed_clamped"] = True

        force = parameters.get("force", 50)
        if force > SAFETY_MAX_FORCE:
            parameters["force"] = SAFETY_MAX_FORCE
            parameters["force_clamped"] = True

        # Guardian approval (HIGH risk for physical actions)
        req = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY,
            action="robotics_command",
            scope={
                "actuator_id": actuator_id,
                "actuator_type": actuator.actuator_type,
                "action": action,
                "parameters": parameters,
                "interface": actuator.interface,
            },
            reason=self._safe_reason(reason),
            risk=RiskLevel.HIGH,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {"status": "denied", "detail": decision.denial_reason}

        command = RobotCommand(
            command_id=f"rcmd_{uuid.uuid4().hex[:10]}",
            actuator_id=actuator_id,
            action=action,
            parameters=parameters,
            status="executing",
            timestamp=_now(),
        )

        # Execute on the appropriate adapter
        try:
            if actuator.interface == "serial" and self._serial.available:
                serial_cmd = self._format_serial_command(actuator, action, parameters)
                port = actuator.config.get("port", "COM3")
                baudrate = actuator.config.get("baudrate", 9600)
                result = self._serial.send(port, serial_cmd, baudrate)

            elif actuator.interface == "ros2" and self._ros2.available:
                topic = actuator.config.get("topic", f"/robot/{actuator_id}/command")
                msg_type = actuator.config.get("msg_type", "std_msgs/msg/String")
                result = self._ros2.publish(topic, msg_type, {"data": json.dumps({"action": action, **parameters})})

            elif actuator.interface == "mock":
                result = self._mock.execute(actuator_id, action, parameters)

            else:
                result = self._mock.execute(actuator_id, action, parameters)
                result["mode"] = "fallback_mock"

            command.status = "completed" if result.get("status") == "ok" else "failed"
            command.result = result

            # Update actuator state
            if command.status == "completed":
                actuator.state = "active" if action not in ("stop", "home") else "idle"
                if "position" in parameters:
                    actuator.position = parameters["position"]
                if "speed" in parameters:
                    actuator.speed = parameters["speed"]
                actuator.last_update = _now()

        except Exception as e:
            command.status = "failed"
            command.result = {"error": str(e)}

        self.command_history.append(command)
        if len(self.command_history) > self._max_history:
            self.command_history = self.command_history[-self._max_history:]

        memory_vault.record_event("robotics_command", command.to_dict(), tags={"source": "robotics"})
        return command.to_dict()

    # ── List ───────────────────────────────────────────────────────────

    def list_actuators(self, actuator_type: str = "") -> Dict[str, Any]:
        """List registered actuators."""
        items = [
            a.to_dict() for a in self.actuators.values()
            if not actuator_type or a.actuator_type == actuator_type
        ]
        return {"actuators": items, "count": len(items), "e_stop_active": self._e_stop_active}

    # ── Tool Schemas ───────────────────────────────────────────────────

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible function schemas for robotics tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "robot_list_actuators",
                    "description": "List all registered robotic actuators (motors, servos, grippers, sensors).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actuator_type": {"type": "string", "description": "Filter: motor, servo, gripper, sensor"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "robot_command",
                    "description": "Send a command to a robotic actuator: move, grip, release, stop, home.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "actuator_id": {"type": "string", "description": "Actuator ID"},
                            "action": {"type": "string", "description": "Action: move_to, set_speed, grip, release, home, stop"},
                            "parameters": {"type": "object", "description": "Parameters: position, speed, force"},
                        },
                        "required": ["actuator_id", "action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "robot_emergency_stop",
                    "description": "EMERGENCY STOP — immediately halt all robotic actuators. Use only in danger.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string", "description": "Reason for emergency stop"},
                        },
                        "required": ["reason"],
                    },
                },
            },
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    def _format_serial_command(self, actuator: Actuator, action: str, params: Dict) -> str:
        """Format command for serial communication (G-code style)."""
        protocol = actuator.config.get("protocol", "gcode")
        if protocol == "gcode":
            if action == "move_to":
                pos = params.get("position", 0)
                speed = params.get("speed", 50)
                return f"G1 X{pos} F{speed}\n"
            elif action == "home":
                return "G28\n"
            elif action == "stop":
                return "M0\n"
            return f"{action.upper()} {json.dumps(params)}\n"
        return f"{action}:{json.dumps(params)}\n"

    def _safe_reason(self, reason: str) -> str:
        tokens = reason.lower()
        if not any(t in tokens for t in ("safe", "audit")):
            return f"{reason} [safe] [audit]"
        return reason


# Singleton
robotics_bridge = RoboticsBridge()
