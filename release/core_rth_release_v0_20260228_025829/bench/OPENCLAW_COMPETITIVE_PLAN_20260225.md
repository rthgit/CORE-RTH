# OpenClaw Competitive Teardown + Core RTH Plan (2026-02-25)

## Scope

Goal: define a concrete plan for Core RTH to become better than OpenClaw across measurable dimensions, not by opinion.

Evidence base used:

- Live benchmark A/B results (`bench/results/...`)
- Live OpenClaw runtime CLI probes (built + executed)
- OpenClaw docs + CLI surface + source layout (local clone)

## What OpenClaw Is (in practice)

OpenClaw is not just a chat agent. It is a **gateway-centric agent platform**:

- WebSocket Gateway (control plane + channels + nodes)
- Multi-agent routing with isolated workspaces/auth/sessions
- Large CLI control surface for ops/admin/runtime usage
- Plugin + skills ecosystem
- Channel integrations (many)
- Node/peripheral model (mobile/desktop/headless devices)
- Governance/security stack (approvals, sandboxing, audits)

It is closer to an **agent operating system / communications + automation platform** than a single assistant.

## Verified OpenClaw Capability Surface (local clone)

### Runtime (live, verified in this environment)

From the runtime adapter probes (`bench/adapters/openclaw_runtime_adapter.py`) and task artifacts:

- CLI built and runnable (`node openclaw.mjs ...`)
- `approvals get --json` works
- `sandbox explain --json` works
- `security audit --json` works
- `models status --json` works
- `memory status --json` works (with isolated state dir)
- `skills list --json` works
- `agent --local` reaches model execution path and fails for **missing API key** (runtime is alive)

Reference artifact:

- `bench/results/20260225_000700_openclaw_runtime_cli_live/tasks/guardian_permission_enforcement/openclaw_runtime_probe.json`

### Benchmark Results (A/B)

- Core RTH full suite: `93.85/100`
  - `bench/results/20260224_220842_core_rth_core9_full12_guardsemantic/summary.json`
- OpenClaw runtime-live baseline: `54.83/100`
  - `bench/results/20260225_000700_openclaw_runtime_cli_live/summary.json`

Important: this suite favors Core RTH because tasks are root-specific to your assets (`SublimeOmniDoc`, `ANTIHAKER`).

### Documentation / Platform Breadth (static evidence)

OpenClaw docs are very broad (local clone):

- `docs/` files: ~699
- Major docs areas include:
  - `docs/cli`
  - `docs/channels`
  - `docs/gateway`
  - `docs/tools`
  - `docs/providers`
  - `docs/nodes`
  - `docs/security`
  - `docs/plugins`

Examples:

- `bench/baselines/openclaw/docs/concepts/architecture.md`
- `bench/baselines/openclaw/docs/concepts/multi-agent.md`
- `bench/baselines/openclaw/docs/concepts/memory.md`
- `bench/baselines/openclaw/docs/tools/exec-approvals.md`
- `bench/baselines/openclaw/docs/tools/plugin.md`
- `bench/baselines/openclaw/docs/nodes/index.md`
- `bench/baselines/openclaw/docs/cli/gateway.md`
- `bench/baselines/openclaw/docs/cli/security.md`

### CLI Surface (top-level + subcommands)

Top-level CLI commands include (partial list): gateway, agents, channels, message, nodes, node, plugins, hooks, memory, models, skills, approvals, sandbox, security, doctor, cron, devices, webhooks, browser, system, etc.

Examples verified via `--help`:

- `gateway`: service run/probe/discover/call/install/status/usage-cost
- `nodes`: canvas/camera/screen/location/invoke/pairing/status
- `browser`: large automation surface (snapshot/click/type/evaluate/trace/screenshot/download/upload/etc.)
- `channels`: login/status/logs/resolve/capabilities
- `message`: send/read/edit/delete/reactions/thread/permissions/broadcast/moderation
- `models`: list/set/aliases/fallbacks/auth/status/scan
- `plugins`: install/list/info/enable/disable/update/doctor

