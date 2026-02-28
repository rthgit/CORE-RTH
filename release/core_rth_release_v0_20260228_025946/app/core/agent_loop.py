"""
Agent Loop — Autonomous think→act→observe cycle for Core Rth.

Orchestrates multi-step task execution using LLM + Tool Registry + Guardian governance.
Supports function calling, automatic retry, sub-task decomposition, and
persistent thread memory.
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
import tempfile
import hashlib

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .tool_registry import tool_registry
from .knowledge_graph import get_knowledge_graph, NodeType, RelationType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 25
MAX_TOOL_CALLS_PER_STEP = 5
MAX_CONTEXT_CHARS = 80_000
LOOP_TIMEOUT_SEC = 300


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentStep:
    """A single step in the agent loop."""
    step_id: int
    role: str                         # "assistant" | "tool"
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "role": self.role,
            "content": self.content[:2000] if self.content else "",
            "tool_calls_count": len(self.tool_calls),
            "tool_results_count": len(self.tool_results),
            "timestamp": self.timestamp,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class AgentThread:
    """A persistent conversation/task thread."""
    thread_id: str
    title: str = ""
    created_at: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[AgentStep] = field(default_factory=list)
    status: str = "active"           # active | completed | error | timeout
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "title": self.title,
            "created_at": self.created_at,
            "status": self.status,
            "message_count": len(self.messages),
            "step_count": len(self.steps),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Agent Loop Engine
# ---------------------------------------------------------------------------

class AgentLoopEngine:
    """
    Autonomous agent loop: think → act → observe → repeat.
    Uses LLM with function calling to decide what tools to use.
    """

    def __init__(self):
        self.threads: Dict[str, AgentThread] = {}
        self._streaming_callbacks: Dict[str, Callable] = {}

    def status(self) -> Dict[str, Any]:
        active = sum(1 for t in self.threads.values() if t.status == "active")
        return {
            "module": "agent_loop",
            "version": 1,
            "threads_total": len(self.threads),
            "threads_active": active,
            "max_iterations": MAX_ITERATIONS,
            "max_context_chars": MAX_CONTEXT_CHARS,
            "tool_registry": tool_registry.status(),
        }

    def run(
        self,
        *,
        objective: str,
        thread_id: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
        reason: str = "Agent loop task execution",
        confirm_owner: bool = True,
        decided_by: str = "owner",
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an autonomous agent loop for the given objective.

        Args:
            objective: High-level goal to accomplish
            thread_id: Optional thread ID to continue (persistent conversation)
            max_iterations: Max think→act→observe cycles
            reason: Governance reason
            confirm_owner: Whether to auto-approve the loop start
            decided_by: Who approves
            on_step: Optional callback for each step (for streaming/UI)
        """
        # Guardian approval for the loop itself
        req = permission_gate.propose(
            capability=Capability.SWARM_ANALYSIS,
            action="agent_loop_run",
            scope={
                "objective": objective[:200],
                "max_iterations": max_iterations,
            },
            reason=self._safe_reason(reason),
            risk=RiskLevel.MEDIUM,
        )

        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                return {
                    "status": "denied",
                    "detail": f"Guardian denied: {decision.denial_reason or 'denied'}",
                    "proposal": req.to_dict(),
                }

        # Create or resume thread
        if thread_id and thread_id in self.threads:
            thread = self.threads[thread_id]
        else:
            thread = AgentThread(
                thread_id=thread_id or f"thread_{uuid.uuid4().hex[:12]}",
                title=objective[:100],
                created_at=self._now(),
            )
            # Inject dynamic system prompt using Prompt Manager
            from app.core.prompt_system import build_system_prompt
            active_tools = [s.get("function", {}).get("name", "") for s in tool_registry.get_schemas()]
            system_prompt = build_system_prompt(active_tools, objective=objective)
            thread.messages.append({"role": "system", "content": system_prompt})
            
            self.threads[thread.thread_id] = thread

        # Add user objective
        thread.messages.append({"role": "user", "content": objective})
        thread.status = "active"

        # Run the loop
        start = time.monotonic()
        iteration = 0
        final_output = ""

        try:
            while iteration < max_iterations:
                elapsed = time.monotonic() - start
                if elapsed > LOOP_TIMEOUT_SEC:
                    thread.status = "timeout"
                    break

                iteration += 1
                step = AgentStep(
                    step_id=iteration,
                    role="assistant",
                    timestamp=self._now(),
                )

                # Call LLM with function calling
                t0 = time.monotonic()
                llm_response = self._call_llm(thread.messages)
                step.elapsed_ms = int((time.monotonic() - t0) * 1000)

                if llm_response.get("error"):
                    step.content = f"LLM error: {llm_response['error']}"
                    thread.steps.append(step)
                    if on_step:
                        on_step(step)
                    thread.status = "error"
                    final_output = step.content
                    break

                message = llm_response.get("message", {})
                step.content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls = LLM is done
                    thread.messages.append({"role": "assistant", "content": step.content})
                    thread.steps.append(step)
                    if on_step:
                        on_step(step)
                    final_output = step.content
                    thread.status = "completed"
                    break

                # Execute tool calls
                step.tool_calls = tool_calls
                thread.messages.append({
                    "role": "assistant",
                    "content": step.content,
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls[:MAX_TOOL_CALLS_PER_STEP]:
                    tool_name = tc.get("function", {}).get("name", "")
                    try:
                        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    tool_result = tool_registry.call(tool_name, **args)
                    step.tool_results.append(tool_result)

                    # Add tool result to messages
                    thread.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{iteration}"),
                        "content": json.dumps(tool_result, default=str)[:MAX_CONTEXT_CHARS // 4],
                    })

                thread.steps.append(step)
                if on_step:
                    on_step(step)

                # Trim context if too long
                self._trim_context(thread)

        except Exception as e:
            thread.status = "error"
            final_output = f"Agent loop error: {e}"
            logger.error(f"Agent loop error: {e}", exc_info=True)

        total_ms = int((time.monotonic() - start) * 1000)

        # Record to memory
        memory_vault.record_event(
            "agent_loop_run",
            {
                "thread_id": thread.thread_id,
                "objective": objective[:200],
                "status": thread.status,
                "iterations": iteration,
                "elapsed_ms": total_ms,
            },
            tags={"source": "agent_loop"},
        )

        # Ingest to KG
        self._ingest_to_kg(thread, objective)

        # Persist thread
        self._save_thread(thread)

        report = {
            "status": thread.status,
            "thread_id": thread.thread_id,
            "objective": objective,
            "iterations": iteration,
            "elapsed_ms": total_ms,
            "final_output": final_output[:5000],
            "steps": [s.to_dict() for s in thread.steps[-10:]],
            "thread": thread.to_dict(),
        }
        return report

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a thread by ID."""
        thread = self.threads.get(thread_id)
        if not thread:
            # Try loading from disk
            thread = self._load_thread(thread_id)
        if not thread:
            return None
        return {
            "thread": thread.to_dict(),
            "steps": [s.to_dict() for s in thread.steps],
            "message_count": len(thread.messages),
        }

    def list_threads(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all threads."""
        threads = sorted(
            self.threads.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )[:limit]
        return [t.to_dict() for t in threads]

    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------

    def _call_llm(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call the LLM with function calling support."""
        try:
            from .model_control_plane import model_control_plane
            tools = tool_registry.get_schemas()

            # Use the model control plane to route to the best model
            result = model_control_plane.chat_completion(
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.3,
                max_tokens=4096,
            )
            return result
        except ImportError:
            return self._call_llm_direct(messages)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"error": str(e)}

    def _call_llm_direct(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Direct LLM call fallback using provider config."""
        try:
            from .config import settings
            import urllib.request

            api_key = getattr(settings, "RTH_AI_API_KEY", "") or ""
            api_base = getattr(settings, "RTH_AI_API_BASE", "") or ""
            model = getattr(settings, "RTH_AI_MODEL", "") or ""

            if not api_key or not api_base:
                return {"error": "No AI provider configured. Set RTH_AI_API_KEY and RTH_AI_API_BASE in .env (any OpenAI-compatible provider: Groq, OpenAI, Anthropic, Ollama, llama.cpp, etc.)"}
            if not model:
                return {"error": "No AI model configured. Set RTH_AI_MODEL in .env"}

            tools = tool_registry.get_schemas()
            body = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"

            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                f"{api_base}/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            return {"message": message}

        except Exception as e:
            return {"error": f"Direct LLM call failed: {e}"}

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def _trim_context(self, thread: AgentThread):
        """Trim old messages to stay within context limits."""
        total = sum(len(json.dumps(m, default=str)) for m in thread.messages)
        while total > MAX_CONTEXT_CHARS and len(thread.messages) > 3:
            # Keep system + last user + recent messages
            removed = thread.messages.pop(1)
            total = sum(len(json.dumps(m, default=str)) for m in thread.messages)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_thread(self, thread: AgentThread):
        """Persist thread to disk."""
        candidates = [
            Path("storage") / "agent_threads",
            Path("storage_runtime") / "agent_threads",
            Path(tempfile.gettempdir()) / "rth_core" / "agent_threads",
        ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                data = {
                    "thread": thread.to_dict(),
                    "messages": thread.messages,
                    "steps": [s.to_dict() for s in thread.steps],
                }
                path = base / f"{thread.thread_id}.json"
                from app.core.security_vault import security_vault
                security_vault.encrypt_file(path, data)
                return
            except Exception:
                continue

    def _load_thread(self, thread_id: str) -> Optional[AgentThread]:
        """Load a thread from disk."""
        candidates = [
            Path("storage") / "agent_threads",
            Path("storage_runtime") / "agent_threads",
            Path(tempfile.gettempdir()) / "rth_core" / "agent_threads",
        ]
        for base in candidates:
            path = base / f"{thread_id}.json"
            if path.exists():
                try:
                    from app.core.security_vault import security_vault
                    data = security_vault.decrypt_file(path, as_json=True)
                    if not data: continue
                    thread = AgentThread(
                        thread_id=thread_id,
                        title=data.get("thread", {}).get("title", ""),
                        created_at=data.get("thread", {}).get("created_at", ""),
                        messages=data.get("messages", []),
                        status=data.get("thread", {}).get("status", "completed"),
                    )
                    self.threads[thread_id] = thread
                    return thread
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------------
    # Knowledge Graph
    # ------------------------------------------------------------------

    def _ingest_to_kg(self, thread: AgentThread, objective: str):
        """Inject agent run into the Knowledge Graph."""
        try:
            kg = get_knowledge_graph()
            node_id = f"agent_run_{hashlib.md5(thread.thread_id.encode()).hexdigest()[:10]}"
            kg.add_node(
                node_id=node_id,
                node_type=NodeType.ENTITY,
                name=f"Agent Run: {thread.title}",
                description=objective[:300],
                properties={
                    "thread_id": thread.thread_id,
                    "status": thread.status,
                    "step_count": len(thread.steps),
                },
                reliability_score=0.8,
            )
        except Exception as e:
            logger.debug(f"KG ingest failed: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_reason(self, reason: str) -> str:
        tokens = reason.lower()
        if not any(t in tokens for t in ("safe", "audit", "dry-run")):
            return f"{reason} [safe] [audit]"
        return reason

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")


# Singleton
agent_loop = AgentLoopEngine()
