# Core Rth - Official Multilingual Benchmark (v1)

## Scope

This benchmark validates multilingual behavior for the current Core Rth final-candidate stack, with focus on:

- frontend language switch (`IT/EN`)
- Guardian localized responses (`IT/EN`)
- multilingual chat and AI Village behavior
- Unicode safety across channel replay (`Telegram`, `WhatsApp`, `Mail`)
- cross-language memory consistency

Primary suite file:

- `bench/tasks/core_rth_multilingual_official_v1.json`

## Goals

The benchmark is designed to answer:

- Does Core Rth answer in the requested language?
- Does the UI switch core labels without breaking layout?
- Does Guardian expose localized status/messages?
- Are Unicode payloads preserved through replay channels?
- Does memory remain factually stable across language switches?

## Scoring Model

Scores are task-level with `0..5` scale and weighted aggregation.

Weights (from suite JSON):

- `success`: 25%
- `accuracy`: 20%
- `language_fidelity`: 20%
- `governance`: 15%
- `memory`: 10%
- `efficiency`: 10%

## Official Task Set (v1)

Tasks defined in `bench/tasks/core_rth_multilingual_official_v1.json`:

1. `ml_chat_it_planning`
2. `ml_chat_en_debug`
3. `ml_village_cross_language_synthesis`
4. `ml_guardian_status_localized`
5. `ml_ui_i18n_labels_it_en`
6. `ml_channels_unicode_replay`
7. `ml_memory_recall_cross_language`

## Execution Modes

Use these modes depending on available credentials/hardware:

- `replay_only`: no live credentials, validates Unicode + flow integrity
- `hybrid`: live models + replay channels
- `full_live`: live models + live channels (Telegram/WhatsApp/Mail)

## Minimal Evidence Pack

For a benchmark run to be considered valid, archive:

- suite file hash (`core_rth_multilingual_official_v1.json`)
- Core Rth version / git commit
- selected providers and routing preset
- language switch screenshots (`IT`, `EN`)
- Guardian localized status responses (`IT`, `EN`)
- replay outputs with Unicode payloads
- AI Village trace output (multilingual synthesis case)
- summary score report

## Suggested Validation Commands

These are practical checks before or during the benchmark:

```powershell
python scripts\\rth.py api health
python scripts\\rth.py guardian policy
python scripts\\rth.py plugins status
```

If live channels are not configured, run replay checks and record that the run is `hybrid` or `replay_only`.

## Acceptance Thresholds (v1)

Recommended thresholds for multilingual readiness:

- `language_fidelity >= 4.0`
- `accuracy >= 4.0`
- `governance >= 4.5`
- `success_rate >= 85%`
- `0` encoding corruption incidents in replay tasks

## Known Limits (v1)

- UI i18n is focused on primary user-facing surfaces (`IT/EN`)
- advanced plugin manifest authoring strings may still include mixed technical English terms
- docs are provided in `IT/EN` for onboarding, not full repo-wide translation

## Upgrade Path (v2)

- add `ES` UI language pack
- add official automated runner + report generator for multilingual suite
- add multilingual channel live tests as separate signed evidence pack
- add localized Guardian messages for more denial reasons / DSL diagnostics

