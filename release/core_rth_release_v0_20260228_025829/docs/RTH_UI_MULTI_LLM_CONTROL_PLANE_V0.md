# Core Rth UI + Multi-LLM Control Plane (v0 Draft)

## Goal

Build a local-first UI that lets the user:

- use Core Rth through a chatbot interface
- configure API keys without editing files manually
- connect local LLM endpoints
- choose which model is used for which task
- enable multi-model orchestration ("AI village") with budget control

This is a product differentiator and a direct response to the one-model limitation seen in other agent systems.

## Short Answers (Product Direction)

- **Will Core Rth have a UI?** Yes.
- **Will the UI include a chatbot?** Yes (main operator chat surface).
- **Can we support multiple LLMs with orchestration/comparison/brainstorming?** Yes, and it should be a core feature.
- **Can we optimize cost/quality automatically?** Yes, with a routing matrix + budget policy + fallback chains.

## UX Modules (v0 -> v1)

### 1. Operator Chat (main UI)

Single chat for the user. Core Rth decides routing and orchestration behind the scenes.

Visible in chat:

- selected model (or village composition)
- reason for selection (cost/latency/quality/privacy)
- consent requests (Guardian)
- execution/audit trace summary

### 2. Provider & API Key Mask (simple settings)

User-friendly form (no `.env` editing required):

- provider name (`openai`, `anthropic`, `openrouter`, `ollama`, `lmstudio`, `vllm`, `llama_cpp`, custom)
- API key field (masked)
- base URL (for local/custom endpoints)
- "Test connection" button
- model list (auto-discover or manual)

Security requirements:

- masked display after save
- local encrypted storage (or OS credential store when available)
- export/import only with explicit consent

### 3. Model Routing Matrix

Map tasks to models using simple categories:

- `chat_general`
- `coding`
- `planning`
- `research`
- `summarization`
- `vision`
- `verification`
- `tool_calling`

Per-category controls:

- primary model
- fallback models (ordered)
- max cost per task
- max latency target
- privacy mode (`local_only`, `allow_cloud`)
- reasoning level (`cheap`, `balanced`, `deep`)

### 4. Presets (recommended configurations)

Provide ready-made profiles so the user can start fast:

- `premium`: best quality / higher cost
- `golden`: high quality balanced
- `local`: only local models/endpoints
- `low_cost`: economy-first routing
- `hybrid_balanced`: local-first, cloud escalation on demand

Presets should be editable and clonable.

### 5. AI Village (optional orchestration mode)

A mode for complex tasks where multiple specialists collaborate.

Roles (example):

- `researcher`
- `coder`
- `critic`
- `verifier`
- `strategist`
- `synthesizer` (Cortex-assisted)

Capabilities:

- assign model per role
- compare outputs side by side
- run brainstorming rounds
- merge + score responses
- budget cap for the whole village run

### 6. Guardian Severity Console (required)

The UI must expose a simple Guardian severity selector:

- `lenient`
- `balanced` (default)
- `strict`
- `paranoid`

Requirements:

- apply severity through Guardian/consent flow (not direct hidden file writes)
- show which rules become active/inactive
- explain why a severity change is denied (if current Guardian profile blocks it)
- keep a safe/audit marker in severity-change proposals to avoid self-lockout

## Routing Strategy (core advantage)

Core Rth should choose the cheapest model that satisfies task requirements, and escalate only when needed.

Decision inputs:

- task class
- difficulty estimate (Cortex/Praxis signals)
- tool usage required or not
- privacy constraints (local-only vs cloud allowed)
- token/context size
- latency budget
- cost budget
- historical success for similar tasks

Output:

- selected model or village plan
- fallback chain
- explanation string (for UI and audit)

## Minimal Backend API (v0 target)

Suggested endpoints:

- `GET /api/v1/models/providers`
- `POST /api/v1/models/providers/upsert` (masked secrets)
- `POST /api/v1/models/providers/test`
- `GET /api/v1/models/catalog`
- `GET /api/v1/models/routing-policy`
- `POST /api/v1/models/routing-policy`
- `POST /api/v1/models/presets/apply`
- `POST /api/v1/models/route/explain`
- `POST /api/v1/village/run/propose`

All write/execute actions must go through Guardian.

## Governance Notes

Guardian should enforce:

- per-provider usage caps
- no-go tasks on premium models if policy disallows
- cloud usage denied when task/root is `local_only`
- village runs require explicit consent above budget threshold
- severity profile changes via auditable policy proposals

## Benchmarks To Add (Phase 0)

To prove superiority over one-model systems:

- cost-aware routing correctness
- fallback reliability (provider/model down)
- local-only privacy enforcement
- multi-model synthesis quality vs single-model baseline
- budget adherence under repeated tasks

## Implementation Order (recommended)

1. Backend config schema + masked secret storage
2. Routing policy engine (single-model selection first)
3. UI settings pages (provider mask + routing matrix)
4. Operator chat with route trace
5. AI village mode (specialists + compare + synthesize)
