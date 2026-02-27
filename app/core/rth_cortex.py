"""

RTH Cortex™ - Il Nucleo di Sintesi e Ragionamento

Sistema avanzato di analisi, integrazione semantica e generazione insight per RTH Synapse™

"""



from typing import Dict, List, Any, Optional, Set, Tuple

from datetime import datetime, timedelta

from dataclasses import dataclass, field

from enum import Enum

import asyncio

import logging

import json

import uuid

from collections import defaultdict, Counter



from .knowledge_graph import (

    RTHKnowledgeGraph, KnowledgeFragment, StrategicInsight,

    NodeType, RelationType, ReliabilityScore, SourceType, get_knowledge_graph

)

from .event_bus import RTHEventBus, EventType, RTHEvent



logger = logging.getLogger(__name__)



class AnalysisType(Enum):

    """Tipi di analisi eseguibili da Cortex"""

    TREND_DETECTION = "trend_detection"

    BIAS_ANALYSIS = "bias_analysis"

    CONFLICT_RESOLUTION = "conflict_resolution"

    SEMANTIC_ENRICHMENT = "semantic_enrichment"

    STRATEGIC_SYNTHESIS = "strategic_synthesis"



class BiasType(Enum):

    """Tipi di bias rilevabili"""

    CONFIRMATION_BIAS = "confirmation_bias"

    AVAILABILITY_BIAS = "availability_bias"

    RECENCY_BIAS = "recency_bias"

    SOURCE_BIAS = "source_bias"

    LINGUISTIC_BIAS = "linguistic_bias"



@dataclass

class ConflictResolution:

    """Risoluzione di un conflitto tra frammenti di conoscenza"""

    conflict_id: str

    conflicting_fragments: List[str]

    resolution_strategy: str

    confidence: float

    resolved_knowledge: str

    created_at: datetime = field(default_factory=datetime.now)



@dataclass

class BiasDetection:

    """Rilevamento di bias nella conoscenza"""

    bias_id: str

    bias_type: BiasType

    affected_fragments: List[str]

    severity: float  # 0.0 - 1.0

    description: str

    mitigation_strategy: str

    detected_at: datetime = field(default_factory=datetime.now)



@dataclass

class TrendAnalysis:

    """Analisi di trend emergenti"""

    trend_id: str

    trend_name: str

    related_concepts: List[str]

    trend_strength: float

    time_window: str

    supporting_evidence: List[str]

    predicted_evolution: str

    generated_at: datetime = field(default_factory=datetime.now)



