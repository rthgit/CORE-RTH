"""
RTH Praxis™ - L'Adattatore del Framework Operativo
Modulo per l'evoluzione del framework RTH e la gestione dei Super Prompt
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from .event_bus import RTHEventBus, EventType, RTHEvent
from .knowledge_graph import get_knowledge_graph, StrategicInsight

logger = logging.getLogger(__name__)

class PraxisProposalType(Enum):
    FRAMEWORK_EVOLUTION = "framework_evolution"
    PROMPT_REFINEMENT = "prompt_refinement"
    CONTENT_UPDATE = "content_update"

@dataclass
class FrameworkEvolutionProposal:
    proposal_id: str
    title: str
    description: str
    insights: List[str]
    feedback_summary: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    approved_by_guardian: bool = False

@dataclass
class PromptRefinementRequest:
    request_id: str
    prompt_name: str
    current_prompt: str
    suggested_change: str
    rationale: str
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    approved_by_guardian: bool = False

class RTHPraxis:
    """
    RTH Praxis™ - Modulo di Adattamento e Evoluzione del Framework
    - Riceve insight da Cortex e feedback da FeedbackLoop
    - Formula proposte di evoluzione del framework
    - Gestisce l'affinamento dei Super Prompt
    - Coordina aggiornamenti documentazione e metodologie
    """
    def __init__(self, event_bus: RTHEventBus):
        self.event_bus = event_bus
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        self.framework_proposals: Dict[str, FrameworkEvolutionProposal] = {}
        self.prompt_requests: Dict[str, PromptRefinementRequest] = {}
        self.metrics = {
            "proposals_created": 0,
            "proposals_approved": 0,
            "prompt_refinements": 0,
            "last_update": None
        }
        self._subscribe_to_events()
        logger.info(f"RTH Praxis™ v{self.version} inizializzato")

    def _subscribe_to_events(self):
        event_types = {
            EventType.INSIGHT_GENERATED,
            EventType.FEEDBACK_ANALYSIS_COMPLETED
        }
        self.event_bus.subscribe(
            module_name="RTH Praxis™",
            event_types=event_types,
            callback=self._handle_event
        )

    async def _handle_event(self, event: RTHEvent):
        try:
            if event.event_type == EventType.INSIGHT_GENERATED:
                await self._process_insight(event)
            elif event.event_type == EventType.FEEDBACK_ANALYSIS_COMPLETED:
                await self._process_feedback(event)
        except Exception as e:
            logger.error(f"Errore processing evento in Praxis: {str(e)}")

    async def _process_insight(self, event: RTHEvent):
        insight_data = event.data.get('insight')
        if not insight_data:
            return
        insight_id = insight_data.get('insight_id')
        title = insight_data.get('title', 'Proposta Evolutiva')
        description = insight_data.get('description', '')
        proposal = FrameworkEvolutionProposal(
            proposal_id=f"proposal_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            insights=[insight_id] if insight_id else [],
            status="pending"
        )
        self.framework_proposals[proposal.proposal_id] = proposal
        self.metrics["proposals_created"] += 1
        self.metrics["last_update"] = datetime.now()
        logger.info(f"Nuova proposta di evoluzione framework: {proposal.title}")
        # Pubblica evento di proposta
        await self.event_bus.publish(
            EventType.FRAMEWORK_EVOLUTION_PROPOSED,
            {
                'proposal_id': proposal.proposal_id,
                'title': proposal.title,
                'description': proposal.description,
                'insights': proposal.insights
            },
            source_module="RTH Praxis™"
        )

    async def _process_feedback(self, event: RTHEvent):
        feedback_data = event.data
        summary = feedback_data.get('summary', '')
        # Crea una richiesta di raffinamento prompt se necessario
        if 'prompt' in feedback_data:
            prompt_info = feedback_data['prompt']
            request = PromptRefinementRequest(
                request_id=f"prompt_{uuid.uuid4().hex[:8]}",
                prompt_name=prompt_info.get('name', 'Super Prompt'),
                current_prompt=prompt_info.get('current', ''),
                suggested_change=prompt_info.get('suggested', ''),
                rationale=summary,
                status="pending"
            )
            self.prompt_requests[request.request_id] = request
            self.metrics["prompt_refinements"] += 1
            self.metrics["last_update"] = datetime.now()
            logger.info(f"Nuova richiesta di raffinamento prompt: {request.prompt_name}")
            # Pubblica evento di richiesta
            await self.event_bus.publish(
                EventType.PROMPT_REFINEMENT_REQUESTED,
                {
                    'request_id': request.request_id,
                    'prompt_name': request.prompt_name,
                    'suggested_change': request.suggested_change,
                    'rationale': request.rationale
                },
                source_module="RTH Praxis™"
            )

    def approve_proposal(self, proposal_id: str):
        proposal = self.framework_proposals.get(proposal_id)
        if proposal:
            proposal.status = "approved"
            proposal.approved_by_guardian = True
            self.metrics["proposals_approved"] += 1
            logger.info(f"Proposta approvata: {proposal.title}")

    def get_status(self) -> Dict[str, Any]:
        return {
            'module': 'RTH Praxis™',
            'version': self.version,
            'creator': self.creator,
            'metrics': self.metrics,
            'proposals': list(self.framework_proposals.values()),
            'prompt_requests': list(self.prompt_requests.values()),
            'framework_updates': len([p for p in self.framework_proposals.values() 
                                    if p.status == "approved"])
        }

# Istanza globale (singleton pattern)
praxis_instance: Optional[RTHPraxis] = None

def get_praxis() -> RTHPraxis:
    global praxis_instance
    if praxis_instance is None:
        from .event_bus import get_event_bus
        praxis_instance = RTHPraxis(get_event_bus())
    return praxis_instance 