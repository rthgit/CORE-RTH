# Reality Bridges - Core Rth

Core Rth non si ferma allo schermo: il cerchio dell'AI Agentica si chiude interfacciandosi con materia e spazio. L'orchestratore "Sovereign" include **tre Bridge nativi** per smart home, robot industriali e veicoli autonomi, regolati dalle strict policy del Guardian. 

## 1. IoT / Domotica Bridge
Ponte di comunicazione per smart home e array di dispositivi hardware.
- **Protocolli:** 
   - `Home Assistant` REST API adapter nativo.
   - `MQTT` adapter per sensori diretti (Zigbee, Z-Wave).
   - Ingressi HTTP per webhook generici.
- **Funzionalità:** Discovery device automatico, lettura sensori, controllo attuatori e raggruppamento azioni in `Scene` eseguibili.
- **Sicurezza:** Modifica sistemi mappata su `SYSTEM_MODIFY` a `RiskLevel.MEDIUM`.

## 2. Robotics Bridge
Integrazione profonda per il controllo bracci, giunti e hardware industriale/domestico.
- **Backend:** `ROS2` (rclpy / rosbridge HTTP) e proxy diretti su porta seriale (`Arduino` e `ESP32`). Driver Mock pronto all'uso per dry-run in sviluppo. 
- **Modellazione Sicurezza Attiva:** Interpolazione costretta della velocità (Clamping MAX 100%) e restrizione della forza motrice limite per manovre pericolose. 
- **Gestore Emergenze:** Emergency stop immediato e globale a sovrascrittura prioritaria (interrompe il Guardian e i code-tools). Ora attivabile istantaneamente dal Control Plane tramite il **Global E-Stop**.
- **Controllo Custom:** Driver che esporta movimenti come istruzioni G-Code per stampanti 3D o CNC base.

## 3. Vehicle / Drone Bridge
Regolamentatore dello sciame UAV e ground vehicles.
- **Backend:** Connessioni protocollo aerospaziale aperto `MAVLink` via `pymavlink` (per ArduPilot e PX4 firmware). Modulo ROS2 sperimentale per flotte stradali (es: CARLA, Autoware).
- **Safety e Geofencing:** Controllo rigidissimo di limitazione spaziale con Haversine distance, raggio operativo bloccato soft/hard, limitazioni di quota massima rigide.
- **Manovra e Telemetria:** Tracking status real-time, pianificazione file missioni o Waypoints, con esecuzione bypass prioritaria "E-Land" o Hover in caso di instabilità logica della IA di comando. (L'E-Land condivide l'innesco con il pulsante **Global E-Stop** del Mission Control).
- **Severità Guardian:** Esecuzioni di piano segnate tutte `RiskLevel.HIGH` o `RiskLevel.CRITICAL`.

*Nota:* 
Tutti e tre i bridge sono incorporati nell'`Agent Loop` tramite gli schemi dei Function Tools nativi (es: `iot_control`, `robot_command`, `vehicle_mission`).
