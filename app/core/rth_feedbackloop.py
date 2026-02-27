"""
RTH FeedbackLoop™ - Il Sensore di Qualità e Impatto
Modulo per la raccolta, analisi e sintesi del feedback su strumenti e servizi RTH
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from .event_bus import RTHEventBus, EventType, RTHEvent

logger = logging.getLogger(__name__)

class FeedbackSource(Enum):
    USER = "user"
    CONSULTANT = "consultant"
    SYSTEM = "system"

@dataclass
class FeedbackEntry:
    feedback_id: str
    source: FeedbackSource
    content: str
    sentiment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class FeedbackSummary:
    summary_id: str
    main_themes: List[Dict[str, Any]]
    sentiment_overall: str
    actionable_insights: List[str]
    created_at: datetime = field(default_factory=datetime.now)

class RTHFeedbackLoop:
    """
    RTH FeedbackLoop™ - Modulo di raccolta e analisi feedback
    - Raccoglie feedback strutturato e non strutturato da utenti e consulenti
    - Analizza temi, sentiment e aree di miglioramento
    - Pubblica riassunti e insight su Event Bus per Cortex e Praxis
    """
    def __init__(self, event_bus: RTHEventBus):
        self.event_bus = event_bus
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        self.feedback_entries: Dict[str, FeedbackEntry] = {}
        self.summaries: Dict[str, FeedbackSummary] = {}
        self.metrics = {
            "feedback_received": 0,
            "summaries_generated": 0,
            "last_update": None
        }
        logger.info(f"RTH FeedbackLoop™ v{self.version} inizializzato")

    def receive_feedback(self, content: str, source: FeedbackSource, sentiment: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        entry = FeedbackEntry(
            feedback_id=f"feedback_{uuid.uuid4().hex[:8]}",
            source=source,
            content=content,
            sentiment=sentiment,
            metadata=metadata or {}
        )
        self.feedback_entries[entry.feedback_id] = entry
        self.metrics["feedback_received"] += 1
        self.metrics["last_update"] = datetime.now()
        logger.info(f"Feedback ricevuto da {source.value}")
        return entry.feedback_id

    async def analyze_feedback(self):
        """Analizza il feedback raccolto, identifica temi e sentiment, pubblica riassunto"""
        if not self.feedback_entries:
            return None
        # Analisi semplificata: raggruppa per sentiment e cerca parole chiave
        theme_counter = {}
        sentiment_counter = {}
        for entry in self.feedback_entries.values():
            sentiment = entry.sentiment or "neutral"
            sentiment_counter[sentiment] = sentiment_counter.get(sentiment, 0) + 1
            # Estrazione temi (semplificata)
            for keyword in ["usabilità", "velocità", "precisione", "chiarezza", "supporto", "innovazione", "esperienza"]:
                if keyword in entry.content.lower():
                    theme_counter[keyword] = theme_counter.get(keyword, 0) + 1
        main_themes = [
            {"name": k, "frequency": v, "sentiment": max(sentiment_counter, key=sentiment_counter.get)}
            for k, v in theme_counter.items()
        ]
        sentiment_overall = max(sentiment_counter, key=sentiment_counter.get)
        actionable_insights = [f"Migliorare {t['name']}" for t in main_themes if t["frequency"] > 1]
        summary = FeedbackSummary(
            summary_id=f"summary_{uuid.uuid4().hex[:8]}",
            main_themes=main_themes,
            sentiment_overall=sentiment_overall,
            actionable_insights=actionable_insights
        )
        self.summaries[summary.summary_id] = summary
        self.metrics["summaries_generated"] += 1
        self.metrics["last_update"] = datetime.now()
        logger.info(f"Feedback summary generato: {summary.summary_id}")
        # Pubblica evento di analisi completata
        await self.event_bus.publish(
            EventType.FEEDBACK_ANALYSIS_COMPLETED,
            {
                'summary_id': summary.summary_id,
                'themes': main_themes,
                'sentiment_overall': sentiment_overall,
                'actionable_insights': actionable_insights,
                'summary': '\n'.join(actionable_insights)
            },
            source_module="RTH FeedbackLoop™"
        )
        return summary.summary_id

    def get_status(self) -> Dict[str, Any]:
        return {
            'module': 'RTH FeedbackLoop™',
            'version': self.version,
            'creator': self.creator,
            'metrics': self.metrics,
            'feedback_entries': len(self.feedback_entries),
            'summaries': len(self.summaries)
        }

# Istanza globale (singleton pattern)
feedbackloop_instance: Optional[RTHFeedbackLoop] = None

def get_feedbackloop() -> RTHFeedbackLoop:
    global feedbackloop_instance
    if feedbackloop_instance is None:
        from .event_bus import get_event_bus
        feedbackloop_instance = RTHFeedbackLoop(get_event_bus())
    return feedbackloop_instance 