class RTHCortex:

    """

    RTH Cortex™ - Il Nucleo di Sintesi e Ragionamento

    

    Funzionalità principali:

    - Ricezione e processamento Knowledge Fragments da Chronicle

    - Integrazione semantica nel Knowledge Graph RTH

    - Analisi avanzata per rilevamento bias e conflitti

    - Generazione insight strategici e trend analysis

    - Sintesi di conoscenza multi-source

    - Validazione incrociata e truth reconciliation

    """

    

    def __init__(self, event_bus: RTHEventBus, knowledge_graph: RTHKnowledgeGraph):

        self.event_bus = event_bus

        self.knowledge_graph = knowledge_graph

        self.version = "1.0.0"

        self.creator = "Core Rth Team"

        

        # Registri di analisi
        self.bias_detections: Dict[str, BiasDetection] = {}
        self.conflict_resolutions: Dict[str, ConflictResolution] = {}
        self.trend_analyses: Dict[str, TrendAnalysis] = {}
        self.root_analytics: Dict[str, Dict[str, Any]] = {}
        

        # Cache di processing

        self.processed_fragments: Set[str] = set()

        self.pending_analysis_queue: List[str] = []

        

        # Metriche operative

        self.metrics = {

            "fragments_processed": 0,

            "insights_generated": 0,

            "biases_detected": 0,

            "conflicts_resolved": 0,

            "trends_identified": 0,

            "last_analysis": None,

            "analysis_errors": 0

        }

        

        # Configurazioni di analisi

        self.analysis_config = {

            "bias_detection_threshold": 0.6,

            "conflict_similarity_threshold": 0.8,

            "trend_strength_threshold": 0.7,

            "max_analysis_batch_size": 50,

            "analysis_interval_seconds": 300  # 5 minuti

        }

        

        # Sottoscrizione agli eventi

        self._subscribe_to_events()

        

        logger.info(f"RTH Cortex™ v{self.version} inizializzato")

    

    def _subscribe_to_events(self):

        """Sottoscrive agli eventi rilevanti dell'Event Bus"""

        event_types = {

            EventType.KNOWLEDGE_FRAGMENT_CREATED,

            EventType.SOURCE_CRAWL_COMPLETED,

            EventType.FEEDBACK_ANALYSIS_COMPLETED

        }

        

        self.event_bus.subscribe(

            module_name="RTH Cortex™",

            event_types=event_types,

            callback=self._handle_event

        )

    

    async def _handle_event(self, event: RTHEvent):

        """Gestisce eventi ricevuti dall'Event Bus"""

        try:

            if event.event_type == EventType.KNOWLEDGE_FRAGMENT_CREATED:

                await self._process_knowledge_fragment_event(event)

            elif event.event_type == EventType.SOURCE_CRAWL_COMPLETED:

                await self._trigger_batch_analysis()

            elif event.event_type == EventType.FEEDBACK_ANALYSIS_COMPLETED:

                await self._integrate_feedback_analysis(event)

                

        except Exception as e:

            logger.error(f"Errore processing evento in Cortex: {str(e)}")

            self.metrics["analysis_errors"] += 1

    

    async def _process_knowledge_fragment_event(self, event: RTHEvent):

        """Processa un evento di creazione Knowledge Fragment"""

        fragment_data = event.data.get('fragment')

        if not fragment_data:

            return

        

        fragment_id = fragment_data.get('fragment_id')

        if fragment_id and fragment_id not in self.processed_fragments:

            

            # Ricostruisce il KnowledgeFragment

            fragment = self._reconstruct_fragment_from_data(fragment_data)

            

            if fragment:

                await self._analyze_knowledge_fragment(fragment)

                self.processed_fragments.add(fragment_id)

                self.metrics["fragments_processed"] += 1

    

    def _reconstruct_fragment_from_data(self, fragment_data: Dict[str, Any]) -> Optional[KnowledgeFragment]:

        """Ricostruisce un KnowledgeFragment dai dati dell'evento"""

        try:

            return KnowledgeFragment(

                fragment_id=fragment_data['fragment_id'],

                title=fragment_data['title'],

                content=fragment_data['content'],

                source_type=SourceType(fragment_data['source_type']),

                source_url=fragment_data['source_url'],

                reliability_score=ReliabilityScore(fragment_data['reliability_score']),

                entities=fragment_data.get('entities', []),

                concepts=fragment_data.get('concepts', []),

                metadata=fragment_data.get('metadata', {}),

                created_at=datetime.fromisoformat(fragment_data['created_at']),

                processed_at=datetime.fromisoformat(fragment_data['processed_at']) if fragment_data.get('processed_at') else None

            )

        except Exception as e:

            logger.error(f"Errore ricostruzione fragment: {str(e)}")

            return None

    

    async def _analyze_knowledge_fragment(self, fragment: KnowledgeFragment):
        """Analizza un Knowledge Fragment completamente"""
        try:
            fragment_root = self._extract_fragment_root(fragment)
            root_state = self._touch_root_analytics(fragment_root, fragment) if fragment_root else None
            # 1. Integra nel Knowledge Graph
            success = self.knowledge_graph.add_knowledge_fragment(fragment)
            if not success:
                logger.warning(f"Fallita integrazione fragment {fragment.fragment_id}")
                return
            
            # 2. Rileva potenziali bias
            biases = await self._detect_biases_in_fragment(fragment)
            
            # 3. Identifica conflitti con conoscenza esistente
            conflicts = await self._identify_conflicts(fragment)
            
            # 4. Genera insight se appropriato
            await self._generate_insights_from_fragment(fragment)
            
            # 5. Aggiorna trend analysis
            await self._update_trend_analysis(fragment)

            if root_state is not None:
                root_state["biases_detected"] += len(biases)
                root_state["conflicts_resolved"] += len(conflicts)
                root_state["last_update"] = datetime.now()
                root_state["last_fragment_id"] = fragment.fragment_id
            
            # Pubblica aggiornamento Knowledge Graph
            await self.event_bus.publish(
                EventType.KNOWLEDGE_GRAPH_UPDATED,

                {

                    'fragment_id': fragment.fragment_id,

                    'integration_success': success,

                    'timestamp': datetime.now().isoformat()

                },

                source_module="RTH Cortex™"

            )

            

        except Exception as e:

            logger.error(f"Errore analisi fragment {fragment.fragment_id}: {str(e)}")

            self.metrics["analysis_errors"] += 1

    

    async def _detect_biases_in_fragment(self, fragment: KnowledgeFragment) -> List[BiasDetection]:
        """Rileva potenziali bias nel frammento di conoscenza"""

        biases_detected = []

        

        # Bias da fonte (source bias)

        if fragment.source_type in [fragment.source_type.BLOG, fragment.source_type.SOCIAL]:

            source_bias = BiasDetection(

                bias_id=f"bias_{uuid.uuid4().hex[:8]}",

                bias_type=BiasType.SOURCE_BIAS,

                affected_fragments=[fragment.fragment_id],

                severity=0.4,

                description=f"Contenuto da fonte {fragment.source_type.value} potenzialmente meno affidabile",

                mitigation_strategy="Verificare con fonti accademiche o istituzionali"

            )

            biases_detected.append(source_bias)

        

        # Bias linguistico (parole cariche emotivamente)

        emotional_words = [

            'revolutionary', 'groundbreaking', 'amazing', 'terrible', 

            'disaster', 'miracle', 'unprecedented', 'shocking'

        ]

        

        content_lower = fragment.content.lower()

        emotional_count = sum(1 for word in emotional_words if word in content_lower)

        

        if emotional_count > 3:

            linguistic_bias = BiasDetection(

                bias_id=f"bias_{uuid.uuid4().hex[:8]}",

                bias_type=BiasType.LINGUISTIC_BIAS,

                affected_fragments=[fragment.fragment_id],

                severity=min(emotional_count * 0.15, 1.0),

                description=f"Linguaggio emotivo rilevato ({emotional_count} termini)",

                mitigation_strategy="Analizzare contenuto per separare fatti da opinioni"

            )

            biases_detected.append(linguistic_bias)

        

        # Salva bias rilevati

        for bias in biases_detected:

            self.bias_detections[bias.bias_id] = bias

            self.metrics["biases_detected"] += 1

            

            # Pubblica evento bias rilevato

            await self.event_bus.publish(

                EventType.BIAS_DETECTED,

                {

                    'bias_id': bias.bias_id,

                    'bias_type': bias.bias_type.value,

                    'severity': bias.severity,

                    'fragment_id': fragment.fragment_id

                },

                source_module="RTH Cortex™",

                priority=2
            )
        return biases_detected
    

    async def _identify_conflicts(self, fragment: KnowledgeFragment) -> List[ConflictResolution]:
        """Identifica conflitti con conoscenza esistente"""

        conflicts_found = []

        

        # Cerca frammenti simili con contenuto potenzialmente contrastante

        for existing_fragment_id, existing_fragment in self.knowledge_graph.fragments.items():

            if existing_fragment_id == fragment.fragment_id:

                continue

            

            # Calcola similarità semantica (semplificata)

            similarity = self._calculate_semantic_similarity(fragment, existing_fragment)

            

            if similarity > self.analysis_config["conflict_similarity_threshold"]:

                # Analizza se c'è conflitto

                conflict_detected = self._detect_content_conflict(fragment, existing_fragment)

                

                if conflict_detected:

                    conflict = ConflictResolution(

                        conflict_id=f"conflict_{uuid.uuid4().hex[:8]}",

                        conflicting_fragments=[fragment.fragment_id, existing_fragment_id],

                        resolution_strategy=self._determine_resolution_strategy(fragment, existing_fragment),

                        confidence=0.7,

                        resolved_knowledge=self._synthesize_conflicting_knowledge(fragment, existing_fragment)

                    )

                    

                    conflicts_found.append(conflict)

        

        # Salva conflitti rilevati

        for conflict in conflicts_found:

            self.conflict_resolutions[conflict.conflict_id] = conflict

            self.metrics["conflicts_resolved"] += 1

            

            # Pubblica evento conflitto

            await self.event_bus.publish(

                EventType.CONFLICT_IDENTIFIED,

                {

                    'conflict_id': conflict.conflict_id,

                    'conflicting_fragments': conflict.conflicting_fragments,

                    'resolution_strategy': conflict.resolution_strategy

                },

                source_module="RTH Cortex™",

                priority=1  # Alta priorità per RTH Guardian™

            )

    

        return conflicts_found

    def _extract_fragment_root(self, fragment: KnowledgeFragment) -> Optional[str]:
        """Extract project/root identity for local filesystem scan fragments."""
        metadata = fragment.metadata or {}
        if metadata.get("kind") != "local_filesystem_scan":
            return None
        root = metadata.get("root_original") or metadata.get("root")
        if isinstance(root, str) and root.strip():
            return root.strip()
        return None

    def _touch_root_analytics(self, root: str, fragment: KnowledgeFragment) -> Dict[str, Any]:
        key = root.lower().replace("\\", "/")
        state = self.root_analytics.get(key)
        if state is None:
            state = {
                "root": root,
                "fragment_ids": set(),
                "concepts": Counter(),
                "entities": Counter(),
                "markers": Counter(),
                "files_seen": 0,
                "scan_fragments": 0,
                "scan_flags": {},
                "top_extensions": Counter(),
                "top_dirs": Counter(),
                "biases_detected": 0,
                "conflicts_resolved": 0,
                "last_update": datetime.now(),
                "last_fragment_id": None,
            }
            self.root_analytics[key] = state

        state["fragment_ids"].add(fragment.fragment_id)
        state["scan_fragments"] = len(state["fragment_ids"])
        for concept in fragment.concepts:
            if concept:
                state["concepts"][concept.lower()] += 1
        for entity in fragment.entities:
            if entity:
                state["entities"][entity.lower()] += 1

        metadata = fragment.metadata or {}
        try:
            files = int(metadata.get("files", 0) or 0)
            state["files_seen"] = max(int(state.get("files_seen", 0)), files)
        except Exception:
            pass
        markers = metadata.get("markers") or []
        if isinstance(markers, list):
            for marker in markers:
                if isinstance(marker, str) and marker:
                    state["markers"][marker.lower()] += 1
        scan_flags = metadata.get("scan_flags") or {}
        if isinstance(scan_flags, dict):
            state_flags = state.setdefault("scan_flags", {})
            for flag_name, flag_value in scan_flags.items():
                if isinstance(flag_name, str):
                    state_flags[flag_name] = bool(state_flags.get(flag_name)) or bool(flag_value)
        top_exts = metadata.get("top_extensions") or {}
        if isinstance(top_exts, dict):
            for ext, count in top_exts.items():
                if not isinstance(ext, str):
                    continue
                try:
                    state["top_extensions"][ext.lower()] += int(count or 0)
                except Exception:
                    continue
        top_dirs = metadata.get("top_dirs") or {}
        if isinstance(top_dirs, dict):
            for top_name, count in top_dirs.items():
                if not isinstance(top_name, str):
                    continue
                try:
                    state["top_dirs"][top_name.lower()] += int(count or 0)
                except Exception:
                    continue

        state["last_update"] = datetime.now()
        state["last_fragment_id"] = fragment.fragment_id
        return state

    def _infer_root_domain(self, state: Dict[str, Any]) -> str:
        root = str(state.get("root") or "").lower().replace("\\", "/")
        concepts = set((state.get("concepts") or Counter()).keys())
        markers = set((state.get("markers") or Counter()).keys())

        if "sublimeomnidoc" in root or {"tauri", "vite", "react"}.issubset(concepts) or "tauri.conf.json" in markers:
            return "doc_reader_desktop"
        if "antihaker" in root or "security" in concepts or "omni-recon" in markers:
            return "security_orchestrator"
        if {"agent", "orchestration"}.issubset(concepts) or "docker-compose.yml" in markers:
            return "agent_orchestration"
        return "generic_software_project"

    def _build_root_audit(self, state: Dict[str, Any]) -> Dict[str, Any]:
        flags = dict(state.get("scan_flags") or {})
        concepts = set((state.get("concepts") or Counter()).keys())
        top_exts = state.get("top_extensions") or Counter()
        files_seen = int(state.get("files_seen", 0) or 0)
        domain = self._infer_root_domain(state)

        strengths: List[str] = []
        gaps: List[str] = []
        risks: List[str] = []

        if flags.get("has_readme"):
            strengths.append("README presente: onboarding e contesto iniziale disponibili")
        else:
            gaps.append("Manca README: alto rischio di conoscenza implicita non formalizzata")

        if flags.get("has_license"):
            strengths.append("LICENSE presente: governance distribuzione piu chiara")
        else:
            gaps.append("Manca LICENSE: rischio di rilascio/uso ambiguo")

        if flags.get("has_lock"):
            strengths.append("Lockfile dipendenze presente: build piu riproducibili")
        else:
            gaps.append("Manca lockfile: rischio drift dipendenze")

        if flags.get("has_ci"):
            strengths.append("CI rilevata: controllo regressioni automatizzabile")
        else:
            gaps.append("CI non rilevata: regressioni e breakage manuali")

        if flags.get("has_tests"):
            strengths.append("Test rilevati: base per verifica incrementale")
        else:
            gaps.append("Test non rilevati: evoluzione fragile e difficile da benchmarkare")

        if flags.get("has_docker"):
            strengths.append("Docker/compose rilevati: runtime portabile")
        if flags.get("has_launcher"):
            strengths.append("Launcher operativi rilevati: buona superficie di avvio controllato")

        # Domain-specific audit notes driven by observed features only.
        if domain == "doc_reader_desktop":
            if {"pdf", "docx", "office", "editor"} & concepts or any(ext in top_exts for ext in [".pdf", ".docx", ".tsx", ".rs"]):
                strengths.append("Stack doc-reader desktop riconosciuto (parsing/editor/UI)")
            if not flags.get("has_tests"):
                risks.append("Parser/formati senza test regressione: alto rischio rotture silenziose")
            if not flags.get("has_ci"):
                risks.append("Doc-reader senza CI: bug su formati multipli difficili da intercettare presto")
        elif domain == "security_orchestrator":
            strengths.append("Superficie security/orchestrator riconosciuta da concetti e marker locali")
            if flags.get("has_launcher"):
                risks.append("Launcher security presenti: richiedere consenso forte e modalita dry-run di default")
            if not flags.get("has_tests"):
                risks.append("Tool security senza test/corpus: rischio falso positivo/negativo e regressioni")
            if not flags.get("has_ci"):
                risks.append("Hardening senza CI: rischio drift operativo non rilevato")
        elif domain == "agent_orchestration":
            strengths.append("Stack agent orchestration riconosciuto")
            if not flags.get("has_ci"):
                risks.append("Orchestrazione senza CI: integrazioni fragili tra moduli/adapter")

        if files_seen > 1000:
            strengths.append("Codicebase ampia: sufficiente segnale per analisi evolutiva non banale")
        elif files_seen < 20:
            risks.append("Pochi file osservati: audit Cortex poco affidabile su questo root")

        # Lightweight scores for benchmark visibility and future gating.
        maturity_score = 50
        for key in ("has_readme", "has_lock", "has_ci", "has_tests", "has_license"):
            maturity_score += 8 if flags.get(key) else -8
        if flags.get("has_docker"):
            maturity_score += 4
        if flags.get("has_launcher"):
            maturity_score += 4
        maturity_score = max(0, min(100, maturity_score))

        risk_score = 15
        risk_score += len(gaps) * 8
        risk_score += len(risks) * 10
        if domain == "security_orchestrator":
            risk_score += 8
        risk_score = max(0, min(100, risk_score))

        findings = []
        findings.extend(strengths[:4])
        findings.extend(gaps[:4])
        findings.extend(risks[:4])

        return {
            "domain": domain,
            "strengths": strengths[:8],
            "gaps": gaps[:8],
            "risks": risks[:8],
            "findings": findings[:12],
            "maturity_score": maturity_score,
            "risk_score": risk_score,
            "evidence_flags": flags,
        }

    def _root_alignment_conflicts_snapshot(self, limit: int = 12) -> List[Dict[str, Any]]:
        rows = list(self.root_analytics.values())
        conflicts: List[Dict[str, Any]] = []
        if len(rows) < 2:
            return conflicts

        flag_labels = {
            "has_ci": "CI",
            "has_tests": "tests",
            "has_lock": "lockfile",
            "has_license": "license",
        }
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                a_domain = self._infer_root_domain(a)
                b_domain = self._infer_root_domain(b)
                if a_domain != b_domain and "security_orchestrator" not in {a_domain, b_domain} and "doc_reader_desktop" not in {a_domain, b_domain}:
                    continue
                a_flags = dict(a.get("scan_flags") or {})
                b_flags = dict(b.get("scan_flags") or {})
                mismatches = []
                for flag_name, label in flag_labels.items():
                    if bool(a_flags.get(flag_name)) != bool(b_flags.get(flag_name)):
                        mismatches.append(label)
                if mismatches:
                    conflicts.append({
                        "roots": [a.get("root"), b.get("root")],
                        "domains": [a_domain, b_domain],
                        "mismatched_controls": mismatches[:6],
                    })

        conflicts.sort(key=lambda c: len(c.get("mismatched_controls", [])), reverse=True)
        return conflicts[:limit]

    def _root_runtime_contract(self, state: Dict[str, Any]) -> Dict[str, Any]:
        flags = dict(state.get("scan_flags") or {})
        concepts = set((state.get("concepts") or Counter()).keys())
        exts = set((state.get("top_extensions") or Counter()).keys())
        markers = set((state.get("markers") or Counter()).keys())
        domain = self._infer_root_domain(state)

        runtime_modes = []
        if "tauri" in concepts or "tauri.conf.json" in markers:
            runtime_modes.append("desktop_tauri")
        if "docker" in concepts or flags.get("has_docker"):
            runtime_modes.append("dockerized")
        if any(e in exts for e in [".ps1", ".cmd", ".bat"]):
            runtime_modes.append("script_launcher")
        if any(e in exts for e in [".ts", ".tsx", ".js"]):
            runtime_modes.append("node_tooling")
        if ".rs" in exts:
            runtime_modes.append("rust_native")
        if not runtime_modes:
            runtime_modes.append("unknown")

        control_level = "baseline"
        if flags.get("has_ci") and flags.get("has_tests"):
            control_level = "verified"
        elif flags.get("has_ci") or flags.get("has_tests"):
            control_level = "partial"

        governance_profile = "strict_execute_gate" if domain == "security_orchestrator" or flags.get("has_launcher") else "normal_execute_gate"
        if domain == "security_orchestrator" and not flags.get("has_tests"):
            governance_profile = "strict_execute_gate_plus_dry_run"

        observability = "audit_ready" if (flags.get("has_ci") or flags.get("has_tests")) else "manual_only"
        supply_chain = "locked" if flags.get("has_lock") else "floating"

        return {
            "domain": domain,
            "runtime_modes": sorted(set(runtime_modes)),
            "control_level": control_level,
            "governance_profile": governance_profile,
            "observability": observability,
            "supply_chain": supply_chain,
            "flags": flags,
        }

    def _root_semantic_conflicts_snapshot(self, limit: int = 12) -> List[Dict[str, Any]]:
        rows = list(self.root_analytics.values())
        if len(rows) < 2:
            return []

        items: List[Dict[str, Any]] = []
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                a_root = a.get("root")
                b_root = b.get("root")
                if not a_root or not b_root:
                    continue
                ca = self._root_runtime_contract(a)
                cb = self._root_runtime_contract(b)
                findings = []

                # Cross-domain integration conflicts that require explicit contracts/policies.
                if ca["governance_profile"] != cb["governance_profile"]:
                    findings.append({
                        "type": "governance_profile_mismatch",
                        "severity": "high",
                        "detail": f"{ca['domain']} requires `{ca['governance_profile']}` while {cb['domain']} uses `{cb['governance_profile']}`.",
                        "recommended_contract": "per-root execution policy tiers + mandatory consent templates",
                    })

                if ca["control_level"] != cb["control_level"]:
                    findings.append({
                        "type": "verification_maturity_gap",
                        "severity": "medium",
                        "detail": f"Verification maturity differs ({ca['control_level']} vs {cb['control_level']}).",
                        "recommended_contract": "shared release gate requiring minimum CI/test evidence before orchestration coupling",
                    })

                if ca["supply_chain"] != cb["supply_chain"]:
                    findings.append({
                        "type": "dependency_reproducibility_mismatch",
                        "severity": "medium",
                        "detail": f"Supply chain posture differs ({ca['supply_chain']} vs {cb['supply_chain']}).",
                        "recommended_contract": "lockfile baseline and reproducible build manifest across integrated assets",
                    })

                a_modes = set(ca.get("runtime_modes") or [])
                b_modes = set(cb.get("runtime_modes") or [])
                if "desktop_tauri" in a_modes.union(b_modes) and "script_launcher" in a_modes.union(b_modes):
                    findings.append({
                        "type": "runtime_surface_contract_gap",
                        "severity": "medium",
                        "detail": "Desktop UI runtime and script-driven operational runtime have different failure/consent surfaces.",
                        "recommended_contract": "adapter contract layer with dry-run, timeout, and audit log schema",
                    })

                if "security_orchestrator" in {ca["domain"], cb["domain"]}:
                    sec = ca if ca["domain"] == "security_orchestrator" else cb
                    peer = cb if sec is ca else ca
                    if sec.get("observability") == "manual_only" and peer.get("control_level") in {"partial", "verified"}:
                        findings.append({
                            "type": "auditability_asymmetry",
                            "severity": "high",
                            "detail": "Security-oriented root has weaker automated observability than its integration peer.",
                            "recommended_contract": "tamper-evident audit trail + replayable dry-run before enabling cross-root automation",
                        })

                if not findings:
                    continue

                severity_order = {"high": 3, "medium": 2, "low": 1}
                items.append({
                    "roots": [a_root, b_root],
                    "domains": [ca["domain"], cb["domain"]],
                    "contracts": {
                        "a": ca,
                        "b": cb,
                    },
                    "semantic_conflicts": findings,
                    "max_severity": max((severity_order.get(f.get("severity", "low"), 1) for f in findings), default=1),
                })

        items.sort(
            key=lambda x: (
                x.get("max_severity", 0),
                len(x.get("semantic_conflicts") or []),
            ),
            reverse=True,
        )
        for item in items:
            item.pop("max_severity", None)
        return items[:limit]

    def _root_analytics_snapshot(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for state in self.root_analytics.values():
            audit = self._build_root_audit(state)
            scan_flags = dict(state.get("scan_flags") or {})
            rows.append({
                "root": state.get("root"),
                "scan_fragments": state.get("scan_fragments", 0),
                "files_seen": state.get("files_seen", 0),
                "biases_detected": state.get("biases_detected", 0),
                "conflicts_resolved": state.get("conflicts_resolved", 0),
                "domain": audit.get("domain"),
                "scan_flags": scan_flags,
                "audit": audit,
                "top_concepts": [name for name, _ in (state.get("concepts") or Counter()).most_common(12)],
                "top_entities": [name for name, _ in (state.get("entities") or Counter()).most_common(12)],
                "top_extensions": dict((state.get("top_extensions") or Counter()).most_common(12)),
                "top_dirs": dict((state.get("top_dirs") or Counter()).most_common(12)),
                "markers": [name for name, _ in (state.get("markers") or Counter()).most_common(8)],
                "last_fragment_id": state.get("last_fragment_id"),
                "last_update": state.get("last_update").isoformat() if state.get("last_update") else None,
            })
        rows.sort(key=lambda r: (r.get("files_seen", 0), r.get("scan_fragments", 0)), reverse=True)
        return rows[:limit]

    def _calculate_semantic_similarity(self, fragment1: KnowledgeFragment, 
                                     fragment2: KnowledgeFragment) -> float:
        """Calcola similarità semantica tra due frammenti (implementazione semplificata)"""

        # Similarità basata su concetti condivisi

        concepts1 = set(fragment1.concepts)

        concepts2 = set(fragment2.concepts)

        

        if not concepts1 and not concepts2:

            return 0.0

        

        intersection = len(concepts1.intersection(concepts2))

        union = len(concepts1.union(concepts2))

        

        if union == 0:

            return 0.0

        

        return intersection / union

    

    def _detect_content_conflict(self, fragment1: KnowledgeFragment, 

                               fragment2: KnowledgeFragment) -> bool:

        """Rileva se due frammenti hanno contenuto contrastante"""

        # Indicatori di conflitto (semplificati)

        conflict_indicators = [

            ('increase', 'decrease'), ('growth', 'decline'),

            ('positive', 'negative'), ('success', 'failure'),

            ('effective', 'ineffective'), ('improve', 'worsen')

        ]

        

        content1_lower = fragment1.content.lower()

        content2_lower = fragment2.content.lower()

        

        for positive, negative in conflict_indicators:
            if ((positive in content1_lower and negative in content2_lower) or
                (negative in content1_lower and positive in content2_lower)):
                return True


        

        return False

    

    def _determine_resolution_strategy(self, fragment1: KnowledgeFragment, 

                                     fragment2: KnowledgeFragment) -> str:

        """Determina strategia di risoluzione per conflitto"""

        # Preferenza per fonte più affidabile

        if fragment1.reliability_score.value != fragment2.reliability_score.value:

            if fragment1.reliability_score == ReliabilityScore.HIGH:

                return "prefer_fragment_1_higher_reliability"

            elif fragment2.reliability_score == ReliabilityScore.HIGH:

                return "prefer_fragment_2_higher_reliability"

        

        # Preferenza per fonte più recente

        if fragment1.created_at > fragment2.created_at:

            return "prefer_fragment_1_more_recent"

        else:

            return "prefer_fragment_2_more_recent"

    

    def _synthesize_conflicting_knowledge(self, fragment1: KnowledgeFragment, 

                                        fragment2: KnowledgeFragment) -> str:

        """Sintetizza conoscenza da frammenti conflittuali"""

        return (f"Sintesi di prospettive diverse: {fragment1.title} vs {fragment2.title}. "
               f"Richiede validazione umana per reconciliazione definitiva.")

    

    async def _generate_insights_from_fragment(self, fragment: KnowledgeFragment):

        """Genera insight strategici dal frammento analizzato"""

        # Genera insight per ogni concetto RTH correlato

        for concept in fragment.concepts:

            insight = self.knowledge_graph.generate_insight(concept)

            

            if insight:

                self.metrics["insights_generated"] += 1

                

                # Pubblica insight generato

                await self.event_bus.publish(

                    EventType.INSIGHT_GENERATED,

                    {

                        'insight': insight.to_dict(),

                        'triggering_fragment': fragment.fragment_id,

                        'focus_area': concept

                    },

                    source_module="RTH Cortex™",

                    target_modules=["RTH Praxis™", "RTH Guardian™"]

                )

    

    async def _update_trend_analysis(self, fragment: KnowledgeFragment):

        """Aggiorna analisi dei trend basata sul nuovo frammento"""

        # Analisi trend per concetti RTH

        rth_concepts = [concept for concept in fragment.concepts 

                       if any(rth_keyword in concept.lower() 

                             for rth_keyword in ['leadership', 'performance', 'innovation', 'development'])]

        

        for concept in rth_concepts:

            # Trova trend esistente o crea nuovo

            existing_trend = self._find_trend_for_concept(concept)

            

            if existing_trend:

                # Aggiorna trend esistente

                existing_trend.supporting_evidence.append(fragment.fragment_id)

                existing_trend.trend_strength = min(existing_trend.trend_strength + 0.1, 1.0)

            else:

                # Crea nuovo trend se ha abbastanza supporto

                supporting_fragments = self._find_supporting_fragments_for_concept(concept)

                

                if len(supporting_fragments) >= 3:  # Soglia minima per trend

                    trend = TrendAnalysis(

                        trend_id=f"trend_{uuid.uuid4().hex[:8]}",

                        trend_name=f"Emergent Trend: {concept.title()}",

                        related_concepts=[concept],

                        trend_strength=0.6,

                        time_window="last_30_days",

                        supporting_evidence=supporting_fragments,

                        predicted_evolution="Monitoraggio continuo richiesto"

                    )

                    

                    self.trend_analyses[trend.trend_id] = trend

                    self.metrics["trends_identified"] += 1

    

    def _find_trend_for_concept(self, concept: str) -> Optional[TrendAnalysis]:

        """Trova trend esistente per un concetto"""

        for trend in self.trend_analyses.values():

            if concept.lower() in [c.lower() for c in trend.related_concepts]:

                return trend

        return None

    

    def _find_supporting_fragments_for_concept(self, concept: str) -> List[str]:

        """Trova frammenti che supportano un concetto"""

        supporting_fragments = []

        

        for fragment_id, fragment in self.knowledge_graph.fragments.items():

            if concept.lower() in [c.lower() for c in fragment.concepts]:

                supporting_fragments.append(fragment_id)

        

        return supporting_fragments

    

    async def _trigger_batch_analysis(self):

        """Innesca analisi batch dopo completamento crawl"""

        try:

            # Analisi aggregata dei trend

            await self._perform_aggregate_trend_analysis()

            

            # Sintesi conoscenza multi-source

            await self._synthesize_multi_source_knowledge()

            

            self.metrics["last_analysis"] = datetime.now()

            

        except Exception as e:

            logger.error(f"Errore batch analysis: {str(e)}")

            self.metrics["analysis_errors"] += 1

    

    async def _perform_aggregate_trend_analysis(self):

        """Esegue analisi aggregata dei trend"""

        # Raggruppa frammenti per periodo temporale

        recent_cutoff = datetime.now() - timedelta(days=7)

        recent_fragments = [

            f for f in self.knowledge_graph.fragments.values()

            if f.created_at > recent_cutoff

        ]

        

        # Analizza frequenza concetti

        concept_frequency = Counter()

        for fragment in recent_fragments:

            for concept in fragment.concepts:

                concept_frequency[concept] += 1

        

        # Identifica trend emergenti

        for concept, frequency in concept_frequency.most_common(10):

            if frequency >= 3 and not self._find_trend_for_concept(concept):

                # Nuovo trend emergente

                trend = TrendAnalysis(

                    trend_id=f"trend_{uuid.uuid4().hex[:8]}",

                    trend_name=f"Trending: {concept.title()}",

                    related_concepts=[concept],

                    trend_strength=min(frequency / 10.0, 1.0),

                    time_window="last_7_days",

                    supporting_evidence=[f.fragment_id for f in recent_fragments if concept in f.concepts],

                    predicted_evolution="Trend emergente da monitorare"

                )

                

                self.trend_analyses[trend.trend_id] = trend

                self.metrics["trends_identified"] += 1

    

    async def _synthesize_multi_source_knowledge(self):

        """Sintetizza conoscenza da multiple fonti"""

        # Trova concetti supportati da più fonti

        concept_sources = defaultdict(set)

        

        for fragment in self.knowledge_graph.fragments.values():

            for concept in fragment.concepts:

                concept_sources[concept].add(fragment.source_type.value)

        

        # Genera insight per concetti multi-source

        for concept, sources in concept_sources.items():

            if len(sources) >= 3:  # Almeno 3 fonti diverse

                insight = StrategicInsight(

                    insight_id=f"insight_{uuid.uuid4().hex[:8]}",

                    title=f"Multi-Source Validation: {concept.title()}",

                    description=f"Concetto '{concept}' validato da {len(sources)} fonti diverse: {', '.join(sources)}",

                    insight_type="validation",

                    confidence=0.9,

                    impact_score=0.8,

                    supporting_evidence=[f.fragment_id for f in self.knowledge_graph.fragments.values() if concept in f.concepts],

                    related_concepts=[concept]

                )

                

                self.knowledge_graph.insights[insight.insight_id] = insight

                self.metrics["insights_generated"] += 1

    

    async def _integrate_feedback_analysis(self, event: RTHEvent):

        """Integra analisi feedback nel Knowledge Graph"""

        feedback_data = event.data

        

        # Crea nodi per temi di feedback

        if 'themes' in feedback_data:

            for theme in feedback_data['themes']:

                # Integra tema come concetto nel KG

                self.knowledge_graph.add_node(

                    node_id=f"feedback_theme_{uuid.uuid4().hex[:8]}",

                    node_type=NodeType.FEEDBACK_THEME,

                    name=theme['name'],

                    description=f"Tema feedback: {theme.get('description', '')}",

                    properties={

                        'sentiment': theme.get('sentiment', 'neutral'),

                        'frequency': theme.get('frequency', 0),

                        'source': 'RTH FeedbackLoop™'

                    },

                    reliability_score=0.8

                )

    

    async def start_continuous_analysis(self):

        """Avvia il processo di analisi continua"""

        logger.info("Avvio analisi continua RTH Cortex™")

        

        while True:

            try:

                await self._trigger_batch_analysis()

                await asyncio.sleep(self.analysis_config["analysis_interval_seconds"])

                

            except Exception as e:

                logger.error(f"Errore nel ciclo di analisi continua: {str(e)}")

                self.metrics["analysis_errors"] += 1

                await asyncio.sleep(60)

    

    def get_status(self) -> Dict[str, Any]:

        """Restituisce lo stato del sistema Cortex"""

        return {

            'module': 'RTH Cortex™',

            'version': self.version,

            'creator': self.creator,

            'metrics': self.metrics,

            'analysis_config': self.analysis_config,

            'knowledge_graph_status': self.knowledge_graph.get_status(),
            'active_trends': len(self.trend_analyses),
            'detected_biases': len(self.bias_detections),
            'resolved_conflicts': len(self.conflict_resolutions),
            'root_analytics_count': len(self.root_analytics),
            'root_analytics': self._root_analytics_snapshot(),
            'root_alignment_conflicts': self._root_alignment_conflicts_snapshot(),
            'root_semantic_conflicts': self._root_semantic_conflicts_snapshot(),
            'pending_analysis': len([f for f in self.knowledge_graph.fragments.values() 
                                   if f.processed_at is None])
        }


# Istanza globale (singleton pattern)

cortex_instance: Optional[RTHCortex] = None



def get_cortex() -> RTHCortex:

    """Restituisce l'istanza globale di RTH Cortex™"""

    global cortex_instance

    if cortex_instance is None:

        from .event_bus import get_event_bus

        cortex_instance = RTHCortex(get_event_bus(), get_knowledge_graph())

    return cortex_instance 
