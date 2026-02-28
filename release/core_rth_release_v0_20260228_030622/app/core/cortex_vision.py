"""
Cortex-Vision (Multimodal Integraiton)
Fornisce al Core Rth la capacità di vedere. Usa modelli vision-capable 
(GPT-4o, Claude 3.5 Sonnet, Llama 3.2 Vision) per processare screenshot, 
frame di telemetria, o immagini in base64.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .tool_registry import tool_registry

logger = logging.getLogger(__name__)

class CortexVision:
    def __init__(self):
        self._module_name = "cortex_vision"

    def status(self) -> Dict[str, Any]:
        return {
            "module": self._module_name,
            "version": 1,
            "status": "active"
        }

    def _encode_image(self, image_path: str) -> str:
        """Legge un'immagine dal disco e la converte in base64."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found at {path}")
        
        # Guardian Check (Read)
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_READ,
            action="cortex_vision_read_image",
            scope={"path": str(path)},
            reason="Load image for Cortex-Vision analysis",
            risk=RiskLevel.LOW
        )
        decision = permission_gate.approve(req.request_id, decided_by="owner")
        if decision.decision.value != "approved":
            raise PermissionError("Guardian denied image read")

        with open(path, "rb") as imm:
            return base64.b64encode(imm.read()).decode("utf-8")

    def _get_mime_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in [".png"]: return "image/png"
        if ext in [".jpg", ".jpeg"]: return "image/jpeg"
        if ext in [".webp"]: return "image/webp"
        return "image/jpeg"

    def analyze_image(self, image_path_or_base64: str, prompt: str, is_path: bool = True) -> Dict[str, Any]:
        """Invia un'immagine e un prompt al VLM per l'analisi."""
        try:
            if is_path:
                base64_img = self._encode_image(image_path_or_base64)
                mime = self._get_mime_type(image_path_or_base64)
            else:
                base64_img = image_path_or_base64
                mime = "image/jpeg" # Default per stringhe grezze base64

            # Formato payload per la chat completion standard (OpenAI-compatible)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{base64_img}"
                            }
                        }
                    ]
                }
            ]

            # Siccome Cortex-Vision invoca un modello via rete, deve passare da _call_llm di agent_loop
            # Per evitare un'import ciclico con AgentLoopEngine, facciamo una direct call al Control Plane
            from ..model_control_plane import control_plane
            
            # Guardian Auth: Network call for external API (Vision)
            req = permission_gate.propose(
                capability=Capability.NETWORK_ACCESS,
                action="cortex_vision_api_call",
                scope={"prompt": prompt[:50], "image_size": len(base64_img)},
                reason="Send image to external VLM for analysis",
                risk=RiskLevel.MEDIUM
            )
            decision = permission_gate.approve(req.request_id, decided_by="owner")
            if decision.decision.value != "approved":
                return {"status": "denied", "error": f"Guardian blocked Vision API call: {decision.denial_reason}"}

            # Esegui chiamata VLM tramite il control plane (usa provider attivo compatibile col Vision, ex: OpenAI o Claude)
            res = control_plane.run_chat(messages, stream=False)
            
            if res.get("error"):
                return {"status": "error", "error": res["error"]}

            result_text = res.get("message", {}).get("content", "")
            
            memory_vault.record_event("cortex_vision_analysis", {
                "prompt": prompt,
                "response_length": len(result_text),
                "is_path": is_path
            }, tags={"source": "cortex", "type": "vision"})

            return {
                "status": "success",
                "analysis": result_text
            }

        except Exception as e:
            logger.error(f"Cortex-Vision Error: {e}")
            return {"status": "error", "error": str(e)}

cortex_vision = CortexVision()

# Registrazione automatica come tool callable
def _tool_cortex_vision_analyze(args: Dict[str, Any]) -> Dict[str, Any]:
    return cortex_vision.analyze_image(
        image_path_or_base64=args.get("image_source", ""),
        prompt=args.get("prompt", "Describe this image in detail."),
        is_path=args.get("is_path", True)
    )

tool_registry.register(
    "cortex_vision_analyze",
    _tool_cortex_vision_analyze,
    {
        "type": "function",
        "function": {
            "name": "cortex_vision_analyze",
            "description": "Analyze an image (screenshot, photo, map) using a Vision Language Model. Useful to 'see' what's on the screen, read charts, or check telemetry camera feeds. Must provide absolute file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_source": {"type": "string", "description": "Absolute path to the image file (e.g., /tmp/screenshot.png)."},
                    "prompt": {"type": "string", "description": "What to look for or ask about the image."},
                    "is_path": {"type": "boolean", "description": "Set to true if image_source is a file path. Set to false if base64."}
                },
                "required": ["image_source", "prompt"]
            }
        }
    },
    category="cortex"
)
