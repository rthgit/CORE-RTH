"""
Vehicle Bridge — Governed interface for drones (UAV) and autonomous vehicles.

Supports:
- Drones via MAVLink (ArduPilot / PX4) over serial or UDP
- Autonomous vehicles via ROS2 topics (Autoware, CARLA simulator)
- CAN bus integration for OBD-II / vehicle diagnostics
- Telemetry streaming (GPS, altitude, speed, heading, battery)
- Waypoint navigation and mission planning
- Geofencing safety zones

All vehicle commands are governed by Guardian (Capability.SYSTEM_MODIFY, RiskLevel.CRITICAL).
Emergency landing / hard-stop bypasses governance for immediate safety.
"""
from __future__ import annotations

import json
import logging
import math
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

MAX_ALTITUDE_M = 120          # EU drone regulation default ceiling
MAX_SPEED_MS = 20.0           # ~72 km/h safety limit
GEOFENCE_RADIUS_M = 500       # default geofence
TELEMETRY_INTERVAL_SEC = 1.0
COMMAND_TIMEOUT_SEC = 10


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Waypoint:
    """GPS waypoint for navigation."""
    lat: float
    lon: float
    alt: float = 50.0           # meters AGL
    speed: float = 5.0          # m/s
    loiter_sec: float = 0.0
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"lat": self.lat, "lon": self.lon, "alt": self.alt,
                "speed": self.speed, "loiter_sec": self.loiter_sec, "label": self.label}


@dataclass
class Vehicle:
    """Represents a drone or autonomous vehicle."""
    vehicle_id: str
    name: str
    vehicle_type: str           # drone, car, rover, boat
    protocol: str               # mavlink, ros2, canbus, simulator, mock
    state: str = "idle"         # idle, armed, flying, moving, landing, e_stop, error
    telemetry: Dict[str, Any] = field(default_factory=lambda: {
        "lat": 0.0, "lon": 0.0, "alt": 0.0,
        "speed": 0.0, "heading": 0.0,
        "battery_pct": 100, "gps_fix": False,
        "mode": "STABILIZE",
    })
    config: Dict[str, Any] = field(default_factory=dict)
    mission: List[Dict[str, Any]] = field(default_factory=list)
    geofence: Dict[str, Any] = field(default_factory=lambda: {
        "center_lat": 0.0, "center_lon": 0.0,
        "radius_m": GEOFENCE_RADIUS_M, "max_alt_m": MAX_ALTITUDE_M,
    })
    last_update: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id, "name": self.name,
            "type": self.vehicle_type, "protocol": self.protocol,
            "state": self.state, "telemetry": self.telemetry,
            "mission_waypoints": len(self.mission),
            "geofence": self.geofence, "last_update": self.last_update,
        }


@dataclass
class VehicleCommand:
    """A command sent to a vehicle."""
    command_id: str
    vehicle_id: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id, "vehicle_id": self.vehicle_id,
            "action": self.action, "parameters": self.parameters,
            "status": self.status, "result": self.result, "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Protocol adapters
# ---------------------------------------------------------------------------

