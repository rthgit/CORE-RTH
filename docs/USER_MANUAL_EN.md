# 📘 Core Rth: User Manual (v1.0 RC1)

Welcome to the **Core Rth User Manual**. This guide is designed for operators, owners, and technicians who will use the Mission Control Plane to interact with the Sovereign Cognitive Kernel on a daily basis.

---

## Table of Contents
1. [Introduction & Zero-Friction Setup](#1-introduction--zero-friction-setup)
2. [The "Guided Start" (Avvio Guidato)](#2-the-guided-start-avvio-guidato)
3. [Model & Provider Management](#3-model--provider-management)
4. [Conversations and the AI Village](#4-conversations-and-the-ai-village)
5. [Integrations and Plugins Ecosystem](#5-integrations-and-plugins-ecosystem)
6. [Remote Channels](#6-remote-channels)
7. [Governance and Security (The Guardian)](#7-governance-and-security-the-guardian)
8. [Reality Bridges (Physical Automation)](#8-reality-bridges-physical-automation)

---

## 1. Introduction & Zero-Friction Setup

### What is Core Rth?
Core Rth is not just a chatbot; it is a **Command API** designed to connect Artificial Intelligence to the physical world while maintaining absolute data sovereignty and security. Through the Mission Control Plane UI, you can govern multiple language models, orchestrate complex parallel tasks, and trigger actions on physical systems (drones, robots, IoT) under a strict set of rules.

### Accessing the Mission Control Plane
Once the backend API is running (usually via `python scripts/rth.py api start`), you can access the interface by navigating your web browser to:
`http://127.0.0.1:18030/ui/` (or the specific port mapped on your server).

### Understanding User Roles
The top right of the navigation bar allows you to switch between three conceptual roles:
*   **Owner:** Has full visibility and authority over all settings, including security ledgers and the Global E-Stop.
*   **Operator:** Focused on daily tasks. Sees simplified views meant for interacting with the Chat and the AI Village without technical clutter.
*   **Tech (Technician):** Focused on integrations, API configurations, plugin health checks, and system routing matrixes.

---

## 2. The "Guided Start" (Avvio Guidato)

When you first open Core Rth, you will land on the **Guided Start (Overview)** tab. This is your command center for getting the system ready without delving into complex menus.

### The Startup Checklist
This section automatically checks the health of your system:
1.  **API Running:** Verifies the backend is reachable.
2.  **Provider Configured:** Ensures you have at least one LLM provider (like OpenAI or a local Ollama instance) configured.
3.  **Model Catalog:** Confirms that models have been successfully loaded from the provider.
4.  **Guardian Configured:** Checks the active security/governance severity.
5.  **Remote Channels & Secret Store:** Verifies that your integration keys are safely stored in the OS keyring.

### Quick Actions & Wizards
Below the checklist are **Quick Actions**. Clicking these buttons will automatically load preset templates into the corresponding tabs.
*   *Example:* Clicking **"Add provider"** takes you to the Models tab and pastes a boilerplate configuration for OpenAI or Anthropic.
*   Alternatively, use the **End-to-End Use Case Wizard** below the Quick Actions. Select a goal (e.g., "I want to chat"), and the system will guide you step-by-step to achieve it.

---

## 3. Model & Provider Management

Core Rth is model-agnostic. You can connect it to the cloud or run entirely offline.

### Adding a Cloud Provider
1.  Navigate to the **Models** tab.
2.  In the *Provider Form*, select "OpenAI Compatible" (which works for OpenAI, Groq, Anthropic proxies, etc.).
3.  Enter the Base URL (e.g., `https://api.openai.com/v1`).
4.  You **must** supply an API Key. Do *not* put the actual key in the text field; instead, enter a secret reference like `{{SECRET_OPENAI_KEY}}`. (See Section 7 on how to set secrets).
5.  Click **Save provider** and then **Test** to ensure the connection works and models are populated.

### Adding a Local Provider
1.  Ensure you have a local inference engine running (like Ollama or vLLM).
2.  In the *Provider Form*, select "Ollama".
3.  Enter your local URL (e.g., `http://localhost:11434/v1`).
4.  Leave the API Key blank (or use a dummy token if required by your local proxy).
5.  Save and Test.

### The Routing Matrix
In the **Routing** tab, you define the "brain" of Core Rth. You can tell the system:
*   *For General Chat:* Use `gpt-4o-mini`.
*   *For Coding:* Use `claude-3-5-sonnet` (or a local `Qwen2.5-Coder`).
*   *For Privacy-strict Tasks:* Force the system to use `mistral-nemo-local` only.
This allows Core Rth to automatically route your prompts to the cheapest, smartest, or safest model depending on the context.

---

## 4. Conversations and the AI Village

### Single Model Chat
Navigate to the **Chat** tab for standard 1-to-1 interactions.
*   **Simulate Chat:** Runs the routing logic to tell you *which* model it would use and *why*, without actually making the API call. Good for testing your Routing Matrix.
*   **Run Live:** Executes the prompt against the chosen LLM.
*   **Prompt System:** Core Rth prepends your messages with the "Constitution" (Prime Directive & Safety constraints) automatically.

### The AI Village (Knowledge Graph)
The crowning jewel of Core Rth. Found in the **AI Village** tab, this feature allows you to spawn a "swarm" of agents.
1.  Enter a complex problem (e.g., "Design the architecture for a scalable highly-available database").
2.  Click **Generate plan**. Core Rth will propose a set of distinct "Roles" (e.g., `Architect`, `Security Auditor`, `DevOps Engineer`, `Synthesizer`).
3.  Click **Run AI Village Live**.
4.  The system will invoke the LLMs in parallel. They will debate, critique, and eventually, the Synthesizer will combine their outputs into one master document.

---

## 5. Integrations and Plugins Ecosystem

Core Rth is extensible via Plugins. Go to the **Integrations** tab.

*   **Registry Status:** Shows you the loaded capabilities (e.g., reading files, web scraping, git operations).
*   **Batch Healthcheck P0:** Tests critical integrations like your local file system access or your n8n webhooks.
*   To enable a plugin, it must exist in the catalog and be marked as "enabled". The Guardian will actively block plugins that are not explicitly authorized.

---

## 6. Remote Channels

Core Rth can act autonomously based on messages received from Telegram, WhatsApp, or Email.

### Replay Mode (Testing Without Network)
Before putting Core Rth live on Telegram, you can test it locally.
1.  Go to the **Secrets + Test** tab, scroll to **Channel Replay**.
2.  Select a channel (e.g., `Telegram`).
3.  Type a payload that simulates user text (e.g., `"Hello AI, summarize my latest emails"`).
4.  Click **Run Replay**. The system will process this internally as if it came from Telegram, using your Routing Matrix and Plugins, without ever touching the external internet.

---

## 7. Governance and Security (The Guardian)

Security is paramount. Core Rth uses a zero-key storage policy and a strict supervisor called "The Guardian."

### Managing Secrets
1. Go to the **Secrets + Test** tab.
2. In the *Set Secret* form, name your secret (e.g., `SECRET_OPENAI_KEY`).
3. Paste the actual API key in the value field.
4. Provide a mandatory reason (e.g., "Used for GPT-4 routing").
5. Click **Set**.
*How it works: The key is encrypted using AES-256-GCM and stored safely. Core Rth will inject it into API calls only at the last millisecond.*

### The Guardian Severities
Found in the **Guardian** tab:
*   **Balanced:** Allows normal system operations and standard file edits.
*   **Strict:** Demands explicit user approval for dangerous actions (like executing bash commands or modifying the `jarvis_core.py`).
*   **Paranoid:** Fully locks down the system. The AI cannot touch the file system or internet; it becomes read-only.
*All Guardian decisions are logged immutably in the **Policy Ledger**, visible at the bottom of the Guardian tab.*

---

## 8. Reality Bridges (Physical Automation)

Core Rth can control the physical world via Reality Bridges.

### Monitoring Bridges
In the **Start** (Overview) tab, the top widget displays the **State of the Core**. This telemetry dashboard will show you if the IoT Bridge (Home Assistant), Robotics Bridge (ROS2), or Vehicle Bridge (MAVLink/Drones) are connected and healthy.

### Global E-Stop (Emergency Stop)
If an AI agent or automated script controlling a physical device starts behaving erratically:
1.  Look at the top right corner of the navigation bar.
2.  Click the red **GLOBAL E-STOP** button.
3.  Confirm the action.
*This override immediately issues a local `kill` command to robotic axes and an `emergency_land`/`RTL` command to connected drones, instantly severing the AI's physical agency.*

---
*End of User Manual.*
