"""
Knowledge Graph RTH (KG-RTH) - Sistema Centrale di Gestione Conoscenza
Rete dinamica e interconnessa di concetti, entità, relazioni e insight per RTH Synapse™
"""

from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import json
import networkx as nx
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

class SourceType(Enum):
    """Tipi di sorgenti per Knowledge Fragments"""
    ACADEMIC = "academic"
    RESEARCH = "research"
    NEWS = "news"
    BLOG = "blog"
    SOCIAL = "social"
    EXPERT = "expert"
    WEB = "web"
    INTERNAL = "internal"  # Da feedback RTH
    QUINTESSENCE = "quintessence"  # Da Core Rth

class ReliabilityScore(Enum):
    """Punteggi di affidabilità per la conoscenza"""
    HIGH = "high"        # 0.8-1.0
    MEDIUM = "medium"    # 0.5-0.79
    LOW = "low"         # 0.0-0.49

class NodeType(Enum):
    """Tipi di nodi nel Knowledge Graph"""
    CONCEPT = "concept"
    ENTITY = "entity"
    PILLAR_RTH = "pillar_rth"
    TALENT = "talent"
    INSIGHT = "insight"
    FRAMEWORK = "framework"
    METHODOLOGY = "methodology"
    FEEDBACK_THEME = "feedback_theme"
    SOURCE = "source"

class RelationType(Enum):
    """Tipi di relazioni nel Knowledge Graph"""
    INFLUENCES = "influences"
    CAUSED_BY = "caused_by"
    SUPPORTS_CONCEPT = "supports_concept"
    CONTRADICTS = "contradicts"
    PART_OF = "part_of"
    SIMILAR_TO = "similar_to"
    DERIVED_FROM = "derived_from"
    APPLIES_TO = "applies_to"
    ENHANCES = "enhances"
    REQUIRES = "requires"

@dataclass
class KnowledgeFragment:
    """Frammento di conoscenza strutturato da Chronicle"""
    fragment_id: str
    title: str
    content: str
    source_type: SourceType
    source_url: str
    reliability_score: ReliabilityScore
    entities: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            'fragment_id': self.fragment_id,
            'title': self.title,
            'content': self.content,
            'source_type': self.source_type.value,
            'source_url': self.source_url,
            'reliability_score': self.reliability_score.value,
            'entities': self.entities,
            'concepts': self.concepts,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

@dataclass
class KGNode:
    """Nodo nel Knowledge Graph"""
    node_id: str
    node_type: NodeType
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    reliability_score: float = 0.5
    source_fragments: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __hash__(self):
        return hash(self.node_id)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type.value,
            'name': self.name,
            'description': self.description,
            'properties': self.properties,
            'reliability_score': self.reliability_score,
            'source_fragments': list(self.source_fragments),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

@dataclass
class KGRelation:
    """Relazione nel Knowledge Graph"""
    relation_id: str
    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    evidence_fragments: Set[str] = field(default_factory=set)
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'relation_id': self.relation_id,
            'source_node_id': self.source_node_id,
            'target_node_id': self.target_node_id,
            'relation_type': self.relation_type.value,
            'weight': self.weight,
            'properties': self.properties,
            'evidence_fragments': list(self.evidence_fragments),
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat()
        }

@dataclass
class StrategicInsight:
    """Insight strategico generato da Cortex"""
    insight_id: str
    title: str
    description: str
    insight_type: str  # trend, opportunity, risk, recommendation
    confidence: float
    impact_score: float
    supporting_evidence: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    validated_by_human: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'insight_id': self.insight_id,
            'title': self.title,
            'description': self.description,
            'insight_type': self.insight_type,
            'confidence': self.confidence,
            'impact_score': self.impact_score,
            'supporting_evidence': self.supporting_evidence,
            'related_concepts': self.related_concepts,
            'generated_at': self.generated_at.isoformat(),
            'validated_by_human': self.validated_by_human
        }

