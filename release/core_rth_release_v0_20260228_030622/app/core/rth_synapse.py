"""
RTH Synapseâ„¢ - Sistema di Controllo e Validazione
Garantisce che gli edit e le modifiche siano collegati solo al codice primario RTH
Include il sistema di analisi unificata per tutti i questionari RTH
"""

from typing import Dict, List, Any, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import hashlib
import json
import re

logger = logging.getLogger(__name__)

class RTHModuleType(Enum):
    """Tipi di moduli RTH autorizzati"""
    CHRONICLE = "chronicle"            # Sensori: conoscenza esterna
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Memoria viva
    CORTEX = "cortex"                  # Sintesi e giudizio
    PRAXIS = "praxis"                  # Evoluzione framework
    FEEDBACK_LOOP = "feedback_loop"    # Apprendimento
    SYNAPSE = "synapse"                # Governance e coerenza
    GUARDIAN = "guardian"              # Supervisione umana
    METAMORPH = "metamorph"            # Custode del codice vivente
    JARVIS = "jarvis"                # Assistente centrale

class QuestionnaireType(Enum):
    """Tipi di questionari RTH supportati dal sistema unificato"""
    TALENTOSCOPIO = "talentoscopio"
    LEADEROSCOPIO = "leaderoscopio" 
    CULTURASCOPIO = "culturascopio"
    PURPOSEOSCOPIO = "purposeoscopio"
    AZIENDOSCOPIO = "aziendoscopio"
    STUDENTOSCOPIO = "studentoscopio"
    TEAMOSCOPIO = "teamoscopio"
    INNOVASCOPIO = "innovascopio"

class RTHUnifiedAnswer(BaseModel):
    """Risposta processata dal sistema unificato RTH"""
    question_id: str
    raw_answer: str
    processed_answer: str
    semantic_weight: float
    emotional_intensity: float
    talent_indicators: List[str]
    hidden_patterns: List[str]
    confidence_score: float
    questionnaire_type: str

class RTHTalentInsight(BaseModel):
    """Insight sui talenti estratto dal sistema unificato"""
    category: str
    insight_text: str
    confidence: float
    supporting_evidence: List[str]
    talent_correlation: float
    growth_potential: float
    questionnaire_source: str

class RTHUnifiedAnalysis(BaseModel):
    """Analisi completa del sistema unificato RTH"""
    questionnaire_type: str
    submission_id: str
    user_profile: Dict[str, Any]
    processed_answers: List[RTHUnifiedAnswer]
    core_insights: List[RTHTalentInsight]
    talent_matrix: Dict[str, float]
    hidden_talents: List[str]
    growth_vectors: List[str]
    narrative_synthesis: str
    confidence_score: float
    analysis_timestamp: datetime

class RTHCodeSignature(BaseModel):
    """Firma crittografica per il codice RTH autentico"""
    file_path: str
    content_hash: str
    module_type: RTHModuleType
    creator_signature: str = "Core Rth Team - RTH CORE Engine"
    timestamp: datetime = Field(default_factory=datetime.now)
    validated: bool = False

class RTHEditRequest(BaseModel):
    """Richiesta di modifica al codice RTH"""
    file_path: str
    edit_type: str  # "create", "update", "delete"
    content: str
    justification: str
    requested_by: str
    target_module: RTHModuleType
    
