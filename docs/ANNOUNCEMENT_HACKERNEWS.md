Hey HN,

After a massive push we're releasing the RC1 of Core Rth. 

A lot of wrappers just bolt an LLM onto your terminal. Core Rth is built as a Sovereign Cognitive Kernel. By default, it operates under a strict "proposal-first" governance model (The Guardian) because it's built to actually touch the physical world (IoT, Robotics via ROS2, and UAVs via MAVLink) without causing a disaster.

What it does under the hood:

* Model-Agnostic Routing Matrix: You can mix OpenAI, Anthropic, and local bare-metal Ollama/vLLM endpoints. Route coding to claude-3-5-sonnet and privacy-critical tasks to Qwen-2.5-Coder locally, invisibly handling the fallback.

* AI Village (Parallel Knowledge Graph): It doesn't just use one agent. It spins up a swarm (Architect, Critic, Synthesizer) analyzing your prompt in parallel and generating a synthesized answer.

* AES-256-GCM Security Vault: Zero-key storage. The OS keyring manages everything natively. No more plaintext OPENAI_API_KEY in your .env.

* Mission Control Plane: The UI is an operations dashboard built for complete situational awareness. It features live telemetry from hardware bridges and a Global E-Stop (hardware kill switch) to sever physical capabilities if an agent hallucinates.

Stack & Architecture:

* Python 3.10+ Backend (FastAPI, asyncio)
* Zero-friction Vanilla JS frontend (No React overhead)
* Source-Available (Free for non-commercial and research)

We're aiming at engineers integrating AI into enterprise or physical systems who cannot afford a "black box" executing unstructured commands.

Check out the code, the manifesto, and our benchmark suites (Core Rth vs OpenClaw logic). 

GitHub: https://github.com/rthgit/CORE-RTH

Would love to get your thoughts on the routing architecture and the UI design paradigm! Happy to answer any technical questions.
