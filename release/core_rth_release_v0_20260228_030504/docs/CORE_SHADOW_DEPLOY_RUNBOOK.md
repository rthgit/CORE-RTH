# CORE RTH + SHADOW CCS Runbook

## 1. Security Baseline

- Keep `RTH_REQUIRE_OWNER_APPROVAL=true`.
- Keep `RTH_PROCESS_EXEC_ALLOWED_ACTIONS=app_launch,workspace_command,rth_lm_action,shadow_ccs_action`.
- Keep `payments` and `social_posting` as hard `NO-GO` capabilities.

## 2. Local API Start

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health:

```powershell
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/health
```

## 3. SHADOW CCS Status

```powershell
curl http://localhost:8000/api/v1/jarvis/shadow/status
```

## 4. Governed SHADOW Probe

1. Propose:

```json
POST /api/v1/jarvis/shadow/propose
{
  "action": "artifact_probe",
  "reason": "owner probe"
}
```

2. Approve and run:

```json
POST /api/v1/jarvis/shadow/approve-run
{
  "request_id": "perm_xxxxxxxx",
  "decided_by": "owner"
}
```

## 5. Governed SHADOW Benchmark

1. Propose:

```json
POST /api/v1/jarvis/shadow/propose
{
  "action": "benchmark_validation",
  "reason": "performance baseline",
  "output": "benchmark payload",
  "policy_id": "default",
  "cluster_size": 3,
  "iterations": 200,
  "warmup": 20
}
```

2. Approve and run:

```json
POST /api/v1/jarvis/shadow/approve-run
{
  "request_id": "perm_xxxxxxxx",
  "decided_by": "owner"
}
```

Expected metrics:

- `throughput_rps`
- `latency_ms.min`
- `latency_ms.p50`
- `latency_ms.p95`
- `latency_ms.p99`
- `latency_ms.max`

## 6. Docker Deploy

```powershell
$env:RTH_SHADOW_HOST_PATH = "C:\\Users\\PC\\Desktop\\Biome\\shadow_x_models"
docker compose -f docker-compose.core-shadow.yml up -d --build
```

Check:

```powershell
docker compose -f docker-compose.core-shadow.yml ps
docker compose -f docker-compose.core-shadow.yml logs core-rth-api --tail 200
```

## 7. Minimum Acceptance Gate

- `/health/ready` returns `200`.
- `GET /api/v1/jarvis/policy` shows `require_owner_approval=true`.
- SHADOW `artifact_probe` returns `status=ok`.
- SHADOW benchmark returns metrics with `runs > 0`.
