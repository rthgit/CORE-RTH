# Architecture - Core Rth

Core Rth è strutturato in moduli indipendenti ma interconnessi tramite un bus asincrono.

## 1. Chronicle (Sensori e Percezione)
Rappresenta l'udito e la vista passiva dell'IA.
Effettua scansioni cicliche della directory e dei progetti target per raccogliere segnali espliciti. Pubblica gli `EventBus` senza ritardare le operazioni core, popolando silenziosamente il Knowledge Graph.

## 2. Memory Vault e Knowledge Graph
Sistema di storage persistente ibrido e referenziale:
Rende "vivi" ed interconnessi i facts, i file, le astrazioni e le informazioni di contesto estratte da tutto il sistema. Grazie a questo ponte locale, gli agenti riescono a relazionare logiche di file profondamente diversi, mantenendo lo storico degli intent passati e dei prompt.

## 3. Cortex (Giudizio, Analisi, Ragionamento)
Motore analitico che astrae significato dai dati grezzi:
- Diagnostica **conflitti semantici e bias**.
- Elabora le analitiche della _root_ di sviluppo. 
- Valuta la conformità del codice vs governance (Ci/Cd assenti, dipendenze deboli).
**Cortex-Vision** aggiunge capacità multimodali interpretando base64 e schermate/immagini in input.

## 4. Praxis / Sintesi Attiva
Fornisce suggerimenti domain-specific (orchestratori di sicurezza, web app build, setup ambientali) e consiglia migliorie strutturali sulla base degli eventi intercettati e classificati da Cortex. Alimenta le automazioni reattive.

## 5. EventBus e Agent Loop
L'infrastruttura circola su loop d'eventi FastApi:
L'**Agent Loop** è il cuore dell'azione autonoma (Think-Act-Observe), basato sul function-calling (stile OpenAI schema) per governare Code Tools (Edit, diff, terminali virtuali delimitati), e browser swarms.
Mantiene un limite di iterazione (25 step) per lottare contro i loop infiniti. I Task dell'Agent comunicano via **SSE (Server-Sent Events)** per mostrare il log in tempo reale nelle Web UI.

## 6. System Prompt Manager
La *"Costituzione"*:
Centralizzazione delle direttive dell'Agent divise in gerarchie: **Prime Directive** (agire in pragmatismo), **Domain Personas** (ruoli IoT/Coder/Security flessibili iniettati a runtime), e **Safety Constraints** immutabili a livello sorgente. Attribuisce ai modelli uno stato psicologico coerente durante tutta la chiacchierata.

## 7. Il Plugin Ecosystem
Il supporto plugin estende i tools (Terminal, Web, Code reader). 
Il Registry interno, provvisto di schema validation JSON e cataloghi aggiornati, verifica attivamente l'integrità e il manifest (`rth.plugin.v0`) di ciascun driver esterno integrato a Core Rth, approvando l'abilitazione di strumenti come `Cursor`, `Claude Code` e i proxy runtime.
