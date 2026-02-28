# Core Rth Support Matrix (P0/P1) - 2026-02-26

## P0 (validated / core release path)

- Core Rth API + UI control plane
- Guardian (severity, policy, requests, replay-safe ops)
- Multi-LLM control plane (providers, routing, presets, Groq support)
- Local fallback `llama.cpp` (OpenAI-compatible)
- Plugin registry public + healthcheck + driver actions (selected targets)
- Secrets store (set/rotate/export/import/audit)
- Channel replay (Telegram / WhatsApp / Mail)
- RC1 Gate + onboarding + release bundle builder
- Live channel validation performed:
  - Telegram (live)
  - WhatsApp Twilio Sandbox (live)
  - Mail Fastmail IMAP poll (live)

## P1 (present but not enterprise-complete)

- AI Village planning and live multi-role execution/synthesis
- Plugin ecosystem expansion (Claude surfaces / IDE ecosystems beyond current healthchecks)
- WhatsApp Meta Cloud production path (adapter present, live production setup pending)
- Mail remote approval workflows (supported, not fully hardened for enterprise)
- Browser automation fallback integrations

## Post-release / enterprise backlog

- SSO / RBAC / tenant isolation
- Immutable audit signing / external SIEM export
- HA deployment topology / failover playbooks
- Centralized observability (metrics/traces/log pipeline)
- Compliance packaging (policy packs, retention, evidence exports)

