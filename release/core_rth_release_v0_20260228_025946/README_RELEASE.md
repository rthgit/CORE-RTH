# Core Rth Release Bundle (Curated)

This folder is a curated release subset of the workspace:

- runtime code (`app/`)
- operational scripts (`scripts/`)
- benchmark harness + selected evidence (`bench/`)
- deployment files (`Dockerfile`, `docker-compose.core-shadow.yml`, `.env.example`)

## Quick Start

1. Install Python deps:

```powershell
pip install -r requirements.txt
```

2. Start API (local):

```powershell
python scripts/run_core_rth_local_bench_api.py
```

3. Use CLI spine:

```powershell
python scripts/rth.py --help
python scripts/rth.py api start --port 18030
python scripts/rth.py api status
python scripts/rth.py guardian policy
python scripts/rth.py guardian policy get
python scripts/rth.py guardian audit
python scripts/rth.py cortex status
```

4. Open the local UI (Operator Chat + Multi-LLM Control Plane v0):

```text
http://127.0.0.1:18030/ui/
```

5. One-click RC1 gate + onboarding:

```powershell
python scripts/install_zero_friction_local.py --start-api --start-llama
python scripts/release_gate_rc1.py --start-api-if-needed
python scripts/onboard_zero_friction.py --start-api-if-needed
python scripts/channels_live_final_check.py
```

## Notes

- This bundle excludes secrets (`.env`) and large optional model artifacts.
- External project roots (`SublimeOmniDoc`, `ANTIHAKER`) are not copied here.
- See `RELEASE_MANIFEST.json` for included/excluded items.