class RTHKnowledgeGraph:
    """
    Knowledge Graph RTH (KG-RTH) - Sistema Centrale di Gestione Conoscenza
    
    Funzionalità principali:
    - Gestione nodi e relazioni della conoscenza RTH
    - Integrazione Knowledge Fragments da Chronicle
    - Inferenza di nuove relazioni e insight
    - Query complesse e ragionamento semantico
    - Tracciamento provenienza e affidabilità
    - Risoluzione conflitti di conoscenza
    """
    
    def __init__(self):
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        
        # Grafo principale (NetworkX per operazioni avanzate)
        self.graph = nx.MultiDiGraph()
        
        # Registry dei componenti
        self.nodes: Dict[str, KGNode] = {}
        self.relations: Dict[str, KGRelation] = {}
        self.fragments: Dict[str, KnowledgeFragment] = {}
        self.insights: Dict[str, StrategicInsight] = {}
        
        # Indici per query veloci
        self.concept_index: Dict[str, Set[str]] = defaultdict(set)
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)
        self.source_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Metriche operative
        self.metrics = {
            "total_nodes": 0,
            "total_relations": 0,
            "total_fragments": 0,
            "total_insights": 0,
            "avg_node_connectivity": 0.0,
            "last_update": datetime.now()
        }
        
        # Inizializza struttura RTH di base
        self._initialize_rth_core_structure()
        
        logger.info(f"RTH Knowledge Graph v{self.version} inizializzato")
    
    def _initialize_rth_core_structure(self):
        """Inizializza la struttura core del framework RTH"""
        
        # Pilastri RTH
        pilastri_rth = [
            ("innovazione", "Pilastro dell'Innovazione - Capacità di generare e implementare idee creative"),
            ("leadership", "Pilastro della Leadership - Capacità di guidare e ispirare team"),
            ("performance", "Pilastro delle Performance - Capacità di raggiungere risultati eccellenti"),
            ("sviluppo", "Pilastro dello Sviluppo - Capacità di crescita continua"),
            ("strategia", "Pilastro della Strategia - Capacità di pianificazione e visione")
        ]
        
        for pilastro_id, description in pilastri_rth:
            self.add_node(
                node_id=f"pillar_rth_{pilastro_id}",
                node_type=NodeType.PILLAR_RTH,
                name=f"Pilastro RTH {pilastro_id.title()}",
                description=description,
                properties={
                    "core_framework": True,
                    "created_by": self.creator
                },
                reliability_score=1.0
            )
        
        # Talenti Distintivi fondamentali
        talenti_distintivi = [
            ("pensiero_critico", "Capacità di analisi e valutazione oggettiva"),
            ("comunicazione_efficace", "Capacità di trasmettere idee chiaramente"),
            ("problem_solving", "Capacità di risolvere problemi complessi"),
            ("intelligenza_emotiva", "Capacità di gestire emozioni proprie e altrui"),
            ("adattabilità", "Capacità di adattarsi ai cambiamenti")
        ]
        
        for talento_id, description in talenti_distintivi:
            self.add_node(
                node_id=f"talent_{talento_id}",
                node_type=NodeType.TALENT,
                name=talento_id.replace("_", " ").title(),
                description=description,
                properties={
                    "distinctive_talent": True,
                    "core_framework": True
                },
                reliability_score=1.0
            )
        
        # Crea relazioni tra pilastri e talenti
        self._create_core_relationships()
    
    def _create_core_relationships(self):
        """Crea le relazioni fondamentali tra i componenti core RTH"""
        
        # Mappings pilastri -> talenti
        pillar_talent_mappings = {
            "pillar_rth_innovazione": ["talent_pensiero_critico", "talent_problem_solving"],
            "pillar_rth_leadership": ["talent_comunicazione_efficace", "talent_intelligenza_emotiva"],
            "pillar_rth_performance": ["talent_problem_solving", "talent_adattabilità"],
            "pillar_rth_sviluppo": ["talent_adattabilità", "talent_pensiero_critico"],
            "pillar_rth_strategia": ["talent_pensiero_critico", "talent_comunicazione_efficace"]
        }
        
        for pillar_id, talents in pillar_talent_mappings.items():
            for talent_id in talents:
                self.add_relation(
                    source_node_id=pillar_id,
                    target_node_id=talent_id,
                    relation_type=RelationType.REQUIRES,
                    weight=0.8,
                    confidence=1.0,
                    properties={"core_relationship": True}
                )
    
    def add_knowledge_fragment(self, fragment: KnowledgeFragment) -> bool:
        """Aggiunge un Knowledge Fragment e lo integra nel grafo"""
        try:
            # Memorizza fragment
            self.fragments[fragment.fragment_id] = fragment
            
            # Estrae e crea nodi per entità e concetti
            created_nodes = []
            
            # Processa entità
            for entity in fragment.entities:
                node_id = self._create_entity_node(entity, fragment)
                if node_id:
                    created_nodes.append(node_id)
            
            # Processa concetti
            for concept in fragment.concepts:
                node_id = self._create_concept_node(concept, fragment)
                if node_id:
                    created_nodes.append(node_id)
            
            # Inferisce relazioni tra nodi creati
            self._infer_relations_from_fragment(fragment, created_nodes)
            
            # Aggiorna indici
            self._update_indices(fragment)
            
            # Aggiorna metriche
            self._update_metrics()
            
            logger.debug(f"Knowledge Fragment {fragment.fragment_id} integrato nel KG-RTH")
            return True
            
        except Exception as e:
            logger.error(f"Errore integrazione fragment: {str(e)}")
            return False
    
    def _create_entity_node(self, entity: str, fragment: KnowledgeFragment) -> Optional[str]:
        """Crea un nodo entità dal fragment"""
        node_id = f"entity_{hashlib.md5(entity.lower().encode()).hexdigest()[:8]}"
        
        if node_id in self.nodes:
            # Aggiorna nodo esistente
            existing_node = self.nodes[node_id]
            existing_node.source_fragments.add(fragment.fragment_id)
            existing_node.updated_at = datetime.now()
            
            # Aggiorna reliability score (media pesata)
            fragment_reliability = self._reliability_to_float(fragment.reliability_score)
            current_weight = len(existing_node.source_fragments) - 1
            existing_node.reliability_score = (
                (existing_node.reliability_score * current_weight + fragment_reliability) /
                len(existing_node.source_fragments)
            )
        else:
            # Crea nuovo nodo
            self.add_node(
                node_id=node_id,
                node_type=NodeType.ENTITY,
                name=entity,
                description=f"Entità estratta da fonti esterne: {entity}",
                properties={
                    "source_type": fragment.source_type.value,
                    "first_mentioned": fragment.created_at.isoformat()
                },
                reliability_score=self._reliability_to_float(fragment.reliability_score),
                source_fragments={fragment.fragment_id}
            )
        
        return node_id
    
    def _create_concept_node(self, concept: str, fragment: KnowledgeFragment) -> Optional[str]:
        """Crea un nodo concetto dal fragment"""
        node_id = f"concept_{hashlib.md5(concept.lower().encode()).hexdigest()[:8]}"
        
        if node_id in self.nodes:
            # Aggiorna nodo esistente
            existing_node = self.nodes[node_id]
            existing_node.source_fragments.add(fragment.fragment_id)
            existing_node.updated_at = datetime.now()
            
            # Aggiorna reliability score
            fragment_reliability = self._reliability_to_float(fragment.reliability_score)
            current_weight = len(existing_node.source_fragments) - 1
            existing_node.reliability_score = (
                (existing_node.reliability_score * current_weight + fragment_reliability) /
                len(existing_node.source_fragments)
            )
        else:
            # Crea nuovo nodo
            self.add_node(
                node_id=node_id,
                node_type=NodeType.CONCEPT,
                name=concept,
                description=f"Concetto estratto: {concept}",
                properties={
                    "source_type": fragment.source_type.value,
                    "rth_relevant": True,
                    "first_mentioned": fragment.created_at.isoformat()
                },
                reliability_score=self._reliability_to_float(fragment.reliability_score),
                source_fragments={fragment.fragment_id}
            )
        
        return node_id
    
    def _reliability_to_float(self, score: ReliabilityScore) -> float:
        """Converte ReliabilityScore in float"""
        mapping = {
            ReliabilityScore.HIGH: 0.9,
            ReliabilityScore.MEDIUM: 0.7,
            ReliabilityScore.LOW: 0.4
        }
        return mapping.get(score, 0.5)
    
    def _infer_relations_from_fragment(self, fragment: KnowledgeFragment, node_ids: List[str]):
        """Inferisce relazioni tra nodi basandosi sul contenuto del fragment"""
        
        # Cerca connessioni con pilastri RTH esistenti
        for node_id in node_ids:
            self._connect_to_rth_framework(node_id, fragment)
        
        # Crea relazioni tra nodi dello stesso fragment (co-occurrence)
        for i, node_id_1 in enumerate(node_ids):
            for node_id_2 in node_ids[i+1:]:
                if node_id_1 != node_id_2:
                    self.add_relation(
                        source_node_id=node_id_1,
                        target_node_id=node_id_2,
                        relation_type=RelationType.SIMILAR_TO,
                        weight=0.3,
                        confidence=0.6,
                        properties={"inferred_from": "co_occurrence"},
                        evidence_fragments={fragment.fragment_id}
                    )
    
    def _connect_to_rth_framework(self, node_id: str, fragment: KnowledgeFragment):
        """Connette un nodo ai pilastri RTH se rilevante"""
        node = self.nodes.get(node_id)
        if not node:
            return
        
        # Analizza contenuto per connessioni ai pilastri
        content_lower = fragment.content.lower()
        node_name_lower = node.name.lower()
        
        # Mappings concetti -> pilastri RTH
        pillar_keywords = {
            "pillar_rth_innovazione": ["innovation", "creative", "new idea", "breakthrough", "disruptive"],
            "pillar_rth_leadership": ["leadership", "leader", "guide", "inspire", "motivate", "team"],
            "pillar_rth_performance": ["performance", "result", "achievement", "excellence", "outcome"],
            "pillar_rth_sviluppo": ["development", "growth", "learning", "skill", "competency"],
            "pillar_rth_strategia": ["strategy", "strategic", "planning", "vision", "goal"]
        }
        
        for pillar_id, keywords in pillar_keywords.items():
            # Verifica se il nodo o il contenuto è correlato al pilastro
            relevance_score = 0
            for keyword in keywords:
                if keyword in content_lower or keyword in node_name_lower:
                    relevance_score += 0.2
            
            if relevance_score >= 0.4:  # Soglia di rilevanza
                self.add_relation(
                    source_node_id=node_id,
                    target_node_id=pillar_id,
                    relation_type=RelationType.SUPPORTS_CONCEPT,
                    weight=min(relevance_score, 1.0),
                    confidence=0.7,
                    properties={"inferred_connection": True},
                    evidence_fragments={fragment.fragment_id}
                )
    
    def add_node(self, node_id: str, node_type: NodeType, name: str, 
                 description: str = "", properties: Dict[str, Any] = None,
                 reliability_score: float = 0.5, source_fragments: Set[str] = None) -> bool:
        """Aggiunge un nodo al Knowledge Graph"""
        try:
            if node_id in self.nodes:
                logger.warning(f"Nodo {node_id} già esistente")
                return False
            
            node = KGNode(
                node_id=node_id,
                node_type=node_type,
                name=name,
                description=description,
                properties=properties or {},
                reliability_score=reliability_score,
                source_fragments=source_fragments or set()
            )
            
            self.nodes[node_id] = node
            self.graph.add_node(node_id, **node.to_dict())
            
            # Aggiorna indici
            if node_type == NodeType.CONCEPT:
                self.concept_index[name.lower()].add(node_id)
            elif node_type == NodeType.ENTITY:
                self.entity_index[name.lower()].add(node_id)
            self._update_metrics()
            
            return True
            
        except Exception as e:
            logger.error(f"Errore aggiunta nodo: {str(e)}")
            return False
    
    def add_relation(self, source_node_id: str, target_node_id: str, 
                    relation_type: RelationType, weight: float = 1.0,
                    confidence: float = 0.5, properties: Dict[str, Any] = None,
                    evidence_fragments: Set[str] = None) -> bool:
        """Aggiunge una relazione al Knowledge Graph"""
        try:
            if source_node_id not in self.nodes or target_node_id not in self.nodes:
                logger.warning(f"Nodi non esistenti per relazione: {source_node_id} -> {target_node_id}")
                return False
            
            relation_id = f"{source_node_id}_{relation_type.value}_{target_node_id}_{uuid.uuid4().hex[:8]}"
            
            relation = KGRelation(
                relation_id=relation_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relation_type=relation_type,
                weight=weight,
                confidence=confidence,
                properties=properties or {},
                evidence_fragments=evidence_fragments or set()
            )
            
            self.relations[relation_id] = relation
            self.graph.add_edge(
                source_node_id, 
                target_node_id, 
                key=relation_id,
                **relation.to_dict()
            )
            self._update_metrics()
            
            return True
            
        except Exception as e:
            logger.error(f"Errore aggiunta relazione: {str(e)}")
            return False
    
    def query_related_concepts(self, concept: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Query per trovare concetti correlati"""
        concept_nodes = self.concept_index.get(concept.lower(), set())
        if not concept_nodes:
            return []
        
        related_concepts = []
        
        for node_id in concept_nodes:
            # Usa NetworkX per trovare nodi connessi
            try:
                # Nodi raggiungibili in max_depth passi
                reachable = nx.single_source_shortest_path_length(
                    self.graph, node_id, cutoff=max_depth
                )
                
                for related_id, distance in reachable.items():
                    if (related_id != node_id and 
                        related_id in self.nodes and 
                        self.nodes[related_id].node_type == NodeType.CONCEPT):
                        
                        related_node = self.nodes[related_id]
                        related_concepts.append({
                            'concept': related_node.name,
                            'distance': distance,
                            'reliability': related_node.reliability_score,
                            'description': related_node.description
                        })
                        
            except Exception as e:
                logger.error(f"Errore query concetti correlati: {str(e)}")
        
        # Ordina per rilevanza (distanza bassa, reliability alta)
        related_concepts.sort(key=lambda x: (x['distance'], -x['reliability']))
        return related_concepts[:20]  # Limita risultati
    
    def generate_insight(self, focus_area: str) -> Optional[StrategicInsight]:
        """Genera insight strategico basato su area di focus"""
        try:
            # Cerca nodi correlati all'area di focus
            relevant_nodes = []
            focus_lower = focus_area.lower()
            
            for node_id, node in self.nodes.items():
                if (focus_lower in node.name.lower() or 
                    focus_lower in node.description.lower()):
                    relevant_nodes.append(node)
            
            if len(relevant_nodes) < 2:
                return None
            
            # Analizza pattern nei nodi rilevanti
            high_reliability_nodes = [
                node for node in relevant_nodes 
                if node.reliability_score > 0.7
            ]
            
            if not high_reliability_nodes:
                return None
            
            # Genera insight basato sui pattern trovati
            insight = StrategicInsight(
                insight_id=f"insight_{uuid.uuid4().hex[:8]}",
                title=f"Analisi Strategica: {focus_area.title()}",
                description=self._generate_insight_description(
                    focus_area, high_reliability_nodes
                ),
                insight_type="trend",
                confidence=min(sum(n.reliability_score for n in high_reliability_nodes) / len(high_reliability_nodes), 1.0),
                impact_score=0.7,
                supporting_evidence=[node.node_id for node in high_reliability_nodes],
                related_concepts=[node.name for node in high_reliability_nodes if node.node_type == NodeType.CONCEPT]
            )
            
            self.insights[insight.insight_id] = insight
            return insight
            
        except Exception as e:
            logger.error(f"Errore generazione insight: {str(e)}")
            return None
    
    def _generate_insight_description(self, focus_area: str, nodes: List[KGNode]) -> str:
        """Genera descrizione insight basata sui nodi analizzati"""
        concept_names = [node.name for node in nodes if node.node_type == NodeType.CONCEPT]
        entity_names = [node.name for node in nodes if node.node_type == NodeType.ENTITY]
        
        description = f"Analisi dell'area '{focus_area}' nel contesto RTH. "
        
        if concept_names:
            description += f"Concetti chiave emergenti: {', '.join(concept_names[:3])}. "
        
        if entity_names:
            description += f"Entità rilevanti: {', '.join(entity_names[:3])}. "
        
        description += "Questo insight è stato generato dall'analisi automatica del Knowledge Graph RTH."
        
        return description
    
    def _update_indices(self, fragment: KnowledgeFragment):
        """Aggiorna indici di ricerca"""
        for concept in fragment.concepts:
            self.concept_index[concept.lower()].add(fragment.fragment_id)
        
        for entity in fragment.entities:
            self.entity_index[entity.lower()].add(fragment.fragment_id)
        
        self.source_index[fragment.source_type.value].add(fragment.fragment_id)
    
    def _update_metrics(self):
        """Aggiorna metriche del Knowledge Graph"""
        self.metrics.update({
            "total_nodes": len(self.nodes),
            "total_relations": len(self.relations),
            "total_fragments": len(self.fragments),
            "total_insights": len(self.insights),
            "avg_node_connectivity": (
                sum(dict(self.graph.degree()).values()) / len(self.nodes) 
                if self.nodes else 0
            ),
            "last_update": datetime.now()
        })
    
    def get_rth_structure(self) -> Dict[str, Any]:
        """Restituisce la struttura centrale RTH del Knowledge Graph"""
        try:
            rth_pillars = {}
            rth_frameworks = {}
            rth_methodologies = {}
            
            # Raccoglie nodi per tipo RTH
            for node_id, node in self.nodes.items():
                if node.node_type == NodeType.PILLAR_RTH:
                    rth_pillars[node_id] = {
                        'name': node.name,
                        'description': node.description,
                        'reliability': node.reliability_score,
                        'connections': len([r for r in self.relations.values() 
                                          if r.source_node_id == node_id or r.target_node_id == node_id])
                    }
                elif node.node_type == NodeType.FRAMEWORK:
                    rth_frameworks[node_id] = {
                        'name': node.name,
                        'description': node.description,
                        'reliability': node.reliability_score
                    }
                elif node.node_type == NodeType.METHODOLOGY:
                    rth_methodologies[node_id] = {
                        'name': node.name,
                        'description': node.description,
                        'reliability': node.reliability_score
                    }
            
            return {
                'rth_pillars': rth_pillars,
                'rth_frameworks': rth_frameworks,
                'rth_methodologies': rth_methodologies,
                'total_rth_nodes': len(rth_pillars) + len(rth_frameworks) + len(rth_methodologies),
                'core_structure_health': len(rth_pillars) >= 5,  # Almeno 5 pilastri per una struttura sana
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Errore get_rth_structure: {str(e)}")
            return {
                'rth_pillars': {},
                'rth_frameworks': {},
                'rth_methodologies': {},
                'total_rth_nodes': 0,
                'core_structure_health': False,
                'error': str(e)
            }

    def get_status(self) -> Dict[str, Any]:
        """Restituisce lo stato del Knowledge Graph"""
        node_types_count = defaultdict(int)
        for node in self.nodes.values():
            node_types_count[node.node_type.value] += 1
        
        relation_types_count = defaultdict(int)
        for relation in self.relations.values():
            relation_types_count[relation.relation_type.value] += 1
        
        return {
            'module': 'RTH Knowledge Graph',
            'version': self.version,
            'creator': self.creator,
            'metrics': self.metrics,
            'node_types_distribution': dict(node_types_count),
            'relation_types_distribution': dict(relation_types_count),
            'index_sizes': {
                'concepts': len(self.concept_index),
                'entities': len(self.entity_index),
                'sources': len(self.source_index)
            }
        }

# Istanza globale del Knowledge Graph
_kg_rth_instance: Optional[RTHKnowledgeGraph] = None

def get_knowledge_graph() -> RTHKnowledgeGraph:
    """Restituisce l'istanza globale del Knowledge Graph RTH"""
    global _kg_rth_instance
    if _kg_rth_instance is None:
        _kg_rth_instance = RTHKnowledgeGraph()
    return _kg_rth_instance 
