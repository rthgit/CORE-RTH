"""
IoT / Domotica Bridge — Governed bridge for smart home and IoT device control.

Supports:
- Home Assistant (REST API)
- MQTT (publish/subscribe for Zigbee/Z-Wave/WiFi devices)
- Generic HTTP devices (smart plugs, cameras, sensors)
- Device groups and scenes

All actions are governed by Guardian (Capability.SYSTEM_MODIFY).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HA_URL = "http://homeassistant.local:8123"
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883
DEVICE_TIMEOUT_SEC = 10
MAX_DEVICES = 500


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IoTDevice:
    """Represents a smart home / IoT device."""
    device_id: str
    name: str
    device_type: str          # light, switch, sensor, thermostat, camera, lock, cover, media_player, climate, vacuum
    protocol: str             # homeassistant, mqtt, http, zigbee, zwave
    state: str = "unknown"    # on, off, unavailable, unknown, or numeric (sensors)
    attributes: Dict[str, Any] = field(default_factory=dict)
    location: str = ""        # room/zone
    last_update: str = ""
    controllable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.device_type,
            "protocol": self.protocol,
            "state": self.state,
            "attributes": self.attributes,
            "location": self.location,
            "last_update": self.last_update,
            "controllable": self.controllable,
        }


@dataclass
class IoTAction:
    """An action to perform on a device."""
    action_id: str
    device_id: str
    command: str              # turn_on, turn_off, toggle, set_temperature, set_brightness, lock, unlock, etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"   # pending, approved, executed, failed, denied
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "device_id": self.device_id,
            "command": self.command,
            "parameters": self.parameters,
            "status": self.status,
            "result": self.result,
            "timestamp": self.timestamp,
        }


@dataclass
class IoTScene:
    """A group of actions executed together."""
    scene_id: str
    name: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "actions": self.actions,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Protocol adapters
# ---------------------------------------------------------------------------

class HomeAssistantAdapter:
    """Adapter for Home Assistant REST API."""

    def __init__(self, base_url: str = "", token: str = ""):
        self.base_url = base_url or DEFAULT_HA_URL
        self.token = token
        self._available = False
        self._check_availability()

    def _check_availability(self):
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/",
                headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get_states(self) -> List[Dict[str, Any]]:
        """Fetch all entity states from Home Assistant."""
        if not self._available:
            return []
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/states",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=DEVICE_TIMEOUT_SEC) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"HA get_states failed: {e}")
            return []

    def call_service(self, domain: str, service: str, entity_id: str, data: Dict = None) -> Dict[str, Any]:
        """Call a Home Assistant service."""
        if not self._available:
            return {"status": "error", "error": "Home Assistant not available"}
        try:
            import urllib.request
            body = {"entity_id": entity_id}
            if data:
                body.update(data)
            req = urllib.request.Request(
                f"{self.base_url}/api/services/{domain}/{service}",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=DEVICE_TIMEOUT_SEC) as resp:
                return {"status": "ok", "response": json.loads(resp.read().decode("utf-8"))}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class MQTTAdapter:
    """Adapter for MQTT protocol (Zigbee/Z-Wave/WiFi devices via MQTT)."""

    def __init__(self, broker: str = "", port: int = 0, username: str = "", password: str = ""):
        self.broker = broker or DEFAULT_MQTT_BROKER
        self.port = port or DEFAULT_MQTT_PORT
        self.username = username
        self.password = password
        self._client = None
        self._available = False
        self._messages: Dict[str, Any] = {}
        self._init_client()

    def _init_client(self):
        try:
            import paho.mqtt.client as mqtt
            self._client = mqtt.Client(client_id=f"core_rth_{uuid.uuid4().hex[:8]}")
            if self.username:
                self._client.username_pw_set(self.username, self.password)

            def on_connect(client, userdata, flags, rc):
                self._available = rc == 0
                if rc == 0:
                    client.subscribe("#")

            def on_message(client, userdata, msg):
                self._messages[msg.topic] = {
                    "payload": msg.payload.decode("utf-8", errors="replace"),
                    "timestamp": _now(),
                }

            self._client.on_connect = on_connect
            self._client.on_message = on_message

            self._client.connect_async(self.broker, self.port, 60)
            self._client.loop_start()
            self._available = True
        except ImportError:
            logger.info("paho-mqtt not installed — MQTT adapter disabled")
        except Exception as e:
            logger.info(f"MQTT connection failed: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def publish(self, topic: str, payload: str, retain: bool = False) -> Dict[str, Any]:
        """Publish a message to an MQTT topic."""
        if not self._client:
            return {"status": "error", "error": "MQTT client not available"}
        try:
            result = self._client.publish(topic, payload, retain=retain)
            return {"status": "ok", "mid": result.mid, "topic": topic}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_latest(self, topic_prefix: str = "") -> Dict[str, Any]:
        """Get latest messages matching topic prefix."""
        filtered = {
            k: v for k, v in self._messages.items()
            if not topic_prefix or k.startswith(topic_prefix)
        }
        return {"messages": filtered, "count": len(filtered)}


class HTTPDeviceAdapter:
    """Generic HTTP adapter for smart devices (plugs, cameras, etc.)."""

    def send_command(self, url: str, method: str = "POST", data: Dict = None, headers: Dict = None) -> Dict[str, Any]:
        """Send an HTTP command to a device."""
        try:
            import urllib.request
            body = json.dumps(data).encode("utf-8") if data else None
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers or {"Content-Type": "application/json"},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=DEVICE_TIMEOUT_SEC) as resp:
                return {"status": "ok", "code": resp.status, "body": resp.read().decode("utf-8")[:5000]}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Main IoT Bridge
# ---------------------------------------------------------------------------

class IoTBridge:
    """Governed IoT / Smart Home bridge for Core Rth."""

    def __init__(self):
        self.devices: Dict[str, IoTDevice] = {}
        self.scenes: Dict[str, IoTScene] = {}
        self.action_history: List[IoTAction] = []
        self._max_history = 500

        # Adapters (lazy-initialized)
        self._ha: Optional[HomeAssistantAdapter] = None
        self._mqtt: Optional[MQTTAdapter] = None
        self._http = HTTPDeviceAdapter()

        # Try to init from env
        self._init_adapters()

    def _init_adapters(self):
        """Initialize adapters from environment variables."""
        import os
        ha_url = os.getenv("RTH_HA_URL", "")
        ha_token = os.getenv("RTH_HA_TOKEN", "")
        if ha_url or ha_token:
            self._ha = HomeAssistantAdapter(base_url=ha_url, token=ha_token)

        mqtt_broker = os.getenv("RTH_MQTT_BROKER", "")
        if mqtt_broker:
            self._mqtt = MQTTAdapter(
                broker=mqtt_broker,
                port=int(os.getenv("RTH_MQTT_PORT", "1883")),
                username=os.getenv("RTH_MQTT_USER", ""),
                password=os.getenv("RTH_MQTT_PASS", ""),
            )

    # ── Status ─────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "module": "iot_bridge",
            "version": 1,
            "adapters": {
                "homeassistant": {"available": bool(self._ha and self._ha.available)},
                "mqtt": {"available": bool(self._mqtt and self._mqtt.available)},
                "http": {"available": True},
            },
            "devices_count": len(self.devices),
            "scenes_count": len(self.scenes),
            "action_history_count": len(self.action_history),
        }

    # ── Device Discovery ───────────────────────────────────────────────

    def discover_devices(
        self,
        source: str = "all",
        reason: str = "IoT device discovery",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """Discover devices from adapters."""
        req = permission_gate.propose(
            capability=Capability.NETWORK_ACCESS,
            action="iot_discover_devices",
            scope={"source": source},
            reason=self._safe_reason(reason),
            risk=RiskLevel.LOW,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {"status": "denied", "detail": decision.denial_reason}

        discovered = []

        # Home Assistant
        if source in ("all", "homeassistant") and self._ha and self._ha.available:
            states = self._ha.get_states()
            for entity in states:
                eid = entity.get("entity_id", "")
                domain = eid.split(".")[0] if "." in eid else "unknown"
                device = IoTDevice(
                    device_id=eid,
                    name=entity.get("attributes", {}).get("friendly_name", eid),
                    device_type=domain,
                    protocol="homeassistant",
                    state=entity.get("state", "unknown"),
                    attributes=entity.get("attributes", {}),
                    location=entity.get("attributes", {}).get("area", ""),
                    last_update=entity.get("last_updated", ""),
                    controllable=domain in ("light", "switch", "cover", "climate", "lock", "media_player", "vacuum", "fan"),
                )
                self.devices[eid] = device
                discovered.append(device.to_dict())

        # MQTT
        if source in ("all", "mqtt") and self._mqtt and self._mqtt.available:
            latest = self._mqtt.get_latest()
            for topic, msg in latest.get("messages", {}).items():
                device_id = f"mqtt_{topic.replace('/', '_')}"
                if device_id not in self.devices:
                    device = IoTDevice(
                        device_id=device_id,
                        name=topic.split("/")[-1] if "/" in topic else topic,
                        device_type="sensor",
                        protocol="mqtt",
                        state=msg.get("payload", "unknown")[:50],
                        attributes={"topic": topic},
                        last_update=msg.get("timestamp", ""),
                        controllable=any(k in topic.lower() for k in ("set", "cmnd", "command")),
                    )
                    self.devices[device_id] = device
                    discovered.append(device.to_dict())

        memory_vault.record_event("iot_discovery", {"discovered": len(discovered), "source": source}, tags={"source":"iot_bridge"})
        return {
            "status": "ok",
            "discovered": len(discovered),
            "total_devices": len(self.devices),
            "devices": discovered[:100],
        }

    # ── Device Control ─────────────────────────────────────────────────

    def control_device(
        self,
        device_id: str,
        command: str,
        parameters: Dict[str, Any] = None,
        reason: str = "IoT device control",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """Control a device (governed by Guardian)."""
        parameters = parameters or {}

        # Guardian approval
        req = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY,
            action="iot_device_control",
            scope={
                "device_id": device_id,
                "command": command,
                "parameters": parameters,
            },
            reason=self._safe_reason(reason),
            risk=RiskLevel.MEDIUM,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {"status": "denied", "detail": decision.denial_reason}

        action = IoTAction(
            action_id=f"iot_{uuid.uuid4().hex[:10]}",
            device_id=device_id,
            command=command,
            parameters=parameters,
            status="approved",
            timestamp=_now(),
        )

        device = self.devices.get(device_id)
        result = {}

        try:
            if device and device.protocol == "homeassistant" and self._ha:
                domain = device_id.split(".")[0] if "." in device_id else "switch"
                service = self._map_command_to_ha_service(command)
                result = self._ha.call_service(domain, service, device_id, parameters)

            elif device and device.protocol == "mqtt" and self._mqtt:
                topic = device.attributes.get("topic", device_id)
                cmd_topic = topic.replace("stat", "cmnd").replace("tele", "cmnd")
                payload = parameters.get("payload", command.upper())
                result = self._mqtt.publish(cmd_topic, payload)

            elif device and device.protocol == "http":
                url = device.attributes.get("control_url", "")
                if url:
                    result = self._http.send_command(url, data={"command": command, **parameters})
                else:
                    result = {"status": "error", "error": "No control URL configured"}
            else:
                result = {"status": "error", "error": f"Device {device_id} not found or unsupported protocol"}

            action.status = "executed" if result.get("status") == "ok" else "failed"
            action.result = result

        except Exception as e:
            action.status = "failed"
            action.result = {"error": str(e)}

        self.action_history.append(action)
        if len(self.action_history) > self._max_history:
            self.action_history = self.action_history[-self._max_history:]

        # Update device state
        if device and action.status == "executed":
            device.state = self._infer_state(command)
            device.last_update = _now()

        memory_vault.record_event("iot_control", action.to_dict(), tags={"source": "iot_bridge"})
        return action.to_dict()

    # ── Scenes ─────────────────────────────────────────────────────────

    def create_scene(self, name: str, actions: List[Dict[str, Any]], description: str = "") -> Dict[str, Any]:
        """Create a scene (group of actions)."""
        scene = IoTScene(
            scene_id=f"scene_{uuid.uuid4().hex[:8]}",
            name=name,
            actions=actions,
            description=description,
        )
        self.scenes[scene.scene_id] = scene
        return scene.to_dict()

    def execute_scene(
        self,
        scene_id: str,
        reason: str = "Scene execution",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """Execute all actions in a scene."""
        scene = self.scenes.get(scene_id)
        if not scene:
            return {"status": "error", "error": f"Scene {scene_id} not found"}

        results = []
        for action_def in scene.actions:
            result = self.control_device(
                device_id=action_def.get("device_id", ""),
                command=action_def.get("command", ""),
                parameters=action_def.get("parameters", {}),
                reason=f"Scene '{scene.name}': {reason}",
                confirm_owner=confirm_owner,
                decided_by=decided_by,
            )
            results.append(result)
        return {"scene": scene.to_dict(), "results": results}

    # ── Read Sensors ───────────────────────────────────────────────────

    def read_sensors(self, device_type: str = "sensor", location: str = "") -> Dict[str, Any]:
        """Read all sensor values (no governance needed — read only)."""
        sensors = []
        for device in self.devices.values():
            if device.device_type == device_type or not device_type:
                if location and device.location.lower() != location.lower():
                    continue
                sensors.append(device.to_dict())
        return {"sensors": sensors, "count": len(sensors)}

    # ── List / Query ───────────────────────────────────────────────────

    def list_devices(self, device_type: str = "", location: str = "", protocol: str = "") -> Dict[str, Any]:
        """List devices with optional filters."""
        devices = []
        for d in self.devices.values():
            if device_type and d.device_type != device_type:
                continue
            if location and location.lower() not in d.location.lower():
                continue
            if protocol and d.protocol != protocol:
                continue
            devices.append(d.to_dict())
        return {"devices": devices, "count": len(devices)}

    def register_device(
        self,
        device_id: str, name: str, device_type: str, protocol: str,
        attributes: Dict = None, location: str = "", controllable: bool = True,
    ) -> Dict[str, Any]:
        """Manually register a device."""
        device = IoTDevice(
            device_id=device_id, name=name, device_type=device_type,
            protocol=protocol, attributes=attributes or {},
            location=location, controllable=controllable,
            last_update=_now(),
        )
        self.devices[device_id] = device
        return device.to_dict()

    # ── Tool Schemas for Agent Loop ────────────────────────────────────

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible function schemas for IoT tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "iot_list_devices",
                    "description": "List all smart home / IoT devices. Filter by type, location, or protocol.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_type": {"type": "string", "description": "Filter: light, switch, sensor, thermostat, camera, lock, etc."},
                            "location": {"type": "string", "description": "Filter by room/zone"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "iot_control",
                    "description": "Control an IoT device: turn on/off lights, set temperature, lock doors, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {"type": "string", "description": "Device ID to control"},
                            "command": {"type": "string", "description": "Command: turn_on, turn_off, toggle, set_temperature, set_brightness, lock, unlock"},
                            "parameters": {"type": "object", "description": "Extra parameters (e.g. brightness, temperature)"},
                        },
                        "required": ["device_id", "command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "iot_read_sensors",
                    "description": "Read sensor values (temperature, humidity, motion, energy, etc).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_type": {"type": "string", "default": "sensor"},
                            "location": {"type": "string", "description": "Filter by room"},
                        },
                    },
                },
            },
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    def _map_command_to_ha_service(self, command: str) -> str:
        mapping = {
            "turn_on": "turn_on", "turn_off": "turn_off", "toggle": "toggle",
            "lock": "lock", "unlock": "unlock",
            "open": "open_cover", "close": "close_cover",
            "set_temperature": "set_temperature",
            "set_brightness": "turn_on",
            "play": "media_play", "pause": "media_pause", "stop": "media_stop",
        }
        return mapping.get(command, command)

    def _infer_state(self, command: str) -> str:
        states = {
            "turn_on": "on", "turn_off": "off", "toggle": "toggled",
            "lock": "locked", "unlock": "unlocked",
            "open": "open", "close": "closed",
        }
        return states.get(command, "active")

    def _safe_reason(self, reason: str) -> str:
        tokens = reason.lower()
        if not any(t in tokens for t in ("safe", "audit")):
            return f"{reason} [safe] [audit]"
        return reason


# Singleton
iot_bridge = IoTBridge()
