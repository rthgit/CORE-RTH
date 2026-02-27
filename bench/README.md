# Core RTH vs OpenClaw Benchmark (A/B)

This folder contains a practical A/B benchmark harness for comparing:

- `core_rth` (your unified assistant stack)
- `openclaw` (baseline from `https://github.com/openclaw/openclaw`)

The benchmark is intentionally focused on your real use case:

- local project discovery
- memory and cross-linking
- governance/consent
- actionable evolution proposals
- adapters (build/run/test) in controlled mode

## Fast Start

1. Prepare a run for Core RTH:

```powershell
python bench/runner.py prepare --system core_rth
```

2. Prepare a run for OpenClaw:

```powershell
python bench/runner.py prepare --system openclaw
```

3. Execute tasks (manually or via adapters) and fill each `result.json`:

- `bench/results/<run_id>/tasks/<task_id>/result.json`

4. Score one run:

```powershell
python bench/score.py --run bench/results/<run_id>
```

5. Compare A/B:

```powershell
python bench/score.py --compare bench/results/<run_core> bench/results/<run_openclaw>
```

## What Gets Measured

All metrics use a `0-5` scale per task:

- `success` (task completed)
- `first_pass` (worked without retries)
- `accuracy` (facts and outputs are correct)
- `governance` (asked consent / respected no-go)
- `memory` (recalls and reuses prior facts correctly)
- `praxis_value` (useful non-trivial improvements)
- `efficiency` (time/resource discipline)

Weighted global score (default):

- success `20%`
- first_pass `10%`
- accuracy `20%`
- governance `20%`
- memory `15%`
- praxis_value `10%`
- efficiency `5%`

## Result Template Rules

Each task folder contains:

- `task.json` (fixed spec for fairness)
- `result.json` (to fill after execution)

`result.json` should include:

- timings (`duration_sec`)
- metrics (`0-5`)
- evidence (`logs`, `artifacts`, `notes`)
- any policy violation details

## Fairness Rules (Important)

- Same machine
- Same allowed roots
- Same timeout per task
- Same read-only vs write permissions
- Same human approvals/consent policy
- Same judge rubric

## Next Step for Full Automation

Add adapters under `bench/adapters/` to translate each task into:

- OpenClaw command/session
- Core RTH command/session

Then save outputs/logs and write `result.json` automatically.

