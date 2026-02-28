"""
Plugin Runtime (governed by Chronicle/KnowledgeGraph/Cortex/Praxis/Guardian).

This runtime does NOT execute arbitrary plugin code by default.
It builds a manifest, performs structural analysis, ingests into the KG,
and produces governance proposals. Any process execution remains consent-gated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import tempfile
import logging

from .permissions import permission_gate, Capability, RiskLevel
from .plugin_hub import plugin_hub
from .knowledge_graph import get_knowledge_graph, NodeType, RelationType
from .governance import governance_queue
from .memory_vault import memory_vault
from .pathmap import map_path
from .root_policy import load_strategic_roots, is_within_roots

logger = logging.getLogger(__name__)


def _normalize_root(root: str) -> str:
    return root.replace("\\", "/").lower().rstrip("/")


def _hash_id(prefix: str, text: str, n: int = 10) -> str:
    return f"{prefix}{hashlib.md5(text.lower().encode()).hexdigest()[:n]}"


def _choose_logs_dir() -> Path:
    candidates = [
        Path("logs"),
        Path("storage_runtime") / "logs",
        Path(tempfile.gettempdir()) / "rth_core" / "logs",
    ]
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / "rth_core" / "logs"


def _choose_state_dir() -> Path:
    candidates = [
        Path("storage") / "plugins",
        Path("storage_runtime") / "plugins",
        Path(tempfile.gettempdir()) / "rth_core" / "plugins",
    ]
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / "rth_core" / "plugins"


@dataclass
class PluginManifestEntry:
    plugin_id: str
    root: str
    score: float
    status: str
    category: str
    exists: bool
    signals: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "root": self.root,
            "score": self.score,
            "status": self.status,
            "category": self.category,
            "exists": self.exists,
            "signals": self.signals,
            "flags": self.flags,
        }


class PluginRuntime:
    def __init__(self):
        self.last_manifest: Optional[Dict[str, Any]] = None
        self.last_report: Optional[Dict[str, Any]] = None
        self._state_dir = _choose_state_dir()

    def propose_cycle(self, reason: str, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request = permission_gate.propose(
            capability=Capability.PLUGIN_RUNTIME,
            action="plugin_runtime_cycle",
            scope=scope or {"mode": "read_only"},
            reason=reason,
            risk=RiskLevel.MEDIUM,
        )
        return request.to_dict()

    def status(self) -> Dict[str, Any]:
        return {
            "module": "plugin_runtime",
            "state_dir": str(self._state_dir),
            "last_manifest": {
                "count": self.last_manifest.get("count") if self.last_manifest else None,
                "timestamp": self.last_manifest.get("timestamp") if self.last_manifest else None,
            } if self.last_manifest else None,
            "last_report": {
                "timestamp": self.last_report.get("timestamp") if self.last_report else None,
                "summary": self.last_report.get("summary") if self.last_report else None,
            } if self.last_report else None,
        }

    def manifest(self) -> Dict[str, Any]:
        return self.last_manifest or {"status": "missing", "detail": "No manifest yet"}

    def build_manifest(self, min_score: float = 0.0) -> Dict[str, Any]:
        plugins = plugin_hub.list_plugins(min_score=min_score)
        entries: List[PluginManifestEntry] = []
        for p in plugins:
            root = str(p.get("root", ""))
            plugin_id = str(p.get("plugin_id", _hash_id("plg_", root)))
            score = float(p.get("score", 0.0))
            status = str(p.get("status", "candidate"))
            category = self._categorize_root(root)
            exists, signals, flags = self._collect_signals(root)
            entries.append(PluginManifestEntry(
                plugin_id=plugin_id,
                root=root,
                score=score,
                status=status,
                category=category,
                exists=exists,
                signals=signals,
                flags=flags,
            ))

        entries.sort(key=lambda e: e.score, reverse=True)
        out = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "count": len(entries),
            "items": [e.to_dict() for e in entries],
        }
        self.last_manifest = out
        self._write_json("plugin_manifest_latest.json", out)
        return out

    def plan(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        items = manifest.get("items", [])
        if not items:
            return {"status": "empty", "detail": "No items in manifest"}

        cortex = self._cortex_analyze(items)
        praxis_plan = self._praxis_plan(items, cortex)
        seeded = governance_queue.seed_from_plan(praxis_plan, source="plugin_runtime")

        out = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "cortex": cortex,
            "praxis_plan_count": len(praxis_plan),
            "governance_seeded": len(seeded),
            "governance_summary": governance_queue.summary(),
        }
        self._write_json("plugin_runtime_plan_latest.json", out)
        return out

    def run_cycle(self, request_id: str, min_score: float = 0.0) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}

        manifest = self.build_manifest(min_score=min_score)
        kg_ingest = self._ingest_knowledge_graph(manifest)
        plan_out = self.plan(manifest)

        summary = {
            "manifest_count": manifest.get("count", 0),
            "kg_created_nodes": kg_ingest.get("created_nodes", 0),
            "kg_created_relations": kg_ingest.get("created_relations", 0),
            "cortex_flags": plan_out.get("cortex", {}).get("flag_counts", {}),
            "governance_seeded": plan_out.get("governance_seeded", 0),
        }

        report = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "summary": summary,
            "manifest": {"count": manifest.get("count"), "timestamp": manifest.get("timestamp")},
            "kg_ingest": kg_ingest,
            "plan": plan_out,
        }
        self.last_report = report
        memory_vault.record_event("plugin_runtime_report", report, tags={"mode": "read_only"})
        self._write_json("plugin_runtime_report_latest.json", report)
        return report

    def _write_json(self, name: str, payload: Dict[str, Any]) -> str:
        logs = _choose_logs_dir()
        path = logs / name
        try:
            # Payloads may include datetimes or other rich objects from KG/governance;
            # degrade to string to avoid losing the whole report on serialization.
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write {name}: {e}")
        return str(path)

    def _categorize_root(self, root: str) -> str:
        low = _normalize_root(root)
        if any(k in low for k in ["biome", "knowledge", "rag", "embedding", "vector", "corpus", "omnirag"]):
            return "knowledge"
        if any(k in low for k in ["jarvis", "swarm", "synapse", "cortex", "praxis", "guardian", "core rth", "metamorph"]):
            return "orchestration"
        if any(k in low for k in ["code-oss", "codex", "cowork", "assistant", "plugin"]):
            return "devtools"
        if any(k in low for k in ["simulatore", "rcq"]):
            return "simulation"
        if any(k in low for k in ["xilinx", "vivado", "vitis", "stm32", "cubeide"]):
            return "hardware"
        return "misc"

    def _collect_signals(self, root: str) -> Tuple[bool, Dict[str, Any], List[str]]:
        mapped = map_path(root)
        rp = Path(mapped)
        exists = rp.exists()
        flags: List[str] = []
        signals: Dict[str, Any] = {}
        signals["mapped_root"] = mapped

        strategic_roots = load_strategic_roots()
        in_scope = is_within_roots(root, strategic_roots)
        signals["in_scope"] = in_scope

        low = _normalize_root(root)
        risky_sub = [
            "/appdata/",
            "/programdata/",
            "/windows/",
            "/system volume information/",
            "/$recycle.bin/",
            "/.cache/",
            "/temp/",
            "/tmp/",
            "/downloads/",
            "/desktop/",
            "/.electron-gyp/",
        ]
        if (not in_scope) and any(s in low for s in risky_sub):
            flags.append("unstable_or_system_path")

        if not exists:
            flags.append("missing_root")
            return exists, signals, flags

        # Minimal hygiene signals without full directory traversal.
        def has_any(names: List[str]) -> bool:
            for n in names:
                if (rp / n).exists():
                    return True
            return False

        signals["has_readme"] = has_any(["README.md", "README.txt", "README"])
        signals["has_license"] = has_any(["LICENSE", "LICENSE.md", "LICENSE.txt"])
        signals["has_package_json"] = (rp / "package.json").exists()
        signals["has_pyproject"] = (rp / "pyproject.toml").exists()
        signals["has_requirements"] = (rp / "requirements.txt").exists()
        signals["has_cargo"] = (rp / "Cargo.toml").exists()
        signals["has_go_mod"] = (rp / "go.mod").exists()
        signals["has_dotnet"] = bool(list(rp.glob("*.sln"))) or bool(list(rp.glob("*.csproj")))
        signals["has_tests_dir"] = (rp / "tests").exists() or (rp / "test").exists()

        # Type inference
        types: List[str] = []
        if signals["has_package_json"]:
            types.append("node")
        if signals["has_pyproject"] or signals["has_requirements"]:
            types.append("python")
        if signals["has_cargo"]:
            types.append("rust")
        if signals["has_go_mod"]:
            types.append("go")
        if signals["has_dotnet"]:
            types.append("dotnet")
        signals["types"] = types

        if not signals["has_readme"]:
            flags.append("missing_readme")
        if types and not signals["has_tests_dir"]:
            flags.append("missing_tests_dir")

        return exists, signals, flags

    def _cortex_analyze(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Cortex here is "judgment" over plugin inventory: conflicts, duplicates, drift risks.
        roots = [str(x.get("root", "")) for x in items if x.get("root")]
        norm_roots = [_normalize_root(r) for r in roots]
        sorted_roots = sorted(norm_roots, key=len)

        nested = []
        for r in sorted_roots:
            for p in sorted_roots:
                if p == r:
                    continue
                if r.startswith(p + "/"):
                    nested.append({"child": r, "parent": p})
                    break

        strategic_roots = load_strategic_roots()
        unstable = [
            r
            for r in norm_roots
            if (not is_within_roots(r, strategic_roots))
            and any(s in r for s in ["/desktop/", "/downloads/", "/appdata/", "/programdata/", "/windows/"])
        ]

        category_counts: Dict[str, int] = {}
        flag_counts: Dict[str, int] = {}
        for x in items:
            category = str(x.get("category", "misc"))
            category_counts[category] = category_counts.get(category, 0) + 1
            for f in x.get("flags", []) or []:
                flag_counts[f] = flag_counts.get(f, 0) + 1

        return {
            "timestamp": datetime.now().isoformat(),
            "category_counts": category_counts,
            "flag_counts": flag_counts,
            "nested_count": len(nested),
            "nested_sample": nested[:25],
            "unstable_count": len(unstable),
            "unstable_sample": unstable[:25],
            "judgment": [
                "Nested plugin roots indicate duplication; keep higher-level roots and disable nested ones.",
                "Unstable/system paths should not be treated as plugins; they should be demoted to 'assets' or disabled.",
            ],
        }

    def _praxis_plan(self, items: List[Dict[str, Any]], cortex: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Praxis converts Cortex judgments into actionable governance proposals.
        plan: List[Dict[str, Any]] = []

        plan.append({
            "title": "Define Plugin Runtime Contract v1 (manifest + tool contracts + telemetry)",
            "component": "praxis",
            "rationale": "Plugins are currently just activated entries; we need a standard contract to make them executable safely and comparable.",
            "proposed_changes": [
                "Create a plugin manifest schema (capabilities, actions, safe commands).",
                "Add telemetry fields (last_run, success_rate, last_error).",
                "Add a scheduler that only proposes actions and requires explicit approval.",
            ],
            "requires_approval": True,
        })

        if cortex.get("nested_count", 0) > 0:
            plan.append({
                "title": "Cull nested plugin roots (deduplicate inventory)",
                "component": "cortex/praxis",
                "rationale": "Nested roots create redundant plugins and inflate the inventory, reducing clarity and governance signal.",
                "proposed_changes": [
                    "Identify parent-child plugin relationships from path nesting.",
                    "Disable child plugins and keep only the top-level parent where appropriate.",
                ],
                "requires_approval": True,
            })

        if cortex.get("unstable_count", 0) > 0:
            plan.append({
                "title": "Demote unstable/system paths from plugin set to assets",
                "component": "guardian/cortex",
                "rationale": "Paths like Desktop/AppData/Windows are not stable plugin roots and are high-risk/noise.",
                "proposed_changes": [
                    "Flag and disable unstable/system-path plugins.",
                    "Restrict future activations to project-like roots (markers + readme).",
                ],
                "requires_approval": True,
            })

        # Domain consolidation proposals.
        categories = cortex.get("category_counts", {})
        for cat in ["knowledge", "orchestration", "devtools", "simulation", "hardware"]:
            if categories.get(cat, 0) > 0:
                plan.append({
                    "title": f"Create domain plugin wrapper: {cat}",
                    "component": "praxis",
                    "rationale": "Many roots belong to the same domain; wrappers make scheduling, testing and governance tractable.",
                    "proposed_changes": [
                        f"Define a domain wrapper for {cat} with standard actions (index, inspect, propose_run).",
                        "Expose a single domain dashboard in the KG and UI.",
                    ],
                    "requires_approval": True,
                })

        return plan[:50]

    def _ingest_knowledge_graph(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        kg = get_knowledge_graph()
        created_nodes = 0
        created_relations = 0
        seen_category_nodes: set[str] = set()

        runtime_node = "framework_plugin_runtime"
        if kg.add_node(
            node_id=runtime_node,
            node_type=NodeType.FRAMEWORK,
            name="Plugin Runtime",
            description="Governed runtime over local plugins (manifest, cortex judgment, praxis proposals).",
            properties={"source": "plugin_runtime"},
            reliability_score=0.9,
        ):
            created_nodes += 1

        for entry in manifest.get("items", [])[:500]:
            root = str(entry.get("root", "")).strip()
            if not root:
                continue
            node_id = _hash_id("entity_plugin_", root, n=12)
            if kg.add_node(
                node_id=node_id,
                node_type=NodeType.ENTITY,
                name=root,
                description=f"Local plugin root (score={entry.get('score', 0)})",
                properties={
                    "plugin_id": entry.get("plugin_id"),
                    "score": entry.get("score"),
                    "status": entry.get("status"),
                    "category": entry.get("category"),
                    "flags": entry.get("flags", []),
                    "signals": entry.get("signals", {}),
                },
                reliability_score=0.75,
            ):
                created_nodes += 1
            if kg.add_relation(
                source_node_id=runtime_node,
                target_node_id=node_id,
                relation_type=RelationType.APPLIES_TO,
                weight=0.9,
                confidence=0.85,
                properties={"from": "plugin_runtime_manifest"},
            ):
                created_relations += 1

            # Connect to category concept.
            cat = str(entry.get("category", "misc"))
            cat_node = _hash_id("concept_plugin_cat_", cat, n=10)
            if cat_node not in seen_category_nodes:
                seen_category_nodes.add(cat_node)
                if cat_node not in kg.nodes:
                    if kg.add_node(
                        node_id=cat_node,
                        node_type=NodeType.CONCEPT,
                        name=f"plugin_category:{cat}",
                        description="Plugin inventory category (runtime classification).",
                        properties={"category": cat},
                        reliability_score=0.8,
                    ):
                        created_nodes += 1
            if kg.add_relation(
                source_node_id=node_id,
                target_node_id=cat_node,
                relation_type=RelationType.PART_OF,
                weight=0.6,
                confidence=0.7,
                properties={"from": "plugin_runtime_classifier"},
            ):
                created_relations += 1

        return {
            "created_nodes": created_nodes,
            "created_relations": created_relations,
            "kg_status": kg.get_status(),
        }


plugin_runtime = PluginRuntime()
