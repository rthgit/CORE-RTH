# Core Rth Connector Priority Matrix (User-Requested Targets v0)

Questa matrice traduce la tua richiesta in backlog tecnico pubblico, con priorita' e superficie di integrazione.

## Obiettivo

Rilasciare Core Rth con compatibilita' forte verso software importanti in commercio, anche senza includere i tuoi prodotti interni.

## Blocchi richiesti (da te) -> traduzione tecnica

### 1. Anthropic / Claude ecosystem (priorita' massima)

Target richiesti:

- Claude Code
- Claude `cowork` (target da normalizzare al prodotto/superficie esatta)
- Claude `mem` (target da normalizzare al prodotto/superficie esatta)

Strategia:

- `anthropic_provider` plugin (provider + routing + budget policy)
- `claude_code` adapter (CLI/workflow integration)
- `claude_web_or_workspace` adapter (browser/API, se disponibile)
- `claude_memory_surface` adapter (quando la superficie e' verificata)

Tier iniziale consigliato:

- Claude Code: `verified` -> `first_class`
- cowork/mem: `community` / `fallback_browser` finche' non fissiamo API/surface

## 2. AI IDE ecosystem (priorita' massima)

Target richiesti:

- Cursor
- Antigravity
- Trae
- Windsurf
- Lovable

Strategia:

- `ai_ide_base` adapter pack (filesystem/workspace/CLI/browser)
- plugin specifici per IDE dove c'e' CLI/API/utilita' verificabile
- fallback browser per superfici chiuse

Capacita' comuni da riusare:

- scan workspace + context pack
- build/run/test adapters
- patch proposal + Guardian consent
- prompt/export session bridge (quando disponibile)

## 3. LLM runtime locale (`llama_cpp`) (priorita' altissima)

Target richiesto:

- `llama_cpp` (presumo `llama.cpp`; se intendevi altro, lo rinominiamo)

Strategia:

- provider type `llama_cpp` nel control plane multi-LLM
- test connessione a endpoint OpenAI-compatible (`/v1/models` / `/models`)
- routing policy e preset (local / hybrid / low_cost)

Stato attuale:

- supporto base aggiunto nel control plane v0 (provider tipo `llama_cpp`)
- manca esecuzione reale LLM (oggi la chat UI e' simulazione routing)

## Matrice tecnica (v0)

| Target | Tipo integrazione | Superficie primaria | Tier iniziale | Priorita' |
|---|---|---|---|---|
| Claude Code | plugin + adapter | CLI / local workflows | verified | P0 |
| Claude cowork | adapter | API/web/browser (da verificare) | community/fallback_browser | P0 |
| Claude mem | adapter | API/web/browser (da verificare) | community/fallback_browser | P0 |
| Cursor | plugin/adapter | CLI/filesystem/browser | verified | P0 |
| Windsurf | plugin/adapter | CLI/filesystem/browser | verified | P0 |
| Trae | plugin/adapter | CLI/filesystem/browser | verified | P0 |
| Lovable | adapter | web/browser/API | fallback_browser -> verified | P0 |
| Antigravity | adapter | da verificare | community | P0 |
| llama.cpp (`llama_cpp`) | provider plugin | OpenAI-compatible HTTP | verified | P0 |

## Cosa serve per chiudere davvero questa richiesta (step pratici)

1. Manifest + registry plugin v0 (catalogo pubblico)
2. Adapter pack `AI IDE`
3. Adapter pack `Claude ecosystem`
4. Provider runtime `llama_cpp` con esecuzione reale
5. UI tab `Plugins` con tier compatibilita' + healthcheck

## Nota importante

Per `cowork`, `mem`, `antigravity` serve **normalizzazione nomi/prodotto/superficie**:

- nome esatto del prodotto
- endpoint/API/CLI disponibili
- piattaforma (desktop/web)

Ma il backlog e la struttura architetturale sono gia' pronti per accoglierli.