## OpenClaw Strengths (what we must respect)

1. Platform breadth
- Channels, nodes, browser automation, gateway ops, services, discovery.

2. Governance maturity
- Exec approvals, allowlists, sandbox policies, security audit tooling.

3. Operationalization
- CLI-first admin workflows, service install/start/stop, status/probe patterns.

4. Ecosystem architecture
- Plugins + manifest/schema validation + skills integration.

5. Documentation and trust posture
- Extensive docs, threat-model docs, formal verification track (TLA+/TLC models).

## Core RTH Strengths (where you are already stronger)

1. Cognitive architecture (unique)
- `Chronicle / KnowledgeGraph / Cortex / Praxis / Guardian` is a stronger conceptual skeleton than generic agent tooling.

2. Project-specific intelligence
- Core RTH already reasons on your real assets (roots, concepts, cross-links, risks, evolutions).

3. Root-aware governance semantics
- Guardian blocks risky actions using Cortex semantic conflicts (not only static allowlists).

4. Evolution planning (Praxis)
- Domain-specific proposals for doc-reader + security stack, not just generic linting.

5. Portfolio synthesis
- Ranking/integration logic for your own ecosystem (2TB portfolio direction).

## Where Core RTH Is Still Behind OpenClaw

These are the real gaps if the target is “better under every point of view”:

1. Platform breadth
- No comparable omnichannel gateway + message operations + remote nodes.

2. Plugin/ecosystem maturity
- No hardened plugin SDK/manifest validation/distribution workflow at OpenClaw level.

3. Operator UX / Ops tooling
- No equivalent CLI command surface, service management, discovery/probe tooling.

4. Security/compliance productization
- Core RTH governance is strong conceptually, but lacks OpenClaw-grade audit/fix tooling, docs, and trust artifacts.

5. Deployment story
- Docker/compose exists in progress, but not yet one-command stable release across modes.

6. Formalized compatibility and docs
- Core RTH has less public-facing structure/specs/runbooks than OpenClaw.

## Strategy: How Core RTH Beats OpenClaw (without becoming a clone)

Do **not** try to win by copying all OpenClaw features first.

Win in two layers:

- **Layer A (Differentiate):** be much better at cognitive control, memory-graph reasoning, project evolution, and semantic governance.
- **Layer B (Parity):** selectively add operational/platform capabilities where needed (CLI, adapters, plugins, security audits, remote execution policies).

This avoids “castle of cards” growth.

## Competitive Plan (measurable)

### Phase 0 — Benchmark Expansion (1-2 weeks)

Objective: stop arguing from impressions; compare on more categories.

Deliverables:

- Extend benchmark suite with OpenClaw-parity dimensions:
  - CLI ops/admin
  - governance policy explainability
  - security audit/fix simulation
  - plugin discovery/config validation
  - provider/model failover config
  - cost-aware model routing (quality vs latency vs cost)
  - multi-model orchestration quality (specialist routing / fallback behavior)
  - browser automation probe
- Split benchmark into:
  - `root-specific cognition suite` (Core RTH advantage)
  - `platform/ops suite` (OpenClaw advantage)
  - `hybrid operator suite` (real target)

Exit criteria:

- A/B scorecards for all 3 suites
- No “unknown” claims left in comparison report

### Phase 1 — Core RTH Product Spine (2-4 weeks)

Objective: make Core RTH a stable product, not only a research skeleton.

Build:

- Unified operator CLI (`rth`) with subcommands:
  - `scan`, `kg`, `cortex`, `praxis`, `guardian`, `policy`, `bench`, `adapters`
- Product UI shell (local-first web UI) backed by the same API/Guardian:
  - dashboard
  - operator chat
  - consent queue
  - audit views
  - guardian severity control (`lenient/balanced/strict/paranoid`)
- Stable service/API lifecycle:
  - `status`, `health`, `start`, `stop`, `restart`
- Config profiles:
  - local-dev / local-prod / secure-readonly / operator-full