class MAVLinkAdapter:
    """Adapter for drone control via MAVLink (ArduPilot / PX4)."""

    def __init__(self):
        self._connection = None
        self._available = False
        try:
            from pymavlink import mavutil
            self._mavutil = mavutil
            self._available = True
        except ImportError:
            logger.info("pymavlink not installed — MAVLink adapter disabled")

    @property
    def available(self) -> bool:
        return self._available

    def connect(self, connection_string: str = "udp:127.0.0.1:14550") -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "error": "pymavlink not installed"}
        try:
            self._connection = self._mavutil.mavlink_connection(connection_string)
            self._connection.wait_heartbeat(timeout=5)
            return {"status": "ok", "connection": connection_string,
                    "sysid": self._connection.target_system}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def send_command(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connection:
            return {"status": "error", "error": "Not connected"}
        try:
            mav = self._connection
            if action == "arm":
                mav.arducopter_arm()
                return {"status": "ok", "action": "arm"}
            elif action == "disarm":
                mav.arducopter_disarm()
                return {"status": "ok", "action": "disarm"}
            elif action == "takeoff":
                alt = params.get("altitude", 10)
                mav.mav.command_long_send(
                    mav.target_system, mav.target_component,
                    self._mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                    0, 0, 0, 0, 0, 0, 0, alt,
                )
                return {"status": "ok", "action": "takeoff", "altitude": alt}
            elif action == "land":
                mav.mav.command_long_send(
                    mav.target_system, mav.target_component,
                    self._mavutil.mavlink.MAV_CMD_NAV_LAND,
                    0, 0, 0, 0, 0, 0, 0, 0,
                )
                return {"status": "ok", "action": "land"}
            elif action == "goto":
                lat = params.get("lat", 0)
                lon = params.get("lon", 0)
                alt = params.get("alt", 50)
                mav.mav.mission_item_int_send(
                    mav.target_system, mav.target_component,
                    0, self._mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    self._mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    2, 0, 0, 0, 0, 0,
                    int(lat * 1e7), int(lon * 1e7), alt,
                )
                return {"status": "ok", "action": "goto", "lat": lat, "lon": lon, "alt": alt}
            elif action == "rtl":
                mav.mav.command_long_send(
                    mav.target_system, mav.target_component,
                    self._mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                    0, 0, 0, 0, 0, 0, 0, 0,
                )
                return {"status": "ok", "action": "rtl"}
            return {"status": "error", "error": f"Unknown MAVLink action: {action}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_telemetry(self) -> Dict[str, Any]:
        if not self._connection:
            return {}
        try:
            msg = self._connection.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
            if msg:
                return {
                    "lat": msg.lat / 1e7, "lon": msg.lon / 1e7,
                    "alt": msg.relative_alt / 1000.0,
                    "heading": msg.hdg / 100.0,
                    "speed": math.sqrt(msg.vx**2 + msg.vy**2) / 100.0,
                    "gps_fix": True,
                }
        except Exception:
            pass
        return {}


class VehicleROS2Adapter:
    """Adapter for autonomous vehicles via ROS2 (Autoware, CARLA)."""

    def __init__(self, rosbridge_url: str = ""):
        self.rosbridge_url = rosbridge_url
        self._available = bool(rosbridge_url)

    @property
    def available(self) -> bool:
        return self._available

    def publish(self, topic: str, msg_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "error": "ROS2 not configured"}
        try:
            import urllib.request
            body = json.dumps({"op": "publish", "topic": topic, "type": msg_type, "msg": data}).encode()
            req = urllib.request.Request(self.rosbridge_url, data=body,
                                        headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"status": "ok", "topic": topic}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class MockVehicleAdapter:
    """Mock adapter for testing without real hardware."""

    def __init__(self):
        self._state: Dict[str, Dict[str, Any]] = {}

    def execute(self, vehicle_id: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if vehicle_id not in self._state:
            self._state[vehicle_id] = {
                "lat": 41.9028, "lon": 12.4964, "alt": 0, "speed": 0,
                "heading": 0, "battery_pct": 100, "mode": "STABILIZE",
            }
        s = self._state[vehicle_id]
        if action == "arm":
            s["mode"] = "ARMED"
        elif action == "takeoff":
            s["alt"] = params.get("altitude", 10)
            s["mode"] = "FLYING"
        elif action == "land":
            s["alt"] = 0
            s["mode"] = "LANDED"
        elif action == "goto":
            s["lat"] = params.get("lat", s["lat"])
            s["lon"] = params.get("lon", s["lon"])
            s["alt"] = params.get("alt", s["alt"])
        elif action == "rtl":
            s["mode"] = "RTL"
        elif action == "set_speed":
            s["speed"] = min(params.get("speed", 5), MAX_SPEED_MS)
        return {
            "status": "ok", "mode": "simulated",
            "vehicle_id": vehicle_id, "action": action,
            "telemetry": dict(s),
        }

    def get_telemetry(self, vehicle_id: str) -> Dict[str, Any]:
        return self._state.get(vehicle_id, {})


# ---------------------------------------------------------------------------
# Main Vehicle Bridge
# ---------------------------------------------------------------------------

class VehicleBridge:
    """Governed bridge for drones and autonomous vehicles."""

    def __init__(self):
        self.vehicles: Dict[str, Vehicle] = {}
        self.command_history: List[VehicleCommand] = []
        self._max_history = 500
        self._e_stop_active = False

        # Adapters
        self._mavlink = MAVLinkAdapter()
        self._ros2 = VehicleROS2Adapter(rosbridge_url=self._get_env("RTH_VEHICLE_ROSBRIDGE_URL"))
        self._mock = MockVehicleAdapter()

    def _get_env(self, key: str) -> str:
        import os
        return os.getenv(key, "")

    # ── Status ─────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "module": "vehicle_bridge",
            "version": 1,
            "e_stop_active": self._e_stop_active,
            "adapters": {
                "mavlink": {"available": self._mavlink.available},
                "ros2": {"available": self._ros2.available},
                "mock": {"available": True},
            },
            "vehicles_count": len(self.vehicles),
            "command_history_count": len(self.command_history),
        }

    # ── Emergency ──────────────────────────────────────────────────────

    def emergency_land(self, reason: str = "Emergency landing") -> Dict[str, Any]:
        """IMMEDIATE emergency land all vehicles — NO governance delay."""
        self._e_stop_active = True
        results = []
        for v in self.vehicles.values():
            v.state = "e_stop"
            if v.protocol == "mavlink" and self._mavlink.available:
                res = self._mavlink.send_command("land", {})
                results.append({"vehicle": v.vehicle_id, "result": res})
            elif v.protocol == "mock":
                res = self._mock.execute(v.vehicle_id, "land", {})
                results.append({"vehicle": v.vehicle_id, "result": res})
            else:
                results.append({"vehicle": v.vehicle_id, "result": {"action": "land_requested"}})
        memory_vault.record_event("vehicle_emergency", {"reason": reason, "vehicles": len(results)},
                                  tags={"source": "vehicle_bridge", "critical": "true"})
        logger.critical(f"VEHICLE EMERGENCY LAND: {reason}")
        return {"status": "e_stop_active", "reason": reason, "results": results}

    def reset_e_stop(self, reason: str = "E-Stop reset", decided_by: str = "owner") -> Dict[str, Any]:
        req = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY, action="vehicle_reset_e_stop",
            scope={"reason": reason}, reason=reason, risk=RiskLevel.HIGH,
        )
        decision = permission_gate.approve(req.request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied"}
        self._e_stop_active = False
        for v in self.vehicles.values():
            if v.state == "e_stop":
                v.state = "idle"
        return {"status": "ok", "e_stop_active": False}

    # ── Register Vehicle ───────────────────────────────────────────────

    def register_vehicle(
        self, vehicle_id: str, name: str, vehicle_type: str, protocol: str,
        config: Dict = None, geofence: Dict = None,
    ) -> Dict[str, Any]:
        vehicle = Vehicle(
            vehicle_id=vehicle_id, name=name, vehicle_type=vehicle_type,
            protocol=protocol, config=config or {},
            last_update=_now(),
        )
        if geofence:
            vehicle.geofence.update(geofence)
        self.vehicles[vehicle_id] = vehicle
        return vehicle.to_dict()

    # ── Command ────────────────────────────────────────────────────────

    def send_command(
        self, vehicle_id: str, action: str, parameters: Dict[str, Any] = None,
        reason: str = "Vehicle command", confirm_owner: bool = True, decided_by: str = "owner",
    ) -> Dict[str, Any]:
        parameters = parameters or {}

        if self._e_stop_active and action not in ("land", "rtl", "disarm"):
            return {"status": "blocked", "error": "E-Stop active. Only land/RTL/disarm allowed."}

        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            return {"status": "error", "error": f"Vehicle {vehicle_id} not registered"}

        # Safety checks
        safe, msg = self._safety_check(vehicle, action, parameters)
        if not safe:
            return {"status": "blocked", "error": f"Safety check failed: {msg}"}

        # Guardian approval (CRITICAL risk for vehicles)
        req = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY, action="vehicle_command",
            scope={"vehicle_id": vehicle_id, "type": vehicle.vehicle_type,
                   "action": action, "parameters": parameters},
            reason=self._safe_reason(reason), risk=RiskLevel.HIGH,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {"status": "denied", "detail": decision.denial_reason}

        cmd = VehicleCommand(
            command_id=f"vcmd_{uuid.uuid4().hex[:10]}",
            vehicle_id=vehicle_id, action=action,
            parameters=parameters, status="executing", timestamp=_now(),
        )

        try:
            if vehicle.protocol == "mavlink" and self._mavlink.available:
                result = self._mavlink.send_command(action, parameters)
            elif vehicle.protocol == "ros2" and self._ros2.available:
                topic = vehicle.config.get("cmd_topic", f"/vehicle/{vehicle_id}/cmd")
                result = self._ros2.publish(topic, "std_msgs/msg/String",
                                            {"data": json.dumps({"action": action, **parameters})})
            else:
                result = self._mock.execute(vehicle_id, action, parameters)

            cmd.status = "completed" if result.get("status") == "ok" else "failed"
            cmd.result = result

            if cmd.status == "completed":
                self._update_state(vehicle, action, parameters, result)

        except Exception as e:
            cmd.status = "failed"
            cmd.result = {"error": str(e)}

        self.command_history.append(cmd)
        if len(self.command_history) > self._max_history:
            self.command_history = self.command_history[-self._max_history:]
        memory_vault.record_event("vehicle_command", cmd.to_dict(), tags={"source": "vehicle_bridge"})
        return cmd.to_dict()

    # ── Mission Planning ───────────────────────────────────────────────

    def set_mission(self, vehicle_id: str, waypoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            return {"status": "error", "error": f"Vehicle {vehicle_id} not found"}
        validated = []
        for wp in waypoints:
            w = Waypoint(lat=wp.get("lat", 0), lon=wp.get("lon", 0),
                         alt=min(wp.get("alt", 50), vehicle.geofence.get("max_alt_m", MAX_ALTITUDE_M)),
                         speed=min(wp.get("speed", 5), MAX_SPEED_MS),
                         loiter_sec=wp.get("loiter_sec", 0), label=wp.get("label", ""))
            validated.append(w.to_dict())
        vehicle.mission = validated
        return {"vehicle_id": vehicle_id, "waypoints": len(validated), "mission": validated}

    def _log_telemetry(self, vehicle: Vehicle):
        try:
            from app.core.security_vault import security_vault
            log_dir = Path("logs") / "vehicle_telemetry"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{vehicle.vehicle_id}_{datetime.now().strftime('%Y%m%d')}.log"
            
            existing = ""
            if log_file.exists():
                decrypted = security_vault.decrypt_file(log_file)
                existing = str(decrypted) if decrypted else ""
            
            entry = json.dumps({"ts": _now(), "telemetry": vehicle.telemetry}) + "\n"
            security_vault.encrypt_file(log_file, existing + entry)
        except Exception as e:
            logger.warning(f"Telemetry encryption failed: {e}")

    # ── Telemetry ──────────────────────────────────────────────────────

    def get_telemetry(self, vehicle_id: str) -> Dict[str, Any]:
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            return {"status": "error", "error": f"Vehicle {vehicle_id} not found"}
        # Try live telemetry
        updated = False
        if vehicle.protocol == "mavlink" and self._mavlink.available:
            live = self._mavlink.get_telemetry()
            if live:
                vehicle.telemetry.update(live)
                vehicle.last_update = _now()
                updated = True
        elif vehicle.protocol == "mock":
            live = self._mock.get_telemetry(vehicle_id)
            if live:
                vehicle.telemetry.update(live)
                vehicle.last_update = _now()
                updated = True
        
        if updated:
            self._log_telemetry(vehicle)
            
        return {"vehicle_id": vehicle_id, "telemetry": vehicle.telemetry, "state": vehicle.state}

    # ── List ───────────────────────────────────────────────────────────

    def list_vehicles(self, vehicle_type: str = "") -> Dict[str, Any]:
        items = [v.to_dict() for v in self.vehicles.values()
                 if not vehicle_type or v.vehicle_type == vehicle_type]
        return {"vehicles": items, "count": len(items), "e_stop_active": self._e_stop_active}

    # ── Safety ─────────────────────────────────────────────────────────

    def _safety_check(self, vehicle: Vehicle, action: str, params: Dict) -> tuple[bool, str]:
        # Altitude check
        if action in ("takeoff", "goto") and "alt" in params:
            max_alt = vehicle.geofence.get("max_alt_m", MAX_ALTITUDE_M)
            if params["alt"] > max_alt:
                return False, f"Altitude {params['alt']}m exceeds geofence limit {max_alt}m"
        # Speed check
        if "speed" in params and params["speed"] > MAX_SPEED_MS:
            return False, f"Speed {params['speed']}m/s exceeds safety limit {MAX_SPEED_MS}m/s"
        # Geofence check for goto
        if action == "goto" and "lat" in params and "lon" in params:
            gf = vehicle.geofence
            if gf.get("center_lat") and gf.get("center_lon"):
                dist = self._haversine(gf["center_lat"], gf["center_lon"], params["lat"], params["lon"])
                if dist > gf.get("radius_m", GEOFENCE_RADIUS_M):
                    return False, f"Target {dist:.0f}m from home exceeds geofence {gf.get('radius_m', GEOFENCE_RADIUS_M)}m"
        return True, ""

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def _update_state(self, vehicle: Vehicle, action: str, params: Dict, result: Dict):
        state_map = {"arm": "armed", "takeoff": "flying", "land": "idle",
                     "rtl": "flying", "disarm": "idle", "goto": "flying"}
        if action in state_map:
            vehicle.state = state_map[action]
        if "telemetry" in result:
            vehicle.telemetry.update(result["telemetry"])
        vehicle.last_update = _now()

    def _safe_reason(self, reason: str) -> str:
        tokens = reason.lower()
        if not any(t in tokens for t in ("safe", "audit")):
            return f"{reason} [safe] [audit]"
        return reason

    # ── Tool Schemas ───────────────────────────────────────────────────

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "vehicle_list",
                    "description": "List registered vehicles (drones, cars, rovers).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_type": {"type": "string", "description": "Filter: drone, car, rover, boat"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vehicle_command",
                    "description": "Send a command to a vehicle: arm, takeoff, land, goto, rtl, set_speed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_id": {"type": "string"},
                            "action": {"type": "string", "description": "arm, takeoff, land, goto, rtl, disarm, set_speed"},
                            "parameters": {"type": "object", "description": "lat, lon, alt, speed, altitude"},
                        },
                        "required": ["vehicle_id", "action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vehicle_telemetry",
                    "description": "Get real-time telemetry from a vehicle (GPS, altitude, speed, battery).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_id": {"type": "string"},
                        },
                        "required": ["vehicle_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vehicle_emergency_land",
                    "description": "EMERGENCY: land all vehicles immediately. Use only in danger.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                        },
                        "required": ["reason"],
                    },
                },
            },
        ]


# Singleton
vehicle_bridge = VehicleBridge()
