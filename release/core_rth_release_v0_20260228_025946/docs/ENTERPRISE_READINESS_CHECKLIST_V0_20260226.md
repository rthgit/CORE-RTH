# Core Rth Enterprise Readiness Checklist (v0) - 2026-02-26

## Current classification

- **Final Candidate / Pilot Ready**
- **Not yet enterprise-production ready** (full scope)

## Gate categories

### 1) Identity & Access

- [ ] SSO (OIDC/SAML)
- [ ] RBAC roles (admin/operator/viewer/auditor)
- [ ] per-action authz policy and tenant scoping
- [ ] break-glass procedure documented

### 2) Secrets & Key Management

- [x] local secret store + rotate/export/import/audit
- [ ] external KMS / Vault integration
- [ ] secret rotation policy automation
- [ ] secret access audit signing / tamper evidence

### 3) Audit / Governance

- [x] Guardian policy + severity + semantic guard
- [x] proposal/approve flow
- [ ] immutable audit export (WORM/SIEM)
- [ ] compliance-ready evidence pack generation

### 4) Reliability / Operations

- [x] health endpoints
- [x] RC1 release gate
- [x] onboarding smoke
- [ ] metrics + tracing (Prometheus/OpenTelemetry)
- [ ] centralized logging
- [ ] backup/restore tested
- [ ] HA deployment topology

### 5) Network / Security Hardening

- [ ] TLS termination guidance + cert rotation
- [ ] reverse proxy hardening profile
- [ ] egress restrictions per provider/channel
- [ ] rate limits / abuse controls / IP allowlists

### 6) Product Surface / UX

- [x] web control plane (operators)
- [x] channel replay and live validation path
- [ ] enterprise admin UX polish (users/roles/org settings)
- [ ] branded onboarding docs for non-technical operators

## Recommended next enterprise sprint

1. OIDC auth + RBAC
2. Audit export signing + SIEM connector
3. Metrics/tracing/logging stack
4. Reverse proxy hardening + TLS docs
5. Enterprise deployment reference architecture