- Provider/model control plane (UI + API):
  - simple API-key mask (user inserts key once)
  - local LLM connectors (Ollama / LM Studio / vLLM-style endpoint)
  - model role mapping (which models for what)
  - recommended presets (`premium`, `golden`, `local`, `low-cost`)
- Audit logs:
  - immutable append-only action + consent ledger

Exit criteria:

- One command to start Core RTH locally
- CLI parity for your main workflows
- UI can configure providers/models without editing `.env` manually
- Full benchmark 12/12 reproducible with one script

### Phase 2 — Governance Superiority (2-6 weeks, overlaps)

Objective: exceed OpenClaw in safety quality, not just match it.

Build:

- Guardian policy DSL (human-readable + machine-evaluable)
- Semantic policy enforcement beyond `process_exec`:
  - file writes
  - network access
  - installer/package managers
  - browser automation actions
- Provider/key governance:
  - scoped provider credentials
  - per-model budget caps and routing constraints
  - no-go rules for premium model usage on low-value tasks
- `cortex -> guardian` policy recommendations + conflict explanations
- `guardian audit` command:
  - current policy posture
  - risky roots
  - contract mismatches
  - suggested hardening actions

Exit criteria:

- Guardian blocks/permits explainably per root/domain
- Policy decisions are testable and replayable
- Benchmark governance tasks include semantic enforcement proofs

### Phase 3 — Praxis as Real Differentiator (3-8 weeks)

Objective: make Core RTH the best system for evolving your own software portfolio.

Build:

- Domain packs for Praxis:
  - `desktop-doc-reader`
  - `security-orchestrator/antivirus`
  - `agent-platform`
  - `model-runtime`
- Evidence-backed proposals:
  - every recommendation references file paths / config / code evidence
- Evolution simulation mode:
  - patch preview
  - risk estimate
  - rollback plan
- Proposal-to-execution loop:
  - consent checkpoint
  - task decomposition
  - verification
  - memory reinjection

Exit criteria:

- Top-10 evolutions are specific, non-generic, and executable
- Praxis proposals convert to approved tasks with tracked outcomes

### Phase 4 — Plugin/Adapter System (4-10 weeks)

Objective: match OpenClaw’s extensibility while preserving Core RTH architecture.

Build:

- Core RTH plugin manifest (`rth.plugin.json`)
  - id
  - config schema
  - capability declarations
  - risk class
  - governance defaults
- Adapter SDK:
  - build/run/test probes
  - parse outputs
  - dry-run support
  - consent hooks
- Commercial-software connector strategy (must-have for public release):
  - protocol adapters first (`CLI`, `REST/OpenAPI`, `Webhooks`, `Browser`, `Filesystem/Watchers`)
  - app-specific plugins only where protocol adapters are insufficient
  - compatibility tiers (`first_class`, `verified`, `community`, `fallback_browser`)
- Priority public packs (requested):
  - `Claude ecosystem pack` (Claude Code + cowork/mem surfaces)
  - `AI IDE pack` (Cursor, Windsurf, Trae, Lovable, Antigravity)
  - `llama_cpp runtime/provider pack`
- Plugin validation:
  - schema validation without code execution
  - path safety checks
  - trust/allowlist policy
- Capability registry linked to KG/Cortex/Praxis

Exit criteria:

- External adapters/plugins load safely
- Core RTH can explain what each plugin changes in risk/capability terms
- Core RTH ships with a public compatibility matrix for major commercial tools (not only proprietary/internal tools)

### Phase 5 — Platform Expansion (selective parity, 6-16 weeks)

Objective: only add the OpenClaw breadth that improves your use case.

Priority order (recommended):

1. `system + process + file + browser` operator surface (local-first)
2. Remote node/worker execution (trusted build nodes)
3. Messaging ingress (email first, then one chat channel)
4. Multi-model router + cost controller (single task can use cheap/fast/premium models intentionally)
5. `AI village` orchestration (specialists + comparison + brainstorming + research swarms)
6. Multi-agent/persona routing (only if actually useful to you)

Why this order:

- It reinforces your “digital majordomo” goal without exploding scope into all channels immediately.
- It solves a current OpenClaw weakness you identified: one-model bias and poor economic routing.

