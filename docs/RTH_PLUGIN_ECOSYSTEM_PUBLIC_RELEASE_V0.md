# Core Rth Plugin Ecosystem (Public Release v0)

## Premessa (importante)

Se il rilascio pubblico **non include** `ANTIHAKER` e `SublimeOmniDoc`, allora Core Rth deve essere forte su:

- plugin
- adapter
- integrazioni con software commerciali diffusi

Altrimenti il prodotto pubblico sembra "vuoto" rispetto al tuo sistema interno.

## Principio architetturale (per non impazzire)

Non costruiamo subito un plugin per ogni singolo programma.

Costruiamo prima **plugin per protocolli/superfici**:

- `CLI adapter`
- `REST/OpenAPI adapter`
- `Webhook adapter`
- `Browser automation adapter`
- `Filesystem + watcher adapter`
- `Email/IMAP adapter`
- `Database adapter`
- `Local app launcher + safe probes`

Con questi copriamo moltissimi software commerciali senza moltiplicare il codice.

Poi aggiungiamo plugin app-specifici solo dove serve UX profonda o API particolari.

## Target pubblico (major software categories)

### A. Sviluppo / Coding (priorita' alta)

- VS Code
- JetBrains IDEs (IntelliJ, PyCharm, WebStorm, etc.)
- Cursor
- Windsurf
- Trae
- Lovable
- Antigravity (target pack dedicato, se confermato stack/API)
- Git / GitHub / GitLab
- Docker / Docker Compose
- Kubernetes (read-only + dry-run first)
- Terminal/shell tools (PowerShell, bash, cmd)

### B. Produttivita' / Office (priorita' alta)

- Microsoft Word / Excel / PowerPoint (via file + automation/adapters)
- Outlook
- Google Docs / Sheets / Drive
- LibreOffice
- PDF tools (lettura/estrazione/annotazione workflow)

### C. Comunicazione / Collaboration (priorita' alta)

- Gmail / IMAP
- Slack
- Microsoft Teams
- Discord
- Telegram

### C2. Anthropic / Claude Ecosystem (priorita' altissima)

- Claude Code
- Claude workspace/collaboration surfaces (es. "cowork" target)
- Claude memory/mem surfaces (es. "mem" target)
- Anthropic account/provider routing via multi-LLM control plane

Nota:

- i nomi commerciali e le superfici possono cambiare; Core Rth deve modellare queste integrazioni come plugin/adapters con tier di compatibilita' esplicito.

### D. Knowledge / Project Mgmt (priorita' media-alta)

- Notion
- Obsidian
- OneNote
- Jira
- Trello
- Asana / ClickUp

### E. Browser / Web Ops (priorita' alta)

- Chrome / Edge / Firefox (browser adapter + policy)
- download/upload automation
- form fill
- snapshot / scrape / compare

### F. Storage / Cloud / Data (priorita' media)

- OneDrive
- Dropbox
- S3-compatible storage
- Postgres / MySQL / SQLite
- MongoDB (read-first)

### G. AI / Model Runtime (priorita' altissima per il posizionamento)

- Ollama
- LM Studio
- vLLM / OpenAI-compatible endpoints
- llama.cpp server (`llama_cpp`, OpenAI-compatible)
- OpenAI / Anthropic / OpenRouter

## Compatibility tiers (da mostrare in UI e docs)

Ogni integrazione deve avere un tier chiaro:

- `first_class`
  - plugin dedicato + test + policy + docs
- `verified`
  - adapter generico testato su quel programma
- `community`
  - supporto non ufficiale ma installabile
- `fallback_browser`
  - funziona via browser automation con limiti noti

Questo evita promesse vaghe tipo "supporta tutto".

## Plugin Manifest minimo (`rth.plugin.json`)

Ogni plugin deve dichiarare:

- `id`, `name`, `version`
- `vendor`
- `category`
- `surface` (`cli`, `rest`, `browser`, `filesystem`, `hybrid`)
- `capabilities_requested`
- `risk_class`
- `consent_defaults`
- `config_schema`
- `supported_apps`
- `compatibility_tier`
- `healthcheck`
- `commands` / `actions`

## Governance (obbligatoria)

Tutti i plugin devono essere governati da Guardian:

- capability declaration -> policy check
- proposal-first for execution
- dry-run support se possibile
- audit trail
- plugin risk profile
- per-plugin severity overrides (in futuro)

## UI (pubblica) necessaria per plugin ecosystem

La UI deve mostrare:

- catalogo plugin
- stato installazione
- compatibilita' per programma
- configurazione provider/credenziali (mascherata)
- rischio / capability del plugin
- test connessione / healthcheck
- log ultimo run

## Roadmap pratica (rilascio pubblico)

### Phase P1 - Foundation

- `rth.plugin.json` schema v0
- validator manifest
- plugin registry locale
- UI catalogo plugin (read-only)

### Phase P2 - Core adapter packs

- CLI adapter pack
- REST/OpenAPI adapter pack
- Browser adapter pack
- Email/IMAP adapter pack
- Local LLM provider pack
- Claude ecosystem adapter pack (Claude Code + cowork/mem targets)
- AI IDE adapter pack (Cursor / Windsurf / Trae / Lovable / Antigravity)
- llama.cpp runtime adapter pack

### Phase P3 - Major app packs (commercial)

- Dev pack (VS Code/JetBrains/GitHub/GitLab/Docker)
- AI IDE pack (Cursor/Windsurf/Trae/Lovable/Antigravity) con compat matrix
- Office pack (Office/Google Workspace/PDF)
- Collaboration pack (Slack/Teams/Discord/Telegram)
- Claude ecosystem pack (Claude Code + workspace/memory surfaces)
- Knowledge pack (Notion/Obsidian/Jira/Trello)

### Phase P4 - Marketplace / Community

- signed plugins
- trust tier
- compatibility reports
- benchmark + security score per plugin

## Regola prodotto (molto importante)

Il messaggio pubblico non deve essere:

- "abbiamo plugin per tutto"

Ma:

- "abbiamo un'architettura plugin universale + compatibilita' verificata su categorie chiave"

Questo e' piu' credibile, piu' scalabile e ti permette di superare OpenClaw anche in qualita' del controllo.
