# Core Rth - Overview

## Cos'e' Core Rth
Core Rth è un **assistente cognitivo locale/cloud governato**, dotato di memoria viva, giudizio strutturato, proposte di evoluzione, routing multi-LLM cost-aware, ecosistema di plugin, e bridge verso il mondo fisico. Non è un semplice wrapper per API LLM, ma un **Control Plane** per agenti autonomi multi-livello.

## Obiettivo Principale
Costruire un assistente tipo "maggiordomo digitale" o "Kernel Cognitivo" che:
- Osserva e capisce il contesto corrente (file, progetti, sistemi).
- Ricorda e collega informazioni nel tempo (Knowledge Graph).
- Giudica conflitti, bias e rischi (Cortex).
- Esegue azioni rigorosamente tramite governance (Proposal-First).
- Usa il modello o lo sciame (Browser Swarm, AI Village) giusto per ogni task, ottimizzando qualità, costo, latenza e privacy.

## Architettura a Blocchi Base
Il sistema gira attorno all’orchestrazione tra questi moduli:
1. **Sensori e Percezione:** `Chronicle` per la scansione file, `EventBus` per il routing asincrono.
2. **Memoria e Ragionamento:** `Knowledge Graph` (memoria viva), `Cortex` (analytics e audit), base vision per i modelli.
3. **Esecuzione:** `Praxis` per suggerimenti operativi evolutivi, `Agent Loop` (autonomo).
4. **Protezione:** `Guardian` (Permission Gate), Policy DSL (Proposal -> Approve -> Execute).

## Multi-LLM Control Plane (Strategic Core)
Il motore di Core Rth prevede provider multipli, un catalogo globale, regole di routing e preset di fallback. 
- **Mission Control UI:** Interfaccia Web avanzata che include telemetria in tempo reale, **Memory Explorer 2D** per esplorare il Knowledge Graph, **Policy Ledger** per l'audit delle decisioni del Guardian, e pulsante **Global E-Stop** per interrompere le azioni fisiche critiche.
- **Surface API:** Supporta provider come OpenAI, Groq, Ollama, LMStudio, vLLM e Llama.cpp.
- **Routing Cost-Aware:** Sceglie automaticamente i modelli analizzando *Task Class*, *Privacy Mode* locale/cloud, *Costo*, *Latenza*, ragionamento necessario.
- **Preset:** Modalità "premium", "low cost", "hybrid balanced".

## AI Village (Esecuzione ad orchestra)
Una delle funzionalità differenzianti è il Villaggio AI. L'astrazione di un "team" di agenti con ruoli separati (es: *Researcher, Coder, Critic, Synthesizer*) che collaborano a un obiettivo.
Il Village pianifica il flusso, gestisce i token limits, controlla i budget e restituisce un risultato sintetizzato o un feedback comparativo.