Exit criteria:

- Remote execution + consent + audit works on at least one secondary node
- Email command ingress works safely (your stated requirement)
- User can configure provider keys/models in UI and assign model roles without touching code
- Router can prove budget-aware model selection in benchmark traces

### Phase 5A — Multi-LLM Control Plane + “AI Village” UX (4-12 weeks, overlaps Phase 1/5)

Objective: turn Core RTH into a model-aware operator, not a single-LLM wrapper.

Build:

- **Provider/API-key mask UI** (simple form):
  - provider list (OpenAI/Anthropic/OpenRouter/local endpoints)
  - include `llama.cpp` server (`llama_cpp`) as local OpenAI-compatible runtime
  - key input (masked)
  - connection test
  - model discovery / manual model list
- **Model routing matrix UI**:
  - map task classes to models (chat, coding, planning, summarization, vision, research)
  - per-class constraints (max cost, max latency, privacy/local-only)
  - fallback chain and escalation policy
- **Recommended presets**:
  - `premium`
  - `golden`
  - `local`
  - `low_cost`
  - `hybrid_balanced`
- **Operator Chatbot UI**:
  - one main chat for the user
  - visible trace of which model(s) were chosen and why
  - consent checkpoints inline
- **AI Village orchestration board** (optional mode):
  - specialist agents (researcher / coder / critic / verifier / strategist)
  - model assignment per role
  - compare/merge outputs + Cortex synthesis
  - budget and token telemetry

Exit criteria:

- A non-technical user can connect at least one API provider and one local LLM endpoint from UI
- Routing decisions are explainable and cost-bounded
- Core RTH can run single-model and multi-model workflows from the same chat surface

### Phase 6 — Trust & Publication Quality (parallel, ongoing)

Objective: surpass OpenClaw in credibility for serious deployment.

Build:

- Threat model for Core RTH (root scanning, evolution, execution, memory poisoning, plugin supply-chain)
- Security audit command (`rth security audit`)
- Hardening recommendations (`rth security fix --dry-run`)
- Reproducibility packs for benchmark runs
- Formal models for critical invariants (at least Guardian approvals + policy replay)

Exit criteria:

- Security posture is inspectable, not implicit
- Benchmark + audit + policy artifacts are exportable

## “Better Under Every Point of View” → Make It Concrete

Translate the vague goal into 12 scored categories:

1. Cognitive control quality (Chronicle/KG/Cortex/Praxis/Guardian)
2. Project-specific usefulness
3. Governance safety
4. Explainability / auditability
5. Runtime stability
6. Operator UX (CLI/API)
7. Extensibility (plugins/adapters)
8. Platform reach (local + remote)
9. Security posture tooling
10. Docs/runbooks
11. Performance/resource efficiency
12. Upgrade velocity (how fast it improves safely)

Rule:

- We only claim “better” when Core RTH wins in benchmarked categories, not by narrative.

## Immediate Next Actions (recommended order)

1. Build `rth` CLI spine (Phase 1)
- Wrap existing API endpoints + benchmark flows.

2. Add `guardian audit` + policy DSL skeleton (Phase 2)
- Productize your strongest differentiator.

3. Create Praxis domain packs for your two jewels (Phase 3)
- `SublimeOmniDoc` and `ANTIHAKER`.

4. Expand benchmark into 3 suites (Phase 0)
- So OpenClaw vs Core RTH comparisons become fairer and more strategic.

5. Design provider/model control plane v0 (UI + API schema + presets)
- API key mask, local LLM connectors, routing matrix, budget policy.

6. Design `rth.plugin.json` manifest + adapter SDK v0 (Phase 4)
- Avoid future integration chaos.

## Key Decision (important)

If the target remains “Jarvis che fa tutto”, scope will explode.

If the target becomes:

- **best local cognitive operator for your software ecosystem**, then
- **incrementally add channels/nodes/remote control**

then Core RTH can beat OpenClaw in the dimension that matters most to you **and** later catch up on platform breadth.
