# 📘 Core Rth: Manuale d'Uso (v1.0 RC1)

Benvenuto nel **Manuale d'Uso di Core Rth**. Questa guida è pensata per gli operatori, i proprietari (Owner) e i tecnici che utilizzeranno quotidianamente il Mission Control Plane per interagire con il Sovereign Cognitive Kernel.

---

## Indice
1. [Introduzione & Setup a Zero Attrito](#1-introduzione--setup-a-zero-attrito)
2. [L'"Avvio Guidato" (Guided Start)](#2-lavvio-guidato-guided-start)
3. [Gestione Modelli & Provider](#3-gestione-modelli--provider)
4. [Conversazioni e Villaggio AI](#4-conversazioni-e-villaggio-ai)
5. [Integrazioni ed Ecosistema Plugin](#5-integrazioni-ed-ecosistema-plugin)
6. [Canali Remoti (Channels)](#6-canali-remoti-channels)
7. [Governance e Sicurezza (Il Guardian)](#7-governance-e-sicurezza-il-guardian)
8. [Reality Bridges (Automazione Fisica)](#8-reality-bridges-automazione-fisica)

---

## 1. Introduzione & Setup a Zero Attrito

### Cos'è Core Rth?
Core Rth non è un semplice chatbot; è una **Command API** progettata per connettere l'Intelligenza Artificiale al mondo fisico, mantenendo al tempo stesso un'assoluta sovranità e sicurezza dei dati. Attraverso la UI del Mission Control Plane, puoi governare molteplici modelli linguistici, orchestrare task paralleli complessi e innescare azioni su sistemi fisici (droni, robot, IoT) sotto un rigoroso set di regole.

### Accedere al Mission Control Plane
Una volta che l'API backend è in esecuzione (generalmente tramite `python scripts/rth.py api start`), puoi accedere all'interfaccia aprendo il tuo browser web all'indirizzo:
`http://127.0.0.1:18030/ui/` (o la porta specifica mappata sul tuo server).

### Comprendere i Ruoli Utente
In alto a destra nella barra di navigazione, puoi alternare tra tre ruoli concettuali:
*   **Owner (Proprietario):** Ha visibilità e autorità totale su tutte le impostazioni, inclusi i registri di sicurezza (Ledger) e il Global E-Stop.
*   **Operatore:** Focalizzato sui task quotidiani. Vede schermate semplificate per interagire con la Chat e il Villaggio AI senza distrazioni tecniche.
*   **Tecnico:** Focalizzato sulle integrazioni, le configurazioni API, gli healthcheck dei plugin e le matrici di routing del sistema.

---

## 2. L'"Avvio Guidato" (Guided Start)

Appena apri Core Rth, atterrerai sul tab **Avvio Guidato (Overview)**. Questo è il tuo centro di comando per preparare il sistema senza doverti addentrare in menu complessi.

### La Startup Checklist (Checklist di Avvio)
Questa sezione verifica automaticamente la salute del tuo sistema:
1.  **API Attiva:** Verifica che il backend sia raggiungibile.
2.  **Provider Configurato:** Assicura che tu abbia configurato almeno un provider LLM (come OpenAI o un'istanza locale di Ollama).
3.  **Catalogo Modelli:** Conferma che i modelli siano stati caricati con successo dal provider.
4.  **Guardian Configurato:** Controlla l'attuale severità di sicurezza/governance.
5.  **Canali Remoti & Secret Store:** Verifica che le tue chiavi di integrazione siano conservate in modo sicuro nel keyring del sistema operativo.

### Azioni Rapide & Wizard
Sotto la checklist si trovano le **Azioni Rapide**. Cliccando questi pulsanti verranno caricati automaticamente dei template preconfigurati nei tab corrispondenti.
*   *Esempio:* Cliccando **"Aggiungi provider"** (Add provider) verrai portato al tab Modelli (Models) e verrà incollata una configurazione standard per OpenAI o Anthropic.
*   In alternativa, usa lo **Wizard End-to-End per Use Case** sotto le Azioni Rapide. Seleziona un obiettivo (es. "Voglio chattare"), e il sistema ti guiderà passo dopo passo per realizzarlo.

---

## 3. Gestione Modelli & Provider

Core Rth è agnostico rispetto ai modelli. Puoi connetterlo al cloud o farlo girare interamente offline.

### Aggiungere un Provider Cloud
1.  Naviga al tab **Modelli** (Models).
2.  Nel *Provider Form*, seleziona "OpenAI Compatible" (funziona per OpenAI, Groq, proxy Anthropic, ecc.).
3.  Inserisci la Base URL (es. `https://api.openai.com/v1`).
4.  **Devi** fornire una API Key. *Non* inserire la chiave reale nel campo di testo; inserisci invece un riferimento a un segreto come `{{SECRET_OPENAI_KEY}}`. (Vedi la Sezione 7 su come impostare i segreti).
5.  Clicca **Save provider** (Salva provider) e poi **Test** per assicurarti che la connessione funzioni e che i modelli vengano popolati.

### Aggiungere un Provider Locale
1.  Assicurati di avere un motore di inferenza locale in esecuzione (come Ollama o vLLM).
2.  Nel *Provider Form*, seleziona "Ollama".
3.  Inserisci l'URL locale (es. `http://localhost:11434/v1`).
4.  Lascia vuoto il campo API Key (o usa un token fittizio se richiesto dal tuo proxy locale).
5.  Salva e Testa.

### La Matrice di Routing
Nel tab **Routing**, tu definisci il "cervello" di Core Rth. Puoi indicare al sistema:
*   *Per Chat Generali:* Usa `gpt-4o-mini`.
*   *Per il Coding:* Usa `claude-3-5-sonnet` (o un `Qwen2.5-Coder` locale).
*   *Per task rigorosi sulla Privacy:* Forza il sistema a usare *solo* `mistral-nemo-local`.
Questo permette a Core Rth di instradare automaticamente i tuoi prompt verso il modello più economico, intelligente o sicuro a seconda del contesto.

---

## 4. Conversazioni e Villaggio AI

### Chat a Singolo Modello
Naviga al tab **Chat** per interazioni standard 1-a-1.
*   **Simula Chat (Simulate Chat):** Esegue la logica di routing per dirti *quale* modello verrebbe usato e *perché*, senza effettuare realmente la chiamata API. Ottimo per testare la tua Matrice di Routing.
*   **Esegui Live (Run Live):** Invia effettivamente il prompt al LLM scelto.
*   **Prompt System:** Core Rth antepone automaticamente ai tuoi messaggi la "Costituzione" (La Direttiva Primaria e i vincoli di Sicurezza).

### Il Villaggio AI (Knowledge Graph)
Il fiore all'occhiello di Core Rth. Si trova nel tab **AI Village**, questa funzione ti permette di generare uno "sciame" (swarm) di agenti.
1.  Inserisci un problema complesso (es. "Progetta l'architettura per un database scalabile in alta affidabilità").
2.  Clicca **Generate plan**. Core Rth proporrà una serie di "Ruoli" distinti (es. `Architetto`, `Revisore Sicurezza`, `Ingegnere DevOps`, `Sintetizzatore`).
3.  Clicca **Run AI Village Live**.
4.  Il sistema invocherà gli LLM in parallelo. Loro dibatteranno, criticheranno e, alla fine, il Sintetizzatore combinerà i loro output in un unico documento definitivo.

---

## 5. Integrazioni ed Ecosistema Plugin

Core Rth è estendibile tramite Plugin. Vai al tab **Integrazioni** (Integrations).

*   **Registry Status:** Ti mostra le capacità caricate (es. lettura file, web scraping, operazioni git).
*   **Batch Healthcheck P0:** Testa le integrazioni critiche come l'accesso al tuo file system locale o i toui webhook n8n.
*   Per abilitare un plugin, questo deve esistere nel catalogo ed essere contrassegnato come "enabled" (abilitato). Il Guardian bloccherà attivamente i plugin che non sono esplicitamente autorizzati.

---

## 6. Canali Remoti (Channels)

Core Rth può agire in autonomia basandosi su messaggi ricevuti da Telegram, WhatsApp o Email.

### Modalità Replay (Test Senza Rete)
Prima di mettere Core Rth live su Telegram, puoi testarlo localmente.
1.  Vai al tab **Segreti + Test** (Secrets + Test), scorri fino a **Channel Replay**.
2.  Seleziona un canale (es. `Telegram`).
3.  Scrivi un payload che simuli il testo dell'utente (es. `"Ciao AI, riassumi le mie ultime email"`).
4.  Clicca **Run Replay**. Il sistema processerà l'input internamente come se provenisse da Telegram, utilizzando la tua Matrice di Routing e i Plugin, senza mai toccare la rete internet esterna.

---

## 7. Governance e Sicurezza (Il Guardian)

La sicurezza è fondamentale. Core Rth utilizza una politica di archiviazione "zero-key" (nessuna chiave mostrata) e un supervisore rigoroso chiamato "Il Guardian".

### Gestione Segreti
1. Vai al tab **Segreti + Test** (Secrets + Test).
2. Nel form *Set Secret*, dai un nome al tuo segreto (es. `SECRET_OPENAI_KEY`).
3. Incolla la vera e propria API key nel campo value (valore).
4. Fornisci un motivo obbligatorio (es. "Usata per il routing su GPT-4").
5. Clicca **Set**.
*Come funziona: La chiave viene codificata usando AES-256-GCM e archiviata in modo sicuro. Core Rth la inietterà nelle chiamate API limitrofe solo all'ultimo millesimo di secondo.*

### Le Severità del Guardian
Si trovano nel tab **Guardian**:
*   **Balanced (Bilanciato):** Consente operazioni di sistema normali e modifiche file standard.
*   **Strict (Rigoroso):** Richiede un'esplicita approvazione dell'utente per azioni pericolose (come eseguire comandi bash o modificare `jarvis_core.py`).
*   **Paranoid (Paranoico):** Blocca completamente il sistema. L'AI non può toccare il file system o internet; diventa di sola lettura (read-only).
*Tutte le decisioni del Guardian sono registrate immutabilmente nel **Policy Ledger**, visibile in fondo al tab Guardian.*

---

## 8. Reality Bridges (Automazione Fisica)

Core Rth può controllare il mondo fisico attraverso i Reality Bridges.

### Monitorare i Bridge
Nel tab **Start** (Overview), il widget in alto mostra la **State of the Core** (Telemetria del Nucleo). Questa dashboard ti mostrerà se l'IoT Bridge (Home Assistant), il Robotics Bridge (ROS2), o il Vehicle Bridge (MAVLink/Droni) sono connessi e in salute.

### Global E-Stop (Arresto di Emergenza)
Se un agente AI o uno script automatizzato che controlla un dispositivo fisico inizia a comportarsi in modo irregolare:
1.  Guarda nell'angolo in alto a destra della barra di navigazione.
2.  Clicca il pulsante rosso **GLOBAL E-STOP**.
3.  Conferma l'azione.
*Questo override prioritario emette immediatamente un comando `kill` locale agli assi robotici e un comando `emergency_land`/`RTL` (Return To Launch) ai droni connessi, recidendo all'istante l'agire fisico dell'AI.*

---
*Fine del Manuale.*