class RTHSynapseGuardian:
    """
    RTH Synapseâ„¢ Guardian - Sistema di Controllo Centrale
    Garantisce che solo modifiche collegate al codice primario RTH siano autorizzate
    Include il sistema di analisi unificata per tutti i questionari RTH
    """
    
    def __init__(self):
        self.version = "1.0.0"
        self.creator = "Core Rth Team"
        self.authorized_signatures: Dict[str, RTHCodeSignature] = {}
        self.rth_core_files: Set[str] = set()
        
        # Sistema di analisi unificata
        self.talent_patterns = self._load_talent_patterns()
        self.semantic_filters = self._initialize_semantic_filters()
        self.unified_analysis_cache: Dict[str, RTHUnifiedAnalysis] = {}
        
        self._initialize_core_registry()
        logger.info(f"RTH Synapseâ„¢ Guardian v{self.version} inizializzato")
        logger.info("Sistema di analisi unificata RTH attivato per tutti i questionari")
    
    def _load_talent_patterns(self) -> Dict[str, List[str]]:
        """Carica i pattern di riconoscimento talenti per tutti i questionari"""
        return {
            "leadership": [
                "leader", "guidare", "coordinare", "dirigere", "organizzare", "responsabilitÃ ",
                "decisioni", "team", "gruppo", "motivare", "ispirare", "visione"
            ],
            "creativitÃ ": [
                "creativo", "innovativo", "originale", "immaginazione", "arte", "design",
                "inventare", "sperimentare", "nuovo", "diverso", "unico", "fantasia"
            ],
            "analisi": [
                "analizzare", "logico", "ragionamento", "problema", "soluzione", "critico",
                "dati", "ricerca", "studiare", "approfondire", "dettaglio", "precisione"
            ],
            "comunicazione": [
                "comunicare", "parlare", "scrivere", "esprimere", "presentare", "convincere",
                "ascoltare", "dialogo", "relazione", "sociale", "empatia", "comprensione"
            ],
            "esecuzione": [
                "fare", "realizzare", "completare", "finire", "risultati", "obiettivi",
                "efficienza", "produttivitÃ ", "organizzazione", "pianificazione", "metodo"
            ],
            "apprendimento": [
                "imparare", "studiare", "curiositÃ ", "conoscenza", "crescita", "sviluppo",
                "migliorare", "competenze", "abilitÃ ", "formazione", "esperienza"
            ],
            "relazioni": [
                "persone", "relazioni", "collaborare", "aiutare", "supportare", "condividere",
                "fiducia", "rispetto", "comprensione", "empatia", "ascolto", "sociale"
            ],
            "strategia": [
                "strategia", "pianificare", "futuro", "obiettivi", "visione", "lungo termine",
                "anticipare", "prevedere", "scenario", "opportunitÃ ", "rischi", "decisioni"
            ]
        }
    
    def _initialize_semantic_filters(self) -> Dict[str, Any]:
        """Inizializza i filtri semantici per l'analisi del testo"""
        return {
            "emotional_keywords": {
                "positive": ["amo", "adoro", "mi piace", "entusiasmo", "passione", "felice", "soddisfatto"],
                "negative": ["odio", "detesto", "difficile", "faticoso", "stressante", "noioso"],
                "neutral": ["penso", "credo", "ritengo", "secondo me", "probabilmente"]
            },
            "intensity_modifiers": {
                "high": ["molto", "estremamente", "incredibilmente", "assolutamente", "completamente"],
                "medium": ["abbastanza", "piuttosto", "discretamente", "moderatamente"],
                "low": ["poco", "leggermente", "appena", "raramente"]
            },
            "talent_indicators": {
                "natural_ability": ["naturale", "istintivo", "spontaneo", "facile", "viene da sÃ©"],
                "learned_skill": ["ho imparato", "ho studiato", "mi sono allenato", "ho sviluppato"],
                "passion": ["passione", "amore", "entusiasmo", "mi appassiona", "mi coinvolge"]
            }
        }
    
    async def analyze_questionnaire_unified(
        self,
        questionnaire_type: QuestionnaireType,
        answers: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        submission_id: str
    ) -> RTHUnifiedAnalysis:
        """
        Sistema di analisi unificata per tutti i questionari RTH
        Filtra e analizza le risposte per identificare i veri talenti nascenti
        """
        logger.info(f"[RTH SYNAPSE] Avvio analisi unificata per {questionnaire_type.value}")
        
        try:
            # 1. Processamento delle risposte
            processed_answers = await self._process_answers_unified(answers, questionnaire_type)
            
            # 2. Estrazione insights sui talenti
            core_insights = await self._extract_talent_insights(processed_answers, questionnaire_type)
            
            # 3. Costruzione matrice talenti
            talent_matrix = await self._build_talent_matrix(processed_answers, core_insights, questionnaire_type)
            
            # 4. Identificazione talenti nascosti
            hidden_talents = await self._identify_hidden_talents(processed_answers, questionnaire_type)
            
            # 5. Calcolo vettori di crescita
            growth_vectors = await self._calculate_growth_vectors(talent_matrix, core_insights)
            
            # 6. Sintesi narrativa
            narrative_synthesis = await self._generate_narrative_synthesis(
                processed_answers, core_insights, talent_matrix, questionnaire_type, user_profile
            )
            
            # 7. Calcolo confidence score
            confidence_score = self._calculate_confidence_score(processed_answers, core_insights)
            
            # Crea analisi unificata
            unified_analysis = RTHUnifiedAnalysis(
                questionnaire_type=questionnaire_type.value,
                submission_id=submission_id,
                user_profile=user_profile,
                processed_answers=processed_answers,
                core_insights=core_insights,
                talent_matrix=talent_matrix,
                hidden_talents=hidden_talents,
                growth_vectors=growth_vectors,
                narrative_synthesis=narrative_synthesis,
                confidence_score=confidence_score,
                analysis_timestamp=datetime.now()
            )
            
            # Cache dell'analisi
            self.unified_analysis_cache[submission_id] = unified_analysis
            
            logger.info(f"[RTH SYNAPSE] âœ… Analisi unificata completata per {questionnaire_type.value}")
            logger.info(f"[RTH SYNAPSE] ðŸŽ¯ Confidence Score: {confidence_score:.1f}%")
            logger.info(f"[RTH SYNAPSE] ðŸ’Ž Talenti identificati: {len(talent_matrix)}")
            logger.info(f"[RTH SYNAPSE] ðŸ” Talenti nascosti: {len(hidden_talents)}")
            
            return unified_analysis
            
        except Exception as e:
            logger.error(f"[RTH SYNAPSE] âŒ Errore nell'analisi unificata: {str(e)}")
            raise
    
    async def _process_answers_unified(
        self, 
        answers: List[Dict[str, Any]], 
        questionnaire_type: QuestionnaireType
    ) -> List[RTHUnifiedAnswer]:
        """Processa le risposte con filtri semantici avanzati"""
        processed_answers = []
        
        for answer in answers:
            raw_text = str(answer.get("value", ""))
            
            # Pulizia del testo
            cleaned_text = self._clean_text(raw_text)
            
            # Calcolo peso semantico
            semantic_weight = self._calculate_semantic_weight(cleaned_text, questionnaire_type)
            
            # Analisi intensitÃ  emotiva
            emotional_intensity = self._analyze_emotional_intensity(cleaned_text)
            
            # Identificazione indicatori di talento
            talent_indicators = self._identify_talent_indicators(cleaned_text, questionnaire_type)
            
            # Rilevamento pattern nascosti
            hidden_patterns = self._detect_hidden_patterns(cleaned_text)
            
            # Calcolo confidence della risposta
            confidence_score = self._calculate_answer_confidence(
                cleaned_text, semantic_weight, emotional_intensity, talent_indicators
            )
            
            processed_answer = RTHUnifiedAnswer(
                question_id=answer.get("question_id", ""),
                raw_answer=raw_text,
                processed_answer=cleaned_text,
                semantic_weight=semantic_weight,
                emotional_intensity=emotional_intensity,
                talent_indicators=talent_indicators,
                hidden_patterns=hidden_patterns,
                confidence_score=confidence_score,
                questionnaire_type=questionnaire_type.value
            )
            
            processed_answers.append(processed_answer)
        
        return processed_answers
    
    def _initialize_core_registry(self):
        """Inizializza il registro dei file RTH autorizzati"""
        self.rth_core_files = {
            "app/__init__.py",
            "app/main.py",
            "app/core/config.py",
            "app/core/event_bus.py",
            "app/core/knowledge_graph.py",
            "app/core/rth_chronicle.py",
            "app/core/rth_cortex.py",
            "app/core/rth_praxis.py",
            "app/core/rth_feedbackloop.py",
            "app/core/rth_synapse.py",
            "app/core/rth_metamorph.py",
            "app/core/permissions.py",
            "app/core/memory_vault.py",
            "app/core/fs_scanner.py",
            "app/core/jarvis.py",
            "app/core/evolution.py",
            "app/core/swarm.py",
            "app/core/governance.py",
            "app/core/plugin_hub.py",
            "app/core/plugin_runtime.py",
            "app/core/strategy.py",
            "app/core/system_bridge.py",
            "app/core/workspace_adapter.py",
            "app/core/rth_lm_adapter.py",
            "app/api/api_v1/endpoints/jarvis.py",
            "app/api/api_v1/api.py",
            "app/api/api_v1/endpoints/__init__.py",
            "app/api/api_v1/endpoints/rth_synapse.py",
            "app/api/api_v1/endpoints/rth_metamorph.py",
        }
        
        # Genera firme per i file esistenti
        self._generate_core_signatures()
    
    def _generate_core_signatures(self):
        """Genera firme crittografiche per i file RTH core"""
        for file_path in self.rth_core_files:
            try:
                # Simula la generazione di una firma per i file esistenti
                content_hash = self._calculate_file_hash(file_path)
                module_type = self._determine_module_type(file_path)
                
                signature = RTHCodeSignature(
                    file_path=file_path,
                    content_hash=content_hash,
                    module_type=module_type,
                    validated=True
                )
                
                self.authorized_signatures[file_path] = signature
                logger.debug(f"Firma generata per {file_path}")
                
            except Exception as e:
                logger.warning(f"Impossibile generare firma per {file_path}: {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calcola hash del contenuto del file"""
        try:
            # Per ora genera un hash simulato
            return hashlib.md5(f"{file_path}_{self.creator}".encode()).hexdigest()
        except Exception:
            return "simulated_hash"
    
    def _determine_module_type(self, file_path: str) -> RTHModuleType:
        """Determina il tipo di modulo RTH basato sul path del file"""
        path = file_path.lower()
        
        if "rth_chronicle" in path:
            return RTHModuleType.CHRONICLE
        if "knowledge_graph" in path:
            return RTHModuleType.KNOWLEDGE_GRAPH
        if "rth_cortex" in path or "cortex" in path:
            return RTHModuleType.CORTEX
        if "rth_praxis" in path or "praxis" in path:
            return RTHModuleType.PRAXIS
        if "evolution" in path:
            return RTHModuleType.PRAXIS
        if "plugin_hub" in path:
            return RTHModuleType.PRAXIS
        if "strategy" in path:
            return RTHModuleType.PRAXIS
        if "system_bridge" in path:
            return RTHModuleType.GUARDIAN
        if "workspace_adapter" in path:
            return RTHModuleType.GUARDIAN
        if "rth_lm_adapter" in path:
            return RTHModuleType.JARVIS
        if "governance" in path:
            return RTHModuleType.GUARDIAN
        if "rth_feedbackloop" in path or "feedback" in path:
            return RTHModuleType.FEEDBACK_LOOP
        if "rth_metamorph" in path or "metamorph" in path:
            return RTHModuleType.METAMORPH
        if "jarvis" in path:
            return RTHModuleType.JARVIS
        if "rth_synapse" in path or "synapse" in path:
            return RTHModuleType.SYNAPSE
        if "event_bus" in path or "config.py" in path:
            return RTHModuleType.SYNAPSE
        
        return RTHModuleType.GUARDIAN
    
    def validate_edit_request(self, edit_request: RTHEditRequest) -> Dict[str, Any]:
        """
        Valida una richiesta di modifica del codice RTH
        Garantisce che solo modifiche collegate al codice primario siano autorizzate
        """
        validation_result = {
            "authorized": False,
            "reason": "",
            "recommendations": [],
            "signature_required": True
        }
        
        # Verifica 1: Il file Ã¨ nel registro RTH autorizzato?
        if edit_request.file_path not in self.rth_core_files:
            validation_result["reason"] = f"File {edit_request.file_path} non Ã¨ parte del codice primario RTH autorizzato"
            validation_result["recommendations"].append("Verifica che il file sia un componente RTH legittimo")
            return validation_result
        
        # Verifica 2: Il tipo di modulo Ã¨ coerente?
        expected_module_type = self._determine_module_type(edit_request.file_path)
        if edit_request.target_module != expected_module_type:
            validation_result["reason"] = f"Tipo modulo inconsistente. Previsto: {expected_module_type}, Richiesto: {edit_request.target_module}"
            validation_result["recommendations"].append("Specificare il tipo di modulo corretto")
            return validation_result
        
        # Verifica 3: La giustificazione Ã¨ adeguata?
        if len(edit_request.justification) < 20:
            validation_result["reason"] = "Giustificazione insufficiente per la modifica"
            validation_result["recommendations"].append("Fornire una giustificazione dettagliata collegata al framework RTH")
            return validation_result
        
        # Verifica 4: Il contenuto contiene riferimenti RTH validi?
        if not self._validate_rth_content(edit_request.content):
            validation_result["reason"] = "Contenuto non conforme ai principi RTH"
            validation_result["recommendations"].append("Integrare riferimenti al framework RTH e alla metodologia")
            return validation_result
        
        # Tutte le verifiche superate
        validation_result["authorized"] = True
        validation_result["reason"] = "Modifica autorizzata - collegata al codice primario RTH"
        validation_result["signature_required"] = False
        
        logger.info(f"Edit autorizzato per {edit_request.file_path} - Modulo: {edit_request.target_module}")
        
        return validation_result
    
    def _validate_rth_content(self, content: str) -> bool:
        """Valida che il contenuto sia conforme ai principi RTH"""
        rth_keywords = [
            "RTH",
            "Core Rth Team",
            "CORE Engine",
            "Synapse",
            "Chronicle",
            "Knowledge Graph",
            "Cortex",
            "Praxis",
            "FeedbackLoop",
            "Guardian",
            "Metamorph"
        ]
        # Il contenuto deve contenere almeno uno dei keywords RTH
        return any(keyword.lower() in content.lower() for keyword in rth_keywords)
    
    def authorize_rth_file(self, file_path: str, module_type: RTHModuleType) -> bool:
        """Autorizza un nuovo file come parte del sistema RTH"""
        if file_path in self.rth_core_files:
            logger.warning(f"File {file_path} giÃ  autorizzato")
            return True
        
        # Aggiunge al registro
        self.rth_core_files.add(file_path)
        
        # Genera firma
        content_hash = self._calculate_file_hash(file_path)
        signature = RTHCodeSignature(
            file_path=file_path,
            content_hash=content_hash,
            module_type=module_type,
            validated=True
        )
        
        self.authorized_signatures[file_path] = signature
        logger.info(f"Nuovo file RTH autorizzato: {file_path} - Modulo: {module_type}")
        
        return True
    
    def get_authorized_files(self) -> List[str]:
        """Restituisce la lista dei file RTH autorizzati"""
        return list(self.rth_core_files)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Restituisce lo stato del sistema RTH Synapseâ„¢"""
        return {
            "synapse_version": self.version,
            "creator": self.creator,
            "authorized_files_count": len(self.rth_core_files),
            "signatures_count": len(self.authorized_signatures),
            "modules_active": list(set(sig.module_type.value for sig in self.authorized_signatures.values())),
            "timestamp": datetime.now(),
            "status": "Operativo - Controllo RTH Attivo"
        }

# Istanza globale del Guardian
rth_guardian = RTHSynapseGuardian()

def validate_rth_edit(file_path: str, content: str, justification: str, 
                     module_type: RTHModuleType, editor: str = "System") -> Dict[str, Any]:
    """
    Funzione di utilitÃ  per validare un edit RTH
    """
    edit_request = RTHEditRequest(
        file_path=file_path,
        edit_type="update",
        content=content,
        justification=justification,
        requested_by=editor,
        target_module=module_type
    )
    
    return rth_guardian.validate_edit_request(edit_request)

def is_rth_authorized_file(file_path: str) -> bool:
    """Verifica se un file Ã¨ autorizzato RTH"""
    return file_path in rth_guardian.rth_core_files

# ==========================================
# FUNZIONI HELPER PER ANALISI UNIFICATA
# ==========================================

def _clean_text(self, text: str) -> str:
    """Pulisce e normalizza il testo per l'analisi"""
    if not text:
        return ""
    
    # Rimuove caratteri speciali e normalizza
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def _calculate_semantic_weight(self, text: str, questionnaire_type: QuestionnaireType) -> float:
    """Calcola il peso semantico del testo basato sul tipo di questionario"""
    if not text:
        return 0.0
    
    words = text.split()
    if not words:
        return 0.0
    
    # Peso base per lunghezza e completezza
    length_score = min(len(words) / 50.0, 1.0)  # Normalizza a 50 parole
    
    # Peso per pattern di talenti rilevanti
    talent_score = 0.0
    for talent_category, keywords in self.talent_patterns.items():
        matches = sum(1 for keyword in keywords if keyword in text)
        talent_score += matches / len(keywords)
    
    # Peso specifico per tipo di questionario
    type_multiplier = {
        QuestionnaireType.TALENTOSCOPIO: 1.2,
        QuestionnaireType.LEADEROSCOPIO: 1.1,
        QuestionnaireType.STUDENTOSCOPIO: 1.0,
        QuestionnaireType.AZIENDOSCOPIO: 1.1,
        QuestionnaireType.CULTURASCOPIO: 1.0,
        QuestionnaireType.PURPOSEOSCOPIO: 1.1,
        QuestionnaireType.TEAMOSCOPIO: 1.0,
        QuestionnaireType.INNOVASCOPIO: 1.2
    }.get(questionnaire_type, 1.0)
    
    final_score = (length_score * 0.3 + talent_score * 0.7) * type_multiplier
    return min(final_score, 1.0)

def _analyze_emotional_intensity(self, text: str) -> float:
    """Analizza l'intensitÃ  emotiva del testo"""
    if not text:
        return 0.0
    
    emotional_keywords = self.semantic_filters["emotional_keywords"]
    intensity_modifiers = self.semantic_filters["intensity_modifiers"]
    
    # Conta parole emotive
    positive_count = sum(1 for word in emotional_keywords["positive"] if word in text)
    negative_count = sum(1 for word in emotional_keywords["negative"] if word in text)
    
    # Conta modificatori di intensitÃ 
    high_intensity = sum(1 for word in intensity_modifiers["high"] if word in text)
    medium_intensity = sum(1 for word in intensity_modifiers["medium"] if word in text)
    
    # Calcola intensitÃ  emotiva
    emotional_score = (positive_count + negative_count) / max(len(text.split()), 1)
    intensity_score = (high_intensity * 1.0 + medium_intensity * 0.5) / max(len(text.split()), 1)
    
    return min((emotional_score + intensity_score) * 2, 1.0)

def _identify_talent_indicators(self, text: str, questionnaire_type: QuestionnaireType) -> List[str]:
    """Identifica indicatori di talento nel testo"""
    indicators = []
    
    # Cerca pattern di talenti
    for talent_category, keywords in self.talent_patterns.items():
        matches = [keyword for keyword in keywords if keyword in text]
        if matches:
            indicators.append(f"{talent_category}: {', '.join(matches[:3])}")
    
    # Cerca indicatori specifici di talento
    talent_indicators = self.semantic_filters["talent_indicators"]
    for indicator_type, keywords in talent_indicators.items():
        matches = [keyword for keyword in keywords if keyword in text]
        if matches:
            indicators.append(f"{indicator_type}: {matches[0]}")
    
    return indicators[:5]  # Limita a 5 indicatori principali

def _detect_hidden_patterns(self, text: str) -> List[str]:
    """Rileva pattern nascosti nel testo"""
    patterns = []
    
    # Pattern di ripetizione
    words = text.split()
    word_freq = {}
    for word in words:
        if len(word) > 3:  # Solo parole significative
            word_freq[word] = word_freq.get(word, 0) + 1
    
    repeated_words = [word for word, freq in word_freq.items() if freq > 1]
    if repeated_words:
        patterns.append(f"Enfasi ripetuta: {', '.join(repeated_words[:3])}")
    
    # Pattern di contrasto
    if any(neg in text for neg in ["ma", "perÃ²", "tuttavia", "nonostante"]):
        patterns.append("Contrasto/Ambivalenza rilevata")
    
    # Pattern di crescita
    growth_words = ["migliorare", "crescere", "sviluppare", "imparare", "progredire"]
    if any(word in text for word in growth_words):
        patterns.append("Orientamento alla crescita")
    
    return patterns

def _calculate_answer_confidence(
    self, 
    text: str, 
    semantic_weight: float, 
    emotional_intensity: float, 
    talent_indicators: List[str]
) -> float:
    """Calcola il punteggio di confidenza per una risposta"""
    if not text:
        return 0.0
    
    # Fattori di confidenza
    length_factor = min(len(text.split()) / 20.0, 1.0)  # Lunghezza adeguata
    semantic_factor = semantic_weight
    emotional_factor = emotional_intensity
    indicators_factor = min(len(talent_indicators) / 3.0, 1.0)  # Presenza di indicatori
    
    # Peso dei fattori
    confidence = (
        length_factor * 0.2 +
        semantic_factor * 0.4 +
        emotional_factor * 0.2 +
        indicators_factor * 0.2
    )
    
    return min(confidence * 100, 100.0)  # Restituisce percentuale

# Aggiungi queste funzioni alla classe RTHSynapseGuardian
RTHSynapseGuardian._clean_text = _clean_text
RTHSynapseGuardian._calculate_semantic_weight = _calculate_semantic_weight
RTHSynapseGuardian._analyze_emotional_intensity = _analyze_emotional_intensity
RTHSynapseGuardian._identify_talent_indicators = _identify_talent_indicators
RTHSynapseGuardian._detect_hidden_patterns = _detect_hidden_patterns
RTHSynapseGuardian._calculate_answer_confidence = _calculate_answer_confidence

# Funzioni mancanti per completare l'analisi unificata
async def _extract_talent_insights(self, processed_answers: List[RTHUnifiedAnswer], questionnaire_type: QuestionnaireType) -> List[RTHTalentInsight]:
    """Estrae insights sui talenti dalle risposte processate"""
    insights = []
    
    # Raggruppa indicatori per categoria
    talent_categories = {}
    for answer in processed_answers:
        for indicator in answer.talent_indicators:
            if ":" in indicator:
                category, details = indicator.split(":", 1)
                if category not in talent_categories:
                    talent_categories[category] = []
                talent_categories[category].append({
                    "details": details.strip(),
                    "confidence": answer.confidence_score,
                    "question_id": answer.question_id
                })
    
    # Crea insights per ogni categoria
    for category, indicators in talent_categories.items():
        if len(indicators) >= 2:  # Almeno 2 evidenze
            avg_confidence = sum(ind["confidence"] for ind in indicators) / len(indicators)
            
            insight = RTHTalentInsight(
                category=category,
                insight_text=f"Forte indicazione di talento in {category} basata su {len(indicators)} evidenze",
                confidence=avg_confidence,
                supporting_evidence=[ind["details"] for ind in indicators[:3]],
                talent_correlation=min(avg_confidence / 100.0, 1.0),
                growth_potential=0.8 if avg_confidence > 70 else 0.6,
                questionnaire_source=questionnaire_type.value
            )
            insights.append(insight)
    
    return sorted(insights, key=lambda x: x.confidence, reverse=True)[:8]

async def _build_talent_matrix(self, processed_answers: List[RTHUnifiedAnswer], core_insights: List[RTHTalentInsight], questionnaire_type: QuestionnaireType) -> Dict[str, float]:
    """Costruisce la matrice dei talenti"""
    talent_matrix = {}
    
    # Inizializza con categorie base
    for category in self.talent_patterns.keys():
        talent_matrix[category] = 0.0
    
    # Calcola punteggi basati su insights
    for insight in core_insights:
        if insight.category in talent_matrix:
            talent_matrix[insight.category] = max(
                talent_matrix[insight.category],
                insight.talent_correlation
            )
    
    # Normalizza i punteggi
    max_score = max(talent_matrix.values()) if talent_matrix.values() else 1.0
    if max_score > 0:
        for category in talent_matrix:
            talent_matrix[category] = (talent_matrix[category] / max_score) * 100
    
    return talent_matrix

async def _identify_hidden_talents(self, processed_answers: List[RTHUnifiedAnswer], questionnaire_type: QuestionnaireType) -> List[str]:
    """Identifica talenti nascosti attraverso pattern analysis"""
    hidden_talents = []
    
    # Analizza pattern nascosti
    all_patterns = []
    for answer in processed_answers:
        all_patterns.extend(answer.hidden_patterns)
    
    # Cerca pattern ricorrenti
    pattern_freq = {}
    for pattern in all_patterns:
        pattern_freq[pattern] = pattern_freq.get(pattern, 0) + 1
    
    # Identifica talenti nascosti basati su pattern ricorrenti
    for pattern, freq in pattern_freq.items():
        if freq >= 2:  # Pattern che appare almeno 2 volte
            if "crescita" in pattern.lower():
                hidden_talents.append("Potenziale di sviluppo accelerato")
            elif "contrasto" in pattern.lower():
                hidden_talents.append("CapacitÃ  di gestione della complessitÃ ")
            elif "enfasi" in pattern.lower():
                hidden_talents.append("Forte orientamento valoriale")
    
    # Analisi semantica avanzata per talenti nascosti
    high_confidence_answers = [a for a in processed_answers if a.confidence_score > 80]
    if len(high_confidence_answers) > len(processed_answers) * 0.6:
        hidden_talents.append("Elevata autoconsapevolezza")
    
    high_emotional_answers = [a for a in processed_answers if a.emotional_intensity > 0.7]
    if len(high_emotional_answers) > len(processed_answers) * 0.4:
        hidden_talents.append("Forte coinvolgimento emotivo")
    
    return list(set(hidden_talents))[:5]  # Rimuovi duplicati e limita a 5

async def _calculate_growth_vectors(self, talent_matrix: Dict[str, float], core_insights: List[RTHTalentInsight]) -> List[str]:
    """Calcola i vettori di crescita"""
    growth_vectors = []
    
    # Identifica aree di forza (>70)
    strong_areas = [cat for cat, score in talent_matrix.items() if score > 70]
    
    # Identifica aree di potenziale (40-70)
    potential_areas = [cat for cat, score in talent_matrix.items() if 40 <= score <= 70]
    
    # Genera vettori di crescita
    if strong_areas:
        growth_vectors.append(f"Potenziamento eccellenze: {', '.join(strong_areas[:2])}")
    
    if potential_areas:
        growth_vectors.append(f"Sviluppo potenziale: {', '.join(potential_areas[:2])}")
    
    # Vettori basati su insights
    high_growth_insights = [i for i in core_insights if i.growth_potential > 0.7]
    if high_growth_insights:
        growth_vectors.append(f"Focus crescita: {high_growth_insights[0].category}")
    
    return growth_vectors[:4]

async def _generate_narrative_synthesis(
    self, 
    processed_answers: List[RTHUnifiedAnswer], 
    core_insights: List[RTHTalentInsight], 
    talent_matrix: Dict[str, float], 
    questionnaire_type: QuestionnaireType, 
    user_profile: Dict[str, Any]
) -> str:
    """Genera la sintesi narrativa dell'analisi"""
    
    # Identifica talenti principali
    top_talents = sorted(talent_matrix.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Costruisce narrativa
    narrative = f"L'analisi RTH Synapseâ„¢ di {user_profile.get('name', 'lo studente')} rivela un profilo ricco di potenziale. "
    
    if top_talents:
        narrative += f"I talenti principali emergono nelle aree di {', '.join([t[0] for t in top_talents])}. "
    
    if core_insights:
        narrative += f"L'analisi semantica ha identificato {len(core_insights)} insight significativi sui talenti, "
        narrative += f"con un livello di confidenza medio del {sum(i.confidence for i in core_insights) / len(core_insights):.1f}%. "
    
    # Aggiunge osservazioni sui pattern
    high_confidence_count = len([a for a in processed_answers if a.confidence_score > 75])
    if high_confidence_count > len(processed_answers) * 0.5:
        narrative += "Le risposte mostrano un elevato livello di autoconsapevolezza e chiarezza espressiva. "
    
    narrative += "Questo profilo indica un potenziale di crescita significativo nelle aree identificate."
    
    return narrative

def _calculate_confidence_score(self, processed_answers: List[RTHUnifiedAnswer], core_insights: List[RTHTalentInsight]) -> float:
    """Calcola il punteggio di confidenza complessivo dell'analisi"""
    if not processed_answers:
        return 0.0
    
    # Media dei punteggi di confidenza delle risposte
    avg_answer_confidence = sum(a.confidence_score for a in processed_answers) / len(processed_answers)
    
    # Fattore di qualitÃ  degli insights
    insight_quality = min(len(core_insights) / 5.0, 1.0) * 100  # Normalizza a 5 insights
    
    # Fattore di completezza
    completeness_factor = min(len(processed_answers) / 20.0, 1.0) * 100  # Normalizza a 20 risposte
    
    # Calcolo finale
    final_confidence = (
        avg_answer_confidence * 0.5 +
        insight_quality * 0.3 +
        completeness_factor * 0.2
    )
    
    return min(final_confidence, 100.0)

# Aggiungi le nuove funzioni alla classe
RTHSynapseGuardian._extract_talent_insights = _extract_talent_insights
RTHSynapseGuardian._build_talent_matrix = _build_talent_matrix
RTHSynapseGuardian._identify_hidden_talents = _identify_hidden_talents
RTHSynapseGuardian._calculate_growth_vectors = _calculate_growth_vectors
RTHSynapseGuardian._generate_narrative_synthesis = _generate_narrative_synthesis
RTHSynapseGuardian._calculate_confidence_score = _calculate_confidence_score 




