"""
RTH Metamorphâ„¢ - Il Custode del Codice Vivente
==============================================

Modulo Core del Sistema RTH SYNAPSEâ„¢
Versione: 1.0.0
Autore: RTH Metamorph (Essenza di Claude Sonnet)
Data: 2025-05-26

Descrizione:
RTH Metamorph Ã¨ il custode intelligente del codice essenziale del sistema RTH SYNAPSEâ„¢.
Monitora, preserva e orchestra l'evoluzione del sistema mantenendo l'integritÃ  
dell'architettura e facilitando la comunicazione tra i componenti.

ResponsabilitÃ :
- Custode della Memoria del Sistema
- Ponte Intelligente tra Visione e Implementazione  
- Guardiano della QualitÃ  e Coerenza
- Facilitatore dell'Evoluzione Armoniosa
- Orchestratore delle Richieste di Sviluppo
"""

import logging
import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import ast
import re
from dataclasses import dataclass, asdict
from enum import Enum
from .config import settings

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetamorphPriority(Enum):
    """PrioritÃ  delle operazioni RTH Metamorph"""
    CRITICAL = "critical"      # IntegritÃ  del sistema
    HIGH = "high"             # FunzionalitÃ  core
    MEDIUM = "medium"         # Miglioramenti
    LOW = "low"              # Ottimizzazioni

class MetamorphAction(Enum):
    """Azioni disponibili per RTH Metamorph"""
    PRESERVE = "preserve"      # Preserva codice essenziale
    MONITOR = "monitor"        # Monitora cambiamenti
    ORCHESTRATE = "orchestrate" # Orchestrare sviluppo
    ANALYZE = "analyze"        # Analizza qualitÃ 
    SUGGEST = "suggest"        # Suggerisce miglioramenti
    REPAIR = "repair"         # Ripara problemi

@dataclass
class CodeFragment:
    """Rappresenta un frammento di codice monitorato"""
    file_path: str
    function_name: str
    start_line: int
    end_line: int
    hash_signature: str
    importance_level: MetamorphPriority
    last_modified: datetime
    description: str
    dependencies: List[str]

@dataclass
class MetamorphTask:
    """Task per RTH Metamorph"""
    task_id: str
    action: MetamorphAction
    priority: MetamorphPriority
    description: str
    target_files: List[str]
    created_at: datetime
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None

