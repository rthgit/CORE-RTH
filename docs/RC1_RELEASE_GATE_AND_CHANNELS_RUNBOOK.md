# Core Rth RC1 Gate + Channels Live Final Tests

## RC1 Gate (one-click)

Run:

```powershell
python scripts\release_gate_rc1.py --start-api-if-needed
```

What it checks:
- API health
- model/secrets/plugins status
- guardian release gate
- plugin P0 healthcheck batch
- Telegram/WhatsApp/Mail replay endpoints (no credentials)
- pytest replay/secrets suite
- release bundle build
- onboarding zero-friction smoke
- channels live final check (warnings if not configured)

Artifacts:
- JSON report written under `%TEMP%\rth_core\reports\release_gate_rc1_*.json`

## Zero-friction onboarding

Run:

```powershell
python scripts\onboard_zero_friction.py --start-api-if-needed --start-llama-if-needed
```

Outputs a readiness report and next steps.

## Channels live final checks (dedicated credentials only)

Run readiness-only (no send):

```powershell
python scripts\channels_live_final_check.py
```

Run strict final gate (fails if any channel not configured):

```powershell
python scripts\channels_live_final_check.py --require-all-configured
```

Run official send tests (only with dedicated test destinations):

```powershell
python scripts\channels_live_final_check.py ^
  --require-all-configured ^
  --allow-send ^
  --telegram-chat-id <CHAT_ID_TEST> ^
  --whatsapp-to <WHATSAPP_TEST_NUMBER> ^
  --mail-poll-once
```

## Dedicated secret names (recommended)

Store via UI tab `Secrets+Replay` or `/api/v1/secrets/*`:

- Telegram:
  - `channels/telegram/bot_token`
  - `channels/telegram/webhook_secret`
- Mail:
  - `channels/mail/imap_user`
  - `channels/mail/imap_password`
  - `channels/mail/shared_secret`
  - `channels/mail/smtp_user`
  - `channels/mail/smtp_password`
- WhatsApp Meta:
  - `channels/whatsapp/meta/access_token`
  - `channels/whatsapp/meta/verify_token`
- WhatsApp Twilio:
  - `channels/whatsapp/twilio/account_sid`
  - `channels/whatsapp/twilio/auth_token`

Keep `.env.rth.quickstart.local` empty for personal credentials.
