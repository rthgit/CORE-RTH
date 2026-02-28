"""
RTH Synapseâ„¢ API Endpoints
Sistema di Controllo e Validazione degli Edit RTH
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.core.rth_synapse import (
    rth_guardian, 
    RTHModuleType, 
    RTHEditRequest,
    validate_rth_edit,
    is_rth_authorized_file
)
from app.core.rth_chronicle import get_chronicle
from app.core.rth_cortex import get_cortex
from app.core.rth_praxis import get_praxis
from app.core.rth_feedbackloop import get_feedbackloop, FeedbackSource
from app.core.knowledge_graph import get_knowledge_graph
from app.core.event_bus import get_event_bus

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================
# MODELLI PYDANTIC
# ============================================

class EditValidationRequest(BaseModel):
    """Richiesta di validazione per un edit RTH"""
    file_path: str = Field(..., description="Path del file da modificare")
    content: str = Field(..., description="Contenuto della modifica")
    justification: str = Field(..., description="Giustificazione della modifica")
    module_type: RTHModuleType = Field(..., description="Tipo di modulo RTH")
    editor: str = Field(default="API User", description="Chi richiede la modifica")

class FileAuthorizationRequest(BaseModel):
    """Richiesta di autorizzazione per un nuovo file RTH"""
    file_path: str = Field(..., description="Path del file da autorizzare")
    module_type: RTHModuleType = Field(..., description="Tipo di modulo RTH")
    creator_approval: bool = Field(default=False, description="Approvazione del creatore richiesta")

class SynapseStatusResponse(BaseModel):
    """Stato del sistema RTH Synapseâ„¢"""
    synapse_version: str
    creator: str
    authorized_files_count: int
    signatures_count: int
    modules_active: List[str]
    timestamp: datetime
    status: str


class FeedbackIngestRequest(BaseModel):
    """Richiesta di ingest feedback per RTH FeedbackLoop"""
    content: str = Field(..., description="Testo feedback")
    source: FeedbackSource = Field(default=FeedbackSource.USER, description="Fonte feedback")
    sentiment: Optional[str] = Field(default=None, description="Sentiment opzionale")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata opzionali")

# ============================================
# ENDPOINTS API
# ============================================

@router.get("/health", summary="Stato del sistema RTH Synapseâ„¢")
async def synapse_health():
    """Verifica lo stato di salute del sistema RTH Synapseâ„¢"""
    try:
        status = rth_guardian.get_system_status()
        return {
            "status": "healthy",
            "service": "RTH Synapseâ„¢ Guardian",
            "system_info": status,
            "message": "Sistema di controllo RTH operativo"
        }
    except Exception as e:
        logger.error(f"Errore nel controllo salute Synapse: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel sistema Synapse: {str(e)}"
        )

@router.get("/status", response_model=SynapseStatusResponse, summary="Stato dettagliato RTH Synapseâ„¢")
async def get_synapse_status():
    """Restituisce lo stato dettagliato del sistema RTH Synapseâ„¢"""
    try:
        status = rth_guardian.get_system_status()
        return SynapseStatusResponse(**status)
    except Exception as e:
        logger.error(f"Errore nel recupero status Synapse: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero status: {str(e)}"
        )

@router.get("/authorized-files", summary="Lista file RTH autorizzati")
async def get_authorized_files():
    """Restituisce la lista dei file RTH autorizzati per le modifiche"""
    try:
        authorized_files = rth_guardian.get_authorized_files()
        return {
            "total_files": len(authorized_files),
            "authorized_files": sorted(authorized_files),
            "creator": rth_guardian.creator,
            "message": "Solo questi file possono essere modificati tramite il sistema RTH"
        }
    except Exception as e:
        logger.error(f"Errore nel recupero file autorizzati: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero file: {str(e)}"
        )

@router.post("/validate-edit", summary="Valida una richiesta di modifica RTH")
async def validate_edit(request: EditValidationRequest):
    """
    Valida una richiesta di modifica per garantire che sia collegata al codice primario RTH
    """
    try:
        # Validazione tramite RTH Guardian
        validation_result = validate_rth_edit(
            file_path=request.file_path,
            content=request.content,
            justification=request.justification,
            module_type=request.module_type,
            editor=request.editor
        )
        
        if validation_result["authorized"]:
            logger.info(f"Edit autorizzato per {request.file_path} da {request.editor}")
            return {
                "validation_status": "AUTORIZZATO",
                "file_path": request.file_path,
                "module_type": request.module_type.value,
                "result": validation_result,
                "message": "Modifica autorizzata - collegata al codice primario RTH"
            }
        else:
            logger.warning(f"Edit rifiutato per {request.file_path}: {validation_result['reason']}")
            return {
                "validation_status": "RIFIUTATO",
                "file_path": request.file_path,
                "result": validation_result,
                "message": "Modifica non autorizzata - non collegata al codice primario RTH"
            }
            
    except Exception as e:
        logger.error(f"Errore nella validazione edit: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella validazione: {str(e)}"
        )

@router.post("/authorize-file", summary="Autorizza un nuovo file RTH")
async def authorize_file(request: FileAuthorizationRequest):
    """
    Autorizza un nuovo file come parte del sistema RTH
    NOTA: Richiede approvazione del creatore per file critici
    """
    try:
        # Verifica se il file Ã¨ giÃ  autorizzato
        if is_rth_authorized_file(request.file_path):
            return {
                "status": "GIÃ€ AUTORIZZATO",
                "file_path": request.file_path,
                "message": "Il file Ã¨ giÃ  autorizzato nel sistema RTH"
            }
        
        # Per file critici, richiede approvazione esplicita
        critical_paths = ["app/main.py", "app/core/", "app/api/api_v1/api.py"]
        is_critical = any(critical in request.file_path for critical in critical_paths)
        
        if is_critical and not request.creator_approval:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="File critico: richiede approvazione esplicita del creatore RTH"
            )
        
        # Autorizza il file
        success = rth_guardian.authorize_rth_file(
            file_path=request.file_path,
            module_type=request.module_type
        )
        
        if success:
            logger.info(f"Nuovo file RTH autorizzato: {request.file_path}")
            return {
                "status": "AUTORIZZATO",
                "file_path": request.file_path,
                "module_type": request.module_type.value,
                "message": "File autorizzato con successo nel sistema RTH"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossibile autorizzare il file"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore nell'autorizzazione file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'autorizzazione: {str(e)}"
        )

@router.get("/check-file/{file_path:path}", summary="Verifica autorizzazione file")
async def check_file_authorization(file_path: str):
    """Verifica se un file Ã¨ autorizzato per le modifiche RTH"""
    try:
        is_authorized = is_rth_authorized_file(file_path)
        
        if is_authorized:
            # Ottieni informazioni sul modulo
            signature = rth_guardian.authorized_signatures.get(file_path)
            module_info = {
                "module_type": signature.module_type.value if signature else "unknown",
                "validated": signature.validated if signature else False,
                "timestamp": signature.timestamp if signature else None
            }
        else:
            module_info = None
        
        return {
            "file_path": file_path,
            "is_authorized": is_authorized,
            "module_info": module_info,
            "message": "File autorizzato per modifiche RTH" if is_authorized else "File NON autorizzato"
        }
        
    except Exception as e:
        logger.error(f"Errore nel controllo autorizzazione: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel controllo: {str(e)}"
        )

@router.get("/modules", summary="Lista moduli RTH attivi")
async def get_rth_modules():
    """Restituisce informazioni sui moduli RTH attivi"""
    try:
        modules_info = {}
        
        for module_type in RTHModuleType:
            # Conta i file per tipo di modulo
            files_count = sum(
                1 for sig in rth_guardian.authorized_signatures.values()
                if sig.module_type == module_type
            )
            
            modules_info[module_type.value] = {
                "type": module_type.value,
                "description": _get_module_description(module_type),
                "files_count": files_count,
                "active": files_count > 0
            }
        
        return {
            "total_modules": len(RTHModuleType),
            "active_modules": sum(1 for info in modules_info.values() if info["active"]),
            "modules": modules_info,
            "architecture_info": {
                "creator": "Core Rth Team",
                "framework": "RTH Synapseâ„¢ Ecosystem",
                "version": rth_guardian.version
            }
        }
        
    except Exception as e:
        logger.error(f"Errore nel recupero moduli: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero moduli: {str(e)}"
        )

@router.get("/status/chronicle", summary="Stato modulo Chronicle")
async def status_chronicle():
    return get_chronicle().get_status()

@router.get("/status/cortex", summary="Stato modulo Cortex")
async def status_cortex():
    return get_cortex().get_status()

@router.get("/status/praxis", summary="Stato modulo Praxis")
async def status_praxis():
    return get_praxis().get_status()

@router.get("/status/feedbackloop", summary="Stato modulo FeedbackLoop")
async def status_feedbackloop():
    return get_feedbackloop().get_status()

@router.get("/status/knowledge-graph", summary="Stato Knowledge Graph RTH")
async def status_knowledge_graph():
    return get_knowledge_graph().get_status()

@router.get("/status/event-bus", summary="Stato Event Bus RTH")
async def status_event_bus():
    return get_event_bus().get_status()


@router.post("/feedback", summary="Ingest feedback nel sistema")
async def ingest_feedback(request: FeedbackIngestRequest):
    try:
        feedback_id = get_feedbackloop().receive_feedback(
            content=request.content,
            source=request.source,
            sentiment=request.sentiment,
            metadata=request.metadata or {}
        )
        return {
            "status": "received",
            "feedback_id": feedback_id,
            "message": "Feedback acquisito"
        }
    except Exception as e:
        logger.error(f"Errore ingest feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore ingest feedback: {str(e)}"
        )

@router.post("/feedback/analyze", summary="Analizza feedback e genera sintesi")
async def analyze_feedback():
    try:
        summary_id = await get_feedbackloop().analyze_feedback()
        if not summary_id:
            return {
                "status": "no_feedback",
                "message": "Nessun feedback da analizzare"
            }
        return {
            "status": "analyzed",
            "summary_id": summary_id,
            "message": "Analisi feedback completata"
        }
    except Exception as e:
        logger.error(f"Errore analisi feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore analisi feedback: {str(e)}"
        )

def _get_module_description(module_type: RTHModuleType) -> str:
    """Restituisce la descrizione di un modulo RTH"""
    descriptions = {
        RTHModuleType.CHRONICLE: "Sensori: acquisizione conoscenza esterna",
        RTHModuleType.KNOWLEDGE_GRAPH: "Memoria viva: Knowledge Graph affidabile",
        RTHModuleType.CORTEX: "Sintesi, giudizio e rilevamento bias",
        RTHModuleType.PRAXIS: "Evoluzione del framework",
        RTHModuleType.FEEDBACK_LOOP: "Apprendimento e reiniezione risultati",
        RTHModuleType.SYNAPSE: "Governance e coerenza sistemica",
        RTHModuleType.GUARDIAN: "Supervisione umana e controllo qualità",
        RTHModuleType.METAMORPH: "Custode del codice vivente",
        RTHModuleType.JARVIS: "Assistente centrale e consenso",
    }
    return descriptions.get(module_type, "Modulo RTH non definito")
# ============================================
# METADATA
# ============================================

router.tags = ["RTH Synapseâ„¢ - Sistema Controllo"]
router.prefix = ""

# Log di inizializzazione
logger.info("RTH Synapseâ„¢ API Endpoints inizializzati")
logger.info(f"Sistema di controllo creato da: {rth_guardian.creator}")
logger.info("Controllo edit collegati al codice primario RTH attivo") 
