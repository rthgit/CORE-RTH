# Security Model - Core Rth

Core Rth è forgiato sul principio che la sicurezza non è una pezza applicata al prodotto, ma il prerequisito fondamentale dell'azione autonoma.

## Guardian e Permission Gate
Il componente **Guardian** funge da Security Vault e Permission Gate. Applica il modello Proposal-First: `propose -> approve -> execute`.
Il sistema ha vari livelli di severità che definiscono le regole operative: `lenient`, `balanced`, `strict`, `paranoid`.

Il sistema modella e approva azioni di:
- `process_exec`: Avvio processi/script
- `system_modify`: Modifica delle opzioni hardware, del sistema, o stato dei plugin.
- `filesystem_write`: Scrittura e modifica dei file su disco
- `network_access`: Accesso a web scraper / API internet extra.

Sono introdotte categoricamente categorie **Hard-No-Go** (Es: `payments`, `social_posting`) indipendentemente dalla severità. 

## Policy DSL e Guardian Reqs
Le regole sono dichiarative. I conflitti e la semantica dei percorsi sono monitorati. Ad esempio, è pre-impostato un default "deny" sulle scritture o le esecuzioni in root directories classificate ad alto rischio (es: cartelle di sistema).
Quando l'Agent necessita di un'azione a rischio, emana un ticket in coda Governance Request per l'accettazione esplicita dell'`owner`.
Ogni azione proposta, approvata o rifiutata viene registrata indelebilmente nel **Policy Ledger**, uno strumento di Audit Trail integrato nel Control Plane che permette la totale trasparenza delle operazioni di governance nel tempo.

## Security Vault
Crittografia completa Data at Rest tramite:
- **AES-256-GCM** per i segreti API Key, stringhe di connessione, token canali, telemetria log, e memorie di sessione agentica persistente.
- Master Key prelevata dall'OS Keyring (Windows Credential Manager / Mac Keychain).
- Fallback in ambiente "Headless" via Hardware ID hashing.
Tutti i componenti passano dal vault per esportare, caricare o eliminare informazioni.

## Hardening Applicativo
Il motore (`app/`) non fa leva su comandi arbitrari non strutturati.
- **Nessun:** `eval()`, `exec()`, `os.system()`, o `shell=True` presente nella codebase.
- **Nessun:** Segreto hard-coded.
- Input convalidato preventivamente da Pydantic.
- Il Browser Swarm blocca tentativi su IP locali e metadata cloud (SSRF Prevention).

## Manifest Integrity Checksum
Per difendere la codebase da attacchi _supply chain_ o _side-loading_, l'eseguibile richiede la validazione del file `MANIFEST.sha256`. 
I file del bundle vengono scansionati e protetti tramite check degli hash matematici allo start del control plane.
