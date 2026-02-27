<div align="center">

# 🌌 CORE RTH: The Sovereign Cognitive Kernel

**« Nature does not hurry, yet everything is accomplished. » — Lao Tzu**

[![Status: RC1](https://img.shields.io/badge/Release-v1.0--RC1-success.svg?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Security: AES-256](https://img.shields.io/badge/Security-AES%20256%20Data--at--Rest-critical.svg?style=for-the-badge)](#)
[![Control: Governance](https://img.shields.io/badge/Governance-Proposal--First-blueviolet.svg?style=for-the-badge)](#)

*An advanced, governed Control Plane for multi-LLM orchestration, physical reality bridging, and omni-channel autonomy. Born to build, analyze, and automate with absolute sovereignty.*

[Features](#-core-capabilities) • [Installation](#-quick-start) • [The Philosophy](#-the-sovereign-manifesto) • [Architecture](#-architecture) 

</div>

---

## 🚀 The Future of Agentic AI is Governed
Welcome to **Core Rth**, the world's most comprehensive and secure AI assistant framework. We've moved past mere chatbots and hardcoded scripts. Core Rth is a **Living Kernel**, a sophisticated mission control that unites the intelligence of the world's best linguistic models (Claude, GPT-4, LLaMA) and filters their reasoning through an impenetrable wall of security and governance.

Whether you're developing code, parsing complex semantic connections, managing an automated smart-factory via WhatsApp, routing a drone with MAVLink, or simply seeking a highly private, local AI companion—**Core Rth** executes with absolute clarity, safety, and balance.

---

## ✨ Core Capabilities: Why Core Rth is Unmatched

### 🏛️ The AI Village: Multi-LLM Orchestration
Why rely on a single source of truth when you can assemble an expert council?
*   **Role-based Intelligence:** Automatically route tasks to specialized roles: *Researcher, Coder, Critic, Synthesizer*.
*   **Cost-Aware Routing:** Intelligently switches between cloud behemoths (OpenAI, Anthropic) for heavy logic and hyper-fast local models (llama.cpp, vLLM) for drafts, optimizing budget and latency on the fly.
*   **Unified Village Output:** Watch distinct LLMs debate, verify, and consolidate an answer into a single flawless response.

### 🛡️ The Guardian: Absolute Security & Privacy
The power to modify files or command machines means nothing without safety.
*   **The Proposal-First Doctrine:** AI proposes. The Guardian audits against your strict DSL policy. You approve. The AI executes. Never the other way around.
*   **The Security Vault:** Your API keys, cloud tokens, and sensitive project contexts are locked behind **AES-256 Data-at-Rest** encryption bound to your OS Kernel.
*   **Audit Trail:** The **Policy Ledger** provides a transparent, immutable history of every action allowed or denied to the models.

### 🌉 Reality Bridges: From Text to the Physical World
Core Rth closes the circuit between digital thought and physical action.
*   **IoT & Domotics:** Control your smart home natively via Home Assistant REST or MQTT adapters.
*   **Robotics:** Seamlessly interface with industrial ROS2 robotic arms, Arduino, or ESP32 nodes. Generate G-Code directly from reasoning. Hardware operations are bounded by **strict latency timeouts** and safe-state fallbacks to prevent runaway actuations.
*   **Vehicles & Drones:** Send a mission path directly to a MAVLink drone or query the telemetry of modern autonomous systems (like a Tesla) through an API. Includes geofencing and hard-coded altitude ceilings.

> [!CAUTION]
> 🚨 **GLOBAL E-STOP:** A digital emergency brake integrated directly into your Mission Control UI. A single click bypasses all LLM logic, instantly sending HALT/E-LAND commands to all grounded and flying physical operations globally.

### 🧠 Living Memory & The 2D Explorer
An AI without memory is amnesic. Core Rth learns you.
*   **Knowledge Graph (KG):** Constantly builds and refines an entity network of your projects and conversation topics.
*   **Visual Explorer:** Dive into the mind of your assistant. Explore the relationships and nodes it has mapped with the built-in **Memory Explorer 2D** interactive graph.

<div align="center">
  <img src="docs/assets/memory_explorer_placeholder.png" alt="Memory Explorer 2D Interface" width="800" style="border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.5);"/>
  <br>
  <i>Watch the Sovereign Kernel connect the dots in real-time.</i>
</div>

### 🌐 The Browser Swarm & Workflow Automation
Core Rth isn't limited to its internal logic; it extends its reach into the web and enterprise workflows.
*   **Browser Swarm:** Deploy a swarm of headless browsers (via Playwright) navigated by LLMs. Scrape data, test UI, or automate web research autonomously, all under the Guardian's strict SSRF prevention rules.
*   **n8n & Workflow Integrations:** Seamlessly hook into n8n or Make.com to orchestrate infinitely complex enterprise workflows. Let Core Rth be the cognitive brain that triggers your entire existing no-code infrastructure.

### � Chat-to-Matter: Omni-Channel Autonomy
You don't need a complex dashboard to move a robotic arm or reroute a drone. Control your physical and digital fleet while drinking coffee.
*   **Messaging Integrations:** Connect Core Rth to a dedicated **WhatsApp Business, Telegram Bot, or secure Email channel**. 
*   **Anthropic & Plugin Ecosystem:** Directly expose your Reality Bridges as tools to Claude Desktop, Cursor, or any OpenAI-compatible client. Your LLM can natively call `robot_command()` or `vehicle_mission()` right from a chat window.
*   **The Workflow:** Send a simple audio message on Telegram: *"Move the industrial arm to the resting position and land the drone."* Core Rth transcodes the audio, formulates a strategy with the AI Village (Claude/GPT), requests permission through the Guardian, and executes the physical hardware commands simultaneously.

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
