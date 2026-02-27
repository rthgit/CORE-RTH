"""
RTH Chronicle™ - L'Archivista della Conoscenza Esterna
Sistema di acquisizione, preprocessing e validazione di flussi continui di informazioni
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import aiohttp
import logging
from urllib.parse import urlparse
import hashlib
import re
from bs4 import BeautifulSoup
import feedparser
import json

from .knowledge_graph import KnowledgeFragment, SourceType, ReliabilityScore
from .event_bus import RTHEventBus, EventType

logger = logging.getLogger(__name__)

class SourceCategory(Enum):
    """Categorie di fonti di conoscenza esterna"""
    ACADEMIC = "academic"
    INDUSTRY_REPORT = "industry_report"
    NEWS = "news"
    RESEARCH_BLOG = "research_blog"
    PROFESSIONAL_NETWORK = "professional_network"
    GOVERNMENT_DATA = "government_data"
    EXPERT_CONTENT = "expert_content"

@dataclass
class SourceConfig:
    """Configurazione di una fonte di conoscenza"""
    name: str
    url: str
    category: SourceCategory
    update_frequency: timedelta
    reliability_weight: float = 0.8
    last_crawled: Optional[datetime] = None
    active: bool = True
    extraction_rules: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RawContent:
    """Contenuto grezzo estratto da una fonte"""
    source_url: str
    title: str
    content: str
    extracted_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(
                f"{self.title}{self.content}".encode()
            ).hexdigest()

class RTHChronicle:
    """
    RTH Chronicle™ - Modulo di Acquisizione Conoscenza Esterna
    
    Funzionalità principali:
    - Monitoraggio continuo di fonti esterne autorevoli
    - Estrazione e preprocessing di contenuti
    - Validazione qualità e affidabilità
    - Trasformazione in Knowledge Fragments strutturati
    - Pubblicazione su Event Bus per RTH Cortex™
    """
    
    def __init__(self, event_bus: RTHEventBus):
        self.event_bus = event_bus
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        
        # Registry delle fonti configurate
        self.sources: Dict[str, SourceConfig] = {}
        
        # Cache dei contenuti processati (per evitare duplicati)
        self.processed_content_hashes: Set[str] = set()
        
        # Metriche operative
        self.metrics = {
            "total_sources": 0,
            "active_sources": 0,
            "fragments_generated": 0,
            "last_crawl_cycle": None,
            "crawl_errors": 0
        }
        
        # Inizializza fonti predefinite
        self._initialize_default_sources()
        
        logger.info(f"RTH Chronicle™ v{self.version} inizializzato con {len(self.sources)} fonti")
    
    def _initialize_default_sources(self):
        """Inizializza le fonti di conoscenza predefinite"""
        default_sources = [
            SourceConfig(
                name="Harvard Business Review",
                url="https://hbr.org/feed",
                category=SourceCategory.ACADEMIC,
                update_frequency=timedelta(hours=6),
                reliability_weight=0.95
            ),
            SourceConfig(
                name="MIT Technology Review",
                url="https://www.technologyreview.com/feed/",
                category=SourceCategory.RESEARCH_BLOG,
                update_frequency=timedelta(hours=4),
                reliability_weight=0.90
            ),
            SourceConfig(
                name="McKinsey Insights",
                url="https://www.mckinsey.com/feed/insights",
                category=SourceCategory.INDUSTRY_REPORT,
                update_frequency=timedelta(hours=8),
                reliability_weight=0.92
            ),
            SourceConfig(
                name="World Economic Forum",
                url="https://www.weforum.org/feed/",
                category=SourceCategory.EXPERT_CONTENT,
                update_frequency=timedelta(hours=12),
                reliability_weight=0.88
            )
        ]
        
        for source in default_sources:
            self.sources[source.url] = source
            self.metrics["total_sources"] += 1
            if source.active:
                self.metrics["active_sources"] += 1
    
    async def start_continuous_monitoring(self):
        """Avvia il monitoraggio continuo delle fonti esterne"""
        logger.info("Avvio monitoraggio continuo RTH Chronicle™")
        
        while True:
            try:
                await self._execute_crawl_cycle()
                # Pausa tra i cicli di crawling
                await asyncio.sleep(300)  # 5 minuti
                
            except Exception as e:
                logger.error(f"Errore nel ciclo di crawling: {str(e)}")
                self.metrics["crawl_errors"] += 1
                await asyncio.sleep(60)  # Pausa più breve in caso di errore
    
    async def _execute_crawl_cycle(self):
        """Esegue un ciclo completo di crawling di tutte le fonti attive"""
        self.metrics["last_crawl_cycle"] = datetime.now()
        
        tasks = []
        for source in self.sources.values():
            if source.active and self._should_crawl_source(source):
                tasks.append(self._crawl_source(source))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Errore crawling fonte: {str(result)}")
                    self.metrics["crawl_errors"] += 1
                else:
                    logger.debug(f"Crawling completato per fonte {i}")
    
    def _should_crawl_source(self, source: SourceConfig) -> bool:
        """Determina se una fonte deve essere crawlata in base alla frequenza"""
        if not source.last_crawled:
            return True
        
        time_since_last_crawl = datetime.now() - source.last_crawled
        return time_since_last_crawl >= source.update_frequency
    
    async def _crawl_source(self, source: SourceConfig):
        """Crawla una singola fonte e processa il contenuto"""
        try:
            logger.debug(f"Crawling fonte: {source.name}")
            
            # Estrae contenuto dalla fonte
            raw_contents = await self._extract_content_from_source(source)
            
            # Processa ogni contenuto estratto
            for raw_content in raw_contents:
                if raw_content.content_hash not in self.processed_content_hashes:
                    knowledge_fragment = await self._process_raw_content(
                        raw_content, source
                    )
                    
                    if knowledge_fragment:
                        # Pubblica su Event Bus per RTH Cortex™
                        await self._publish_knowledge_fragment(knowledge_fragment)
                        
                        # Marca come processato
                        self.processed_content_hashes.add(raw_content.content_hash)
                        self.metrics["fragments_generated"] += 1
            
            # Aggiorna timestamp ultimo crawling
            source.last_crawled = datetime.now()
            
        except Exception as e:
            logger.error(f"Errore crawling {source.name}: {str(e)}")
            raise
    
    async def _extract_content_from_source(self, source: SourceConfig) -> List[RawContent]:
        """Estrae contenuto da una fonte specifica"""
        contents = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(source.url, timeout=30) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        
                        if 'xml' in content_type or source.url.endswith('.xml'):
                            # Feed RSS/Atom
                            contents = await self._parse_feed(source, await response.text())
                        else:
                            # Pagina web
                            contents = await self._parse_webpage(source, await response.text())
                    else:
                        logger.warning(f"Risposta HTTP {response.status} per {source.url}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout per fonte {source.name}")
        except Exception as e:
            logger.error(f"Errore estrazione da {source.name}: {str(e)}")
        
        return contents
    
    async def _parse_feed(self, source: SourceConfig, feed_content: str) -> List[RawContent]:
        """Parsa un feed RSS/Atom"""
        contents = []
        
        try:
            feed = feedparser.parse(feed_content)
            
            for entry in feed.entries[:10]:  # Limita a 10 articoli più recenti
                content = RawContent(
                    source_url=source.url,
                    title=entry.get('title', ''),
                    content=entry.get('description', '') or entry.get('summary', ''),
                    extracted_at=datetime.now(),
                    metadata={
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'author': entry.get('author', ''),
                        'category': source.category.value
                    }
                )
                contents.append(content)
        
        except Exception as e:
            logger.error(f"Errore parsing feed {source.name}: {str(e)}")
        
        return contents
    
    async def _parse_webpage(self, source: SourceConfig, html_content: str) -> List[RawContent]:
        """Parsa una pagina web per estrarre contenuto"""
        contents = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Estrae titolo principale
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Estrae contenuto principale (semplificato)
            content_text = ""
            
            # Cerca in ordine di priorità
            main_content = (
                soup.find('main') or 
                soup.find('article') or 
                soup.find('div', class_=re.compile(r'content|article|post'))
            )
            
            if main_content:
                # Rimuove script e style
                for script in main_content(['script', 'style']):
                    script.decompose()
                
                content_text = main_content.get_text().strip()
            
            if title and content_text and len(content_text) > 200:
                content = RawContent(
                    source_url=source.url,
                    title=title,
                    content=content_text[:5000],  # Limita lunghezza
                    extracted_at=datetime.now(),
                    metadata={
                        'category': source.category.value,
                        'extraction_method': 'webpage'
                    }
                )
                contents.append(content)
        
        except Exception as e:
            logger.error(f"Errore parsing webpage {source.name}: {str(e)}")
        
        return contents
    
    async def _process_raw_content(self, raw_content: RawContent, source: SourceConfig) -> Optional[KnowledgeFragment]:
        """Processa contenuto grezzo in Knowledge Fragment strutturato"""
        try:
            # Calcola affidabilità basata su fonte e contenuto
            reliability_score = self._calculate_reliability_score(raw_content, source)
            
            # Estrae entità e concetti principali (semplificato)
            entities = self._extract_entities(raw_content.content)
            concepts = self._extract_concepts(raw_content.content)
            
            # Crea Knowledge Fragment
            fragment = KnowledgeFragment(
                fragment_id=raw_content.content_hash,
                title=raw_content.title,
                content=raw_content.content,
                source_type=self._map_category_to_source_type(source.category),
                source_url=raw_content.source_url,
                reliability_score=reliability_score,
                entities=entities,
                concepts=concepts,
                metadata={
                    **raw_content.metadata,
                    'source_name': source.name,
                    'processed_by': 'RTH Chronicle™',
                    'chronicle_version': self.version
                },
                created_at=raw_content.extracted_at,
                processed_at=datetime.now()
            )
            
            return fragment
        
        except Exception as e:
            logger.error(f"Errore processing contenuto: {str(e)}")
            return None
    
    def _calculate_reliability_score(self, content: RawContent, source: SourceConfig) -> ReliabilityScore:
        """Calcola un punteggio di affidabilità per il contenuto"""
        base_score = source.reliability_weight
        
        # Fattori di aggiustamento basati sul contenuto
        content_length_factor = min(len(content.content) / 1000, 1.0)
        
        # Presenza di parole chiave rilevanti per RTH
        rth_keywords = [
            'leadership', 'talent', 'performance', 'development', 
            'strategy', 'innovation', 'management', 'skills',
            'competencies', 'transformation', 'excellence'
        ]
        
        keyword_score = sum(
            1 for keyword in rth_keywords 
            if keyword.lower() in content.content.lower()
        ) / len(rth_keywords)
        
        # Calcola score finale
        final_score = (base_score * 0.6) + (content_length_factor * 0.2) + (keyword_score * 0.2)
        
        if final_score >= 0.8:
            return ReliabilityScore.HIGH
        elif final_score >= 0.6:
            return ReliabilityScore.MEDIUM
        else:
            return ReliabilityScore.LOW
    
    def _extract_entities(self, content: str) -> List[str]:
        """Estrae entità dal contenuto (implementazione semplificata)"""
        # Placeholder per NER più sofisticato
        entities = []
        
        # Pattern per nomi propri (semplificato)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        
        # Filtra e deduplica
        entities = list(set([
            entity for entity in capitalized_words 
            if len(entity) > 2 and len(entity.split()) <= 3
        ]))[:10]  # Limita a 10 entità
        
        return entities
    
    def _extract_concepts(self, content: str) -> List[str]:
        """Estrae concetti principali dal contenuto"""
        # NOTE:
        # We need "canonical" short concepts that align with KG pillars (innovazione/strategia/sviluppo/...)
        # otherwise Cortex->KG insight generation rarely triggers (because focus strings are too specific).

        # Phrase-level concepts (legacy, still useful for specificity).
        rth_phrases = [
            "leadership development",
            "talent management",
            "performance optimization",
            "strategic planning",
            "innovation management",
            "organizational culture",
            "competency framework",
            "succession planning",
            "employee engagement",
            "digital transformation",
            "change management",
            "executive coaching",
        ]

        # Canonical pillar-aligned concepts (Italian labels used by KG core structure).
        rth_canonical = [
            ("leadership", ["leadership", "leader", "leading"]),
            ("performance", ["performance", "excellence", "result", "results", "outcome", "achievement"]),
            ("innovazione", ["innovazione", "innovation", "innovative", "creativ", "disrupt", "breakthrough", "novel"]),
            ("strategia", ["strategia", "strategy", "strategic", "planning", "vision", "goal"]),
            ("sviluppo", ["sviluppo", "development", "growth", "learning", "skill", "skills", "competenc", "training"]),
        ]

        content_lower = (content or "").lower()
        found: List[str] = []

        for phrase in rth_phrases:
            if phrase in content_lower:
                found.append(phrase)

        for canonical, keys in rth_canonical:
            if any(k in content_lower for k in keys):
                found.append(canonical)

        # Stable dedupe while preserving order.
        seen = set()
        out: List[str] = []
        for c in found:
            c = str(c or "").strip()
            if not c or c in seen:
                continue
            seen.add(c)
            out.append(c)

        return out[:8]
    
    def _map_category_to_source_type(self, category: SourceCategory) -> SourceType:
        """Mappa categoria fonte a tipo sorgente per Knowledge Graph"""
        mapping = {
            SourceCategory.ACADEMIC: SourceType.ACADEMIC,
            SourceCategory.INDUSTRY_REPORT: SourceType.RESEARCH,
            SourceCategory.NEWS: SourceType.NEWS,
            SourceCategory.RESEARCH_BLOG: SourceType.BLOG,
            SourceCategory.PROFESSIONAL_NETWORK: SourceType.SOCIAL,
            SourceCategory.GOVERNMENT_DATA: SourceType.ACADEMIC,
            SourceCategory.EXPERT_CONTENT: SourceType.EXPERT
        }
        return mapping.get(category, SourceType.WEB)
    
    async def _publish_knowledge_fragment(self, fragment: KnowledgeFragment):
        """Pubblica Knowledge Fragment su Event Bus per RTH Cortex™"""
        try:
            event_data = {
                'fragment': fragment.to_dict(),
                'source_module': 'RTH Chronicle™',
                'timestamp': datetime.now().isoformat(),
                'reliability_score': fragment.reliability_score.value
            }
            
            await self.event_bus.publish(
                EventType.KNOWLEDGE_FRAGMENT_CREATED,
                event_data
            )
            
            logger.debug(f"Knowledge Fragment pubblicato: {fragment.fragment_id}")
        
        except Exception as e:
            logger.error(f"Errore pubblicazione fragment: {str(e)}")
    
    def add_source(self, source_config: SourceConfig) -> bool:
        """Aggiunge una nuova fonte di conoscenza"""
        try:
            self.sources[source_config.url] = source_config
            self.metrics["total_sources"] += 1
            if source_config.active:
                self.metrics["active_sources"] += 1
            
            logger.info(f"Nuova fonte aggiunta: {source_config.name}")
            return True
        
        except Exception as e:
            logger.error(f"Errore aggiunta fonte: {str(e)}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Restituisce lo stato del sistema Chronicle"""
        return {
            'module': 'RTH Chronicle™',
            'version': self.version,
            'creator': self.creator,
            'metrics': self.metrics,
            'active_sources': [
                {
                    'name': source.name,
                    'category': source.category.value,
                    'last_crawled': source.last_crawled.isoformat() if source.last_crawled else None,
                    'reliability_weight': source.reliability_weight
                }
                for source in self.sources.values() if source.active
            ],
            'processed_hashes_count': len(self.processed_content_hashes)
        }

# Istanza globale (singleton pattern)
chronicle_instance: Optional[RTHChronicle] = None

def get_chronicle() -> RTHChronicle:
    """Restituisce l'istanza globale di RTH Chronicle™"""
    global chronicle_instance
    if chronicle_instance is None:
        from .event_bus import get_event_bus
        chronicle_instance = RTHChronicle(get_event_bus())
    return chronicle_instance 
