# Operations RC1 - Core Rth

Documentazione operativa per l'uso, il deploy rapido e le routine di validazione della Release Candidate 1.

## Stato Attuale (RC1)
L'infrastruttura di base è validata come **Top-tier RC / Final Candidate**:
- Architettura e funzioni chiave stabili.
- System Prompt Manager e Web Control Plane attivi.
- Benchmark A/B eseguiti e canali testati.
- Pronti all'uso *operator*, in attesa di UI enterprise lucidata al 100%.

## Gate e Validazioni (Release Engineering)
Ogni rilascio passa per controlli stretti e pipeline documentate in `scripts/`:

### 1. RC1 Gate One-Click
`scripts/release_gate_rc1.py`
Questo script valida la salute delle API, sblocca o verifica i secrets nel vault, i plugin in catalogo, la policy server, i replay dei canali e compila infine il bundle per la release.

### 2. Onboarding Zero-Friction
`scripts/onboard_zero_friction.py`
Test end-to-end sull'installazione. Mette alla prova le env quickstart, i controlli salute base, i backend di esecuzione locali (es. llama.cpp) e la connettività cloud.

### 3. Builder della Release 
`scripts/build_release_bundle.py`
Impacchetta repository, codice filtrato, documentazione, gli adapter locali e genera il file manifesto **`MANIFEST.sha256`** per l'hashing-signature, evitando side-loading.

## Canali Remoti e Replay Mode
Core Rth espone bridge per la messaggistica (es., `Telegram`, `WhatsApp` tramite Twilio/Meta, `E-Mail`).

Tutti hanno un **Replay Mode**:
Serve a per validare End-To-End l'intero ciclo logico dell'app e le risposte del bot *senza bisogno di credenziali o API token reali*. Utile nello sviluppo, i replay testano i flussi di chat e auto-risposta.

## Web Control Plane 
Interfaccia utente web integrata visiva (Accessibile a `http://localhost:8000/ui/`):
Il design *Glassmorphism* Premium funge da Mission Control per:
- Segnalare proposte pendenti e telemetria live del sistema.
- Passare tra modalità Guidata, Checklists, e Villaggio AI.
- Analizzare il routing e le chat live.
- Manutenere lo storage dei plugin e il Vault segreti.
- Gestire lo status dei runtime hardware (Bridges IoT, Droni e Robotica).
