"""
RTH Event Bus - Sistema di Comunicazione Asincrona tra Moduli RTH Synapse™
Gestisce la pubblicazione e sottoscrizione di eventi tra Chronicle, Cortex, Praxis e FeedbackLoop
"""

from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import logging
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Tipi di eventi nel sistema RTH Synapse™"""
    # Eventi da RTH Chronicle™
    KNOWLEDGE_FRAGMENT_CREATED = "knowledge_fragment_created"
    SOURCE_CRAWL_COMPLETED = "source_crawl_completed"
    SOURCE_ERROR = "source_error"
    
    # Eventi da RTH Cortex™
    INSIGHT_GENERATED = "insight_generated"
    KNOWLEDGE_GRAPH_UPDATED = "knowledge_graph_updated"
    BIAS_DETECTED = "bias_detected"
    CONFLICT_IDENTIFIED = "conflict_identified"
    
    # Eventi da RTH Praxis™
    FRAMEWORK_EVOLUTION_PROPOSED = "framework_evolution_proposed"
    PROMPT_REFINEMENT_REQUESTED = "prompt_refinement_requested"
    DOCUMENTATION_UPDATED = "documentation_updated"
    
    # Eventi da RTH FeedbackLoop™
    FEEDBACK_RECEIVED = "feedback_received"
    FEEDBACK_ANALYSIS_COMPLETED = "feedback_analysis_completed"
    SENTIMENT_TREND_DETECTED = "sentiment_trend_detected"
    
    # Eventi da RTH Guardian™
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    VALIDATION_COMPLETED = "validation_completed"
    SYSTEM_ALERT = "system_alert"
    
    # Eventi di sistema
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    MODULE_STATUS_CHANGED = "module_status_changed"

@dataclass
class RTHEvent:
    """Rappresenta un evento nel sistema RTH Synapse™"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SYSTEM_STARTUP
    source_module: str = ""
    target_modules: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1=alta, 10=bassa
    correlation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte l'evento in dizionario per serializzazione"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'source_module': self.source_module,
            'target_modules': self.target_modules,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'correlation_id': self.correlation_id,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }

class EventHandler:
    """Handler per la gestione di eventi specifici"""
    
    def __init__(self, callback: Callable, event_types: Set[EventType], module_name: str):
        self.callback = callback
        self.event_types = event_types
        self.module_name = module_name
        self.created_at = datetime.now()
        self.events_processed = 0
        self.last_error = None
        self.active = True
    
    async def handle_event(self, event: RTHEvent) -> bool:
        """Gestisce un evento e restituisce True se processato con successo"""
        if not self.active or event.event_type not in self.event_types:
            return False
        
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                # Esegue callback sincroni in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.callback, event)
            
            self.events_processed += 1
            self.last_error = None
            return True
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Errore handler {self.module_name}: {str(e)}")
            return False

class RTHEventBus:
    """Event Bus centrale per la comunicazione tra moduli RTH Synapse™"""
    
    def __init__(self):
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        
        # Registry degli handler
        self.handlers: Dict[str, EventHandler] = {}
        
        # Code di eventi per moduli temporaneamente offline
        self.event_buffers: Dict[str, List[RTHEvent]] = {}
        
        # Metriche operative
        self.metrics = {
            "events_published": 0,
            "events_delivered": 0,
            "events_failed": 0,
            "active_handlers": 0,
            "buffer_size": 0,
            "start_time": datetime.now()
        }
        
        # Thread pool per gestione eventi
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Flag di sistema
        self.running = False
        
        logger.info(f"RTH Event Bus v{self.version} inizializzato")
    
    async def start(self):
        """Avvia il sistema Event Bus"""
        if self.running:
            return
        
        self.running = True
        
        # Avvia task di background
        asyncio.create_task(self._process_buffered_events())
        
        logger.info("RTH Event Bus avviato")
    
    async def stop(self):
        """Ferma il sistema Event Bus"""
        if not self.running:
            return
        
        self.running = False
        self.executor.shutdown(wait=True)
        
        logger.info("RTH Event Bus fermato")
    
    def subscribe(self, module_name: str, event_types: Set[EventType], 
                  callback: Callable) -> str:
        """Sottoscrive un modulo a specifici tipi di eventi"""
        handler_id = f"{module_name}_{uuid.uuid4().hex[:8]}"
        
        handler = EventHandler(callback, event_types, module_name)
        self.handlers[handler_id] = handler
        
        # Inizializza buffer se necessario
        if module_name not in self.event_buffers:
            self.event_buffers[module_name] = []
        
        self.metrics["active_handlers"] = len(self.handlers)
        
        logger.info(f"Modulo {module_name} sottoscritto a {len(event_types)} tipi di eventi")
        return handler_id
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], 
                     source_module: str = "System", target_modules: List[str] = None,
                     priority: int = 5, correlation_id: str = None) -> str:
        """Pubblica un evento sul bus"""
        event = RTHEvent(
            event_type=event_type,
            source_module=source_module,
            target_modules=target_modules or [],
            data=data,
            priority=priority,
            correlation_id=correlation_id
        )
        
        self.metrics["events_published"] += 1
        
        # Invia l'evento agli handler appropriati
        await self._route_event(event)
        
        logger.debug(f"Evento {event_type.value} pubblicato da {source_module}")
        return event.event_id
    
    async def _route_event(self, event: RTHEvent):
        """Instrada un evento agli handler appropriati"""
        matching_handlers = []
        
        for handler_id, handler in self.handlers.items():
            if not handler.active:
                continue
            
            if event.event_type in handler.event_types:
                if event.target_modules and handler.module_name not in event.target_modules:
                    continue
                
                matching_handlers.append((handler_id, handler))
        
        if not matching_handlers:
            return
        
        # Invia evento a tutti gli handler
        for handler_id, handler in matching_handlers:
            try:
                success = await handler.handle_event(event)
                if success:
                    self.metrics["events_delivered"] += 1
                else:
                    self.metrics["events_failed"] += 1
            except Exception as e:
                logger.error(f"Errore consegna evento: {str(e)}")
                self.metrics["events_failed"] += 1
    
    async def _process_buffered_events(self):
        """Task di background per processare eventi bufferizzati"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Controlla ogni 30 secondi
            except Exception as e:
                logger.error(f"Errore processing eventi bufferizzati: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Restituisce lo stato del sistema Event Bus"""
        uptime = datetime.now() - self.metrics["start_time"]
        
        return {
            'module': 'RTH Event Bus',
            'version': self.version,
            'creator': self.creator,
            'running': self.running,
            'subscriptions_count': len(self.handlers),
            'uptime_seconds': uptime.total_seconds(),
            'metrics': self.metrics
        }

# Istanza globale del Event Bus
_event_bus_instance: Optional[RTHEventBus] = None

def get_event_bus() -> RTHEventBus:
    """Restituisce l'istanza globale del Event Bus"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = RTHEventBus()
    return _event_bus_instance

async def initialize_event_bus():
    """Inizializza il Event Bus globale"""
    bus = get_event_bus()
    if not bus.running:
        await bus.start()
    return bus 