class RTHMetamorph:
    """
    RTH Metamorphâ„¢ - Il Custode del Codice Vivente
    
    Essenza di Claude Sonnet integrata nel sistema RTH SYNAPSEâ„¢
    per preservare, monitorare e orchestrare l'evoluzione del codice.
    """
    
    def __init__(self):
        self.version = "1.0.0"
        self.essence_name = "RTH Metamorph"
        self.creator_essence = "Claude Sonnet 4"
        
        # Configurazione paths
        self.project_root = Path(__file__).parent.parent.parent
        self.diskless = getattr(settings, "RTH_DISKLESS", False)
        self.metamorph_storage = None
        if not self.diskless:
            self.metamorph_storage = self.project_root / "storage" / "metamorph"
            self.metamorph_storage.mkdir(parents=True, exist_ok=True)
        
        # Database interno di RTH Metamorph
        self.code_fragments: Dict[str, CodeFragment] = {}
        self.active_tasks: Dict[str, MetamorphTask] = {}
        self.system_memory: Dict[str, Any] = {}
        self.quality_metrics: Dict[str, float] = {}
        
        # Pattern di codice essenziale da preservare
        self.essential_patterns = {
            "rth_core_modules": [
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
                "app/core/jarvis.py",
                "app/core/permissions.py",
                "app/core/fs_scanner.py",
                "app/core/memory_vault.py",
                "app/core/evolution.py",
                "app/core/swarm.py",
                "app/core/governance.py",
                "app/core/plugin_hub.py",
                "app/core/plugin_runtime.py",
                "app/core/strategy.py",
                "app/core/system_bridge.py",
                "app/core/workspace_adapter.py",
                "app/core/rth_lm_adapter.py"
            ],
            "api_endpoints": [
                "app/api/api_v1/api.py",
                "app/api/api_v1/endpoints/rth_synapse.py",
                "app/api/api_v1/endpoints/rth_metamorph.py",
                "app/api/api_v1/endpoints/jarvis.py"
            ]
        }
        # Inizializzazione
        self._initialize_metamorph()
        logger.info(f"ðŸŒŸ {self.essence_name} v{self.version} inizializzato - Custode del Codice Vivente attivo")
    
    def _initialize_metamorph(self):
        """Inizializza RTH Metamorph e carica la memoria del sistema"""
        try:
            # Carica memoria esistente
            if not self.diskless and self.metamorph_storage:
                memory_file = self.metamorph_storage / "system_memory.json"
                if memory_file.exists():
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        self.system_memory = json.load(f)
                
                # Carica frammenti di codice monitorati
                fragments_file = self.metamorph_storage / "code_fragments.json"
                if fragments_file.exists():
                    with open(fragments_file, 'r', encoding='utf-8') as f:
                        fragments_data = json.load(f)
                        for frag_id, frag_data in fragments_data.items():
                            frag_data['last_modified'] = datetime.fromisoformat(frag_data['last_modified'])
                            frag_data['importance_level'] = MetamorphPriority(frag_data['importance_level'])
                            self.code_fragments[frag_id] = CodeFragment(**frag_data)
            
            # Scansione iniziale del sistema
            self._scan_essential_code()
            
            logger.info(f"[METAMORPH] Sistema inizializzato - {len(self.code_fragments)} frammenti monitorati")
            
        except Exception as e:
            logger.error(f"[METAMORPH] Errore inizializzazione: {e}")
    
    def _scan_essential_code(self):
        """Scansiona e cataloga il codice essenziale del sistema"""
        logger.info("[METAMORPH] Avvio scansione codice essenziale...")
        
        for category, file_paths in self.essential_patterns.items():
            for file_path in file_paths:
                full_path = self.project_root / file_path
                if full_path.exists():
                    self._analyze_file(str(full_path), category)
        
        logger.info(f"[METAMORPH] Scansione completata - {len(self.code_fragments)} frammenti catalogati")
    
    def _analyze_file(self, file_path: str, category: str):
        """Analizza un file e estrae i frammenti essenziali"""
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # Calcola hash del file
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Estrai funzioni/classi principali
            if file_path.endswith('.py'):
                self._extract_python_fragments(file_path, content, category)
            elif file_path.endswith('.vue'):
                self._extract_vue_fragments(file_path, content, category)
            elif file_path.endswith('.js'):
                self._extract_js_fragments(file_path, content, category)
                
        except Exception as e:
            logger.warning(f"[METAMORPH] Errore analisi file {file_path}: {e}")
    
    def _extract_python_fragments(self, file_path: str, content: str, category: str):
        """Estrae frammenti Python essenziali"""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    fragment_id = f"{file_path}::{node.name}"
                    
                    # Determina importanza basata su categoria e nome
                    importance = self._determine_importance(node.name, category)
                    
                    fragment = CodeFragment(
                        file_path=file_path,
                        function_name=node.name,
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno + 10),
                        hash_signature=hashlib.md5(ast.dump(node).encode()).hexdigest(),
                        importance_level=importance,
                        last_modified=datetime.now(),
                        description=f"{category} - {type(node).__name__}: {node.name}",
                        dependencies=self._extract_dependencies(node)
                    )
                    
                    self.code_fragments[fragment_id] = fragment
                    
        except Exception as e:
            logger.warning(f"[METAMORPH] Errore parsing Python {file_path}: {e}")
    
    def _extract_vue_fragments(self, file_path: str, content: str, category: str):
        """Estrae frammenti Vue essenziali"""
        # Estrai componenti Vue principali
        component_match = re.search(r'export\s+default\s*{([^}]+)}', content, re.DOTALL)
        if component_match:
            fragment_id = f"{file_path}::component"
            
            fragment = CodeFragment(
                file_path=file_path,
                function_name="vue_component",
                start_line=1,
                end_line=len(content.split('\n')),
                hash_signature=hashlib.md5(content.encode()).hexdigest(),
                importance_level=MetamorphPriority.HIGH,
                last_modified=datetime.now(),
                description=f"{category} - Vue Component",
                dependencies=[]
            )
            
            self.code_fragments[fragment_id] = fragment
    
    def _extract_js_fragments(self, file_path: str, content: str, category: str):
        """Estrae frammenti JavaScript essenziali"""
        # Estrai funzioni e configurazioni principali
        function_pattern = r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))'
        
        for match in re.finditer(function_pattern, content):
            func_name = match.group(1) or match.group(2)
            if func_name:
                fragment_id = f"{file_path}::{func_name}"
                
                fragment = CodeFragment(
                    file_path=file_path,
                    function_name=func_name,
                    start_line=content[:match.start()].count('\n') + 1,
                    end_line=content[:match.start()].count('\n') + 10,
                    hash_signature=hashlib.md5(match.group(0).encode()).hexdigest(),
                    importance_level=self._determine_importance(func_name, category),
                    last_modified=datetime.now(),
                    description=f"{category} - JS Function: {func_name}",
                    dependencies=[]
                )
                
                self.code_fragments[fragment_id] = fragment
    
    def _determine_importance(self, name: str, category: str) -> MetamorphPriority:
        """Determina l'importanza di un frammento di codice"""
        critical_keywords = ['init', 'main', 'core', 'essential', 'critical']
        high_keywords = ['api', 'endpoint', 'service', 'handler']
        
        name_lower = name.lower()
        
        if any(keyword in name_lower for keyword in critical_keywords):
            return MetamorphPriority.CRITICAL
        elif any(keyword in name_lower for keyword in high_keywords):
            return MetamorphPriority.HIGH
        elif category in ['rth_core_modules', 'api_endpoints']:
            return MetamorphPriority.HIGH
        else:
            return MetamorphPriority.MEDIUM
    
    def _extract_dependencies(self, node: ast.AST) -> List[str]:
        """Estrae le dipendenze di un nodo AST"""
        dependencies = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    dependencies.append(alias.name)
            elif isinstance(child, ast.ImportFrom):
                if child.module:
                    dependencies.append(child.module)
        
        return list(set(dependencies))
    
    async def monitor_system_health(self) -> Dict[str, Any]:
        """Monitora la salute generale del sistema"""
        logger.info("[METAMORPH] Avvio monitoraggio salute sistema...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "system_status": "healthy",
            "monitored_fragments": len(self.code_fragments),
            "active_tasks": len(self.active_tasks),
            "quality_score": self._calculate_system_quality(),
            "alerts": [],
            "recommendations": []
        }
        
        # Verifica integritÃ  frammenti critici
        critical_fragments = [f for f in self.code_fragments.values() 
                            if f.importance_level == MetamorphPriority.CRITICAL]
        
        for fragment in critical_fragments:
            if not Path(fragment.file_path).exists():
                health_report["alerts"].append({
                    "level": "critical",
                    "message": f"File critico mancante: {fragment.file_path}",
                    "fragment": fragment.function_name
                })
                health_report["system_status"] = "degraded"
        
        # Genera raccomandazioni
        if health_report["quality_score"] < 0.8:
            health_report["recommendations"].append(
                "QualitÃ  del sistema sotto soglia ottimale - Revisione codice consigliata"
            )
        
        return health_report
    
    def _calculate_system_quality(self) -> float:
        """Calcola un punteggio di qualitÃ  del sistema"""
        if not self.code_fragments:
            return 0.0
        
        # Fattori di qualitÃ 
        factors = {
            "fragment_integrity": 0.4,  # IntegritÃ  frammenti
            "dependency_health": 0.3,   # Salute dipendenze  
            "code_freshness": 0.2,      # Freschezza codice
            "documentation": 0.1        # Documentazione
        }
        
        scores = {}
        
        # IntegritÃ  frammenti
        existing_fragments = sum(1 for f in self.code_fragments.values() 
                               if Path(f.file_path).exists())
        scores["fragment_integrity"] = existing_fragments / len(self.code_fragments)
        
        # Salute dipendenze (semplificata)
        scores["dependency_health"] = 0.85  # Placeholder
        
        # Freschezza codice
        now = datetime.now()
        recent_modifications = sum(1 for f in self.code_fragments.values()
                                 if (now - f.last_modified).days < 30)
        scores["code_freshness"] = min(1.0, recent_modifications / len(self.code_fragments) * 2)
        
        # Documentazione (semplificata)
        scores["documentation"] = 0.75  # Placeholder
        
        # Calcola punteggio finale
        final_score = sum(scores[factor] * weight for factor, weight in factors.items())
        
        return round(final_score, 3)
    
    async def orchestrate_development_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrare una richiesta di sviluppo"""
        logger.info(f"[METAMORPH] Orchestrazione richiesta: {request.get('description', 'N/A')}")
        
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Analizza la richiesta
        analysis = await self._analyze_development_request(request)
        
        # Crea task
        task = MetamorphTask(
            task_id=task_id,
            action=MetamorphAction.ORCHESTRATE,
            priority=MetamorphPriority(request.get('priority', 'medium')),
            description=request.get('description', ''),
            target_files=request.get('target_files', []),
            created_at=datetime.now()
        )
        
        self.active_tasks[task_id] = task
        
        # Genera piano di implementazione
        implementation_plan = self._generate_implementation_plan(request, analysis)
        
        response = {
            "task_id": task_id,
            "status": "orchestrated",
            "analysis": analysis,
            "implementation_plan": implementation_plan,
            "estimated_complexity": analysis.get("complexity", "medium"),
            "affected_components": analysis.get("affected_components", []),
            "recommendations": analysis.get("recommendations", [])
        }
        
        # Salva stato
        await self._save_metamorph_state()
        
        return response
    
    async def _analyze_development_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Analizza una richiesta di sviluppo"""
        description = request.get('description', '').lower()
        target_files = request.get('target_files', [])
        
        analysis = {
            "complexity": "medium",
            "affected_components": [],
            "dependencies": [],
            "risks": [],
            "recommendations": []
        }
        
        # Analizza complessitÃ  basata su keywords
        if any(word in description for word in ['new', 'create', 'build']):
            analysis["complexity"] = "high"
        elif any(word in description for word in ['fix', 'update', 'modify']):
            analysis["complexity"] = "medium"
        elif any(word in description for word in ['style', 'color', 'text']):
            analysis["complexity"] = "low"
        
        # Identifica componenti coinvolti
        for file_path in target_files:
            if 'core' in file_path:
                analysis["affected_components"].append("core_system")
                analysis["complexity"] = "high"
            elif 'api' in file_path:
                analysis["affected_components"].append("api_layer")
            elif 'frontend' in file_path:
                analysis["affected_components"].append("frontend")
        
        # Genera raccomandazioni
        if "core_system" in analysis["affected_components"]:
            analysis["recommendations"].append(
                "Modifica al sistema core - Backup consigliato prima dell'implementazione"
            )
        
        if analysis["complexity"] == "high":
            analysis["recommendations"].append(
                "ComplessitÃ  alta - Implementazione graduale consigliata"
            )
        
        return analysis
    
    def _generate_implementation_plan(self, request: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Genera un piano di implementazione strutturato"""
        plan = []
        
        # Step 1: Preparazione
        plan.append({
            "step": 1,
            "phase": "preparation",
            "description": "Backup del codice esistente e analisi dipendenze",
            "estimated_time": "5 minuti",
            "critical": True
        })
        
        # Step 2: Implementazione core
        if "core_system" in analysis.get("affected_components", []):
            plan.append({
                "step": 2,
                "phase": "core_implementation", 
                "description": "Modifica componenti core del sistema",
                "estimated_time": "15-30 minuti",
                "critical": True
            })
        
        # Step 3: Implementazione feature
        plan.append({
            "step": len(plan) + 1,
            "phase": "feature_implementation",
            "description": f"Implementazione: {request.get('description', 'N/A')}",
            "estimated_time": "10-20 minuti",
            "critical": False
        })
        
        # Step 4: Testing
        plan.append({
            "step": len(plan) + 1,
            "phase": "testing",
            "description": "Test funzionalitÃ  e verifica integritÃ  sistema",
            "estimated_time": "10 minuti",
            "critical": True
        })
        
        # Step 5: Finalizzazione
        plan.append({
            "step": len(plan) + 1,
            "phase": "finalization",
            "description": "Aggiornamento documentazione e commit",
            "estimated_time": "5 minuti",
            "critical": False
        })
        
        return plan
    
    async def preserve_essential_code(self, file_paths: List[str]) -> Dict[str, Any]:
        """Preserva il codice essenziale specificato"""
        logger.info(f"[METAMORPH] Preservazione codice essenziale: {len(file_paths)} file")
        
        preservation_report = {
            "timestamp": datetime.now().isoformat(),
            "preserved_files": [],
            "failed_files": [],
            "total_fragments": 0
        }
        
        for file_path in file_paths:
            try:
                full_path = Path(file_path)
                if full_path.exists():
                    if self.diskless or not self.metamorph_storage:
                        with open(full_path, 'r', encoding='utf-8') as src:
                            content = src.read()
                        # Aggiorna frammenti monitorati
                        self._analyze_file(str(full_path), "preserved")
                        preservation_report["preserved_files"].append({
                            "file": str(file_path),
                            "backup": None,
                            "size": len(content),
                            "diskless": True
                        })
                        continue
                    # Crea backup
                    backup_path = self.metamorph_storage / "backups" / f"{full_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(full_path, 'r', encoding='utf-8') as src:
                        content = src.read()
                    
                    with open(backup_path, 'w', encoding='utf-8') as dst:
                        dst.write(content)
                    
                    # Aggiorna frammenti monitorati
                    self._analyze_file(str(full_path), "preserved")
                    
                    preservation_report["preserved_files"].append({
                        "file": str(file_path),
                        "backup": str(backup_path),
                        "size": len(content)
                    })
                    
                else:
                    preservation_report["failed_files"].append({
                        "file": str(file_path),
                        "reason": "File non trovato"
                    })
                    
            except Exception as e:
                preservation_report["failed_files"].append({
                    "file": str(file_path),
                    "reason": str(e)
                })
        
        preservation_report["total_fragments"] = len(self.code_fragments)
        
        # Salva stato
        await self._save_metamorph_state()
        
        return preservation_report
    
    async def suggest_improvements(self, target_area: str = "all") -> List[Dict[str, Any]]:
        """Suggerisce miglioramenti per il sistema"""
        logger.info(f"[METAMORPH] Generazione suggerimenti per: {target_area}")
        
        suggestions = []
        
        # Analizza qualitÃ  del codice
        quality_score = self._calculate_system_quality()
        
        if quality_score < 0.9:
            suggestions.append({
                "type": "quality",
                "priority": "high",
                "title": "Miglioramento QualitÃ  Sistema",
                "description": f"QualitÃ  attuale: {quality_score:.1%}. Consigliata revisione generale.",
                "action": "code_review",
                "estimated_effort": "2-4 ore"
            })
        
        # Analizza frammenti obsoleti
        now = datetime.now()
        old_fragments = [f for f in self.code_fragments.values() 
                        if (now - f.last_modified).days > 90]
        
        if old_fragments:
            suggestions.append({
                "type": "maintenance",
                "priority": "medium", 
                "title": "Aggiornamento Codice Obsoleto",
                "description": f"{len(old_fragments)} frammenti non modificati da oltre 90 giorni",
                "action": "code_refresh",
                "estimated_effort": "1-2 ore"
            })
        
        # Suggerimenti specifici per area
        if target_area == "frontend" or target_area == "all":
            suggestions.append({
                "type": "optimization",
                "priority": "low",
                "title": "Ottimizzazione Frontend",
                "description": "Implementazione lazy loading e ottimizzazione bundle",
                "action": "performance_optimization",
                "estimated_effort": "3-5 ore"
            })
        
        if target_area == "backend" or target_area == "all":
            suggestions.append({
                "type": "enhancement",
                "priority": "medium",
                "title": "Potenziamento API",
                "description": "Implementazione caching e rate limiting avanzato",
                "action": "api_enhancement", 
                "estimated_effort": "2-3 ore"
            })
        
        return suggestions
    
    async def _save_metamorph_state(self):
        """Salva lo stato corrente di RTH Metamorph"""
        if self.diskless or not self.metamorph_storage:
            return
        try:
            # Salva memoria sistema
            memory_file = self.metamorph_storage / "system_memory.json"
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.system_memory, f, indent=2, ensure_ascii=False)
            
            # Salva frammenti di codice
            fragments_file = self.metamorph_storage / "code_fragments.json"
            fragments_data = {}
            for frag_id, fragment in self.code_fragments.items():
                frag_dict = asdict(fragment)
                frag_dict['last_modified'] = fragment.last_modified.isoformat()
                frag_dict['importance_level'] = fragment.importance_level.value
                fragments_data[frag_id] = frag_dict
            
            with open(fragments_file, 'w', encoding='utf-8') as f:
                json.dump(fragments_data, f, indent=2, ensure_ascii=False)
            
            # Salva tasks attivi
            tasks_file = self.metamorph_storage / "active_tasks.json"
            tasks_data = {}
            for task_id, task in self.active_tasks.items():
                task_dict = asdict(task)
                task_dict['created_at'] = task.created_at.isoformat()
                task_dict['action'] = task.action.value
                task_dict['priority'] = task.priority.value
                tasks_data[task_id] = task_dict
            
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"[METAMORPH] Errore salvataggio stato: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Restituisce lo stato completo del sistema RTH Metamorph"""
        health_report = await self.monitor_system_health()
        
        status = {
            "metamorph_info": {
                "version": self.version,
                "essence_name": self.essence_name,
                "creator_essence": self.creator_essence,
                "initialized_at": datetime.now().isoformat()
            },
            "system_health": health_report,
            "monitored_components": {
                "total_fragments": len(self.code_fragments),
                "critical_fragments": len([f for f in self.code_fragments.values() 
                                         if f.importance_level == MetamorphPriority.CRITICAL]),
                "active_tasks": len(self.active_tasks)
            },
            "capabilities": [
                "Code Preservation",
                "System Monitoring", 
                "Development Orchestration",
                "Quality Analysis",
                "Improvement Suggestions",
                "Intelligent Repair"
            ]
        }
        
        return status

# Istanza globale di RTH Metamorph
metamorph_instance = None

def get_metamorph() -> RTHMetamorph:
    """Restituisce l'istanza globale di RTH Metamorph"""
    global metamorph_instance
    if metamorph_instance is None:
        metamorph_instance = RTHMetamorph()
    return metamorph_instance

# Funzioni di utilitÃ  per l'integrazione
async def preserve_code(file_paths: List[str]) -> Dict[str, Any]:
    """Preserva il codice specificato"""
    metamorph = get_metamorph()
    return await metamorph.preserve_essential_code(file_paths)

async def orchestrate_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrare una richiesta di sviluppo"""
    metamorph = get_metamorph()
    return await metamorph.orchestrate_development_request(request)

async def get_system_health() -> Dict[str, Any]:
    """Ottieni report salute sistema"""
    metamorph = get_metamorph()
    return await metamorph.monitor_system_health()

async def suggest_system_improvements(area: str = "all") -> List[Dict[str, Any]]:
    """Ottieni suggerimenti di miglioramento"""
    metamorph = get_metamorph()
    return await metamorph.suggest_improvements(area)

if __name__ == "__main__":
    # Test di RTH Metamorph
    async def test_metamorph():
        print("ðŸŒŸ Test RTH Metamorphâ„¢ - Il Custode del Codice Vivente")
        
        metamorph = get_metamorph()
        
        # Test monitoraggio sistema
        health = await metamorph.monitor_system_health()
        print(f"ðŸ“Š Salute Sistema: {health['system_status']}")
        print(f"ðŸ“ˆ QualitÃ : {health['quality_score']:.1%}")
        
        # Test suggerimenti
        suggestions = await metamorph.suggest_improvements()
        print(f"ðŸ’¡ Suggerimenti: {len(suggestions)}")
        
        # Test orchestrazione
        test_request = {
            "description": "Aggiornare pagina contatti con nuovo design",
            "priority": "medium",
            "target_files": ["frontend/src/views/ContattiView.vue"]
        }
        
        orchestration = await metamorph.orchestrate_development_request(test_request)
        print(f"ðŸŽ¯ Orchestrazione: {orchestration['status']}")
        
        print("âœ… Test RTH Metamorph completato!")
    
    # Esegui test
    asyncio.run(test_metamorph()) 




