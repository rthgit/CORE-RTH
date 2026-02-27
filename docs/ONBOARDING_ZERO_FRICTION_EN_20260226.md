# Core Rth - Zero Friction Onboarding (EN)

## Goal

Start Core Rth in a few minutes without learning the full technical stack first.

This guide covers:

- starting the API
- opening the web UI
- configuring models (Groq or local)
- testing Chat / AI Village
- testing channels in replay mode (no credentials)

## Minimum prerequisites

- Python installed
- project dependencies already installed
- (optional) local `llama.cpp` or a cloud provider (e.g. Groq)

## 1. Start the API

```powershell
python scripts\\rth.py api start --port 18030
```

Verify:

```powershell
python scripts\\rth.py api health --port 18030
```

## 2. Open the UI

Open:

- `http://127.0.0.1:18030/ui/`

Topbar controls:

- `Language` (`IT/EN`)
- `Role` (`Owner`, `Operator`, `Tech`)
- `UI Mode` (`Guided`, `Advanced`)

## 3. Use "Guided Start"

In the `Start` tab:

- check the startup checklist
- use quick actions:
  - `Configure Groq`
  - `Configure local (llama.cpp)`
  - `Open guided chat`
  - `Open AI Village`
  - `Test channels (replay)`

## 4. Use-case Wizard

In the `Wizard` tab choose a scenario:

- `I want to chat`
- `I want to connect Telegram`
- `I want IDE plugins`
- `I want Core Rth as a desktop app`

Then use:

- `Load wizard`
- `Run step`
- `Next step`

## 5. Configure models

### Option A - Groq (cloud)

In the `Models` tab:

- use `Configure Groq` from Guided Start or fill the provider form
- save and `Test`
- go to `Chat` and use `Run Live`

### Option B - Local (`llama.cpp`)

- start the local server (`llama_cpp.server`)
- configure `llama_cpp` provider
- save and `Test`

## 6. Chat and AI Village

### Chat

In `Chat`:

- enter a task
- choose `Task`, `Privacy`, `Difficulty`
- use `Simulate Chat` or `Run Live`

### AI Village

In `AI Village`:

- enter topic/objective
- choose `Privacy`, `Budget`, `Roles`
- use `Generate plan` or `Run AI Village Live`

## 7. Guardian

In `Guardian`:

- check `Severity Status`
- choose severity (`balanced` recommended)
- apply with `Apply Severity`

## 8. Secrets + Test (no real credentials)

In `Secrets + Test`:

- manage secrets in the `secret store`
- use `Channel Replay` to test `Telegram/WhatsApp/Mail` flows without network

## 9. Live channels (only when you are ready)

For final tests with dedicated credentials:

- Telegram
- WhatsApp (Meta/Twilio)
- Mail (IMAP/SMTP)

Run:

```powershell
python scripts\\channels_live_final_check.py --api-base http://127.0.0.1:18030
```

## 10. Internal release validation (RC1)

```powershell
python scripts\\release_gate_rc1.py --api-base http://127.0.0.1:18030
```

## Operational notes

- Daily usage: `Guided mode + Operator role`
- Advanced setup: `Advanced mode + Owner/Tech role`
- Security: use dedicated credentials and rotate them after testing

