(function () {
  const $ = (id) => document.getElementById(id);
  const API = {
    health: "/api/v1/health",
    modelsStatus: "/api/v1/models/status",
    providers: "/api/v1/models/providers",
    providerUpsert: "/api/v1/models/providers/upsert",
    providerDelete: "/api/v1/models/providers/delete",
    providerTest: "/api/v1/models/providers/test",
    catalog: "/api/v1/models/catalog",
    routingPolicy: "/api/v1/models/routing-policy",
    presetApply: "/api/v1/models/presets/apply",
    routeExplain: "/api/v1/models/route/explain",
    chatSim: "/api/v1/models/chat/simulate",
    chatRun: "/api/v1/models/chat/run",
    villagePlan: "/api/v1/models/village/plan",
    villageRun: "/api/v1/models/village/run",
    pluginsStatus: "/api/v1/plugins/status",
    pluginsCatalog: "/api/v1/plugins/catalog",
    pluginsMatrix: "/api/v1/plugins/compatibility-matrix",
    pluginsSchema: "/api/v1/plugins/schema",
    pluginsValidate: "/api/v1/plugins/validate",
    pluginsRegister: "/api/v1/plugins/register",
    pluginsHealthcheck: "/api/v1/plugins/healthcheck",
    pluginsHealthcheckBatch: "/api/v1/plugins/healthcheck/batch",
    pluginsStateSet: "/api/v1/plugins/state/set",
    pluginsDriverAction: "/api/v1/plugins/driver/action",
    secretsStatus: "/api/v1/secrets/status",
    secretsSet: "/api/v1/secrets/set",
    secretsDelete: "/api/v1/secrets/delete",
    secretsRotate: "/api/v1/secrets/rotate",
    secretsResolve: "/api/v1/secrets/resolve",
    secretsExport: "/api/v1/secrets/export",
    secretsImport: "/api/v1/secrets/import",
    secretsAudit: "/api/v1/secrets/audit",
    telegramStatus: "/api/v1/jarvis/telegram/status",
    telegramReplay: "/api/v1/jarvis/telegram/replay",
    whatsappStatus: "/api/v1/jarvis/whatsapp/status",
    whatsappReplay: "/api/v1/jarvis/whatsapp/replay",
    mailStatus: "/api/v1/jarvis/mail/status",
    mailReplay: "/api/v1/jarvis/mail/replay",
    guardianPolicy: "/api/v1/jarvis/policy",
    guardianSeverity: "/api/v1/jarvis/guardian/severity",
    guardianReqs: "/api/v1/jarvis/permissions",
    roboticsEStop: "/api/v1/jarvis/robotics/emergency-stop",
    vehicleELand: "/api/v1/jarvis/vehicle/emergency-land",
    kgQuery: "/api/v1/jarvis/kg/query",
    governanceLedger: "/api/v1/jarvis/governance",
  };

  const state = {
    tasks: ["chat_general", "coding", "planning", "research", "summarization", "vision", "verification", "tool_calling"],
    providers: [],
    catalog: [],
    routingPolicy: null,
    pluginsCatalog: [],
    pluginsMatrix: null,
    lastSecretExportBundle: null,
    overview: null,
    uiMode: "guided",
    uiRole: "owner",
    uiLang: "en",
    pendingRequests: 0,
    wizard: { caseId: "chat_first_run", steps: [], currentIndex: 0, statusById: {} },
  };

  const TASK_LABELS = {
    chat_general: "Chat generale",
    coding: "Coding / sviluppo",
    planning: "Pianificazione",
    research: "Ricerca",
    summarization: "Sintesi",
    vision: "Visione / immagini",
    verification: "Verifica",
    tool_calling: "Tool use / automazioni",
  };
  const PRIVACY_LABELS = {
    allow_cloud: "Cloud consentito",
    local_preferred: "Locale preferito",
    local_only: "Solo locale",
  };
  const DIFFICULTY_LABELS = {
    normal: "Normale",
    hard: "Difficile",
    expert: "Esperto",
  };
  const TASK_LABELS_EN = {
    chat_general: "General chat",
    coding: "Coding / development",
    planning: "Planning",
    research: "Research",
    summarization: "Summarization",
    vision: "Vision / images",
    verification: "Verification",
    tool_calling: "Tool use / automation",
  };
  const PRIVACY_LABELS_EN = {
    allow_cloud: "Cloud allowed",
    local_preferred: "Local preferred",
    local_only: "Local only",
  };
  const DIFFICULTY_LABELS_EN = {
    normal: "Normal",
    hard: "Hard",
    expert: "Expert",
  };
  const ROLE_LABELS = {
    owner: "Owner",
    operator: "Operatore",
    tech: "Tecnico",
  };
  const I18N = {
    it: {
      language_name: "Italiano",
      label_language: "Lingua",
      label_role: "Ruolo",
      label_ui_mode: "Modalita UI",
      role_owner: "Owner",
      role_operator: "Operatore",
      role_tech: "Tecnico",
      ui_mode_guided: "Assistita",
      ui_mode_advanced: "Avanzata",
      topbar_subtitle: "Assistente governato + controllo modelli (v0)",
      topbar_tour: "Guida rapida",
      tab_overview: "Inizia",
      tab_wizard: "Wizard",
      tab_chat: "Chat",
      tab_providers: "Modelli",
      tab_routing: "Routing",
      tab_village: "Villaggio AI",
      tab_plugins: "Integrazioni",
      tab_secrets: "Segreti + Test",
      tab_guardian: "Guardian",
      notify_ui_guided: "Modalita assistita attiva: nasconde opzioni avanzate.",
      notify_ui_advanced: "Modalita avanzata attiva: mostra tutti i controlli.",
      notify_ui_role: "Vista ruolo: {role}.",
      notify_error_operation: "Operazione fallita",
      notify_error_http: "Errore {status} su {path}",
      notify_tour: "Usa checklist e azioni rapide per iniziare.",
      notify_provider_saved: "Provider salvato e stato aggiornato.",
      notify_routing_preset: "Preset {preset} applicato.",
      notify_chat_done: "Chat live completata ({meta}).",
      notify_village_done: "Villaggio AI completato con {count} ruoli.",
      notify_plugin_action: "Plugin {plugin}: {action} completato.",
      notify_secret_saved: "Secret salvato: {name}",
      notify_secret_rotated: "Secret ruotato: {name}",
      notify_secret_deleted: "Secret eliminato: {name}",
      notify_guardian_set: "Guardian impostato su {severity}.",
      notify_quick_cloud: "Template cloud provider caricato nel form provider.",
      notify_quick_local: "Template provider locale caricato nel form provider.",
      notify_quick_chat: "Chat pronta con prompt iniziale.",
      notify_quick_village: "Villaggio AI pronto con prompt iniziale.",
      notify_quick_plugins: "Batch healthcheck P0 completato.",
      notify_quick_guardian: "Stato Guardian aggiornato.",
      notify_quick_channels: "Tab test canali aperto (replay sicuro).",
      notify_quick_desktop: "Wizard desktop shell aperto.",
      notify_wizard_loaded: "Wizard caricato: {title}",
      notify_wizard_step_done: "Passo wizard completato: {title}",
      overview_title: "Avvio Guidato",
      overview_hint: "Questa schermata e' pensata per partire senza conoscere i dettagli tecnici. Segui la checklist e usa le azioni rapide.",
      overview_refresh: "Aggiorna stato",
      overview_checklist: "Checklist di avvio",
      overview_quick: "Azioni rapide",
      quick_setup_cloud: "Configura Cloud Provider",
      quick_setup_local: "Configura Provider Locale",
      quick_start_chat: "Apri chat guidata",
      quick_start_village: "Apri Villaggio AI",
      quick_check_plugins: "Controlla plugin P0",
      quick_guardian: "Controlla Guardian",
      quick_channels_replay: "Test canali (replay)",
      quick_desktop_shell: "Desktop Shell",
      checklist_api_title: "API attiva",
      checklist_api_ok: "Backend raggiungibile.",
      checklist_api_missing: "Avvia API con python scripts\\\\rth.py api start",
      checklist_provider_title: "Provider configurato",
      checklist_provider_ok: "Almeno un provider e' pronto.",
      checklist_provider_missing: "Configura un provider (cloud o locale).",
      checklist_catalog_title: "Catalogo modelli",
      checklist_catalog_ok: "{count} modelli rilevati.",
      checklist_catalog_missing: "Esegui test provider o ricarica catalogo.",
      checklist_guardian_title: "Guardian configurato",
      checklist_guardian_ok: "Severita attuale: {severity}.",
      checklist_guardian_missing: "Controlla il tab Guardian.",
      checklist_channels_title: "Canali remoti",
      checklist_channels_desc: "Configurati {count}/3 (Telegram, Mail, WhatsApp).",
      checklist_secrets_title: "Secret store",
      checklist_secrets_ok: "Mode: {mode}.",
      checklist_secrets_missing: "Apri Segreti + Test.",
      common_ok: "OK",
      common_todo: "TODO",
      common_na: "n/a",
      common_not_reachable: "non raggiungibile",
      label_privacy: "Privacy",
      label_budget: "Budget",
      label_roles_csv: "Ruoli (CSV)",
      label_mode: "Mode",
      label_max_roles: "Max roles",
      label_task: "Task",
      label_difficulty: "Difficolta",
      api_ok_summary: "API OK - provider {enabled}/{total} - modelli {models}",
      api_error_summary: "API non raggiungibile",
      status_models_title: "Modelli",
      status_models_small: "provider attivi - modelli {count}",
      status_plugins_title: "Plugin",
      status_plugins_small: "abilitati - catalogo {count}",
      status_secrets_title: "Segreti",
      status_channels_title: "Canali",
      status_channels_small: "tg:{tg} mail:{mail} wa:{wa}",
      status_guardian_small: "regole {enabled}/{total} - mode {mode}",
      wizard_title: "Wizard End-to-End per Use Case",
      wizard_hint: "Scegli un obiettivo e segui i passi guidati. Il wizard ti porta ai tab giusti, precompila i campi e fa i controlli minimi.",
      wizard_case_chat: "Voglio chattare (prima configurazione)",
      wizard_case_telegram: "Voglio collegare Telegram",
      wizard_case_plugin_ide: "Voglio usare plugin IDE (Cursor / Windsurf / Claude Code)",
      wizard_case_desktop: "Voglio usare Core Rth come app desktop",
      wizard_style: "Stile wizard",
      wizard_guided: "Guidato",
      wizard_checklist: "Checklist",
      wizard_current_step: "Passo corrente",
      wizard_load: "Carica wizard",
      wizard_prev: "Passo precedente",
      wizard_next: "Passo successivo",
      wizard_run_step: "Esegui passo",
      chat_title: "Chat Operatore (simulazione o live)",
      chat_hint: "Usa questa chat per lavorare con un singolo modello scelto automaticamente. Per confronto tra piu' ruoli/modelli usa il tab Villaggio AI.",
      chat_btn_sim: "Simula Chat",
      chat_btn_live: "Esegui Live",
      chat_btn_explain: "Solo Route Explain",
      village_title: "Villaggio AI (planning + live)",
      village_hint: "Avvia piu' ruoli in parallelo (ricerca, critica, verifica, strategia) e ottieni una sintesi unica. Utile per decisioni e brainstorming.",
      village_btn_plan: "Genera piano",
      village_btn_run: "Esegui Village Live",
      providers_title: "Provider Modelli (cloud/locali)",
      providers_hint: "Configura qui i provider (Cloud Provider, OpenAI-compatible, Ollama, Runtime Locali, ecc.). Se sei all'inizio usa un solo provider e fai un test prima di aggiungerne altri.",
      providers_btn_save: "Salva provider",
      providers_btn_test: "Test",
      providers_btn_reload: "Ricarica",
      providers_no_configured: "Nessun provider configurato.",
      providers_btn_fill_form: "Carica nel form",
      providers_btn_delete: "Elimina",
      providers_models_none: "nessuno",
      providers_base_none: "(nessun base_url)",
      providers_local_suffix: "locale",
      routing_title: "Routing Matrix (avanzato)",
      routing_hint: "Questa sezione decide quale modello usare per ogni tipo di task. Se non sai cosa impostare, applica un preset e verifica il risultato in Chat.",
      routing_btn_save: "Salva routing policy",
      routing_btn_reload: "Ricarica",
      routing_not_loaded: "Routing policy non caricata.",
      routing_field_primary: "Primario",
      routing_field_fallbacks: "Fallback (CSV)",
      routing_field_privacy: "Privacy",
      routing_field_max_cost: "Costo max",
      routing_field_reasoning: "Reasoning",
      plugins_title: "Integrazioni / Plugin Ecosystem",
      plugins_hint: "Qui gestisci i connettori verso software esterni. Parti dal batch healthcheck P0, poi abilita solo cio' che serve davvero.",
      plugins_btn_registry_status: "Stato registry",
      plugins_btn_catalog: "Catalogo",
      plugins_btn_matrix: "Compatibility Matrix",
      plugins_btn_schema: "Schema",
      plugins_btn_batch_p0: "Batch Healthcheck P0",
      plugins_btn_batch_filtered: "Batch Healthcheck Filtri",
      plugins_btn_preset_workflow: "Workflow Builders",
      plugins_btn_preset_workflow_enabled: "Workflow + Enabled",
      plugins_btn_preset_workflow_p0: "Workflow P0",
      plugins_btn_batch_workflow: "Batch HC Workflow",
      plugins_btn_batch_workflow_enabled: "Batch HC Workflow + Enabled",
      plugins_btn_batch_workflow_p0: "Batch HC Workflow P0",
      plugins_btn_filters_reset: "Reset Filtri",
      plugins_filter_category: "Filtro categoria",
      plugins_filter_pack: "Filtro pack",
      plugins_filter_tier: "Filtro tier",
      plugins_filter_install_state: "Filtro stato install",
      plugins_filter_enabled_only: "solo enabled",
      plugins_filter_p0_only: "solo P0",
      plugins_manifest_title: "Manifest Validator / Register (avanzato)",
      plugins_manifest_label: "Manifest JSON (rth.plugin.v0)",
      plugins_btn_load_sample: "Carica sample",
      plugins_btn_validate: "Valida",
      plugins_btn_register: "Registra (Guardian)",
      plugins_no_filtered: "Nessun plugin con i filtri attuali.",
      plugins_no_catalog: "Nessun plugin in catalogo.",
      plugins_btn_install: "Install",
      plugins_btn_healthcheck: "Healthcheck",
      plugins_btn_enable: "Enable",
      plugins_btn_disable: "Disable",
      plugins_btn_load_manifest: "Load Manifest",
      plugins_label_apps: "apps",
      plugins_label_caps: "capabilities",
      plugins_label_pack: "pack",
      plugins_label_priority: "priority",
      plugins_label_install: "install",
      plugins_label_health: "health",
      plugins_label_enabled: "abilitato",
      plugins_label_disabled: "disabilitato",
      plugins_status_not_configured: "non_configured",
      plugins_manifest_empty: "Manifest JSON vuoto",
      guardian_title: "Guardian / Governance",
      guardian_hint: "Guardian controlla permessi e sicurezza. Per uso normale: balanced. Se vuoi piu' protezione: strict o paranoid.",
      guardian_label_severity: "Severita' Guardian",
      guardian_label_reason: "Motivo cambio policy",
      guardian_btn_apply: "Applica Severita'",
      guardian_btn_status: "Severity Status",
      guardian_btn_policy: "Policy Status",
      guardian_btn_reqs: "Permission Requests",
      guardian_btn_gate: "Gate Audit (allow-empty)",
      secrets_title: "Segreti + Channel Replay",
      secrets_hint: "Gestisci chiavi e password in modo centralizzato e prova i canali in replay senza usare rete o credenziali reali.",
      secrets_btn_status: "Secrets Status",
      secrets_btn_audit: "Secrets Audit",
      secrets_btn_export_meta: "Export Meta",
      secrets_btn_export_values: "Export Values (enc)",
      secrets_label_name: "Nome secret",
      secrets_label_value: "Valore secret",
      secrets_label_reason: "Motivo",
      secrets_btn_set: "Set",
      secrets_btn_rotate: "Rotate (mantieni prec.)",
      secrets_btn_delete: "Delete",
      secrets_btn_resolve: "Resolve (masked)",
      secrets_bundle_label: "Export / Import bundle JSON",
      secrets_import_values: "importa valori",
      secrets_on_conflict: "Su conflitto",
      secrets_btn_import: "Import Bundle",
      secrets_bundle_empty: "Bundle JSON vuoto",
      channels_replay_title: "Channel Replay (no credenziali, no rete)",
      channels_label_channel: "Canale",
      channels_label_preset_cmd: "Preset comando",
      channels_label_mail_cmd: "Mail cmd (se channel=mail)",
      channels_label_replay_text: "Replay text / helper payload",
      channels_label_tg_chat: "Telegram chat_id",
      channels_label_wa_from: "WhatsApp from",
      channels_label_mail_from: "Mail from",
      channels_btn_run_replay: "Run Replay",
      channels_btn_tg_status: "Telegram Status",
      channels_btn_wa_status: "WhatsApp Status",
      channels_btn_mail_status: "Mail Status",
      channels_preset_custom: "custom",
      village_no_data: "Nessun dato village.",
      chat_no_reply: "(nessuna risposta)",
      chat_no_preview: "(nessuna anteprima)",
      chat_no_model: "nessun modello",
      chat_selected_prefix: "selezionato",
      wizard_recommended_role: "Ruolo consigliato",
      wizard_progress: "Progresso",
      wizard_completed_steps: "passi completati",
      wizard_current: "corrente",
      wizard_action: "azione",
      wizard_manual: "manuale",
      trace_chat_sim: "Simulazione chat",
      trace_chat_run: "Chat live",
      trace_candidate: "Candidato",
      trace_synthesis: "Sintesi",
      trace_stage_plan: "Piano",
      trace_stage_run: "Esecuzione",
      trace_stage_synth: "Sintesi",
      trace_field_model: "modello",
      trace_field_provider: "provider",
      trace_field_privacy: "privacy",
      trace_field_latency: "latenza",
      trace_field_cost: "costo stimato",
      trace_field_task: "task",
      trace_field_status: "stato",
      trace_field_reason: "motivo",
      trace_field_score: "score",
      trace_field_cost_est: "costo stimato",
      trace_field_route: "route",
      trace_field_mode: "mode",
      trace_field_roles: "ruoli",
      trace_field_roles_ok: "Ruoli OK",
      trace_field_latency_total: "latenza cumulata (stimata)",
      ui_no_data: "Nessun dato.",
      ui_status_unavailable: "Stato non disponibile.",
    },
    en: {
      language_name: "English",
      label_language: "Language",
      label_role: "Role",
      label_ui_mode: "UI mode",
      role_owner: "Owner",
      role_operator: "Operator",
      role_tech: "Tech",
      ui_mode_guided: "Guided",
      ui_mode_advanced: "Advanced",
      topbar_subtitle: "Governed assistant + model control plane (v0)",
      topbar_tour: "Quick guide",
      tab_overview: "Start",
      tab_wizard: "Wizard",
      tab_chat: "Chat",
      tab_providers: "Models",
      tab_routing: "Routing",
      tab_village: "AI Village",
      tab_plugins: "Integrations",
      tab_secrets: "Secrets + Test",
      tab_guardian: "Guardian",
      notify_ui_guided: "Guided mode enabled: advanced options are hidden.",
      notify_ui_advanced: "Advanced mode enabled: all controls are visible.",
      notify_ui_role: "Role view: {role}.",
      notify_error_operation: "Operation failed",
      notify_error_http: "Error {status} on {path}",
      notify_tour: "Use the checklist and quick actions to get started.",
      notify_provider_saved: "Provider saved and state refreshed.",
      notify_routing_preset: "Preset {preset} applied.",
      notify_chat_done: "Live chat completed ({meta}).",
      notify_village_done: "AI Village completed with {count} roles.",
      notify_plugin_action: "Plugin {plugin}: {action} completed.",
      notify_secret_saved: "Secret saved: {name}",
      notify_secret_rotated: "Secret rotated: {name}",
      notify_secret_deleted: "Secret deleted: {name}",
      notify_guardian_set: "Guardian set to {severity}.",
      notify_quick_cloud: "Cloud provider template loaded into provider form.",
      notify_quick_local: "Local provider template loaded into provider form.",
      notify_quick_chat: "Chat prepared with starter prompt.",
      notify_quick_village: "AI Village prepared with starter prompt.",
      notify_quick_plugins: "P0 plugin batch healthcheck completed.",
      notify_quick_guardian: "Guardian status refreshed.",
      notify_quick_channels: "Channels test tab opened (safe replay).",
      notify_quick_desktop: "Desktop shell wizard opened.",
      notify_wizard_loaded: "Wizard loaded: {title}",
      notify_wizard_step_done: "Wizard step completed: {title}",
      overview_title: "Guided Start",
      overview_hint: "This screen is designed to get started without knowing technical details. Follow the checklist and use quick actions.",
      overview_refresh: "Refresh status",
      overview_checklist: "Startup checklist",
      overview_quick: "Quick actions",
      quick_setup_cloud: "Configure Cloud Provider",
      quick_setup_local: "Configure Local Provider",
      quick_start_chat: "Open guided chat",
      quick_start_village: "Open AI Village",
      quick_check_plugins: "Check P0 plugins",
      quick_guardian: "Check Guardian",
      quick_channels_replay: "Test channels (replay)",
      quick_desktop_shell: "Desktop Shell",
      checklist_api_title: "API running",
      checklist_api_ok: "Backend reachable.",
      checklist_api_missing: "Start API with python scripts\\\\rth.py api start",
      checklist_provider_title: "Provider configured",
      checklist_provider_ok: "At least one provider is ready.",
      checklist_provider_missing: "Configure a provider (cloud or local).",
      checklist_catalog_title: "Model catalog",
      checklist_catalog_ok: "{count} models detected.",
      checklist_catalog_missing: "Run provider test or reload catalog.",
      checklist_guardian_title: "Guardian configured",
      checklist_guardian_ok: "Current severity: {severity}.",
      checklist_guardian_missing: "Check the Guardian tab.",
      checklist_channels_title: "Remote channels",
      checklist_channels_desc: "{count}/3 configured (Telegram, Mail, WhatsApp).",
      checklist_secrets_title: "Secret store",
      checklist_secrets_ok: "Mode: {mode}.",
      checklist_secrets_missing: "Open Secrets + Test.",
      common_ok: "OK",
      common_todo: "TODO",
      common_na: "n/a",
      common_not_reachable: "not reachable",
      label_privacy: "Privacy",
      label_budget: "Budget",
      label_roles_csv: "Roles (CSV)",
      label_mode: "Mode",
      label_max_roles: "Max roles",
      label_task: "Task",
      label_difficulty: "Difficulty",
      api_ok_summary: "API OK - providers {enabled}/{total} - models {models}",
      api_error_summary: "API unreachable",
      status_models_title: "Models",
      status_models_small: "enabled providers - models {count}",
      status_plugins_title: "Plugins",
      status_plugins_small: "enabled - catalog {count}",
      status_secrets_title: "Secrets",
      status_channels_title: "Channels",
      status_channels_small: "tg:{tg} mail:{mail} wa:{wa}",
      status_guardian_small: "rules {enabled}/{total} - mode {mode}",
      wizard_title: "End-to-End Use Case Wizard",
      wizard_hint: "Choose a goal and follow guided steps. The wizard opens the right tabs, pre-fills fields and runs basic checks.",
      wizard_case_chat: "I want to chat (first setup)",
      wizard_case_telegram: "I want to connect Telegram",
      wizard_case_plugin_ide: "I want IDE plugins (Cursor / Windsurf / Claude Code)",
      wizard_case_desktop: "I want Core Rth as a desktop app",
      wizard_style: "Wizard style",
      wizard_guided: "Guided",
      wizard_checklist: "Checklist",
      wizard_current_step: "Current step",
      wizard_load: "Load wizard",
      wizard_prev: "Previous step",
      wizard_next: "Next step",
      wizard_run_step: "Run step",
      chat_title: "Operator Chat (simulation or live)",
      chat_hint: "Use this chat with a single model selected automatically. For multi-role/model comparison use the AI Village tab.",
      chat_btn_sim: "Simulate Chat",
      chat_btn_live: "Run Live",
      chat_btn_explain: "Route Explain Only",
      village_title: "AI Village (planning + live)",
      village_hint: "Run multiple roles in parallel (research, critique, verification, strategy) and get one final synthesis.",
      village_btn_plan: "Generate plan",
      village_btn_run: "Run AI Village Live",
      providers_title: "Model Providers (cloud/local)",
      providers_hint: "Configure providers here (Cloud Provider, OpenAI-compatible, Ollama, Local Runtimes, etc.). If you are starting, use one provider and test it before adding more.",
      providers_btn_save: "Save provider",
      providers_btn_test: "Test",
      providers_btn_reload: "Reload",
      providers_no_configured: "No providers configured.",
      providers_btn_fill_form: "Load into form",
      providers_btn_delete: "Delete",
      providers_models_none: "none",
      providers_base_none: "(no base_url)",
      providers_local_suffix: "local",
      routing_title: "Routing Matrix (advanced)",
      routing_hint: "This section decides which model is used for each task type. If unsure, apply a preset and validate the result in Chat.",
      routing_btn_save: "Save routing policy",
      routing_btn_reload: "Reload",
      routing_not_loaded: "Routing policy not loaded.",
      routing_field_primary: "Primary",
      routing_field_fallbacks: "Fallbacks (CSV)",
      routing_field_privacy: "Privacy",
      routing_field_max_cost: "Max cost",
      routing_field_reasoning: "Reasoning",
      plugins_title: "Integrations / Plugin Ecosystem",
      plugins_hint: "Manage connectors to external software here. Start with the P0 batch healthcheck, then enable only what you really need.",
      plugins_btn_registry_status: "Registry Status",
      plugins_btn_catalog: "Catalog",
      plugins_btn_matrix: "Compatibility Matrix",
      plugins_btn_schema: "Schema",
      plugins_btn_batch_p0: "P0 Batch Healthcheck",
      plugins_btn_batch_filtered: "Filtered Batch Healthcheck",
      plugins_btn_preset_workflow: "Workflow Builders",
      plugins_btn_preset_workflow_enabled: "Workflow + Enabled",
      plugins_btn_preset_workflow_p0: "Workflow P0",
      plugins_btn_batch_workflow: "Workflow Batch HC",
      plugins_btn_batch_workflow_enabled: "Workflow Batch HC + Enabled",
      plugins_btn_batch_workflow_p0: "Workflow Batch HC P0",
      plugins_btn_filters_reset: "Reset Filters",
      plugins_filter_category: "Category filter",
      plugins_filter_pack: "Pack filter",
      plugins_filter_tier: "Tier filter",
      plugins_filter_install_state: "Install state filter",
      plugins_filter_enabled_only: "enabled only",
      plugins_filter_p0_only: "P0 only",
      plugins_manifest_title: "Manifest Validator / Register (advanced)",
      plugins_manifest_label: "Manifest JSON (rth.plugin.v0)",
      plugins_btn_load_sample: "Load sample",
      plugins_btn_validate: "Validate",
      plugins_btn_register: "Register (Guardian)",
      plugins_no_filtered: "No plugins match current filters.",
      plugins_no_catalog: "No plugins in catalog.",
      plugins_btn_install: "Install",
      plugins_btn_healthcheck: "Healthcheck",
      plugins_btn_enable: "Enable",
      plugins_btn_disable: "Disable",
      plugins_btn_load_manifest: "Load Manifest",
      plugins_label_apps: "apps",
      plugins_label_caps: "capabilities",
      plugins_label_pack: "pack",
      plugins_label_priority: "priority",
      plugins_label_install: "install",
      plugins_label_health: "health",
      plugins_label_enabled: "enabled",
      plugins_label_disabled: "disabled",
      plugins_status_not_configured: "not_configured",
      plugins_manifest_empty: "Manifest JSON is empty",
      guardian_title: "Guardian / Governance",
      guardian_hint: "Guardian controls permissions and safety. For normal use: balanced. For stronger protection: strict or paranoid.",
      guardian_label_severity: "Guardian severity",
      guardian_label_reason: "Policy change reason",
      guardian_btn_apply: "Apply Severity",
      guardian_btn_status: "Severity Status",
      guardian_btn_policy: "Policy Status",
      guardian_btn_reqs: "Permission Requests",
      guardian_btn_gate: "Gate Audit (allow-empty)",
      secrets_title: "Secrets + Channel Replay",
      secrets_hint: "Manage keys/passwords centrally and test channels in replay without network or real credentials.",
      secrets_btn_status: "Secrets Status",
      secrets_btn_audit: "Secrets Audit",
      secrets_btn_export_meta: "Export Meta",
      secrets_btn_export_values: "Export Values (enc)",
      secrets_label_name: "Secret name",
      secrets_label_value: "Secret value",
      secrets_label_reason: "Reason",
      secrets_btn_set: "Set",
      secrets_btn_rotate: "Rotate (keep prev)",
      secrets_btn_delete: "Delete",
      secrets_btn_resolve: "Resolve (masked)",
      secrets_bundle_label: "Export / Import bundle JSON",
      secrets_import_values: "import values",
      secrets_on_conflict: "On conflict",
      secrets_btn_import: "Import Bundle",
      secrets_bundle_empty: "Bundle JSON is empty",
      channels_replay_title: "Channel Replay (no credentials, no network)",
      channels_label_channel: "Channel",
      channels_label_preset_cmd: "Preset command",
      channels_label_mail_cmd: "Mail cmd (if channel=mail)",
      channels_label_replay_text: "Replay text / payload helper",
      channels_label_tg_chat: "Telegram chat_id",
      channels_label_wa_from: "WhatsApp from",
      channels_label_mail_from: "Mail from",
      channels_btn_run_replay: "Run Replay",
      channels_btn_tg_status: "Telegram Status",
      channels_btn_wa_status: "WhatsApp Status",
      channels_btn_mail_status: "Mail Status",
      channels_preset_custom: "custom",
      village_no_data: "No village data.",
      chat_no_reply: "(no response)",
      chat_no_preview: "(no preview)",
      chat_no_model: "no model",
      chat_selected_prefix: "selected",
      wizard_recommended_role: "Recommended role",
      wizard_progress: "Progress",
      wizard_completed_steps: "completed steps",
      wizard_current: "current",
      wizard_action: "action",
      wizard_manual: "manual",
      trace_chat_sim: "Chat simulation",
      trace_chat_run: "Live chat",
      trace_candidate: "Candidate",
      trace_synthesis: "Synthesis",
      trace_stage_plan: "Plan",
      trace_stage_run: "Run",
      trace_stage_synth: "Synthesis",
      trace_field_model: "model",
      trace_field_provider: "provider",
      trace_field_privacy: "privacy",
      trace_field_latency: "latency",
      trace_field_cost: "estimated cost",
      trace_field_task: "task",
      trace_field_status: "status",
      trace_field_reason: "reason",
      trace_field_score: "score",
      trace_field_cost_est: "estimated cost",
      trace_field_route: "route",
      trace_field_mode: "mode",
      trace_field_roles: "roles",
      trace_field_roles_ok: "Roles OK",
      trace_field_latency_total: "cumulative latency (est.)",
      ui_no_data: "No data.",
      ui_status_unavailable: "Status unavailable.",
    },
  };

  function pretty(v) {
    return JSON.stringify(v, null, 2);
  }

  function currentLang() {
    return I18N[state.uiLang] ? state.uiLang : "it";
  }

  function t(key, vars = {}) {
    const lang = currentLang();
    const base = I18N[lang]?.[key] ?? I18N.it?.[key] ?? key;
    return String(base).replace(/\{([a-zA-Z0-9_]+)\}/g, (_m, k) => String(vars[k] ?? `{${k}}`));
  }

  function ltxt(it, en) {
    return currentLang() === "en" ? en : it;
  }

  function setText(selector, value) {
    const el = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (el) el.textContent = value;
  }

  function setHtml(selector, value) {
    const el = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (el) el.innerHTML = value;
  }

  function setPlaceholder(selector, value) {
    const el = typeof selector === "string" ? document.querySelector(selector) : selector;
    if (el) el.setAttribute("placeholder", value);
  }

  function setSelectOptionText(selectSelector, valueSelector, label) {
    const sel = document.querySelector(selectSelector);
    if (!sel) return;
    const opt = Array.from(sel.options).find((o) => o.value === valueSelector);
    if (opt) opt.textContent = label;
  }

  function setLabelLead(selector, text) {
    const el = document.querySelector(selector);
    if (!el || !el.childNodes || !el.childNodes.length) return;
    const node = Array.from(el.childNodes).find((n) => n.nodeType === Node.TEXT_NODE);
    if (node) node.nodeValue = `${text} `;
  }

  function applyLanguage(lang, opts = {}) {
    state.uiLang = I18N[lang] ? lang : "it";
    if ($("uiLang") && $("uiLang").value !== state.uiLang) $("uiLang").value = state.uiLang;
    document.documentElement.lang = state.uiLang;

    setText(".brand-copy p", t("topbar_subtitle"));
    setLabelLead(".topbar-actions label:nth-of-type(1)", t("label_language"));
    setLabelLead(".topbar-actions label:nth-of-type(2)", t("label_role"));
    setLabelLead(".topbar-actions label:nth-of-type(3)", t("label_ui_mode"));
    setText("#uiTour", t("topbar_tour"));
    setText('.tabs button[data-tab="overview"]', t("tab_overview"));
    setText('.tabs button[data-tab="wizard"]', t("tab_wizard"));
    setText('.tabs button[data-tab="chat"]', t("tab_chat"));
    setText('.tabs button[data-tab="providers"]', t("tab_providers"));
    setText('.tabs button[data-tab="routing"]', t("tab_routing"));
    setText('.tabs button[data-tab="village"]', t("tab_village"));
    setText('.tabs button[data-tab="plugins"]', t("tab_plugins"));
    setText('.tabs button[data-tab="secrets"]', t("tab_secrets"));
    setText('.tabs button[data-tab="guardian"]', t("tab_guardian"));

    setSelectOptionText("#uiRole", "owner", t("role_owner"));
    setSelectOptionText("#uiRole", "operator", t("role_operator"));
    setSelectOptionText("#uiRole", "tech", t("role_tech"));
    setSelectOptionText("#uiMode", "guided", t("ui_mode_guided"));
    setSelectOptionText("#uiMode", "advanced", t("ui_mode_advanced"));

    setText("#panel-overview h2", t("overview_title"));
    setText("#ovRefresh", t("overview_refresh"));
    setText('#panel-overview h3:nth-of-type(1)', t("overview_checklist"));
    setText('#panel-overview h3:nth-of-type(2)', t("overview_quick"));
    setText('#panel-overview .hint', t("overview_hint"));
    setText('[data-action="setup-cloud"]', t("quick_setup_cloud"));
    setText('[data-action="setup-local"]', t("quick_setup_local"));
    setText('[data-action="start-chat"]', t("quick_start_chat"));
    setText('[data-action="start-village"]', t("quick_start_village"));
    setText('[data-action="check-plugins"]', t("quick_check_plugins"));
    setText('[data-action="guardian-check"]', t("quick_guardian"));
    setText('[data-action="channels-replay"]', t("quick_channels_replay"));
    setText('[data-action="desktop-shell"]', t("quick_desktop_shell"));

    setText("#panel-wizard h2", t("wizard_title"));
    setText("#panel-wizard .hint", t("wizard_hint"));
    setLabelLead('#panel-wizard .grid label:nth-of-type(1)', state.uiLang === "en" ? "Use case" : "Use case");
    setLabelLead('#panel-wizard .grid label:nth-of-type(2)', t("wizard_style"));
    setLabelLead('#panel-wizard .grid label:nth-of-type(3)', t("wizard_current_step"));
    setSelectOptionText("#wCase", "chat_first_run", t("wizard_case_chat"));
    setSelectOptionText("#wCase", "connect_telegram", t("wizard_case_telegram"));
    setSelectOptionText("#wCase", "plugin_ide_setup", t("wizard_case_plugin_ide"));
    setSelectOptionText("#wCase", "desktop_shell", t("wizard_case_desktop"));
    setSelectOptionText("#wMode", "guided", t("wizard_guided"));
    setSelectOptionText("#wMode", "checklist", t("wizard_checklist"));
    setText("#wLoad", t("wizard_load"));
    setText("#wPrev", t("wizard_prev"));
    setText("#wNext", t("wizard_next"));
    setText("#wRunStep", t("wizard_run_step"));

    setText("#panel-chat h2", t("chat_title"));
    setText("#panel-chat .hint", t("chat_hint"));
    setText("#chatSend", t("chat_btn_sim"));
    setText("#chatSendLive", t("chat_btn_live"));
    setText("#chatExplain", t("chat_btn_explain"));
    setLabelLead('#panel-chat .row label:nth-of-type(1)', t("label_task"));
    setLabelLead('#panel-chat .row label:nth-of-type(2)', t("label_privacy"));
    setLabelLead('#panel-chat .row label:nth-of-type(3)', t("label_difficulty"));
    setSelectOptionText("#chatPrivacy", "allow_cloud", humanPrivacy("allow_cloud"));
    setSelectOptionText("#chatPrivacy", "local_preferred", humanPrivacy("local_preferred"));
    setSelectOptionText("#chatPrivacy", "local_only", humanPrivacy("local_only"));
    setSelectOptionText("#chatDifficulty", "normal", humanDifficulty("normal"));
    setSelectOptionText("#chatDifficulty", "hard", humanDifficulty("hard"));
    setSelectOptionText("#chatDifficulty", "expert", humanDifficulty("expert"));

    setText("#panel-village h2", t("village_title"));
    setText("#panel-village .hint", t("village_hint"));
    setText("#vPlan", t("village_btn_plan"));
    setText("#vRun", t("village_btn_run"));
    setLabelLead('#panel-village .grid:nth-of-type(1) label:nth-of-type(1)', t("label_privacy"));
    setLabelLead('#panel-village .grid:nth-of-type(1) label:nth-of-type(2)', t("label_budget"));
    setLabelLead('#panel-village .grid:nth-of-type(1) label:nth-of-type(3)', t("label_roles_csv"));
    setLabelLead('#panel-village .grid:nth-of-type(2) label:nth-of-type(1)', t("label_mode"));
    setLabelLead('#panel-village .grid:nth-of-type(2) label:nth-of-type(2)', t("label_max_roles"));

    setText("#panel-providers h2", t("providers_title"));
    setText("#panel-providers .hint", t("providers_hint"));
    setText("#providerSave", t("providers_btn_save"));
    setText("#providerTest", t("providers_btn_test"));
    setText("#providerReload", t("providers_btn_reload"));
    setLabelLead('#panel-providers .grid label:nth-of-type(1)', "Provider ID");
    setLabelLead('#panel-providers .grid label:nth-of-type(2)', "Label");
    setLabelLead('#panel-providers .grid label:nth-of-type(3)', state.uiLang === "en" ? "Type" : "Tipo");
    setLabelLead('#panel-providers .grid label:nth-of-type(4)', "Base URL");
    setLabelLead('#panel-providers .grid label:nth-of-type(5)', "API Key");
    setLabelLead('#panel-providers .grid label:nth-of-type(6)', state.uiLang === "en" ? "enabled" : "abilitato");
    setLabelLead('#panel-providers .grid label:nth-of-type(7)', state.uiLang === "en" ? "local endpoint" : "endpoint locale");
    setLabelLead('#panel-providers > label:nth-of-type(1)', state.uiLang === "en" ? "Models (one per line / CSV)" : "Modelli (uno per riga / CSV)");
    setLabelLead('#panel-providers > label:nth-of-type(2)', "Note");

    setText("#panel-routing h2", t("routing_title"));
    setText("#panel-routing .hint", t("routing_hint"));
    setText("#routingSave", t("routing_btn_save"));
    setText("#routingReload", t("routing_btn_reload"));

    setText("#panel-plugins h2", t("plugins_title"));
    setText("#panel-plugins .hint", t("plugins_hint"));
    setText("#plStatus", t("plugins_btn_registry_status"));
    setText("#plCatalog", t("plugins_btn_catalog"));
    setText("#plMatrix", t("plugins_btn_matrix"));
    setText("#plSchema", t("plugins_btn_schema"));
    setText("#plBatchP0", t("plugins_btn_batch_p0"));
    setText("#plBatchFiltered", t("plugins_btn_batch_filtered"));
    setText("#plPresetWorkflow", t("plugins_btn_preset_workflow"));
    setText("#plPresetWorkflowEnabled", t("plugins_btn_preset_workflow_enabled"));
    setText("#plPresetWorkflowP0", t("plugins_btn_preset_workflow_p0"));
    setText("#plBatchWorkflow", t("plugins_btn_batch_workflow"));
    setText("#plBatchWorkflowEnabled", t("plugins_btn_batch_workflow_enabled"));
    setText("#plBatchWorkflowP0", t("plugins_btn_batch_workflow_p0"));
    setText("#plPresetFiltersReset", t("plugins_btn_filters_reset"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(1)', t("plugins_filter_category"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(2)', t("plugins_filter_pack"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(3)', t("plugins_filter_tier"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(4)', t("plugins_filter_install_state"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(5)', t("plugins_filter_enabled_only"));
    setLabelLead('#panel-plugins .grid label:nth-of-type(6)', t("plugins_filter_p0_only"));
    const pluginsH3 = document.querySelector('#panel-plugins [data-advanced-block="1"] h3');
    if (pluginsH3) pluginsH3.textContent = t("plugins_manifest_title");
    setLabelLead('#panel-plugins [data-advanced-block="1"] label:nth-of-type(1)', t("plugins_manifest_label"));
    setText("#plLoadSample", t("plugins_btn_load_sample"));
    setText("#plValidate", t("plugins_btn_validate"));
    setText("#plRegister", t("plugins_btn_register"));

    setText("#panel-guardian h2", t("guardian_title"));
    setText("#panel-guardian .hint", t("guardian_hint"));
    setLabelLead('#panel-guardian .grid label:nth-of-type(1)', t("guardian_label_severity"));
    setLabelLead('#panel-guardian .grid label:nth-of-type(2)', t("guardian_label_reason"));
    setText("#gSeverityApply", t("guardian_btn_apply"));
    setText("#gSeverityStatus", t("guardian_btn_status"));
    setText("#gPolicy", t("guardian_btn_policy"));
    setText("#gReqs", t("guardian_btn_reqs"));
    setText("#gGate", t("guardian_btn_gate"));

    setText("#panel-secrets h2", t("secrets_title"));
    setText("#panel-secrets .hint", t("secrets_hint"));
    setText("#sStatus", t("secrets_btn_status"));
    setText("#sAudit", t("secrets_btn_audit"));
    setText("#sExportMeta", t("secrets_btn_export_meta"));
    setText("#sExportValues", t("secrets_btn_export_values"));
    setLabelLead('#panel-secrets .grid[data-advanced-block="1"] label:nth-of-type(1)', t("secrets_label_name"));
    setLabelLead('#panel-secrets .grid[data-advanced-block="1"] label:nth-of-type(2)', t("secrets_label_value"));
    setLabelLead('#panel-secrets .grid[data-advanced-block="1"] label:nth-of-type(3)', t("secrets_label_reason"));
    setText("#sSet", t("secrets_btn_set"));
    setText("#sRotate", t("secrets_btn_rotate"));
    setText("#sDelete", t("secrets_btn_delete"));
    setText("#sResolve", t("secrets_btn_resolve"));
    setLabelLead('#panel-secrets > label[data-advanced-block="1"]', t("secrets_bundle_label"));
    setLabelLead('#panel-secrets .row.wrap[data-advanced-block="1"] label.check', t("secrets_import_values"));
    setLabelLead('#panel-secrets .row.wrap[data-advanced-block="1"] label:nth-of-type(2)', t("secrets_on_conflict"));
    setText("#sImport", t("secrets_btn_import"));
    const replayH3 = Array.from(document.querySelectorAll("#panel-secrets h3")).find((h) => h.textContent.toLowerCase().includes("channel") || h.textContent.toLowerCase().includes("replay"));
    if (replayH3) replayH3.textContent = t("channels_replay_title");
    setLabelLead('#panel-secrets .grid:nth-of-type(2) label:nth-of-type(1)', t("channels_label_channel"));
    setLabelLead('#panel-secrets .grid:nth-of-type(2) label:nth-of-type(2)', t("channels_label_preset_cmd"));
    setLabelLead('#panel-secrets .grid:nth-of-type(2) label:nth-of-type(3)', t("channels_label_mail_cmd"));
    setLabelLead('#panel-secrets > label:nth-of-type(2)', t("channels_label_replay_text"));
    setLabelLead('#panel-secrets .grid:nth-of-type(3) label:nth-of-type(1)', t("channels_label_tg_chat"));
    setLabelLead('#panel-secrets .grid:nth-of-type(3) label:nth-of-type(2)', t("channels_label_wa_from"));
    setLabelLead('#panel-secrets .grid:nth-of-type(3) label:nth-of-type(3)', t("channels_label_mail_from"));
    setText("#crRun", t("channels_btn_run_replay"));
    setText("#crTelegramStatus", t("channels_btn_tg_status"));
    setText("#crWhatsappStatus", t("channels_btn_wa_status"));
    setText("#crMailStatus", t("channels_btn_mail_status"));
    setSelectOptionText("#crPreset", "custom", t("channels_preset_custom"));

    setPlaceholder("#chatMsg", state.uiLang === "en" ? "Write a task (e.g. analyze and improve module X)..." : "Scrivi un task (es. analizza e migliora il modulo X)...");
    setPlaceholder("#vPrompt", state.uiLang === "en" ? "Topic / objective..." : "Tema / obiettivo...");
    fillTaskSelects();

    renderOverviewCards(state.overview);
    renderOverviewChecklist(state.overview);
    renderWizard();
    if (!opts.silent) notify(`${t("language_name")} selected`, "success", "Language");
  }

  // App boot
  // renderLangToggle();
  // renderRoleToggle();
  // renderUIModeToggle();
  // updateRoleView();
  // updateUIModeView();

  // State of the Core Polling
  async function loadStateOfTheCore() {
    try {
      const res = await fetch("/api/v1/jarvis/system/state_of_the_core");
      if (!res.ok) throw new Error("API Error");
      const data = await res.json();

      const dash = document.getElementById("coreTelemetryDash");

      // Update Mission Control Badges
      if ($("badgeProposals")) $("badgeProposals").textContent = data.pending_proposals || 0;
      if ($("badgeVault")) {
        const vIcon = data.vault.includes("unlocked") ? "🔓" : "🔐";
        $("badgeVault").innerHTML = `${vIcon} ${data.vault}`;
      }
      if ($("badgeManifest")) {
        const mIcon = data.manifest.status === "valid" ? "✅" : "❌";
        $("badgeManifest").innerHTML = `${mIcon} ${data.manifest.signed_files} files signed`;
      }
      if ($("badgeProviders")) {
        const def = (state.providers || []).find(p => p.is_default);
        $("badgeProviders").textContent = `${(state.providers || []).length} configured (default: ${def ? def.provider_id : 'none'})`;
      }
      if ($("badgePlugins")) {
        const p0count = (state.pluginsCatalog || []).filter(p => p.tier === 'P0').length;
        $("badgePlugins").textContent = `${p0count} loaded`;
      }
      if ($("badgeChannels")) $("badgeChannels").textContent = "Telegram, WhatsApp, Mail";
      if ($("badgeBridges")) {
        $("badgeBridges").innerHTML = `IoT:<span style="color:${data.bridges.iot === 'active' ? 'var(--accent)' : 'inherit'}">${data.bridges.iot}</span>, Robot:<span style="color:${data.bridges.robotics === 'active' ? 'var(--accent)' : (data.bridges.robotics === 'e_stop' ? '#ef4444' : 'inherit')}">${data.bridges.robotics}</span>, Veh:<span style="color:${data.bridges.vehicle === 'active' ? 'var(--accent)' : (data.bridges.vehicle === 'e_stop' ? '#ef4444' : 'inherit')}">${data.bridges.vehicle}</span>`;
      }

      if (!dash) return;

      const vIcon = data.vault.includes("unlocked") ? "🔓" : "🔐";
      const mIcon = data.manifest.status === "valid" ? "✅" : "❌";

      dash.innerHTML = `
        <div class="card-grid" style="width: 100%;">
          <div class="box">
            <h4>Security Vault</h4>
            <p style="font-size:1.5rem; margin:0;">${vIcon} <span style="font-size:0.9rem;">${data.vault}</span></p>
          </div>
          <div class="box">
            <h4>RC1 Manifest</h4>
            <p style="font-size:1.5rem; margin:0;">${mIcon} <span style="font-size:0.9rem;">${data.manifest.signed_files} files signed</span></p>
          </div>
          <div class="box">
            <h4>Bridges (IoT/Robotics/Vehicle)</h4>
            <div style="font-size:0.8rem; margin-top:0.5rem; display:flex; flex-direction:column; gap:0.2rem;">
              <div>IoT: <b style="color:${data.bridges.iot === 'active' ? 'var(--accent)' : 'inherit'}">${data.bridges.iot.toUpperCase()}</b></div>
              <div>Robotics: <b style="color:${data.bridges.robotics === 'active' ? 'var(--accent)' : (data.bridges.robotics === 'e_stop' ? '#ef4444' : 'inherit')}">${data.bridges.robotics.toUpperCase()}</b></div>
              <div>Vehicles: <b style="color:${data.bridges.vehicle === 'active' ? 'var(--accent)' : (data.bridges.vehicle === 'e_stop' ? '#ef4444' : 'inherit')}">${data.bridges.vehicle.toUpperCase()}</b></div>
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      console.warn("Failed to load State of the Core", e);
    }
  }

  loadStateOfTheCore();
  setInterval(loadStateOfTheCore, 5000); // Aggiornamento ogni 5 secondi

  loadProviders();

  function notify(message, kind = "info", title = "") {
    const host = $("toastArea");
    if (!host) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`;
    node.innerHTML = title ? `<div class="title">${esc(title)}</div><div>${esc(message)}</div>` : `<div>${esc(message)}</div>`;
    host.appendChild(node);
    window.setTimeout(() => {
      node.style.opacity = "0";
      node.style.transform = "translateY(6px)";
      window.setTimeout(() => node.remove(), 180);
    }, 3200);
  }

  function setBusy(delta) {
    state.pendingRequests = Math.max(0, (state.pendingRequests || 0) + delta);
    document.body.classList.toggle("is-busy", state.pendingRequests > 0);
  }

  function humanTask(t) { return (state.uiLang === "en" ? TASK_LABELS_EN[t] : TASK_LABELS[t]) || TASK_LABELS[t] || t; }
  function humanPrivacy(v) { return (state.uiLang === "en" ? PRIVACY_LABELS_EN[v] : PRIVACY_LABELS[v]) || PRIVACY_LABELS[v] || v; }
  function humanDifficulty(v) { return (state.uiLang === "en" ? DIFFICULTY_LABELS_EN[v] : DIFFICULTY_LABELS[v]) || DIFFICULTY_LABELS[v] || v; }
  function humanRole(r) {
    if (r === "owner") return t("role_owner");
    if (r === "operator") return t("role_operator");
    if (r === "tech") return t("role_tech");
    return ROLE_LABELS[r] || r;
  }

  async function api(path, method = "GET", body = null) {
    setBusy(1);
    try {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : null,
      });
      const text = await res.text();
      let data = text;
      try { data = text ? JSON.parse(text) : {}; } catch (_) { }
      if (!res.ok) {
        if (method !== "GET") notify(t("notify_error_http", { status: res.status, path }), "error", t("notify_error_operation"));
        throw new Error(`${res.status} ${res.statusText}: ${typeof data === "string" ? data : JSON.stringify(data)}`);
      }
      return data;
    } finally {
      setBusy(-1);
    }
  }

  function setBox(id, data) {
    $(id).textContent = typeof data === "string" ? data : pretty(data);
  }

  function esc(v) {
    return String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function setUiMode(mode, opts = {}) {
    state.uiMode = mode === "advanced" ? "advanced" : "guided";
    document.body.classList.toggle("ui-guided", state.uiMode === "guided");
    document.body.classList.toggle("ui-advanced", state.uiMode === "advanced");
    if ($("uiMode") && $("uiMode").value !== state.uiMode) $("uiMode").value = state.uiMode;
    const activeAdvancedTab = document.querySelector(`.tabs button.active[data-level="advanced"]`);
    if (activeAdvancedTab && state.uiMode === "guided") showTab("overview");
    if (!opts.silent) {
      notify(
        state.uiMode === "guided" ? t("notify_ui_guided") : t("notify_ui_advanced"),
        "info",
        "UI"
      );
    }
  }

  function roleAllowed(el) {
    if (!el) return true;
    const raw = el.dataset?.roles;
    if (!raw) return true;
    const roles = raw.split(",").map((x) => x.trim()).filter(Boolean);
    return roles.includes(state.uiRole);
  }

  function applyRoleVisibility() {
    document.querySelectorAll(".tabs button[data-tab]").forEach((btn) => {
      btn.classList.toggle("is-hidden", !roleAllowed(btn));
    });
    document.querySelectorAll(".panel[data-roles]").forEach((panel) => {
      panel.classList.toggle("is-hidden", !roleAllowed(panel));
    });
    const activeBtn = document.querySelector(".tabs button.active[data-tab]");
    if (activeBtn && !roleAllowed(activeBtn)) {
      showTab("overview");
    }
  }

  function setUiRole(role, opts = {}) {
    state.uiRole = ["owner", "operator", "tech"].includes(role) ? role : "owner";
    if ($("uiRole") && $("uiRole").value !== state.uiRole) $("uiRole").value = state.uiRole;
    document.body.dataset.role = state.uiRole;
    applyRoleVisibility();
    if (!opts.silent) {
      notify(t("notify_ui_role", { role: humanRole(state.uiRole) }), "info", "UI");
    }
  }

  function showTab(name) {
    const targetBtn = document.querySelector(`.tabs button[data-tab="${name}"]`);
    if (state.uiMode === "guided" && targetBtn && targetBtn.dataset.level === "advanced") {
      name = "overview";
    }
    if (targetBtn && !roleAllowed(targetBtn)) {
      name = "overview";
    }
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
  }

  function initTabs() {
    $("tabs").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tab]");
      if (!btn) return;
      showTab(btn.dataset.tab);
    });
  }

  function addChat(role, text, meta = "") {
    const box = $("chatLog");
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.innerHTML = `<div class="meta">${esc(meta || role)}</div><div>${esc(String(text)).replace(/\\n/g, "<br>")}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function fillTaskSelects() {
    for (const id of ["chatTask"]) {
      const sel = $(id);
      sel.innerHTML = state.tasks.map((t) => `<option value="${t}">${esc(humanTask(t))}</option>`).join("");
    }
  }

  async function refreshStatus() {
    try {
      const [h, m] = await Promise.all([api(API.health), api(API.modelsStatus)]);
      $("apiDot").className = "dot ok";
      $("apiText").textContent = t("api_ok_summary", { enabled: m.providers_enabled, total: m.providers_total, models: m.catalog_models });
    } catch (e) {
      $("apiDot").className = "dot bad";
      $("apiText").textContent = t("api_error_summary");
      console.error(e);
    }
  }

  function renderOverviewCards(data) {
    const host = $("ovCards");
    if (!host) return;
    if (!data) {
      host.innerHTML = `<div class="status-card warn"><div class="title">${esc(t("tab_overview"))}</div><div class="small">${esc(t("ui_no_data"))}</div></div>`;
      return;
    }
    const cards = [
      {
        title: t("status_models_title"),
        big: `${data.models?.providers_enabled ?? 0}/${data.models?.providers_total ?? 0}`,
        small: t("status_models_small", { count: data.models?.catalog_models ?? 0 }),
        status: (data.models?.providers_enabled || 0) > 0 ? "ok" : "warn",
      },
      {
        title: "Guardian",
        big: `${(data.guardian?.current || "n/a").toUpperCase()}`,
        small: t("status_guardian_small", { enabled: data.guardian?.rules_enabled ?? 0, total: data.guardian?.rules_total ?? 0, mode: data.guardian?.mode || t("common_na") }),
        status: "ok",
      },
      {
        title: t("status_plugins_title"),
        big: `${data.plugins?.enabled_total ?? 0}`,
        small: t("status_plugins_small", { count: data.plugins?.catalog_total ?? 0 }),
        status: (data.plugins?.catalog_total || 0) > 0 ? "ok" : "warn",
      },
      {
        title: t("status_secrets_title"),
        big: `${data.secrets?.entries_total ?? 0}`,
        small: `mode ${data.secrets?.mode || "n/a"}`,
        status: "ok",
      },
      {
        title: t("status_channels_title"),
        big: `${data.channels?.configured_count ?? 0}/3`,
        small: t("status_channels_small", { tg: data.channels?.telegram ? "on" : "off", mail: data.channels?.mail ? "on" : "off", wa: data.channels?.whatsapp ? "on" : "off" }),
        status: (data.channels?.configured_count || 0) > 0 ? "ok" : "warn",
      },
      {
        title: "API",
        big: data.api?.ok ? "READY" : "ERR",
        small: data.api?.service ? `${data.api.service} v${data.api.version || "?"}` : (data.api?.error || t("common_not_reachable")),
        status: data.api?.ok ? "ok" : "err",
      },
    ];
    host.innerHTML = cards.map((c) => `<div class="status-card ${esc(c.status || "ok")}"><div class="title">${esc(c.title)}</div><div class="big">${esc(c.big)}</div><div class="small">${esc(c.small)}</div></div>`).join("");
  }

  function renderOverviewChecklist(data) {
    const host = $("ovChecklist");
    if (!host) return;
    if (!data) {
      host.innerHTML = `<div class="check-card warn"><div class="head"><span>${esc(t("overview_checklist"))}</span><span>?</span></div><div class="desc">${esc(t("ui_status_unavailable"))}</div></div>`;
      return;
    }
    const items = [
      {
        title: t("checklist_api_title"),
        ok: !!data.api?.ok,
        desc: data.api?.ok ? t("checklist_api_ok") : t("checklist_api_missing"),
      },
      {
        title: t("checklist_provider_title"),
        ok: (data.models?.providers_enabled || 0) > 0,
        desc: (data.models?.providers_enabled || 0) > 0 ? t("checklist_provider_ok") : t("checklist_provider_missing"),
      },
      {
        title: t("checklist_catalog_title"),
        ok: (data.models?.catalog_models || 0) > 0,
        desc: (data.models?.catalog_models || 0) > 0 ? t("checklist_catalog_ok", { count: data.models?.catalog_models || 0 }) : t("checklist_catalog_missing"),
      },
      {
        title: t("checklist_guardian_title"),
        ok: !!data.guardian?.current,
        desc: data.guardian?.current ? t("checklist_guardian_ok", { severity: data.guardian.current }) : t("checklist_guardian_missing"),
      },
      {
        title: t("checklist_channels_title"),
        ok: (data.channels?.configured_count || 0) > 0,
        desc: t("checklist_channels_desc", { count: data.channels?.configured_count || 0 }),
      },
      {
        title: t("checklist_secrets_title"),
        ok: !!data.secrets?.mode,
        desc: data.secrets?.mode ? t("checklist_secrets_ok", { mode: data.secrets.mode }) : t("checklist_secrets_missing"),
      },
    ];
    host.innerHTML = items.map((x) => {
      const cls = x.ok ? "ok" : "warn";
      return `<div class="check-card ${cls}"><div class="head"><span>${esc(x.title)}</span><span>${x.ok ? esc(t("common_ok")) : esc(t("common_todo"))}</span></div><div class="desc">${esc(x.desc)}</div></div>`;
    }).join("");
  }

  async function loadOverview() {
    const calls = await Promise.allSettled([
      api(API.health),
      api(API.modelsStatus),
      api(API.pluginsStatus),
      api(API.secretsStatus),
      api(`${API.guardianSeverity}?lang=${encodeURIComponent(currentLang())}`),
      api(API.telegramStatus),
      api(API.mailStatus),
      api(API.whatsappStatus),
    ]);
    const pick = (idx) => (calls[idx].status === "fulfilled" ? calls[idx].value : { error: String(calls[idx].reason || "error") });
    const h = pick(0);
    const tg = pick(5);
    const mail = pick(6);
    const wa = pick(7);
    const summary = {
      api: {
        ok: !h.error,
        service: h.service,
        version: h.version,
        error: h.error || null,
      },
      models: pick(1),
      plugins: pick(2),
      secrets: pick(3),
      guardian: pick(4),
      channels: {
        telegram: !!tg.configured,
        mail: !!mail.configured,
        whatsapp: !!(wa.meta_configured || wa.twilio_configured),
        configured_count: [!!tg.configured, !!mail.configured, !!(wa.meta_configured || wa.twilio_configured)].filter(Boolean).length,
      },
      raw: { telegram: tg, mail, whatsapp: wa },
      generated_at: new Date().toISOString(),
    };
    state.overview = summary;
    renderOverviewCards(summary);
    renderOverviewChecklist(summary);
    setBox("ovOut", summary);
    return summary;
  }

  function providerFormPayload() {
    return {
      provider_id: $("pId").value.trim(),
      label: $("pLabel").value.trim(),
      provider_type: $("pType").value,
      enabled: $("pEnabled").checked,
      local_endpoint: $("pLocal").checked,
      base_url: $("pBase").value.trim() || null,
      api_key: $("pKey").value.trim() || null,
      notes: $("pNotes").value.trim(),
      models: $("pModels").value.trim(),
      reason: "UI provider save",
      confirm_owner: true,
      decided_by: "owner",
    };
  }

  async function loadProviders() {
    const data = await api(API.providers);
    state.providers = data.items || [];
    renderProviders();
    return data;
  }

  function renderProviders() {
    const host = $("providersTable");
    if (!state.providers.length) {
      host.innerHTML = `<div class="row-item">${esc(t("providers_no_configured"))}</div>`;
      return;
    }
    host.innerHTML = state.providers.map((p) => {
      const models = Array.isArray(p.models) ? p.models.map((m) => m.model_id || m.label || "?").join(", ") : "";
      return `
        <div class="row-item" data-provider-id="${p.provider_id}">
          <div class="head">
            <span>${p.label || p.provider_id}</span>
            <span class="meta-small">${p.provider_type} - ${p.enabled ? t("plugins_label_enabled") : t("plugins_label_disabled")} - key:${p.has_api_key ? p.api_key_masked : t("providers_models_none")}</span>
          </div>
          <div class="meta-small">${p.base_url || t("providers_base_none")} ${p.local_endpoint ? `- ${t("providers_local_suffix")}` : ""}</div>
          <div class="meta-small">models: ${models || t("providers_models_none")}</div>
          <div class="row">
            <button class="secondary small fill-provider">${esc(t("providers_btn_fill_form"))}</button>
            <button class="secondary small test-provider">${esc(t("providers_btn_test"))}</button>
            <button class="secondary small delete-provider">${esc(t("providers_btn_delete"))}</button>
          </div>
        </div>`;
    }).join("");
  }

  function fillProviderForm(p) {
    $("pId").value = p.provider_id || "";
    $("pLabel").value = p.label || "";
    $("pType").value = p.provider_type || "openai";
    $("pBase").value = p.base_url || "";
    $("pKey").value = "";
    $("pEnabled").checked = !!p.enabled;
    $("pLocal").checked = !!p.local_endpoint;
    $("pNotes").value = p.notes || "";
    $("pModels").value = (p.models || []).map((m) => m.model_id || m.label || "").filter(Boolean).join("\n");
  }

  async function testProviderByForm() {
    const payload = providerFormPayload();
    const data = await api(API.providerTest, "POST", { provider: payload, timeout_sec: 2.5 });
    setBox("providerOut", data);
  }

  async function saveProvider() {
    const data = await api(API.providerUpsert, "POST", providerFormPayload());
    setBox("providerOut", data);
    await refreshAllModelState();
    notify(t("notify_provider_saved"), "success", t("tab_providers"));
  }

  async function deleteProvider(providerId) {
    const data = await api(API.providerDelete, "POST", {
      provider_id: providerId,
      reason: `UI delete provider ${providerId}`,
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("providerOut", data);
    await refreshAllModelState();
  }

  async function testProviderStored(providerId) {
    const data = await api(API.providerTest, "POST", { provider_id: providerId, timeout_sec: 2.5 });
    setBox("providerOut", data);
  }

  async function loadCatalog() {
    const data = await api(API.catalog);
    state.catalog = data.items || [];
    if (Array.isArray(data.task_classes) && data.task_classes.length) {
      state.tasks = data.task_classes;
      fillTaskSelects();
    }
    return data;
  }

  function modelOptionsHTML(selected) {
    const items = [`<option value="">(auto)</option>`];
    for (const m of state.catalog) {
      const ref = m.ref;
      items.push(`<option value="${ref}" ${selected === ref ? "selected" : ""}>${ref} - ${m.cost_tier}${m.local_endpoint ? " - local" : ""}</option>`);
    }
    return items.join("");
  }

  function renderRoutingMatrix() {
    const host = $("routingGrid");
    const pol = state.routingPolicy;
    if (!pol) {
      host.innerHTML = `<div class="row-item">${esc(t("routing_not_loaded"))}</div>`;
      return;
    }
    const rows = state.tasks.map((task) => {
      const r = (pol.task_routes || {})[task] || {};
      return `
        <div class="route-row" data-task="${task}">
          <div class="route-task">${task}</div>
          <label>${esc(t("routing_field_primary"))}<select class="rt-primary">${modelOptionsHTML(r.primary || "")}</select></label>
          <label>${esc(t("routing_field_fallbacks"))}<input class="rt-fallbacks" value="${(r.fallbacks || []).join(", ")}"></label>
          <label>${esc(t("routing_field_privacy"))}<select class="rt-privacy">
            ${["allow_cloud", "local_preferred", "local_only"].map(v => `<option value="${v}" ${r.privacy_mode === v ? "selected" : ""}>${v}</option>`).join("")}
          </select></label>
          <label>${esc(t("routing_field_max_cost"))}<select class="rt-cost">
            ${["free", "low", "medium", "high", "premium"].map(v => `<option value="${v}" ${r.max_cost_tier === v ? "selected" : ""}>${v}</option>`).join("")}
          </select></label>
          <label>${esc(t("routing_field_reasoning"))}<select class="rt-reason">
            ${["cheap", "balanced", "deep"].map(v => `<option value="${v}" ${r.reasoning_level === v ? "selected" : ""}>${v}</option>`).join("")}
          </select></label>
        </div>`;
    }).join("");
    host.innerHTML = rows;
  }

  async function loadRoutingPolicy() {
    const data = await api(API.routingPolicy);
    state.routingPolicy = data.policy;
    renderRoutingMatrix();
    return data;
  }

  function routingPolicyFromUI() {
    const base = JSON.parse(JSON.stringify(state.routingPolicy || { version: 1, task_routes: {}, budget_defaults: { single_task_unit_cap: 2, village_unit_cap: 10 }, village_profiles: {} }));
    document.querySelectorAll(".route-row").forEach((row) => {
      const task = row.dataset.task;
      base.task_routes[task] = base.task_routes[task] || {};
      base.task_routes[task].primary = row.querySelector(".rt-primary").value || null;
      base.task_routes[task].fallbacks = row.querySelector(".rt-fallbacks").value.split(",").map(s => s.trim()).filter(Boolean);
      base.task_routes[task].privacy_mode = row.querySelector(".rt-privacy").value;
      base.task_routes[task].max_cost_tier = row.querySelector(".rt-cost").value;
      base.task_routes[task].reasoning_level = row.querySelector(".rt-reason").value;
    });
    return base;
  }

  async function saveRoutingPolicy() {
    const data = await api(API.routingPolicy, "POST", {
      policy: routingPolicyFromUI(),
      reason: "UI routing save",
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("routingOut", data);
    await refreshAllModelState();
  }

  async function applyPreset(presetId) {
    const data = await api(API.presetApply, "POST", {
      preset_id: presetId,
      reason: `UI apply preset ${presetId}`,
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("routingOut", data);
    await refreshAllModelState();
    notify(t("notify_routing_preset", { preset: presetId }), "success", t("tab_routing"));
  }

  function firstMetric(obj, keys) {
    for (const k of keys) {
      const v = obj?.[k];
      if (v !== undefined && v !== null && v !== "") return v;
    }
    return null;
  }

  function renderChatTraceVisual(data, kind = "run") {
    const host = $("chatTraceVisual");
    if (!host) return;
    if (!data || typeof data !== "object") {
      host.innerHTML = "";
      return;
    }
    const route = data.route || {};
    const selected = data.selected_model || route.selected || {};
    const selectedRef = selected.ref || selected.model_id || "n/a";
    const latency = firstMetric(data, ["latency_ms", "elapsed_ms", "duration_ms"]) ?? firstMetric(data.timing || {}, ["latency_ms", "elapsed_ms", "total_ms"]);
    const cost = firstMetric(data, ["cost_estimate_units", "cost_units", "estimated_cost_units"]) ?? firstMetric(route, ["cost_estimate_units"]);
    const provider = selected.provider_id || selected.provider || (selectedRef.includes(":") ? selectedRef.split(":")[0] : "n/a");
    const privacy = data.privacy_mode || route.privacy_mode || $("chatPrivacy")?.value || "n/a";
    const candidates = Array.isArray(route.candidates) ? route.candidates.slice(0, 4) : [];
    const candidateCards = candidates.map((c) => {
      const ref = c.ref || c.model_id || "n/a";
      const score = firstMetric(c, ["score", "route_score", "rank_score"]);
      const reason = (c.reason || c.note || "").toString().slice(0, 160);
      return `<div class="trace-card">
        <div class="head"><span>${esc(t("trace_candidate"))}</span><span class="meta-small">${esc(ref)}</span></div>
        <div class="kv">${esc(t("trace_field_score"))}: ${esc(score ?? t("common_na"))}<br>${esc(t("trace_field_reason"))}: ${esc(reason || t("common_na"))}</div>
      </div>`;
    }).join("");
    const preview = (data.assistant_message || data.assistant_preview || "").toString().slice(0, 500);
    host.innerHTML = `
      <div class="trace-card">
        <div class="head"><span>${kind === "sim" ? esc(t("trace_chat_sim")) : esc(t("trace_chat_run"))}</span><span class="role-pill ${esc(state.uiRole)}">${esc(humanRole(state.uiRole))}</span></div>
        <div class="kv">
          ${esc(t("trace_field_model"))}: ${esc(selectedRef)}<br>
          ${esc(t("trace_field_provider"))}: ${esc(provider)}<br>
          ${esc(t("trace_field_privacy"))}: ${esc(humanPrivacy(privacy))}<br>
          ${esc(t("trace_field_latency"))}: ${esc(latency ?? t("common_na"))}<br>
          ${esc(t("trace_field_cost"))}: ${esc(cost ?? t("common_na"))}
        </div>
        <div class="preview">${esc(preview || t("chat_no_reply"))} </div>
      </div>
      ${candidateCards}
    `;
  }

  function renderVillageTraceVisual(data, isLive) {
    const timeline = $("vTimeline");
    const compare = $("vCompare");
    if (!timeline || !compare) return;
    if (!data || typeof data !== "object") {
      timeline.innerHTML = "";
      compare.innerHTML = "";
      return;
    }
    if (!isLive) {
      const roles = Array.isArray(data.roles) ? data.roles : [];
      timeline.innerHTML = `
        <div class="timeline-item"><div class="stage">${esc(t("trace_stage_plan"))}</div><div class="desc">${esc(t("trace_field_roles"))}: ${esc(roles.length)} | budget: ${esc(data.budget_cap ?? t("common_na"))} | ${esc(t("trace_field_privacy"))}: ${esc(humanPrivacy(data.privacy_mode || $("vPrivacy")?.value || "n/a"))}</div></div>
      `;
      compare.innerHTML = roles.slice(0, 8).map((r) => `<div class="trace-card">
        <div class="head"><span>${esc(r.role || "role")}</span><span class="meta-small">${esc(r.selected?.ref || "no-match")}</span></div>
        <div class="kv">${esc(t("trace_field_task"))}: ${esc(humanTask(r.task_class || ""))}<br>${esc(t("trace_field_route"))}: ${esc(r.route_status || t("common_na"))}<br>${esc(t("trace_field_cost_est"))}: ${esc(r.cost_estimate_units ?? t("common_na"))}</div>
      </div>`).join("");
      return;
    }
    const roleResults = Array.isArray(data.role_results) ? data.role_results : [];
    const synth = data.synthesis || {};
    const totalOk = roleResults.filter((r) => r.status === "ok").length;
    const totalLatency = roleResults.reduce((acc, r) => {
      const v = Number(firstMetric(r, ["latency_ms", "elapsed_ms", "duration_ms"]) ?? firstMetric(r.timing || {}, ["latency_ms", "elapsed_ms", "total_ms"]) ?? 0);
      return acc + (Number.isFinite(v) ? v : 0);
    }, 0);
    timeline.innerHTML = `
      <div class="timeline-item"><div class="stage">${esc(t("trace_stage_plan"))}</div><div class="desc">${esc(t("trace_field_mode"))}: ${esc(data.mode || $("vMode")?.value || t("common_na"))} | ${esc(t("trace_field_roles"))}: ${esc(roleResults.length)} | ${esc(t("trace_field_privacy"))}: ${esc(humanPrivacy(data.privacy_mode || $("vPrivacy")?.value || "n/a"))}</div></div>
      <div class="timeline-item"><div class="stage">${esc(t("trace_stage_run"))}</div><div class="desc">${esc(t("trace_field_roles_ok"))}: ${esc(totalOk)}/${esc(roleResults.length)} | ${esc(t("trace_field_latency_total"))}: ${esc(totalLatency || t("common_na"))} ms</div></div>
      <div class="timeline-item"><div class="stage">${esc(t("trace_stage_synth"))}</div><div class="desc">${esc(t("trace_field_status"))}: ${esc(synth.status || t("common_na"))} | ${esc(t("trace_field_model"))}: ${esc(synth.selected_model?.ref || t("common_na"))}</div></div>
    `;
    compare.innerHTML = roleResults.map((r) => {
      const latency = firstMetric(r, ["latency_ms", "elapsed_ms", "duration_ms"]) ?? firstMetric(r.timing || {}, ["latency_ms", "elapsed_ms", "total_ms"]);
      const cost = firstMetric(r, ["cost_estimate_units", "cost_units", "estimated_cost_units"]) ?? firstMetric(r.plan_route || {}, ["cost_estimate_units"]);
      const modelRef = r.selected_model?.ref || r.plan_route?.selected?.ref || "n/a";
      const preview = (r.assistant_preview || r.error || r.status || "").toString().slice(0, 240);
      return `<div class="trace-card ${r.status === "ok" ? "" : "village-role-fail"}">
        <div class="head"><span>${esc(r.role || "role")}</span><span class="meta-small">${esc(r.status || "n/a")}</span></div>
        <div class="kv">${esc(t("trace_field_task"))}: ${esc(humanTask(r.task_class || ""))}<br>${esc(t("trace_field_model"))}: ${esc(modelRef)}<br>${esc(t("trace_field_latency"))}: ${esc(latency ?? t("common_na"))}<br>${esc(t("trace_field_cost_est"))}: ${esc(cost ?? t("common_na"))}</div>
        <div class="preview">${esc(preview)}</div>
      </div>`;
    }).join("");
  }

  async function doRouteExplain() {
    const req = {
      task_class: $("chatTask").value,
      message: $("chatMsg").value,
      privacy_mode: $("chatPrivacy").value,
      difficulty: $("chatDifficulty").value,
    };
    const data = await api(API.routeExplain, "POST", req);
    renderChatTraceVisual({ route: data, privacy_mode: req.privacy_mode, assistant_preview: "", selected_model: data?.selected }, "explain");
    setBox("chatTrace", data);
    return data;
  }

  async function doChatSim() {
    const user = $("chatMsg").value.trim();
    if (!user) return;
    addChat("user", user, `${humanTask($("chatTask").value)} - ${humanPrivacy($("chatPrivacy").value)}`);
    const data = await api(API.chatSim, "POST", {
      message: user,
      task_class: $("chatTask").value,
      privacy_mode: $("chatPrivacy").value,
      difficulty: $("chatDifficulty").value,
    });
    addChat("assistant", data.assistant_preview || t("chat_no_preview"), (data.route?.selected?.ref ? `${t("chat_selected_prefix")}: ${data.route.selected.ref}` : t("chat_no_model")));
    renderChatTraceVisual(data, "sim");
    setBox("chatTrace", data);
  }

  async function doChatRun() {
    const user = $("chatMsg").value.trim();
    if (!user) return;
    addChat("user", user, `${humanTask($("chatTask").value)} - ${humanPrivacy($("chatPrivacy").value)} - live`);
    const data = await api(API.chatRun, "POST", {
      message: user,
      task_class: $("chatTask").value,
      privacy_mode: $("chatPrivacy").value,
      difficulty: $("chatDifficulty").value,
      confirm_owner: true,
      decided_by: "owner",
    });
    const meta = data?.selected_model?.ref ? `${t("chat_selected_prefix")}: ${data.selected_model.ref}` : (data?.route?.selected?.ref ? `${t("chat_selected_prefix")}: ${data.route.selected.ref}` : t("chat_no_model"));
    addChat("assistant", data.assistant_message || data.assistant_preview || "(no response)", meta);
    renderChatTraceVisual(data, "run");
    setBox("chatTrace", data);
    notify(t("notify_chat_done", { meta }), "success", t("tab_chat"));
  }

  async function doVillagePlan() {
    const roles = $("vRoles").value.split(",").map(s => s.trim()).filter(Boolean);
    const data = await api(API.villagePlan, "POST", {
      prompt: $("vPrompt").value,
      mode: $("vMode")?.value || "brainstorm",
      privacy_mode: $("vPrivacy").value,
      budget_cap: Number($("vBudget").value || 10),
      roles,
    });
    renderVillageCards(data, false);
    renderVillageTraceVisual(data, false);
    setBox("vOut", data);
  }

  function renderVillageCards(data, isLive) {
    const host = $("vCards");
    if (!host) return;
    if (!data || (isLive ? !Array.isArray(data.role_results) : !Array.isArray(data.roles))) {
      host.innerHTML = `<div class="row-item">${esc(t("village_no_data"))}</div>`;
      return;
    }
    if (isLive) {
      const rows = data.role_results || [];
      const roleCards = rows.map((r) => {
        const ok = r.status === "ok";
        const cls = ok ? "" : " village-role-fail";
        const modelRef = r.selected_model?.ref || r.plan_route?.selected?.ref || "n/a";
        const preview = (r.assistant_preview || r.error || r.status || "").slice(0, 700);
        return `<div class="row-item${cls}">
          <div class="head"><span>${esc(r.role)} (${esc(r.task_class)})</span><span class="meta-small">${esc(r.status)} - ${esc(modelRef)}</span></div>
          <div class="meta-small">${esc(preview)}</div>
        </div>`;
      }).join("");
      const synth = data.synthesis || {};
      const synthText = synth.assistant_message || synth.assistant_preview || synth.fallback_compilation || synth.reason || "";
      const synthModel = synth.selected_model?.ref || "n/a";
      const synthCard = `<div class="row-item village-synth">
        <div class="head"><span>${esc(t("trace_synthesis"))}</span><span class="meta-small">${esc(synth.status || "n/a")} - ${esc(synthModel)}</span></div>
        <div class="meta-small">${esc(String(synthText).slice(0, 1800))}</div>
      </div>`;
      host.innerHTML = synthCard + roleCards;
      return;
    }
    const rows = data.roles || [];
    host.innerHTML = rows.map((r) => {
      const ref = r.selected?.ref || "no-match";
      return `<div class="row-item">
        <div class="head"><span>${esc(r.role)} (${esc(r.task_class)})</span><span class="meta-small">${esc(r.route_status)} - ${esc(ref)}</span></div>
        <div class="meta-small">${esc(t("trace_field_cost_est"))}: ${esc(r.cost_estimate_units)}</div>
      </div>`;
    }).join("");
  }

  async function doVillageRun() {
    const roles = $("vRoles").value.split(",").map(s => s.trim()).filter(Boolean);
    const data = await api(API.villageRun, "POST", {
      prompt: $("vPrompt").value,
      mode: $("vMode")?.value || "brainstorm",
      privacy_mode: $("vPrivacy").value,
      budget_cap: Number($("vBudget").value || 10),
      roles,
      allow_budget_overrun: !!$("vAllowOverrun")?.checked,
      max_roles: Number($("vMaxRoles")?.value || 8),
      confirm_owner: true,
      decided_by: "owner",
      reason: "UI AI Village live execution",
    });
    renderVillageCards(data, true);
    renderVillageTraceVisual(data, true);
    setBox("vOut", data);
    if (data?.synthesis?.assistant_message) {
      addChat("assistant", data.synthesis.assistant_message, `AI Village synth - ${data.synthesis?.selected_model?.ref || "n/a"}`);
    }
    notify(t("notify_village_done", { count: data?.role_results?.length || 0 }), "success", t("tab_village"));
    return data;
  }

  function pluginFiltersFromUI() {
    return {
      category: ($("plFilterCategory")?.value || "").trim().toLowerCase(),
      pack: ($("plFilterPack")?.value || "").trim().toLowerCase(),
      tier: $("plFilterTier")?.value || "",
      install_state: $("plFilterState")?.value || "",
      enabled_only: !!$("plFilterEnabledOnly")?.checked,
      p0_only: !!$("plFilterP0Only")?.checked,
    };
  }

  function setPluginFilters(filters = {}) {
    if ($("plFilterCategory")) $("plFilterCategory").value = filters.category ?? "";
    if ($("plFilterPack")) $("plFilterPack").value = filters.pack ?? "";
    if ($("plFilterTier")) $("plFilterTier").value = filters.tier ?? "";
    if ($("plFilterState")) $("plFilterState").value = filters.install_state ?? "";
    if ($("plFilterEnabledOnly")) $("plFilterEnabledOnly").checked = !!filters.enabled_only;
    if ($("plFilterP0Only")) $("plFilterP0Only").checked = !!filters.p0_only;
  }

  async function applyPluginFilterPreset(kind) {
    if (kind === "workflow") {
      setPluginFilters({
        category: "automation",
        pack: "workflow_automation",
        tier: "",
        install_state: "",
        enabled_only: false,
        p0_only: false,
      });
    } else if (kind === "workflow_enabled") {
      setPluginFilters({
        category: "automation",
        pack: "workflow_automation",
        tier: "",
        install_state: "",
        enabled_only: true,
        p0_only: false,
      });
    } else if (kind === "workflow_p0") {
      setPluginFilters({
        category: "automation",
        pack: "workflow_automation",
        tier: "",
        install_state: "",
        enabled_only: false,
        p0_only: true,
      });
    } else {
      setPluginFilters({
        category: "",
        pack: "",
        tier: "",
        install_state: "",
        enabled_only: false,
        p0_only: false,
      });
    }
    if (!Array.isArray(state.pluginsCatalog) || !state.pluginsCatalog.length) {
      await loadPluginsCatalog();
      return;
    }
    renderPluginsTable();
  }

  function pluginRowMatchesFilters(p, f) {
    const meta = p.registry_meta || {};
    if (f.category && String(p.category || "").toLowerCase() !== f.category) return false;
    if (f.pack && String(meta.pack || "").toLowerCase() !== f.pack) return false;
    if (f.tier && String(p.compatibility_tier || "").toLowerCase() !== String(f.tier).toLowerCase()) return false;
    if (f.install_state && String(p.install_state || "").toLowerCase() !== String(f.install_state).toLowerCase()) return false;
    if (f.enabled_only && !p.enabled) return false;
    if (f.p0_only && String(meta.priority || "").toUpperCase() !== "P0") return false;
    return true;
  }

  function badgeClass(kind, value) {
    const v = String(value || "").toLowerCase();
    if (kind === "health") {
      if (v === "ok") return "badge good";
      if (v === "never") return "badge neutral";
      if (v === "not_configured") return "badge neutral";
      return "badge bad";
    }
    if (kind === "install") {
      if (v === "enabled") return "badge good";
      if (v === "disabled" || v === "planned" || v === "registered") return "badge neutral";
      return "badge bad";
    }
    return "badge neutral";
  }

  function renderPluginsTable() {
    const host = $("pluginsTable");
    const allRows = state.pluginsCatalog || [];
    const filters = pluginFiltersFromUI();
    const rows = allRows.filter((p) => pluginRowMatchesFilters(p, filters));
    if (allRows.length && !rows.length) {
      host.innerHTML = `<div class="row-item">${esc(t("plugins_no_filtered"))}</div>`;
      return;
    }
    if (!rows.length) {
      host.innerHTML = `<div class="row-item">${esc(t("plugins_no_catalog"))}</div>`;
      return;
    }
    host.innerHTML = rows.map((p) => {
      const apps = (p.supported_apps || []).map(a => a && a.name).filter(Boolean).slice(0, 4).join(", ");
      const caps = (p.capabilities_requested || []).join(", ");
      const h = p.last_healthcheck || null;
      const hState = h ? (h.status || "unknown") : "never";
      const hLabel = `${hState}${h && h.checked_at ? ` @ ${h.checked_at}` : ""}`;
      const meta = p.registry_meta || {};
      const installState = p.install_state || "planned";
      const installBadge = `<span class="${badgeClass("install", installState)}">${esc(t("plugins_label_install"))}: ${esc(installState)}</span>`;
      const healthBadge = `<span class="${badgeClass("health", hState)}">${esc(t("plugins_label_health"))}: ${esc(hState)}</span>`;
      const enabledBadge = p.enabled ? `<span class="badge good">${esc(t("plugins_label_enabled"))}</span>` : `<span class="badge neutral">${esc(t("plugins_label_disabled"))}</span>`;
      return `
        <div class="row-item" data-plugin-id="${p.id}">
          <div class="head">
            <span>${p.name || p.id}</span>
            <span class="meta-small">${p.compatibility_tier} · ${p.surface} · ${p.registry_source}/${p.install_state}</span>
          </div>
          <div class="meta-small">${p.vendor || ""} · ${p.category || ""}</div>
          <div class="meta-small">${esc(t("plugins_label_apps"))}: ${apps || "-"}</div>
          <div class="meta-small">${esc(t("plugins_label_caps"))}: ${caps || "-"}</div>
          <div class="meta-small">${esc(t("plugins_label_pack"))}: ${meta.pack || "-"} | ${esc(t("plugins_label_priority"))}: ${meta.priority || "-"}</div>
          <div class="meta-small">${installBadge} ${healthBadge} ${enabledBadge}</div>
          <div class="meta-small">${esc(t("plugins_label_health"))}: ${hLabel}</div>
          <div class="row">
            <button class="secondary small plugin-install">${esc(t("plugins_btn_install"))}</button>
            <button class="secondary small plugin-healthcheck">${esc(t("plugins_btn_healthcheck"))}</button>
            <button class="secondary small plugin-enable">${esc(t("plugins_btn_enable"))}</button>
            <button class="secondary small plugin-disable">${esc(t("plugins_btn_disable"))}</button>
            <button class="secondary small plugin-load-manifest">${esc(t("plugins_btn_load_manifest"))}</button>
          </div>
        </div>`;
    }).join("");
  }

  function pluginSampleManifest() {
    return {
      manifest_version: "rth.plugin.v0",
      id: "custom.example_cli_tool",
      name: "Example CLI Tool Adapter",
      version: "0.1.0",
      vendor: "Custom",
      category: "development",
      surface: "cli",
      compatibility_tier: "community",
      supported_apps: [{ name: "Example CLI", platforms: ["windows", "linux", "macos"] }],
      capabilities_requested: ["filesystem_read", "process_exec"],
      risk_class: "high",
      consent_defaults: {
        proposal_required: true,
        dry_run_supported: true,
        owner_approval_required: true,
        suggested_guardian_severity_min: "balanced"
      },
      config_schema: {},
      healthcheck: { type: "none" },
      actions: [
        { id: "healthcheck", label: "Healthcheck", capability: "filesystem_read", risk: "low", dry_run_supported: true, description: "Read-only probe" },
        { id: "run_task", label: "Run task", capability: "process_exec", risk: "high", dry_run_supported: true, description: "Execute CLI command with consent" }
      ],
      notes: "Sample manifest for validator/register UI"
    };
  }

  async function loadPluginsCatalog() {
    const out = await api(API.pluginsCatalog);
    state.pluginsCatalog = out.items || [];
    renderPluginsTable();
    return out;
  }

  async function loadPluginsMatrix() {
    const out = await api(API.pluginsMatrix);
    state.pluginsMatrix = out;
    setBox("plOut", out);
    return out;
  }

  async function loadPluginsStatus() {
    const out = await api(API.pluginsStatus);
    setBox("plOut", out);
    return out;
  }

  async function loadPluginsSchema() {
    const out = await api(API.pluginsSchema);
    setBox("plOut", out);
    return out;
  }

  async function pluginValidate() {
    const raw = $("plManifest").value.trim();
    if (!raw) throw new Error(t("plugins_manifest_empty"));
    const manifest = JSON.parse(raw);
    const out = await api(API.pluginsValidate, "POST", { manifest });
    setBox("plOut", out);
    return out;
  }

  async function pluginRegister() {
    const raw = $("plManifest").value.trim();
    if (!raw) throw new Error(t("plugins_manifest_empty"));
    const manifest = JSON.parse(raw);
    const out = await api(API.pluginsRegister, "POST", {
      manifest,
      reason: "UI plugin manifest register",
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("plOut", out);
    await loadPluginsCatalog();
    notify(t("notify_plugin_action", { plugin: manifest.id || manifest.name || "manifest", action: "register" }), "success", t("tab_plugins"));
    return out;
  }

  async function pluginHealthcheck(pluginId) {
    const out = await api(API.pluginsHealthcheck, "POST", {
      plugin_id: pluginId,
      timeout_sec: 2.5,
      reason: `UI plugin healthcheck ${pluginId}`,
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("plOut", out);
    await loadPluginsCatalog();
    return out;
  }

  async function pluginSetState(pluginId, enabled, installState = null) {
    const out = await api(API.pluginsStateSet, "POST", {
      plugin_id: pluginId,
      enabled,
      install_state: installState,
      reason: `UI plugin state ${enabled ? "enable" : "disable"} ${pluginId}`,
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("plOut", out);
    await loadPluginsCatalog();
    return out;
  }

  async function pluginDriverAction(pluginId, action) {
    const out = await api(API.pluginsDriverAction, "POST", {
      plugin_id: pluginId,
      action,
      timeout_sec: action === "install" ? 15.0 : 6.0,
      reason: `UI plugin driver ${action} ${pluginId}`,
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("plOut", out);
    await loadPluginsCatalog();
    return out;
  }

  async function pluginBatchHealthcheck(opts = {}) {
    const f = pluginFiltersFromUI();
    const out = await api(API.pluginsHealthcheckBatch, "POST", {
      priority_only: !!opts.priority_only,
      category: opts.use_filters ? (f.category || null) : null,
      pack: opts.use_filters ? (f.pack || null) : null,
      tier: opts.use_filters ? (f.tier || null) : null,
      install_state: opts.use_filters ? (f.install_state || null) : null,
      enabled_only: opts.use_filters ? !!f.enabled_only : false,
      include_not_configured: !!opts.include_not_configured,
      limit: Number(opts.limit || 20),
      timeout_sec: Number(opts.timeout_sec || 2.0),
      reason: opts.reason || "UI plugin batch healthcheck",
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("plOut", out);
    await loadPluginsCatalog();
    return out;
  }

  function secretReason() {
    return ($("sReason")?.value || "").trim() || "UI secret operation";
  }

  function secretNameValue() {
    return {
      name: ($("sName")?.value || "").trim(),
      value: ($("sValue")?.value || "").trim(),
    };
  }

  async function secretsStatus() {
    const out = await api(API.secretsStatus);
    setBox("sOut", out);
    return out;
  }

  async function secretsAudit() {
    const out = await api(`${API.secretsAudit}?limit=120`);
    setBox("sOut", out);
    return out;
  }

  async function secretSet() {
    const nv = secretNameValue();
    const out = await api(API.secretsSet, "POST", {
      name: nv.name,
      value: nv.value,
      reason: secretReason(),
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("sOut", out);
    notify(t("notify_secret_saved", { name: nv.name }), "success", t("tab_secrets"));
    return out;
  }

  async function secretRotate() {
    const nv = secretNameValue();
    const out = await api(API.secretsRotate, "POST", {
      name: nv.name,
      new_value: nv.value,
      keep_previous: true,
      reason: secretReason(),
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("sOut", out);
    notify(t("notify_secret_rotated", { name: nv.name }), "success", t("tab_secrets"));
    return out;
  }

  async function secretDelete() {
    const name = ($("sName")?.value || "").trim();
    const out = await api(API.secretsDelete, "POST", {
      name,
      reason: secretReason(),
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("sOut", out);
    notify(t("notify_secret_deleted", { name }), "success", t("tab_secrets"));
    return out;
  }

  async function secretResolve() {
    const name = ($("sName")?.value || "").trim();
    const out = await api(API.secretsResolve, "POST", {
      env_name: "",
      secret_name: name,
      default: "",
    });
    setBox("sOut", out);
    return out;
  }

  async function secretExport(includeValues) {
    const out = await api(API.secretsExport, "POST", {
      include_values: !!includeValues,
      reason: includeValues ? "UI secret export values(enc)" : "UI secret export metadata",
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("sOut", out);
    const bundle = out?.result?.bundle;
    if (bundle && $("sBundle")) {
      state.lastSecretExportBundle = bundle;
      $("sBundle").value = pretty(bundle);
    }
    return out;
  }

  async function secretImportBundle() {
    const raw = ($("sBundle")?.value || "").trim();
    if (!raw) throw new Error(t("secrets_bundle_empty"));
    const bundle = JSON.parse(raw);
    const out = await api(API.secretsImport, "POST", {
      bundle,
      import_values: !!$("sImportValues")?.checked,
      on_conflict: $("sImportConflict")?.value || "overwrite",
      reason: "UI secret import bundle",
      confirm_owner: true,
      decided_by: "owner",
    });
    setBox("sOut", out);
    return out;
  }

  function replayTextEffective() {
    const preset = $("crPreset")?.value || "/status";
    if (preset !== "custom") return preset;
    return ($("crText")?.value || "").trim();
  }

  function syncReplayPresetToText() {
    const preset = $("crPreset")?.value || "/status";
    if (preset !== "custom") $("crText").value = preset;
  }

  async function channelStatus(kind) {
    let path = API.telegramStatus;
    if (kind === "whatsapp") path = API.whatsappStatus;
    if (kind === "mail") path = API.mailStatus;
    const out = await api(path);
    setBox("crOut", out);
    return out;
  }

  async function channelReplayRun() {
    const channel = $("crChannel")?.value || "telegram";
    const text = replayTextEffective();
    let out;
    if (channel === "telegram") {
      out = await api(API.telegramReplay, "POST", {
        text,
        chat_id: ($("crTelegramChatId")?.value || "999000111").trim(),
        username: "owner_test",
        auto_reply: true,
      });
    } else if (channel === "whatsapp") {
      out = await api(API.whatsappReplay, "POST", {
        text,
        from_number: ($("crWhatsappFrom")?.value || "15550001111").trim(),
        auto_reply: true,
      });
    } else {
      const cmd = $("crMailCmd")?.value || "status";
      out = await api(API.mailReplay, "POST", {
        payload: { cmd, secret: "rth-replay-secret" },
        from_addr: ($("crMailFrom")?.value || "owner@example.local").trim(),
        subject: `[UI Replay] ${cmd}`,
        shared_secret: "rth-replay-secret",
        allow_remote_approve: false,
      });
    }
    setBox("crOut", out);
    return out;
  }

  async function guardianPolicy() {
    setBox("gOut", await api(`${API.guardianPolicy}?lang=${encodeURIComponent(currentLang())}`));
  }
  async function guardianSeverityStatus() {
    const out = await api(`${API.guardianSeverity}?lang=${encodeURIComponent(currentLang())}`);
    if (out && out.current && $("gSeverity")) $("gSeverity").value = out.current;
    setBox("gOut", out);
  }
  async function guardianSeverityApply() {
    const out = await api(API.guardianSeverity, "POST", {
      severity: $("gSeverity").value,
      reason: $("gSeverityReason").value || "UI guardian severity change",
      lang: currentLang(),
      confirm_owner: true,
      decided_by: "owner",
    });
    if (out && out.severity_status && out.severity_status.current && $("gSeverity")) {
      $("gSeverity").value = out.severity_status.current;
    }
    setBox("gOut", out);
    notify(t("notify_guardian_set", { severity: out?.severity_status?.current || $("gSeverity").value }), "success", t("tab_guardian"));
  }
  async function guardianReqs() {
    setBox("gOut", await api(`${API.guardianReqs}?lang=${encodeURIComponent(currentLang())}`));
  }
  async function guardianGate() {
    const out = await fetch(`/api/v1/jarvis/policy?lang=${encodeURIComponent(currentLang())}`).then(r => r.json());
    setBox("gOut", { note: currentLang() === "en" ? "For full gate use `python scripts/rth.py guardian audit --gate`. UI v0 shows policy + requests." : "Per gate completo usare `python scripts/rth.py guardian audit --gate`. UI v0 mostra policy + richieste.", policy: out });
  }

  async function refreshAllModelState() {
    await Promise.all([loadProviders(), loadCatalog()]);
    await loadRoutingPolicy();
    await refreshStatus();
  }

  function prefillProviderTemplate(kind) {
    if (kind === "cloud") {
      $("pId").value = "cloud_main";
      $("pLabel").value = "Cloud Provider";
      $("pType").value = "openai_compat";
      $("pBase").value = "";
      $("pEnabled").checked = true;
      $("pLocal").checked = false;
      $("pModels").value = "";
      $("pNotes").value = ltxt(
        "Inserisci API base e key del tuo provider cloud preferito (OpenAI, Anthropic, Mistral, ecc.)",
        "Enter API base and key for your preferred cloud provider (OpenAI, Anthropic, Mistral, etc.)"
      );
      showTab("providers");
      notify(t("notify_quick_cloud"), "success", t("overview_title"));
      return;
    }
    if (kind === "local") {
      $("pId").value = "local_main";
      $("pLabel").value = ltxt("Provider Locale", "Local Provider");
      $("pType").value = "openai_compat";
      $("pBase").value = "http://127.0.0.1:8080/v1";
      $("pEnabled").checked = true;
      $("pLocal").checked = true;
      $("pModels").value = "";
      $("pNotes").value = ltxt(
        "Inserisci modello e porta del tuo runtime locale (Ollama, LM Studio, vLLM, ecc.)",
        "Enter model and port for your local runtime (Ollama, LM Studio, vLLM, etc.)"
      );
      showTab("providers");
      notify(t("notify_quick_local"), "success", t("overview_title"));
    }
  }

  async function runQuickAction(action) {
    if (action === "setup-cloud") return prefillProviderTemplate("cloud");
    if (action === "setup-local") return prefillProviderTemplate("local");
    if (action === "start-chat") {
      showTab("chat");
      $("chatTask").value = "planning";
      $("chatPrivacy").value = "local_preferred";
      $("chatDifficulty").value = "normal";
      if (!$("chatMsg").value.trim()) $("chatMsg").value = "Analizza lo stato del progetto e proponi i prossimi 3 passi pratici.";
      $("chatMsg").focus();
      notify(t("notify_quick_chat"), "info", t("overview_title"));
      return;
    }
    if (action === "start-village") {
      showTab("village");
      if (!$("vPrompt").value.trim()) $("vPrompt").value = "Valuta rischi, priorita e piano di esecuzione per il prossimo sprint di Core Rth.";
      $("vPrivacy").value = "local_preferred";
      $("vPrompt").focus();
      notify(t("notify_quick_village"), "info", t("overview_title"));
      return;
    }
    if (action === "check-plugins") {
      showTab("plugins");
      await pluginBatchHealthcheck({ priority_only: true, limit: 12, timeout_sec: 1.2, reason: "UI quick action batch healthcheck P0" });
      notify(t("notify_quick_plugins"), "success", t("tab_plugins"));
      return;
    }
    if (action === "guardian-check") {
      showTab("guardian");
      await guardianSeverityStatus();
      notify(t("notify_quick_guardian"), "success", t("tab_guardian"));
      return;
    }
    if (action === "channels-replay") {
      showTab("secrets");
      $("crChannel").value = "telegram";
      $("crPreset").value = "/status";
      syncReplayPresetToText();
      notify(t("notify_quick_channels"), "info", t("status_channels_title"));
      return;
    }
    if (action === "desktop-shell") {
      showTab("wizard");
      $("wCase").value = "desktop_shell";
      loadWizardCase();
      notify(t("notify_quick_desktop"), "info", "Desktop");
    }
  }

  function wizardDefinitions() {
    return {
      chat_first_run: {
        title: t("wizard_case_chat"),
        targetRole: "operator",
        desc: ltxt("Configura almeno un provider, verifica il routing e fai una chat live.", "Configure at least one provider, verify routing and run a live chat."),
        steps: [
          { id: "check_api", title: ltxt("Controlla API", "Check API"), desc: ltxt("Verifica che l'API sia attiva.", "Verify the API is running."), action: "overview_refresh" },
          { id: "provider_template", title: ltxt("Precompila provider", "Pre-fill provider"), desc: ltxt("Carica template cloud o locale nel form Modelli.", "Load cloud or local template in the Models form."), action: "wizard_provider_template" },
          { id: "provider_test", title: ltxt("Test provider", "Test provider"), desc: ltxt("Esegui test del provider dal tab Modelli.", "Run provider test from the Models tab."), action: "wizard_provider_test" },
          { id: "chat_preset", title: ltxt("Prepara chat", "Prepare chat"), desc: ltxt("Apre Chat con prompt iniziale e settaggi base.", "Open Chat with starter prompt and base settings."), action: "start-chat" },
          { id: "chat_live", title: ltxt("Esegui chat live", "Run live chat"), desc: ltxt("Lancia una richiesta reale dalla chat.", "Send a real request from the chat panel."), action: "wizard_chat_live" },
        ],
      },
      connect_telegram: {
        title: t("wizard_case_telegram"),
        targetRole: "owner",
        desc: ltxt("Configura token, verifica stato e fai replay/test.", "Configure token, verify status and run replay/test."),
        steps: [
          { id: "open_secrets", title: ltxt("Apri Segreti + Test", "Open Secrets + Test"), desc: ltxt("Vai al pannello per gestire token e test canali.", "Open the panel to manage tokens and test channels."), action: "open_secrets" },
          { id: "telegram_status", title: ltxt("Controlla stato Telegram", "Check Telegram status"), desc: ltxt("Verifica se Telegram e' configurato.", "Verify whether Telegram is configured."), action: "telegram_status" },
          { id: "telegram_replay", title: ltxt("Replay Telegram", "Telegram replay"), desc: ltxt("Prova il flusso senza rete/credenziali reali.", "Test the flow without network or real credentials."), action: "telegram_replay" },
          { id: "telegram_live_note", title: ltxt("Test live (quando hai token)", "Live test (when you have a token)"), desc: ltxt("Usa lo script channels_live_final_check per il test finale ufficiale.", "Use channels_live_final_check for the official final live test."), action: "wizard_live_hint" },
        ],
      },
      plugin_ide_setup: {
        title: t("wizard_case_plugin_ide"),
        targetRole: "tech",
        desc: ltxt("Controlla plugin AI IDE, fai healthcheck e abilita i plugin utili.", "Check AI IDE plugins, run healthchecks and enable the useful ones."),
        steps: [
          { id: "open_plugins", title: ltxt("Apri Integrazioni", "Open Integrations"), desc: ltxt("Vai al tab plugin.", "Open the plugin tab."), action: "open_plugins" },
          { id: "batch_p0", title: ltxt("Batch P0", "P0 batch"), desc: ltxt("Esegui healthcheck rapido dei plugin prioritari.", "Run a quick healthcheck for priority plugins."), action: "check-plugins" },
          { id: "filter_ide", title: ltxt("Filtra AI IDE", "Filter AI IDE"), desc: ltxt("Applica filtro pack ai_ide.", "Apply pack filter ai_ide."), action: "wizard_filter_ide" },
          { id: "enable_plugin", title: ltxt("Abilita plugin", "Enable plugin"), desc: ltxt("Usa i pulsanti Enable sui plugin IDE disponibili.", "Use Enable buttons on available IDE plugins."), action: "wizard_enable_hint" },
        ],
      },
      desktop_shell: {
        title: t("wizard_case_desktop"),
        targetRole: "owner",
        desc: ltxt("Avvia Core Rth come app desktop con wrapper Electron.", "Run Core Rth as a desktop app with Electron wrapper."),
        steps: [
          { id: "open_desktop_docs", title: ltxt("Apri istruzioni shell desktop", "Open desktop shell instructions"), desc: ltxt("Consulta il README del desktop shell.", "Read the desktop shell README."), action: "wizard_desktop_hint" },
          { id: "start_api", title: ltxt("Avvia API Core Rth", "Start Core Rth API"), desc: ltxt("L'UI desktop usa l'API locale su http://127.0.0.1:18030.", "The desktop UI uses the local API at http://127.0.0.1:18030."), action: "wizard_api_hint" },
          { id: "run_desktop", title: ltxt("Avvia wrapper desktop", "Run desktop wrapper"), desc: ltxt("Esegui il launcher del desktop shell.", "Run the desktop shell launcher."), action: "wizard_desktop_launch_hint" },
        ],
      },
    };
  }

  function getWizardCase() {
    const defs = wizardDefinitions();
    const key = $("wCase")?.value || "chat_first_run";
    return defs[key] || defs.chat_first_run;
  }

  function renderWizard() {
    const summary = $("wSummary");
    const stepsHost = $("wSteps");
    const out = $("wOut");
    if (!summary || !stepsHost) return;
    const w = state.wizard;
    const def = getWizardCase();
    const current = Math.max(0, Math.min(w.currentIndex || 0, (w.steps || []).length - 1));
    if ($("wStepIndex")) $("wStepIndex").value = String(current + 1);
    summary.innerHTML = `
      <div class="status-card ok">
        <div class="title">${esc(def.title)}</div>
        <div class="small">${esc(def.desc || "")}</div>
        <div class="meta-small" style="margin-top:6px;">${esc(t("wizard_recommended_role"))}: <span class="role-pill ${esc(def.targetRole || "owner")}">${esc(humanRole(def.targetRole || "owner"))}</span></div>
      </div>
      <div class="status-card ${w.steps.length ? "ok" : "warn"}">
        <div class="title">${esc(t("wizard_progress"))}</div>
        <div class="big">${esc(`${Object.values(w.statusById || {}).filter(x => x === "done").length}/${w.steps.length}`)}</div>
        <div class="small">${esc(t("wizard_completed_steps"))}</div>
      </div>
    `;
    stepsHost.innerHTML = (w.steps || []).map((s, i) => {
      const st = (w.statusById || {})[s.id] || (i < current ? "todo" : "todo");
      const cls = `${i === current ? " active-step" : ""}${st === "done" ? " done-step" : ""}`;
      return `<div class="row-item${cls}" data-wizard-step-id="${esc(s.id)}">
        <div class="head"><span>${esc(i + 1)}. ${esc(s.title)}</span><span class="wizard-step-meta">${esc(st === "done" ? "done" : (i === current ? t("wizard_current") : "todo"))}</span></div>
        <div class="meta-small">${esc(s.desc || "")}</div>
        <div class="wizard-step-meta">${esc(t("wizard_action"))}: ${esc(s.action || t("wizard_manual"))}</div>
      </div>`;
    }).join("");
    if (out && !out.textContent.trim()) setBox("wOut", { wizard_case: $("wCase")?.value || "chat_first_run", current_step: current + 1, total_steps: w.steps.length });
  }

  function loadWizardCase() {
    const def = getWizardCase();
    state.wizard = { caseId: $("wCase")?.value || "chat_first_run", steps: [...(def.steps || [])], currentIndex: 0, statusById: {} };
    renderWizard();
    showTab("wizard");
    notify(t("notify_wizard_loaded", { title: def.title }), "success", t("tab_wizard"));
  }

  async function runWizardStep() {
    const w = state.wizard;
    const step = w.steps[w.currentIndex] || null;
    if (!step) return;
    let result = { status: "ok", note: ltxt("nessuna azione", "no action") };
    if (step.action === "overview_refresh") {
      result = await loadOverview();
    } else if (step.action === "wizard_provider_template") {
      prefillProviderTemplate(state.uiRole === "operator" ? "local" : "cloud");
    } else if (step.action === "wizard_provider_test") {
      showTab("providers");
      result = await testProviderByForm();
      setBox("providerOut", result);
    } else if (step.action === "wizard_chat_live") {
      showTab("chat");
      if (!$("chatMsg").value.trim()) $("chatMsg").value = ltxt("Dimmi 3 azioni pratiche da fare ora.", "Tell me 3 practical actions to take now.");
      result = await doChatRun();
    } else if (step.action === "open_secrets") {
      showTab("secrets");
    } else if (step.action === "telegram_status") {
      showTab("secrets");
      result = await channelStatus("telegram");
    } else if (step.action === "telegram_replay") {
      showTab("secrets");
      $("crChannel").value = "telegram";
      $("crPreset").value = "/status";
      syncReplayPresetToText();
      result = await channelReplayRun();
    } else if (step.action === "open_plugins") {
      showTab("plugins");
    } else if (step.action === "wizard_filter_ide") {
      showTab("plugins");
      if ($("plFilterPack")) $("plFilterPack").value = "ai_ide";
      renderPluginsTable();
      result = { status: "ok", filter_pack: "ai_ide" };
    } else if (step.action === "wizard_enable_hint") {
      showTab("plugins");
      result = { status: "manual", note: ltxt("Usa Enable sui plugin IDE che hanno healthcheck OK.", "Use Enable on IDE plugins that have an OK healthcheck.") };
    } else if (step.action === "wizard_live_hint") {
      result = { status: "manual", note: ltxt("Per test live finale usa scripts/channels_live_final_check.py con credenziali dedicate.", "For final live tests use scripts/channels_live_final_check.py with dedicated credentials.") };
    } else if (step.action === "wizard_desktop_hint") {
      result = { status: "manual", note: ltxt("Vedi desktop_shell/README.md", "See desktop_shell/README.md") };
    } else if (step.action === "wizard_api_hint") {
      result = { status: "manual", note: ltxt("Avvia API: python scripts/rth.py api start --port 18030", "Start API: python scripts/rth.py api start --port 18030") };
    } else if (step.action === "wizard_desktop_launch_hint") {
      result = { status: "manual", note: ltxt("Avvia wrapper: desktop_shell/START_CORE_RTH_DESKTOP.cmd", "Run wrapper: desktop_shell/START_CORE_RTH_DESKTOP.cmd") };
    } else if (step.action && step.action in { "start-chat": 1, "start-village": 1, "check-plugins": 1 }) {
      await runQuickAction(step.action);
      result = { status: "ok", quick_action: step.action };
    }
    state.wizard.statusById[step.id] = "done";
    setBox("wOut", { step, result });
    renderWizard();
    notify(t("notify_wizard_step_done", { title: step.title }), "success", t("tab_wizard"));
    return result;
  }

  function wizardGo(delta) {
    if (!state.wizard.steps.length) loadWizardCase();
    const max = Math.max(0, state.wizard.steps.length - 1);
    const idx = Math.max(0, Math.min(max, (state.wizard.currentIndex || 0) + delta));
    state.wizard.currentIndex = idx;
    renderWizard();
  }

  function wizardGoTo(index1) {
    if (!state.wizard.steps.length) loadWizardCase();
    const max = Math.max(1, state.wizard.steps.length);
    const idx = Math.max(1, Math.min(max, Number(index1) || 1)) - 1;
    state.wizard.currentIndex = idx;
    renderWizard();
  }

  function bindTopbarUx() {
    $("uiLang")?.addEventListener("change", (e) => applyLanguage(e.target.value));
    $("uiRole")?.addEventListener("change", (e) => setUiRole(e.target.value));
    $("uiMode")?.addEventListener("change", (e) => setUiMode(e.target.value));
    $("uiTour")?.addEventListener("click", () => {
      showTab("overview");
      notify(t("notify_tour"), "info", t("tab_overview"));
    });
    $("ovQuickActions")?.addEventListener("click", async (e) => {
      const btn = e.target.closest(".quick-action[data-action]");
      if (!btn) return;
      try {
        await runQuickAction(btn.dataset.action);
      } catch (err) {
        setBox("ovOut", String(err));
      }
    });
  }

  // --- NEW INTEGRATIONS RC2 ---
  let kgNetwork = null;
  async function loadKnowledgeGraph() {
    $("kgOut").style.display = "block";
    setBox("kgOut", "Caricamento grafo...");
    try {
      const q = $("kgSearchConcept").value || "";
      const d = $("kgSearchDepth").value || 2;
      let url = API.kgQuery;
      if (q) url += `?concept=${encodeURIComponent(q)}&depth=${encodeURIComponent(d)}`;
      const req = await fetch(url);
      const data = await req.json();
      if (!req.ok) throw new Error(data.detail || data.error || "Fail KG Query");

      const nodes = new vis.DataSet();
      const edges = new vis.DataSet();
      const nodeIds = new Set();

      // If we got a graph back
      if (data.nodes && data.edges) {
        data.nodes.forEach(n => {
          if (!nodeIds.has(n.id)) {
            nodes.add({ id: n.id, label: n.label || n.id, title: JSON.stringify(n.properties || {}), group: n.type });
            nodeIds.add(n.id);
          }
        });
        data.edges.forEach((e, i) => {
          edges.add({ id: "e" + i, from: e.source, to: e.target, label: e.type, arrows: 'to' });
        });
      } else if (data.graph) {
        // Alternative format if backend returns raw graph format
        for (const [subj, rels] of Object.entries(data.graph)) {
          if (!nodeIds.has(subj)) { nodes.add({ id: subj, label: subj }); nodeIds.add(subj); }
          for (const [rel, objs] of Object.entries(rels)) {
            for (const obj of objs) {
              if (!nodeIds.has(obj.id)) { nodes.add({ id: obj.id, label: obj.id }); nodeIds.add(obj.id); }
              edges.add({ from: subj, to: obj.id, label: rel, arrows: 'to' });
            }
          }
        }
      }

      const container = document.getElementById('kgNetworkCanvas');
      const networkData = { nodes: nodes, edges: edges };
      const options = {
        nodes: { shape: 'dot', size: 16, font: { size: 14, color: '#ffffff' }, borderWidth: 2 },
        edges: { width: 1, font: { size: 12, color: '#aaa', align: 'middle' }, color: { color: '#666' } },
        physics: { stabilization: false, barnesHut: { gravitationalConstant: -2000, springConstant: 0.04, springLength: 95 } }
      };
      if (kgNetwork) kgNetwork.destroy();
      kgNetwork = new vis.Network(container, networkData, options);
      setBox("kgOut", `Grafo caricato (${nodes.length} nodi, ${edges.length} archi).`);
    } catch (e) {
      setBox("kgOut", String(e));
    }
  }

  async function loadPolicyLedger() {
    setBox("gOut", "Caricamento ledger...");
    try {
      const req = await fetch(API.governanceLedger);
      const data = await req.json();
      if (!req.ok) throw new Error(data.detail || data.error || "Fail load ledger");

      // Assuming data is a list of requests or has an items array
      const items = Array.isArray(data) ? data : (data.requests || []);

      if (items.length === 0) {
        $("policyLedgerTable").innerHTML = '<div style="padding:1rem;">Nessuna operazione registrata.</div>';
        setBox("gOut", "Ledger vuoto.");
        return;
      }

      let html = `<div class="row header">
        <div class="col" style="flex:1;">Data</div>
        <div class="col" style="flex:2;">Azione</div>
        <div class="col" style="flex:1;">Rischio</div>
        <div class="col" style="flex:1;">Decisione</div>
      </div>`;

      items.reverse().forEach(item => {
        const color = item.decision === "approved" ? "green" : (item.decision === "denied" ? "red" : "var(--accent)");
        html += `<div class="row-item" style="border-left: 3px solid ${color};">
            <div class="col" style="flex:1;font-size:0.8rem;">${(item.updated_at || item.created_at || '').substring(0, 19).replace('T', ' ')}</div>
            <div class="col" style="flex:2;"><strong>${item.action}</strong></div>
            <div class="col" style="flex:1;">${item.risk_level || 'UNKNOWN'}</div>
            <div class="col" style="flex:1; font-weight:bold; color:${color}">${item.decision || item.status}</div>
         </div>`;
      });
      $("policyLedgerTable").innerHTML = html;
      setBox("gOut", `Ledger caricato con ${items.length} eventi.`);
    } catch (e) {
      setBox("gOut", String(e));
    }
  }

  async function triggerGlobalEStop() {
    if (!confirm("Sei sicuro di voler bloccare tutte le azioni fisiche? (E-STOP)")) return;
    try {
      $("globalStatusBar").style.backgroundColor = "var(--bg-red, #450a0a)";
      $("btnGlobalEStop").textContent = "E-STOP ATTIVO";
      $("btnGlobalEStop").style.backgroundColor = "darkred";
      // Trigger entrambi
      await fetch(API.roboticsEStop, { method: "POST" }).catch(e => console.error("Robotics stop error", e));
      await fetch(API.vehicleELand, { method: "POST" }).catch(e => console.error("Vehicle stop error", e));

      notify("GLOBAL E-STOP INVIATO A TUTTI I BRIDGE FISICI.", "error");
      loadOverview(); // refreshes metrics
    } catch (err) {
      console.error(err);
      notify("Errore nell'invio del comando E-STOP", "error");
    }
  }

  function bindEvents() {
    $("wLoad")?.addEventListener("click", () => { try { loadWizardCase(); } catch (e) { setBox("wOut", String(e)); } });
    $("wPrev")?.addEventListener("click", () => { try { wizardGo(-1); } catch (e) { setBox("wOut", String(e)); } });
    $("wNext")?.addEventListener("click", () => { try { wizardGo(1); } catch (e) { setBox("wOut", String(e)); } });
    $("wRunStep")?.addEventListener("click", async () => { try { await runWizardStep(); } catch (e) { setBox("wOut", String(e)); } });
    $("wCase")?.addEventListener("change", () => { try { loadWizardCase(); } catch (e) { setBox("wOut", String(e)); } });
    $("wStepIndex")?.addEventListener("change", () => { try { wizardGoTo($("wStepIndex").value); } catch (e) { setBox("wOut", String(e)); } });
    $("wSteps")?.addEventListener("click", (e) => {
      const row = e.target.closest("[data-wizard-step-id]");
      if (!row) return;
      const idx = (state.wizard.steps || []).findIndex((s) => s.id === row.dataset.wizardStepId);
      if (idx >= 0) {
        state.wizard.currentIndex = idx;
        renderWizard();
      }
    });

    $("providerSave").addEventListener("click", async () => { try { await saveProvider(); } catch (e) { setBox("providerOut", String(e)); } });
    $("providerTest").addEventListener("click", async () => { try { await testProviderByForm(); } catch (e) { setBox("providerOut", String(e)); } });
    $("providerReload").addEventListener("click", async () => { try { await refreshAllModelState(); } catch (e) { setBox("providerOut", String(e)); } });
    $("providersTable").addEventListener("click", async (e) => {
      const row = e.target.closest(".row-item");
      if (!row) return;
      const pid = row.dataset.providerId;
      const p = state.providers.find(x => x.provider_id === pid);
      if (e.target.classList.contains("fill-provider")) { if (p) fillProviderForm(p); }
      if (e.target.classList.contains("test-provider")) { try { await testProviderStored(pid); } catch (err) { setBox("providerOut", String(err)); } }
      if (e.target.classList.contains("delete-provider")) { try { await deleteProvider(pid); } catch (err) { setBox("providerOut", String(err)); } }
    });

    document.querySelectorAll(".preset").forEach((b) => b.addEventListener("click", async () => {
      try { await applyPreset(b.dataset.preset); } catch (e) { setBox("routingOut", String(e)); }
    }));
    $("routingSave").addEventListener("click", async () => { try { await saveRoutingPolicy(); } catch (e) { setBox("routingOut", String(e)); } });
    $("routingReload").addEventListener("click", async () => { try { await loadRoutingPolicy(); } catch (e) { setBox("routingOut", String(e)); } });

    $("chatExplain").addEventListener("click", async () => { try { await doRouteExplain(); } catch (e) { setBox("chatTrace", String(e)); } });
    $("chatSend").addEventListener("click", async () => { try { await doChatSim(); } catch (e) { setBox("chatTrace", String(e)); } });
    $("chatSendLive").addEventListener("click", async () => { try { await doChatRun(); } catch (e) { setBox("chatTrace", String(e)); } });
    $("vPlan").addEventListener("click", async () => { try { await doVillagePlan(); } catch (e) { setBox("vOut", String(e)); } });
    $("vRun").addEventListener("click", async () => { try { await doVillageRun(); } catch (e) { setBox("vOut", String(e)); } });
    $("ovRefresh")?.addEventListener("click", async () => { try { await loadOverview(); } catch (e) { setBox("ovOut", String(e)); } });

    $("plStatus").addEventListener("click", async () => { try { await loadPluginsStatus(); } catch (e) { setBox("plOut", String(e)); } });
    $("plCatalog").addEventListener("click", async () => { try { const out = await loadPluginsCatalog(); setBox("plOut", { status: out.status, count: out.count }); } catch (e) { setBox("plOut", String(e)); } });
    $("plMatrix").addEventListener("click", async () => { try { await loadPluginsMatrix(); } catch (e) { setBox("plOut", String(e)); } });
    $("plSchema").addEventListener("click", async () => { try { await loadPluginsSchema(); } catch (e) { setBox("plOut", String(e)); } });
    $("plBatchP0").addEventListener("click", async () => {
      try { await pluginBatchHealthcheck({ priority_only: true, limit: 12, timeout_sec: 1.2, reason: "UI batch healthcheck P0" }); }
      catch (e) { setBox("plOut", String(e)); }
    });
    $("plBatchFiltered").addEventListener("click", async () => {
      try { await pluginBatchHealthcheck({ use_filters: true, limit: 20, timeout_sec: 1.2, reason: "UI batch healthcheck filtered" }); }
      catch (e) { setBox("plOut", String(e)); }
    });
    $("plPresetWorkflow")?.addEventListener("click", async () => {
      try { await applyPluginFilterPreset("workflow"); } catch (e) { setBox("plOut", String(e)); }
    });
    $("plPresetWorkflowEnabled")?.addEventListener("click", async () => {
      try { await applyPluginFilterPreset("workflow_enabled"); } catch (e) { setBox("plOut", String(e)); }
    });
    $("plPresetWorkflowP0")?.addEventListener("click", async () => {
      try { await applyPluginFilterPreset("workflow_p0"); } catch (e) { setBox("plOut", String(e)); }
    });
    $("plBatchWorkflow")?.addEventListener("click", async () => {
      try {
        await applyPluginFilterPreset("workflow");
        await pluginBatchHealthcheck({
          use_filters: true,
          limit: 24,
          timeout_sec: 1.5,
          reason: "UI batch healthcheck workflow builders",
        });
      } catch (e) { setBox("plOut", String(e)); }
    });
    $("plBatchWorkflowEnabled")?.addEventListener("click", async () => {
      try {
        await applyPluginFilterPreset("workflow_enabled");
        await pluginBatchHealthcheck({
          use_filters: true,
          limit: 24,
          timeout_sec: 1.5,
          reason: "UI batch healthcheck workflow builders enabled-only",
        });
      } catch (e) { setBox("plOut", String(e)); }
    });
    $("plBatchWorkflowP0")?.addEventListener("click", async () => {
      try {
        await applyPluginFilterPreset("workflow_p0");
        await pluginBatchHealthcheck({
          use_filters: true,
          limit: 12,
          timeout_sec: 1.5,
          reason: "UI batch healthcheck workflow builders P0",
        });
      } catch (e) { setBox("plOut", String(e)); }
    });
    $("plPresetFiltersReset")?.addEventListener("click", async () => {
      try { await applyPluginFilterPreset("reset"); } catch (e) { setBox("plOut", String(e)); }
    });
    ["plFilterCategory", "plFilterPack", "plFilterTier", "plFilterState", "plFilterEnabledOnly", "plFilterP0Only"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener("input", renderPluginsTable);
      el.addEventListener("change", renderPluginsTable);
    });
    $("plLoadSample").addEventListener("click", () => { $("plManifest").value = pretty(pluginSampleManifest()); });
    $("plValidate").addEventListener("click", async () => { try { await pluginValidate(); } catch (e) { setBox("plOut", String(e)); } });
    $("plRegister").addEventListener("click", async () => { try { await pluginRegister(); } catch (e) { setBox("plOut", String(e)); } });
    $("pluginsTable").addEventListener("click", async (e) => {
      const row = e.target.closest(".row-item");
      if (!row) return;
      const pid = row.dataset.pluginId;
      const item = (state.pluginsCatalog || []).find(x => x.id === pid);
      if (e.target.closest(".plugin-healthcheck")) {
        try { await pluginHealthcheck(pid); } catch (err) { setBox("plOut", String(err)); }
        return;
      }
      if (e.target.closest(".plugin-install")) {
        try { await pluginDriverAction(pid, "install"); } catch (err) { setBox("plOut", String(err)); }
        return;
      }
      if (e.target.closest(".plugin-enable")) {
        try { await pluginDriverAction(pid, "enable"); } catch (err) { setBox("plOut", String(err)); }
        return;
      }
      if (e.target.closest(".plugin-disable")) {
        try { await pluginDriverAction(pid, "disable"); } catch (err) { setBox("plOut", String(err)); }
        return;
      }
      if (!e.target.closest(".plugin-load-manifest")) return;
      if (!item) return;
      const copy = JSON.parse(JSON.stringify(item));
      delete copy.registry_source;
      delete copy.install_state;
      delete copy.enabled;
      delete copy.registry_meta;
      delete copy.last_healthcheck;
      $("plManifest").value = pretty(copy);
      showTab("plugins");
    });

    $("sStatus")?.addEventListener("click", async () => { try { await secretsStatus(); } catch (e) { setBox("sOut", String(e)); } });
    $("sAudit")?.addEventListener("click", async () => { try { await secretsAudit(); } catch (e) { setBox("sOut", String(e)); } });
    $("sSet")?.addEventListener("click", async () => { try { await secretSet(); } catch (e) { setBox("sOut", String(e)); } });
    $("sRotate")?.addEventListener("click", async () => { try { await secretRotate(); } catch (e) { setBox("sOut", String(e)); } });
    $("sDelete")?.addEventListener("click", async () => { try { await secretDelete(); } catch (e) { setBox("sOut", String(e)); } });
    $("sResolve")?.addEventListener("click", async () => { try { await secretResolve(); } catch (e) { setBox("sOut", String(e)); } });
    $("sExportMeta")?.addEventListener("click", async () => { try { await secretExport(false); } catch (e) { setBox("sOut", String(e)); } });
    $("sExportValues")?.addEventListener("click", async () => { try { await secretExport(true); } catch (e) { setBox("sOut", String(e)); } });
    $("sImport")?.addEventListener("click", async () => { try { await secretImportBundle(); } catch (e) { setBox("sOut", String(e)); } });

    $("crPreset")?.addEventListener("change", () => syncReplayPresetToText());
    $("crRun")?.addEventListener("click", async () => { try { await channelReplayRun(); } catch (e) { setBox("crOut", String(e)); } });
    $("crTelegramStatus")?.addEventListener("click", async () => { try { await channelStatus("telegram"); } catch (e) { setBox("crOut", String(e)); } });
    $("crWhatsappStatus")?.addEventListener("click", async () => { try { await channelStatus("whatsapp"); } catch (e) { setBox("crOut", String(e)); } });
    $("crMailStatus")?.addEventListener("click", async () => { try { await channelStatus("mail"); } catch (e) { setBox("crOut", String(e)); } });

    $("gPolicy").addEventListener("click", async () => { try { await guardianPolicy(); } catch (e) { setBox("gOut", String(e)); } });
    $("gSeverityStatus").addEventListener("click", async () => { try { await guardianSeverityStatus(); } catch (e) { setBox("gOut", String(e)); } });
    $("gSeverityApply").addEventListener("click", async () => { try { await guardianSeverityApply(); } catch (e) { setBox("gOut", String(e)); } });
    $("gReqs").addEventListener("click", async () => { try { await guardianReqs(); } catch (e) { setBox("gOut", String(e)); } });
    $("gGate").addEventListener("click", async () => { try { await guardianGate(); } catch (e) { setBox("gOut", String(e)); } });

    // RC2 Events
    $("btnGlobalEStop")?.addEventListener("click", triggerGlobalEStop);
    $("kgLoadBtn")?.addEventListener("click", loadKnowledgeGraph);
    $("gLoadLedger")?.addEventListener("click", loadPolicyLedger);

    // Also load ledger when opening Guardian tab
    document.querySelector('button[data-tab="guardian"]')?.addEventListener("click", loadPolicyLedger);
  }

  async function init() {
    initTabs();
    fillTaskSelects();
    syncReplayPresetToText();
    bindEvents();
    bindTopbarUx();
    try {
      const initialLang = ($("uiLang")?.value || (navigator.language || "it").slice(0, 2) || "it").toLowerCase();
      applyLanguage(initialLang === "en" ? "en" : "it", { silent: true });
      setUiRole($("uiRole")?.value || "owner", { silent: true });
      setUiMode($("uiMode")?.value || "guided", { silent: true });
      showTab("overview");
      try { await refreshAllModelState(); } catch (e) { console.warn("refreshAllModelState fetch failed:", e); }
      try { await loadPluginsCatalog(); } catch (e) { console.warn("loadPluginsCatalog fetch failed:", e); }
      try { await guardianSeverityStatus(); } catch (e) { console.warn("guardianSeverityStatus fetch failed:", e); }
      try { await secretsStatus(); } catch (e) { console.warn("secretsStatus fetch failed:", e); }
      try { await loadOverview(); } catch (e) { console.warn("loadOverview fetch failed:", e); }
      loadWizardCase();
    } catch (e) {
      console.error(e);
      $("apiDot").className = "dot bad";
      $("apiText").textContent = "Errore caricamento";
    }
  }

  init();
})();
