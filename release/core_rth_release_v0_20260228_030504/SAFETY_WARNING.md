# ⚠️ SAFETY WARNING — Robotics, IoT & Vehicle/Drone Bridges

## Physical Device Control

Core Rth includes bridges for controlling **physical devices and vehicles**:

- **IoT / Domotica** — smart home devices (lights, locks, thermostats, cameras)
- **Robotics** — actuators, motors, servos, robotic arms, CNC machines
- **Vehicles / Drones** — UAVs (ArduPilot/PX4), autonomous vehicles, rovers

### ⚠️ CRITICAL: Physical actions cannot be undone

Unlike software operations, commands sent to physical devices **have real-world consequences**.
A motor that moves, a door that unlocks, a drone that takes off, or a vehicle that accelerates
affects the physical environment and the safety of people nearby.

## Built-in Safety Measures

Core Rth implements multiple safety layers:

| Layer | Protection |
|---|---|
| **Guardian Governance** | Every physical command requires explicit owner approval (`SYSTEM_MODIFY`, `RiskLevel.HIGH`) |
| **Emergency Stop** | Immediate hardware halt via `/robotics/emergency-stop` — bypasses all governance for instant safety |
| **Speed Clamping** | Robotic actuators are software-limited to 100% max speed and 80% max force |
| **Geofencing** | Drones/vehicles are confined to a configurable radius and max altitude (default 500m / 120m) |
| **Altitude Limit** | Maximum altitude enforced per EU drone regulation (120m AGL default) |
| **Speed Limit** | Vehicle speed capped at 20 m/s (~72 km/h) by software |
| **Domain Blocklist** | Browser/network tools block internal IPs to prevent SSRF |
| **Blocked Paths** | File tools block system directories (Windows, /usr, /etc) |
| **Mock Mode** | Robotics and vehicles can run in simulation mode without real hardware |

## ⚠️ AVIATION & VEHICLE REGULATIONS

By using Core Rth's Vehicle/Drone bridge, **you MUST comply with**:

1. **Local aviation law** — EU EASA regulations, FAA Part 107, or equivalent local rules
2. **Drone pilot licensing** — Obtain required certifications (A1/A2/A3 in EU, Part 107 in US)
3. **No-fly zones** — Never operate in restricted airspace (airports, military, government)
4. **Visual Line of Sight** — Maintain VLOS unless you have specific BVLOS authorization
5. **Maximum altitude** — Do not exceed legal ceiling (120m AGL in EU, 400ft in US)
6. **Registration** — Register your drone/vehicle with the relevant authority
7. **Insurance** — Obtain appropriate liability insurance for drone/vehicle operations
8. **Weather** — Do not operate in adverse weather conditions (wind, rain, fog)
9. **Autonomous vehicles** — Comply with local road traffic laws and autonomous vehicle regulations

## ⚠️ User Responsibilities

By using Core Rth's IoT and Robotics bridges, **you accept that**:

1. **YOU are responsible** for ensuring physical safety in all environments where devices are controlled
2. **Always test in mock/simulation mode** before connecting real hardware
3. **Never leave autonomous agent loops running unattended** when connected to physical actuators
4. **Ensure physical emergency stops** (hardware E-Stop buttons) are accessible at all times
5. **Do not use** for safety-critical applications (medical devices, life support, industrial machinery without additional safety PLCs) without professional safety review
6. **Electrical safety** — ensure all connected devices comply with local electrical safety standards
7. **Network security** — protect MQTT brokers, Home Assistant instances, and serial ports from unauthorized access

## ⚠️ Disclaimer

Core Rth is provided **AS-IS** without warranty of any kind. The creators and contributors
are **NOT LIABLE** for any damage, injury, or loss resulting from the use of IoT and Robotics
bridges. This includes but is not limited to: property damage, personal injury, data loss,
or any consequential damages arising from device malfunction or misconfiguration.

**USE AT YOUR OWN RISK.**

## Recommended Setup

1. Start with `mock` interface for all actuators
2. Test commands in `dry_run` mode
3. Set Guardian severity to `strict` or `paranoid` for robotics operations
4. Configure physical hardware E-Stop buttons independent of software
5. Use `confirm_owner: true` (default) for all physical commands
6. Monitor the Memory Vault audit log for all IoT/robotics actions

---

*This safety warning is part of the Core Rth release bundle.*
*Document version: 1.0 — 2026-02-27*
