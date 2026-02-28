# Core Rth - Onboarding Zero Friction (IT)

## Obiettivo

Avviare Core Rth in pochi minuti senza conoscere tutti i dettagli tecnici.

Questa guida copre:

- avvio API
- accesso UI web
- configurazione modelli (Groq o locale)
- test chat / Villaggio AI
- test canali in replay (senza credenziali)

## Prerequisiti minimi

- Python installato
- dipendenze progetto gia installate
- (opzionale) `llama.cpp` locale o provider cloud (es. Groq)

## 1. Avvia API

```powershell
python scripts\\rth.py api start --port 18030
```

Verifica:

```powershell
python scripts\\rth.py api health --port 18030
```

## 2. Apri UI

Apri:

- `http://127.0.0.1:18030/ui/`

Nella topbar puoi scegliere:

- `Lingua` (`IT/EN`)
- `Ruolo` (`Owner`, `Operatore`, `Tecnico`)
- `Modalita UI` (`Assistita`, `Avanzata`)

## 3. Usa "Avvio Guidato"

Nel tab `Inizia`:

- controlla la checklist
- usa le azioni rapide:
  - `Configura Groq`
  - `Configura locale (llama.cpp)`
  - `Apri chat guidata`
  - `Apri Villaggio AI`
  - `Test canali (replay)`

## 4. Wizard per use case

Nel tab `Wizard` scegli uno scenario:

- `Voglio chattare`
- `Voglio collegare Telegram`
- `Voglio usare plugin IDE`
- `Voglio usare Core Rth come app desktop`

Poi usa:

- `Carica wizard`
- `Esegui passo`
- `Passo successivo`

## 5. Configura modelli

### Opzione A - Groq (cloud)

Nel tab `Modelli`:

- usa `Configura Groq` da Avvio Guidato oppure compila il provider
- salva e fai `Test`
- vai in `Chat` e usa `Esegui Live`

### Opzione B - Locale (`llama.cpp`)

- avvia il server locale (`llama_cpp.server`)
- configura provider `llama_cpp`
- salva e fai `Test`

## 6. Chat e Villaggio AI

### Chat

Tab `Chat`:

- scrivi un task
- scegli `Task`, `Privacy`, `Difficolta`
- usa `Simula Chat` o `Esegui Live`

### Villaggio AI

Tab `Villaggio AI`:

- inserisci obiettivo
- scegli `Privacy`, `Budget`, `Ruoli`
- usa `Genera piano` o `Esegui Village Live`

## 7. Guardian

Tab `Guardian`:

- verifica `Severity Status`
- scegli severita (`balanced` consigliato)
- applica con `Applica Severita'`

## 8. Segreti + Test (senza credenziali reali)

Tab `Segreti + Test`:

- gestisci secret nel `secret store`
- usa `Channel Replay` per testare flussi `Telegram/WhatsApp/Mail` senza rete

## 9. Canali live (solo quando vuoi)

Per test finali con credenziali dedicate:

- Telegram
- WhatsApp (Meta/Twilio)
- Mail (IMAP/SMTP)

Usa:

```powershell
python scripts\\channels_live_final_check.py --api-base http://127.0.0.1:18030
```

## 10. Validazione release interna (RC1)

```powershell
python scripts\\release_gate_rc1.py --api-base http://127.0.0.1:18030
```

## Note operative

- Per uso quotidiano: `Modalita Assistita + Ruolo Operatore`
- Per configurazioni avanzate: `Modalita Avanzata + Ruolo Owner/Tecnico`
- Per sicurezza: usa credenziali dedicate e poi ruotale

