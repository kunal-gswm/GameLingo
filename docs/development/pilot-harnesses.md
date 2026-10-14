# Real-game acceptance and pilot harnesses

The GL-039 and GL-040 scripts exercise a real Ren'Py installation on a disposable copy. They never download the commercial fixture. Set its directory explicitly before running a harness; if the variable is missing, the harness stops before creating or cleaning a run directory.

## GL-039 runtime acceptance

Required:

- `GAMELINGO_GL039_ORIGINAL_GAME_PATH`: read-only Ren'Py game directory.

Optional:

- `GAMELINGO_GL039_TEMP_DIR`: disposable copy and isolated Ren'Py configuration root. Defaults to a `gamelingo_gl039_verify` folder in the system temporary directory.
- `GAMELINGO_GL039_EVIDENCE_DIR`: output directory. Defaults to `evidence/gl039_acceptance` in the repository.
- `GAMELINGO_GL039_ACCEPTANCE_ROOT`: existing disposable acceptance workspace used by `gl039_run_acceptance.py`.

## GL-040 real-game pilot

Required:

- `GAMELINGO_GL040_ORIGINAL_GAME_PATH`: read-only Ren'Py game directory.

Optional:

- `GAMELINGO_GL040_PILOT_ROOT`: owned disposable run root. Defaults to a `gamelingo_gl040_pilot` folder in the system temporary directory.
- `GAMELINGO_GL040_EVIDENCE_DIR`: secondary evidence output. The repository copy remains under `evidence/gl040_pilot`.

## Optional runtime compatibility test

Set `GAMELINGO_RENPY_COMPATIBILITY_GAME` to run `test_actual_game_island_runtime_detection` against a local game. Without it, that environment-dependent test makes no filesystem assumptions; all synthetic compatibility tests still run.

Example PowerShell setup:

```powershell
$env:GAMELINGO_GL040_ORIGINAL_GAME_PATH = 'D:\Games\My RenPy Game'
$env:GAMELINGO_GL040_PILOT_ROOT = Join-Path $env:TEMP 'gamelingo_gl040_pilot'
uv run python scripts/gl040_real_game_pilot.py
```

Use the corresponding GL-039 variables to run `scripts/gl039_real_engine_verify.py`. These harnesses are manual real-engine checks and are not part of headless CI.
