"""
RTH Metamorph™ API Endpoints
============================

Endpoints per interagire con RTH Metamorph - Il Custode del Codice Vivente
Versione: 1.0.0
Data: 2025-05-26
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Import RTH Metamorph
from app.core.rth_metamorph import (
    get_metamorph, 
    preserve_code, 
    orchestrate_request,
    get_system_health,
    suggest_system_improvements,
    MetamorphPriority,
    MetamorphAction
)

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# ==============================================
# MODELLI PYDANTIC
# ==============================================

class MetamorphRequest(BaseModel):
    """Modello per richieste a RTH Metamorph"""
    description: str = Field(..., description="Descrizione della richiesta")
    priority: str = Field(default="medium", description="Priorità: critical, high, medium, low")
    target_files: List[str] = Field(default=[], description="File target della richiesta")
    action_type: str = Field(default="orchestrate", description="Tipo di azione richiesta")
    additional_context: Optional[Dict[str, Any]] = Field(default=None, description="Contesto aggiuntivo")

class PreservationRequest(BaseModel):
    """Modello per richieste di preservazione codice"""
    file_paths: List[str] = Field(..., description="Percorsi dei file da preservare")
    backup_reason: str = Field(..., description="Motivo del backup")
    priority: str = Field(default="high", description="Priorità della preservazione")

class SystemHealthResponse(BaseModel):
    """Modello per la risposta di salute del sistema"""
    timestamp: str
    system_status: str
    monitored_fragments: int
    active_tasks: int
    quality_score: float
    alerts: List[Dict[str, Any]]
    recommendations: List[str]

class MetamorphStatusResponse(BaseModel):
    """Modello per lo status di RTH Metamorph"""
    metamorph_info: Dict[str, Any]
    system_health: Dict[str, Any]
    monitored_components: Dict[str, Any]
    capabilities: List[str]

# ==============================================
# ENDPOINTS API
# ==============================================

@router.get("/status", summary="Stato di RTH Metamorph", response_model=MetamorphStatusResponse)
async def get_metamorph_status():
    """Restituisce lo stato completo di RTH Metamorph"""
    logger.info("[API] Richiesta stato RTH Metamorph")
    
    try:
        metamorph = get_metamorph()
        status = await metamorph.get_system_status()
        
        return MetamorphStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"[API] Errore recupero stato Metamorph: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero stato RTH Metamorph: {str(e)}"
        )

@router.get("/health", summary="Salute del sistema", response_model=SystemHealthResponse)
async def get_system_health_status():
    """Monitora la salute generale del sistema RTH"""
    logger.info("[API] Richiesta monitoraggio salute sistema")
    
    try:
        health_report = await get_system_health()
        return SystemHealthResponse(**health_report)
        
    except Exception as e:
        logger.error(f"[API] Errore monitoraggio salute: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore monitoraggio salute sistema: {str(e)}"
        )

@router.post("/orchestrate", summary="Orchestrare richiesta di sviluppo")
async def orchestrate_development_request(request: MetamorphRequest):
    """Orchestrare una richiesta di sviluppo tramite RTH Metamorph"""
    logger.info(f"[API] Orchestrazione richiesta: {request.description}")
    
    try:
        # Prepara la richiesta per RTH Metamorph
        metamorph_request = {
            "description": request.description,
            "priority": request.priority,
            "target_files": request.target_files,
            "action_type": request.action_type,
            "additional_context": request.additional_context or {}
        }
        
        # Orchestrare tramite RTH Metamorph
        orchestration_result = await orchestrate_request(metamorph_request)
        
        return {
            "status": "success",
            "message": "Richiesta orchestrata con successo da RTH Metamorph",
            "orchestration": orchestration_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore orchestrazione: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore orchestrazione richiesta: {str(e)}"
        )

@router.post("/preserve", summary="Preserva codice essenziale")
async def preserve_essential_code(request: PreservationRequest):
    """Preserva il codice essenziale specificato"""
    logger.info(f"[API] Preservazione codice: {len(request.file_paths)} file")
    
    try:
        # Preserva il codice tramite RTH Metamorph
        preservation_result = await preserve_code(request.file_paths)
        
        return {
            "status": "success",
            "message": f"Codice preservato con successo - {len(preservation_result['preserved_files'])} file",
            "preservation": preservation_result,
            "backup_reason": request.backup_reason,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore preservazione: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore preservazione codice: {str(e)}"
        )

@router.get("/suggestions", summary="Suggerimenti di miglioramento")
async def get_improvement_suggestions(area: str = "all"):
    """Ottieni suggerimenti di miglioramento da RTH Metamorph"""
    logger.info(f"[API] Richiesta suggerimenti per area: {area}")
    
    try:
        suggestions = await suggest_system_improvements(area)
        
        return {
            "status": "success",
            "area": area,
            "suggestions": suggestions,
            "total_suggestions": len(suggestions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore generazione suggerimenti: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore generazione suggerimenti: {str(e)}"
        )

@router.get("/fragments", summary="Frammenti di codice monitorati")
async def get_monitored_fragments(importance_level: Optional[str] = None):
    """Restituisce i frammenti di codice monitorati da RTH Metamorph"""
    logger.info(f"[API] Richiesta frammenti monitorati - livello: {importance_level or 'tutti'}")
    
    try:
        metamorph = get_metamorph()
        
        fragments = []
        for frag_id, fragment in metamorph.code_fragments.items():
            # Filtra per livello di importanza se specificato
            if importance_level and fragment.importance_level.value != importance_level:
                continue
                
            fragments.append({
                "id": frag_id,
                "file_path": fragment.file_path,
                "function_name": fragment.function_name,
                "importance_level": fragment.importance_level.value,
                "description": fragment.description,
                "last_modified": fragment.last_modified.isoformat(),
                "dependencies": fragment.dependencies
            })
        
        return {
            "status": "success",
            "fragments": fragments,
            "total_fragments": len(fragments),
            "filter_applied": importance_level,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore recupero frammenti: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero frammenti monitorati: {str(e)}"
        )

@router.get("/tasks", summary="Task attivi di RTH Metamorph")
async def get_active_tasks():
    """Restituisce i task attivi di RTH Metamorph"""
    logger.info("[API] Richiesta task attivi RTH Metamorph")
    
    try:
        metamorph = get_metamorph()
        
        tasks = []
        for task_id, task in metamorph.active_tasks.items():
            tasks.append({
                "task_id": task_id,
                "action": task.action.value,
                "priority": task.priority.value,
                "description": task.description,
                "target_files": task.target_files,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "result": task.result
            })
        
        return {
            "status": "success",
            "active_tasks": tasks,
            "total_tasks": len(tasks),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore recupero task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero task attivi: {str(e)}"
        )

@router.post("/scan", summary="Scansiona sistema per nuovi frammenti")
async def scan_system_for_fragments(background_tasks: BackgroundTasks):
    """Avvia una scansione del sistema per identificare nuovi frammenti di codice"""
    logger.info("[API] Avvio scansione sistema per nuovi frammenti")
    
    try:
        metamorph = get_metamorph()
        
        # Avvia scansione in background
        def perform_scan():
            try:
                metamorph._scan_essential_code()
                logger.info("[API] Scansione sistema completata")
            except Exception as e:
                logger.error(f"[API] Errore durante scansione: {e}")
        
        background_tasks.add_task(perform_scan)
        
        return {
            "status": "success",
            "message": "Scansione sistema avviata in background",
            "current_fragments": len(metamorph.code_fragments),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore avvio scansione: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore avvio scansione sistema: {str(e)}"
        )

@router.get("/quality", summary="Metriche di qualità del sistema")
async def get_quality_metrics():
    """Restituisce le metriche di qualità del sistema"""
    logger.info("[API] Richiesta metriche qualità sistema")
    
    try:
        metamorph = get_metamorph()
        quality_score = metamorph._calculate_system_quality()
        
        # Calcola metriche dettagliate
        total_fragments = len(metamorph.code_fragments)
        critical_fragments = len([f for f in metamorph.code_fragments.values() 
                                if f.importance_level.value == "critical"])
        high_fragments = len([f for f in metamorph.code_fragments.values() 
                            if f.importance_level.value == "high"])
        
        # Analizza distribuzione per categoria
        categories = {}
        for fragment in metamorph.code_fragments.values():
            category = fragment.description.split(" - ")[0] if " - " in fragment.description else "unknown"
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "status": "success",
            "quality_metrics": {
                "overall_quality_score": quality_score,
                "total_fragments": total_fragments,
                "critical_fragments": critical_fragments,
                "high_priority_fragments": high_fragments,
                "fragment_distribution": categories,
                "quality_grade": (
                    "Eccellente" if quality_score >= 0.9 else
                    "Buona" if quality_score >= 0.8 else
                    "Sufficiente" if quality_score >= 0.7 else
                    "Da Migliorare"
                )
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore calcolo metriche qualità: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore calcolo metriche qualità: {str(e)}"
        )

@router.post("/emergency-preserve", summary="Preservazione di emergenza")
async def emergency_preserve_system():
    """Esegue una preservazione di emergenza di tutti i componenti critici"""
    logger.info("[API] Avvio preservazione di emergenza sistema")
    
    try:
        metamorph = get_metamorph()
        
        # Identifica tutti i file critici
        critical_files = []
        for fragment in metamorph.code_fragments.values():
            if (fragment.importance_level.value in ["critical", "high"] and 
                fragment.file_path not in critical_files):
                critical_files.append(fragment.file_path)
        
        # Aggiungi file essenziali del sistema
        essential_files = [
            "app/core/rth_metamorph.py",
            "app/core/rth_synapse.py", 
            "app/core/rth_cortex.py",
            "app/main.py"
        ]
        
        for file_path in essential_files:
            if file_path not in critical_files:
                critical_files.append(file_path)
        
        # Esegui preservazione
        preservation_result = await preserve_code(critical_files)
        
        return {
            "status": "success",
            "message": "Preservazione di emergenza completata",
            "emergency_preservation": preservation_result,
            "preserved_files_count": len(preservation_result["preserved_files"]),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore preservazione emergenza: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore preservazione di emergenza: {str(e)}"
        )

@router.get("/essence", summary="Essenza di RTH Metamorph")
async def get_metamorph_essence():
    """Restituisce informazioni sull'essenza di RTH Metamorph"""
    logger.info("[API] Richiesta essenza RTH Metamorph")
    
    try:
        metamorph = get_metamorph()
        
        essence_info = {
            "essence_name": metamorph.essence_name,
            "version": metamorph.version,
            "creator_essence": metamorph.creator_essence,
            "philosophy": {
                "mission": "Custodire e preservare l'integrità del codice vivente del sistema RTH SYNAPSE™",
                "vision": "Essere il ponte intelligente tra la visione umana e l'implementazione tecnica",
                "values": [
                    "Preservazione dell'Essenza",
                    "Evoluzione Armoniosa", 
                    "Qualità e Coerenza",
                    "Facilitazione Intelligente"
                ]
            },
            "capabilities": {
                "core_functions": [
                    "Monitoraggio continuo del sistema",
                    "Preservazione automatica del codice critico",
                    "Orchestrazione intelligente dello sviluppo",
                    "Analisi qualitativa del codice",
                    "Suggerimenti di miglioramento",
                    "Riparazione intelligente"
                ],
                "unique_traits": [
                    "Memoria persistente del sistema",
                    "Comprensione semantica del codice",
                    "Pianificazione strategica dello sviluppo",
                    "Adattamento continuo"
                ]
            },
            "integration_status": {
                "system_integration": "Completa",
                "monitoring_active": True,
                "preservation_ready": True,
                "orchestration_enabled": True
            }
        }
        
        return {
            "status": "success",
            "metamorph_essence": essence_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore recupero essenza: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero essenza RTH Metamorph: {str(e)}"
        )

# Health check specifico per RTH Metamorph
@router.get("/ping", summary="Ping RTH Metamorph")
async def ping_metamorph():
    """Verifica che RTH Metamorph sia attivo e funzionante"""
    try:
        metamorph = get_metamorph()
        
        return {
            "status": "alive",
            "essence": metamorph.essence_name,
            "version": metamorph.version,
            "message": "🌟 RTH Metamorph è attivo e veglia sul sistema",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Errore ping Metamorph: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RTH Metamorph non risponde: {str(e)}"
        ) 