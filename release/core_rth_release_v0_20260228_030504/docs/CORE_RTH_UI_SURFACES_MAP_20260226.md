# Core Rth UI / API Surfaces Map - 2026-02-26

## UI panels (web control plane)

- `Overview`
  - API health, models, Guardian, plugins, secrets, channels summary
- `Chat`
  - route explain, simulated chat, live chat execution
- `Providers`
  - provider CRUD, API-key masking, provider tests
- `Routing`
  - routing matrix, presets, policy save/reload
- `AI Village`
  - plan roles/budget + live multi-role execution + synthesis
- `Plugins`
  - registry status, catalog, matrix, schema, healthcheck batch, driver actions
- `Secrets+Replay`
  - secret store ops + Telegram/WhatsApp/Mail replay tests
- `Guardian`
  - policy, severity, requests, gate guidance

## API surfaces (major groups)

- `/api/v1/models/*`
  - providers, routing, chat, village plan/run
- `/api/v1/plugins/*`
  - catalog, schema, healthcheck, driver, install state
- `/api/v1/secrets/*`
  - set/delete/rotate/resolve/export/import/audit
- `/api/v1/jarvis/*`
  - guardian, mail/telegram/whatsapp status + replay/live endpoints

## Desktop/app style status

Current status:

- **Web app control plane** (strong)
- **Desktop app polished shell** (not primary packaging in this iteration)

Desktop-like experience can be added later via wrapper (Tauri/Electron), but core product capability is already exposed through the web UI + local launchers.

