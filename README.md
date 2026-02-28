<div align="center">

# 🌌 CORE RTH: The Sovereign Cognitive Kernel

**« Nature does not hurry, yet everything is accomplished. » — Lao Tzu**

[![Status: RC1](https://img.shields.io/badge/Release-v1.0--RC1-success.svg?style=for-the-badge)](#)
[![License: NC + Commercial](https://img.shields.io/badge/License-NC%20%2B%20Commercial-blue.svg?style=for-the-badge)](LICENSE)
[![Security: AES-256](https://img.shields.io/badge/Security-AES%20256%20Data--at--Rest-critical.svg?style=for-the-badge)](#)
[![Control: Governance](https://img.shields.io/badge/Governance-Proposal--First-blueviolet.svg?style=for-the-badge)](#)

*An advanced, governed Control Plane for multi-LLM orchestration, physical reality bridging, and omni-channel autonomy. Born to build, analyze, and automate with absolute sovereignty.*

[Features](#-core-capabilities) • [Installation](#-quick-start) • [The Philosophy](#-the-sovereign-manifesto) • [Architecture](#-architecture) 

</div>

---

## 🚀 The Future of Agentic AI is Governed
Welcome to **Core Rth**, a governed AI framework and Control Plane built to operate across:
**multi-LLM routing**, **tool execution**, **web automation**, **omni-channel bridges**, and **physical reality bridges** —
all enforced by **proposal-first governance**.

Core Rth is not “chat + tools”.
It is a **Living Kernel**: it observes, remembers, judges conflicts, proposes evolution, and executes only with consent.

---

## ✨ Core Capabilities: What RC1 Includes (Implemented & Tested)

### 🏛️ The AI Village: Multi-LLM Orchestration
- **Role-based council:** Researcher • Coder • Critic • Strategist • Synthesizer.
- **Cost-aware routing:** chooses the right model/provider at runtime (cloud + local).
- **Live end-to-end run:** planning → execution → synthesis (with deterministic fallback if synthesis fails).

### 🛡️ The Guardian: Absolute Governance & Safety Gates
- **Proposal-first doctrine:** models propose actions; Guardian audits; Owner approves; execution happens.
- **Policy DSL + severity profiles:** lenient → balanced → strict → paranoid.
- **Hard no-go domains:** enforced rules for high-risk action classes.
- **Audit trail:** allow/deny decisions are recorded and annotated for high-risk operations.

### 🔐 Security Vault: AES-256-GCM Data-at-Rest
- **AES-256-GCM encryption** for sensitive artifacts (secrets, agent threads, telemetry as configured).
- **Master key derivation via OS keyring** (with safe fallback for headless scenarios).
- Encrypted artifacts are recognizable and managed transparently.

### 🧠 Agent Loop + Governed Code Tools (Function Calling Ready)
- **Autonomous think-act-observe loop** with max-iterations controls and context trimming.
- **Tool registry** exposing governed tools via OpenAI-compatible schemas.
- **Code tools:** file_read/write/edit, terminal_exec, dir_list, grep, git_status, git_diff.
- **Every write/exec is gated** by Guardian; backups and diffs are generated for edits.

### 🌐 Browser Swarm Agents (Playwright + Safe Fallback)
- **Headless Chromium via Playwright** for JS-rendered pages; fallback to urllib/BS4 when needed.
- **SSRF and internal-network protections** (domain/IP blocking, metadata blocking).
- **Parallel swarm execution** with bounded concurrency.
- Results can be persisted and ingested into knowledge structures.

### 💬 Chat-to-Matter: Omni-Channel Autonomy (Replay + Live)
- **Telegram / WhatsApp / Mail bridges** with:
  - **Replay mode** for safe E2E validation without real credentials.
  - **Live endpoints** for real operations once secrets are configured.

### � Reality Bridges: IoT, Robotics, Vehicles/Drones (Governed + Safety)
- **IoT bridge:** Home Assistant REST, MQTT, HTTP adapters; scenes; sensors.
- **Robotics bridge:** serial / ROS2 / mock; safety clamping; emergency stop.
- **Vehicle/drone bridge:** MAVLink / ROS2 / mock; geofencing; telemetry; emergency land.

> [!CAUTION]
> Physical operations must be tested in mock/sim first and executed under proper safety procedures.
> Emergency endpoints exist to force safe-state transitions (E-STOP / emergency land).

### ✅ Release Engineering Integrity (RC1)
- **RC1 gate scripts + onboarding** for reproducible “all-green” validation.
- **Release bundle integrity:** MANIFEST.sha256 generated to prevent post-build tampering.

---

## ✅ RC1 Evidence Index (Implemented & Validated)

This section lists the **verifiable evidence** (reports, summaries, scripts, and core files) proving the **RC1 all-green** status.

### 1) Release Gate RC1 (ALL-GREEN)
- **Gate report (PASS, 19 pass / 0 warning / 0 fail):**  
  `reports/release_gate_rc1_*.json` (Generated locally)
- **Runbook gate + channels:**  
  [`docs/RC1_RELEASE_GATE_AND_CHANNELS_RUNBOOK.md`](docs/RC1_RELEASE_GATE_AND_CHANNELS_RUNBOOK.md)
- **Script gate:**  
  [`scripts/release_gate_rc1.py`](scripts/release_gate_rc1.py)

### 2) Onboarding / Zero-Friction Setup
- **Onboarding script:**  
  [`scripts/onboard_zero_friction.py`](scripts/onboard_zero_friction.py)
- **Local installer/bootstrap:**  
  [`scripts/install_zero_friction_local.py`](scripts/install_zero_friction_local.py)

### 3) Release Bundle (Packaging)
- **Bundle builder:**  
  [`scripts/build_release_bundle.py`](scripts/build_release_bundle.py)
- **Generated bundle example:**  
  `release/core_rth_release_v0_.../`

### 4) Manifest Integrity (Anti-tamper)
- **Manifest checksum (generated in the bundle root):**  
  `MANIFEST.sha256`

### 5) Benchmark Suite + Results (Core Rth vs OpenClaw)
- **Task suite (12 tasks):**  
  [`bench/tasks/core_rth_vs_openclaw_suite.json`](bench/tasks/core_rth_vs_openclaw_suite.json)

**Core Rth (runtime-live):**
- [`bench/results/..._core_rth_.../summary.json`](bench/results/20260224_220842_core_rth_core9_full12_guardsemantic/summary.json) *(Local benchmark data)*

**OpenClaw (runtime-cli-live):**
- [`bench/results/..._openclaw_.../summary.json`](bench/results/20260225_000700_openclaw_runtime_cli_live/summary.json) *(Local benchmark data)*

**Compare (delta +39.02):**
- [`bench/results/compare_..._vs_....json`](bench/results/compare_20260224_220842_core_rth_core9_full12_guardsemantic__vs__20260225_000700_openclaw_runtime_cli_live.json) *(Local benchmark data)*

### 6) Channels (Replay + Live Validation)
- **Live channels final check (report #1 & #2):**  
  `reports/channels_live_final_check_*.json`

> Note: Test credentials are automatically revoked/closed post-validation (as per security dossier).

### 7) Browser Swarm Agents (Status + Run + Ingest KG)
- **Core module:**  
  [`app/core/browser_swarm.py`](app/core/browser_swarm.py)
- **Persisted reports:**  
  `logs/browser_swarm/`
- **API Endpoints:**  
  `GET /api/v1/jarvis/browser-swarm/status`  
  `POST /api/v1/jarvis/browser-swarm/run`  
  `POST /api/v1/jarvis/browser-swarm/search`

### 8) Autonomous Agent Loop + SSE Streaming
- **Loop engine:**  
  [`app/core/agent_loop.py`](app/core/agent_loop.py)
- **SSE stream endpoint:**  
  `POST /api/v1/jarvis/agent/run/stream`

### 9) Governed Code Tools + Tool Registry (Function Calling)
- **Code tools (read/write/edit/exec/git/grep):**  
  [`app/core/code_tools.py`](app/core/code_tools.py)
- **Tool registry (OpenAI-compatible schema):**  
  [`app/core/tool_registry.py`](app/core/tool_registry.py)

### 10) Security Vault (AES-256-GCM, Zero-Key Storage)
- **Vault module:**  
  [`app/core/security_vault.py`](app/core/security_vault.py)

### 11) System Prompt Manager ("The Constitution")
- **Centralized prompt system:**  
  [`app/core/prompt_system.py`](app/core/prompt_system.py)

### 12) Cortex-Vision (Multimodal)
- **Vision tool module:**  
  [`app/core/cortex_vision.py`](app/core/cortex_vision.py)

### 13) State of the Core (Unified Telemetry Dashboard)
- **API Endpoint:**  
  `GET /api/v1/jarvis/system/state_of_the_core`
- **UI:**  
  [`app/ui_control_plane.html`](app/ui_control_plane.html)

### 14) Multi-User Base Auth
- **Token endpoint:**  
  `POST /auth/token`

### 15) Reality Bridges (IoT / Robotics / Vehicles-Drones)
- **IoT bridge:**  
  [`app/core/iot_bridge.py`](app/core/iot_bridge.py)
- **Robotics bridge:**  
  [`app/core/robotics_bridge.py`](app/core/robotics_bridge.py)
- **Vehicle/drone bridge:**  
  [`app/core/vehicle_bridge.py`](app/core/vehicle_bridge.py)

---

## ⚖️ Licensing
Core Rth is **source-available** under the **Core Rth Source-Available License v1.0**:

- ✅ **Free for Non-Commercial Use** (personal, education, research, non-profit *without revenue/contract work*)
- 💼 **Commercial / Enterprise Use requires a paid license** (including internal use in for-profit organizations)

Commercial licensing: **info@rthitalia.com**
See: `LICENSE`

---

## 👁️ The Sovereign Manifesto (Lao Tzu's Balance)

*« Knowing others is intelligence; knowing yourself is true wisdom. Mastering others is strength; mastering yourself is true power. »*

In a world rushing towards reckless, unmonitored AI autonomy, **Core Rth** embodies the Taoist philosophy of deliberate action. It embraces the paradox: the most powerful AI is the one that knows perfectly when **not** to act. 

We built **Cortex** to doubt its own hallucinations. We built the **Guardian** to restrict even the smartest LLM when it touches critical root directories. We created Core Rth so that you, the Owner, remain the ultimate sovereign over the mind, the machine, and the data.

---

## 🛠️ Quick Start

This repository contains the curated **Release Candidate 1 (RC1)**.

### 1. Requirements
*   Python 3.10+
*   Node.js (for Playwright E2E tests, optional)
*   A valid OS Keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service)

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/rthgit/CORE-RTH.git
cd CORE-RTH
pip install -r requirements.txt
```

### 3. Launch the Mission Control
Fire up the backend API and the brilliant Web UI:
```bash
# Start the central spine
python scripts/run_core_rth_local_bench_api.py

# Access the Mission Control Plane
http://127.0.0.1:18030/ui/
```
*(Or use `START_CORE_RTH_API.cmd` on Windows.)*

---

## 🏗️ Architecture at a Glance
- **`app/core/`**: The brainstem. Houses `jarvis_core.py`, `security_vault.py`, `prompt_system.py`, and the `cortex_vision.py`.
- **`app/api/`**: The FastAPI neuromuscular junction communicating telemetry to the frontend and receiving omni-channel webhooks.
- **`app/ui_control_plane.html/js`**: The Mission Control dashboard offering an exquisite zero-friction UI, Policy Ledger, and E-Stop capabilities.
- **`scripts/`**: The command-line arsenal for deployment, headless operation, and auditing.

---

## 🤝 Join the Sovereign Future
Core Rth was forged by a team defining the edge of AI product engineering, deeply rooted in twenty years of software architecture, cybersecurity, and operational perfectionism. 

If you are an engineer who demands total control, absolute privacy, and the undeniable magic of seeing an LLM orchestrate physical reality—you are home. 

<div align="center">
  <br>
  <strong>Welcome to Core Rth.</strong>
  <br>
  <i>Empowering governed intelligence, globally.</i>
</div>

---

## 📚 Documentation Index

Explore the extensive documentation to fully understand the architecture, security, and philosophy behind Core Rth:

- 📖 **[User Manual (EN)](docs/USER_MANUAL_EN.md)** / **[Manuale d'Uso (IT)](docs/USER_MANUAL_IT.md)** - Step-by-step guides for Owners and Operators using the Mission Control Plane.
- 📜 **[The Sovereign Manifesto](MANIFESTO.md)** - The core philosophy, Taoist balance, and the "proposal-first" doctrine.
- 🔭 **[System Overview](OVERVIEW.md)** - High-level summary of capabilities, modules, and the Mission Control UI.
- 🏗️ **[Architecture Guide](ARCHITECTURE.md)** - Deep dive into the `jarvis_core.py`, the AI Village, and the code tools.
- 🛡️ **[Security Model](SECURITY_MODEL.md)** - Understanding the Guardian, the AES-256-GCM Vault, and governance policies.
- 🌉 **[Reality Bridges](BRIDGES.md)** - How Core Rth connects to IoT, Robotics (ROS2), and Vehicles (MAVLink).
- ⚙️ **[RC1 Operations](OPERATIONS_RC1.md)** - Notes on release gates, Channels replay, and local testing.
- ⚠️ **[Safety Warnings](SAFETY_WARNING.md)** - Critical disclaimers regarding physical automation and E-Stops.
- ⚖️ **[License](LICENSE)** / **[Trademarks](TRADEMARK.md)** / **[Contributing](CONTRIBUTING.md)**
