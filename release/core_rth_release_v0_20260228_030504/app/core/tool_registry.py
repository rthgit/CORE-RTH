"""
Tool Registry — Central registry of callable tools for Agent Loop and LLM function calling.

Maps tool names to their implementations and provides OpenAI-compatible schemas
for function calling. Integrates Code Tools, Browser Swarm, and system tools.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all callable tools."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_defaults()

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        schema: Dict[str, Any],
        category: str = "general",
    ):
        """Register a tool with its function and OpenAI-compatible schema."""
        self._tools[name] = {
            "fn": fn,
            "schema": schema,
            "category": category,
        }

    def call(self, name: str, **kwargs) -> Dict[str, Any]:
        """Call a registered tool by name with keyword arguments."""
        tool = self._tools.get(name)
        if not tool:
            return {"status": "error", "error": f"Unknown tool: {name}"}
        try:
            result = tool["fn"](**kwargs)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            if isinstance(result, dict):
                return result
            return {"status": "ok", "data": result}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"status": "error", "error": f"{type(e).__name__}: {str(e)}"}

    def get_schemas(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get OpenAI function-calling compatible schemas for registered tools."""
        schemas = []
        for name, entry in self._tools.items():
            if categories and entry.get("category") not in categories:
                continue
            schemas.append(entry["schema"])
        return schemas

    def list_tools(self) -> List[Dict[str, str]]:
        """List all registered tools."""
        return [
            {"name": name, "category": entry.get("category", "general")}
            for name, entry in self._tools.items()
        ]

    def status(self) -> Dict[str, Any]:
        by_cat: Dict[str, int] = {}
        for entry in self._tools.values():
            cat = entry.get("category", "general")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        return {
            "module": "tool_registry",
            "version": 1,
            "tools_count": len(self._tools),
            "categories": by_cat,
        }

    def _register_defaults(self):
        """Register all default tools from Code Tools and Browser Swarm."""
        try:
            from .code_tools import code_tools
            for schema in code_tools.get_tool_schemas():
                fn_name = schema["function"]["name"]
                fn = getattr(code_tools, fn_name, None)
                if fn:
                    self.register(fn_name, fn, schema, category="code")
        except Exception as e:
            logger.warning(f"Failed to register code tools: {e}")

        try:
            from .browser_swarm import browser_swarm
            self.register(
                "browser_scrape",
                lambda urls, reason="Agent browser scrape [safe] [audit]", **kw: browser_swarm.run(
                    urls=urls if isinstance(urls, list) else [urls],
                    reason=reason,
                    **kw,
                ),
                {
                    "type": "function",
                    "function": {
                        "name": "browser_scrape",
                        "description": "Scrape web pages using browser agents. Returns extracted text content.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "urls": {"type": "array", "items": {"type": "string"}, "description": "URLs to scrape"},
                                "reason": {"type": "string", "description": "Why scraping is needed"},
                            },
                            "required": ["urls"],
                        },
                    },
                },
                category="browser",
            )
            self.register(
                "web_search",
                lambda query, reason="Agent web search [safe] [audit]", **kw: browser_swarm.search(
                    query=query,
                    reason=reason,
                    **kw,
                ),
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web and optionally scrape result pages.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "max_results": {"type": "integer", "default": 5},
                            },
                            "required": ["query"],
                        },
                    },
                },
                category="browser",
            )
        except Exception as e:
            logger.warning(f"Failed to register browser swarm tools: {e}")

        # IoT / Domotica tools
        try:
            from .iot_bridge import iot_bridge
            for schema in iot_bridge.get_tool_schemas():
                fn_name = schema["function"]["name"]
                fn_map = {
                    "iot_list_devices": lambda device_type="", location="", **kw: iot_bridge.list_devices(device_type=device_type, location=location),
                    "iot_control": lambda device_id, command, parameters=None, **kw: iot_bridge.control_device(device_id=device_id, command=command, parameters=parameters or {}),
                    "iot_read_sensors": lambda device_type="sensor", location="", **kw: iot_bridge.read_sensors(device_type=device_type, location=location),
                }
                fn = fn_map.get(fn_name)
                if fn:
                    self.register(fn_name, fn, schema, category="iot")
        except Exception as e:
            logger.warning(f"Failed to register IoT tools: {e}")

        # Robotics tools
        try:
            from .robotics_bridge import robotics_bridge
            for schema in robotics_bridge.get_tool_schemas():
                fn_name = schema["function"]["name"]
                fn_map = {
                    "robot_list_actuators": lambda actuator_type="", **kw: robotics_bridge.list_actuators(actuator_type=actuator_type),
                    "robot_command": lambda actuator_id, action, parameters=None, **kw: robotics_bridge.execute_command(actuator_id=actuator_id, action=action, parameters=parameters or {}),
                    "robot_emergency_stop": lambda reason="Emergency stop", **kw: robotics_bridge.emergency_stop(reason=reason),
                }
                fn = fn_map.get(fn_name)
                if fn:
                    self.register(fn_name, fn, schema, category="robotics")
        except Exception as e:
            logger.warning(f"Failed to register robotics tools: {e}")

        # Vehicle / Drone tools
        try:
            from .vehicle_bridge import vehicle_bridge
            for schema in vehicle_bridge.get_tool_schemas():
                fn_name = schema["function"]["name"]
                fn_map = {
                    "vehicle_list": lambda vehicle_type="", **kw: vehicle_bridge.list_vehicles(vehicle_type=vehicle_type),
                    "vehicle_command": lambda vehicle_id, action, parameters=None, **kw: vehicle_bridge.send_command(vehicle_id=vehicle_id, action=action, parameters=parameters or {}),
                    "vehicle_telemetry": lambda vehicle_id, **kw: vehicle_bridge.get_telemetry(vehicle_id=vehicle_id),
                    "vehicle_emergency_land": lambda reason="Emergency landing", **kw: vehicle_bridge.emergency_land(reason=reason),
                }
                fn = fn_map.get(fn_name)
                if fn:
                    self.register(fn_name, fn, schema, category="vehicle")
        except Exception as e:
            logger.warning(f"Failed to register vehicle tools: {e}")


# Singleton
tool_registry = ToolRegistry()
