# GL-038 / GL-038.2: Verified Ren'Py Engine Support Matrix & Exact Boundaries Report

**Repository**: `kunal-gswm/GameLingo`  
**Task ID**: GL-038.2 (Enforce Exact Ren'Py Support Boundaries)  
**Date**: October 12, 2026  
**Status**: Verified & Complete  

---

## Executive Summary

GL-038.2 establishes strict, defensible version-matching boundaries for GameLingo's Ren'Py compatibility adapter. It eliminates open-ended version claims and aligns `detect_renpy_runtime()` with the empirical evidence contract:

### Key Outcomes:
1. **Exact Tested Build Matching**:
   - **Verified**: Only the exact tested engine build `8.5.0.25111603`. Any other `8.5.0` build (e.g. `8.5.0.12345678`) is explicitly categorized under **Untested / best-effort** and is not labeled as verified.
   - **Supported with documented fallback**: Confined strictly to the documented ranges **Ren'Py 7.0.0–7.6.3** (Python 2.7 polyglot fallback) and **Ren'Py 8.0.0–8.4.x** (Python 3 signature fallback).
   - **Untested / best-effort**: Unlisted builds, unverified newer minor releases (`8.5.1`, `8.6.0`), unknown versions (`version = "unknown"`), and future major versions (`9.0.0+`).
   - **Unsupported**: Versions below 7.0.0 (Screen Language 1), rejected in preflight before modifying game files.
2. **Consistent Diagnostics & Warnings**:
   - `apply_plan()` reports strategy diagnostics matching the exact tier:
     - Verified: `native_strings_rpy + verified_real_engine_hook`
     - Supported with Fallback: `native_strings_rpy + polyglot_fallback_hook`
     - Best-effort: `best_effort_polyglot_fallback` (with explicit warning in `report["warnings"]`)
     - Unsupported: Halts with error, 0 files modified.
3. **Boundary Regression Test Coverage**: Added dedicated automated unit tests in `tests/unit/test_renpy_compatibility.py` verifying exact boundaries (`8.5.0.25111603` verified, different `8.5.0` build unverified, `8.5.1`, `8.6.0`, `9.0.0` best-effort, `8.4.x` fallback, `7.6.3` fallback, `7.6.4` best-effort, `< 7.0.0` unsupported, and unknown version warnings).
4. **Build & Test Quality**: All 212 tests passing (100% pass rate), Ruff lint and formatting checks passing cleanly, Windows distribution rebuilt (`dist/GameLingo-Windows-x64.zip`, SHA-256: `659D3A3B4C6152F8EF4C8A6A27C3F56069F8868BB058D65B34C693066CBF8842`).

---

## 1. Audit of Support Matrix & Exact Version Boundaries

### Classification Tiers & Verification Evidence

| Support Tier | Scope / Exact Range | Python Runtime | Verification Basis | Patching Policy & Reported Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Verified on real engine** | Exact build **`8.5.0.25111603`** | Python 3.12.7 (64-bit) | Live fixture execution in `island-1.0-win` (`fixture_result.json`, `log.txt`, `vc_version.py`). All 6 tests passed. | Allowed: `native_strings_rpy + verified_real_engine_hook` |
| **Supported with documented fallback** | **Ren'Py 8.0.0 – 8.4.x** | Python 3.9+ | Mock signature forwarding tests, keyword parameter checks, AST compatibility. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Supported with documented fallback** | **Ren'Py 7.0.0 – 7.6.3** | Python 2.7.x | Python 2.7 AST parser check, PEP 263 headers, `(str, unicode)` polyglot simulation. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Untested / best-effort** | Other `8.5.0` builds, `8.5.1+`, `8.6.x`, `9.0.x+`, unknown | Python 2/3 / unknown | Untested builds outside verified or documented boundaries. | Allowed with warning: `best_effort_polyglot_fallback` |
| **Unsupported** | **Ren'Py < 7.0.0** (e.g. `6.x`) | Legacy Python 2 | Obsolete Screen Language 1 AST, lacks unified string translation dictionary. | **Blocked**: Halts in preflight, rejects patch application. |

### Elimination of Open-Ended Claims
1. **No Wildcard 8.5.0 Claims**: Previous logic used `version_str.startswith("8.5.0")`. This has been replaced with exact build equality `version_str == "8.5.0.25111603"`. Any other build starting with `8.5.0` is treated as an unverified build and assigned `best_effort`.
2. **No Unbounded 8.x Claims**: Versions like `8.5.1`, `8.6.0`, or `9.0.0` are classified as `best_effort` rather than claiming supported status.
3. **No Unbounded 7.x Claims**: Versions above `7.6.3` (such as `7.6.4` or `7.7.0`) are classified as `best_effort`.
4. **Honest Labeling**: Best-effort releases emit an explicit diagnostic warning in `apply_plan()` so users are aware that manual in-game verification is recommended.

---

## 2. Real-Engine Fixture Verification (Build `8.5.0.25111603`)

The real-engine fixture (`zz_compatibility_fixture.rpy`) executed under Ren'Py 8.5.0.25111603 (Python 3.12.7) inside `D:\New folder\island-1.0-win-disposable`.

### Execution Summary (`fixture_result.json`)
```json
{
  "engine_version": "Ren'Py 8.5.0.25111603",
  "engine_version_only": "8.5.0.25111603",
  "script_version": "(8, 5, 0)",
  "python_version": "3.12.7",
  "tests": {
    "1_static_strings": {
      "status": "passed",
      "sample_input": "島の記憶",
      "sample_output": "Memories of the Island"
    },
    "2_dynamic_screen_variable": {
      "status": "passed",
      "input": "探索に出る",
      "output": "Go Exploring"
    },
    "3_menu_button": {
      "status": "passed",
      "input": "閉じる",
      "output": "Close"
    },
    "4_unicode_and_tags": {
      "status": "passed",
      "input": "{size=17}HP{/size}",
      "output": "{size=17}HP{/size}"
    },
    "5_idempotency_and_reload": {
      "status": "passed",
      "repeated_render": "Go Exploring",
      "hook_idempotent": true
    },
    "6_language_switching": {
      "status": "passed",
      "deactivated_output": "探索に出る",
      "reactivated_output": "Go Exploring"
    }
  },
  "errors": []
}
```

---

## 3. Architecture of the Version-Aware Runtime Hook

The activation script generated by `generate_activation_rpy()` provides dynamic UI string translation with complete isolation:

```python
# -*- coding: utf-8 -*-
init python:
    if config.default_language is None:
        config.default_language = "english"

default preferences.language = "english"

init 100 python:
    try:
        # Cross-runtime string type compatibility (Python 2 unicode/str vs Python 3 str)
        try:
            _gl_string_types = (str, unicode)
        except NameError:
            _gl_string_types = (str,)

        # Prevent recursive wrapping on script reloads (Shift+R in Ren'Py)
        if not hasattr(renpy.text.text.Text, "_gl_orig_set_text"):
            renpy.text.text.Text._gl_orig_set_text = renpy.text.text.Text.set_text

            def _gl_set_text(self, text, *args, **kwargs):
                try:
                    in_init = False
                    try:
                        in_init = renpy.game.context().init_phase
                    except Exception:
                        pass

                    if not in_init and getattr(renpy.game.preferences, "language", None):
                        if isinstance(text, _gl_string_types):
                            text = renpy.translation.translate_string(text)
                        elif isinstance(text, (list, tuple)):
                            text = [
                                renpy.translation.translate_string(x)
                                if isinstance(x, _gl_string_types)
                                else x
                                for x in text
                            ]
                except Exception as _gl_tx_err:
                    try:
                        if getattr(config, "developer", False):
                            renpy.display.log.write(
                                "GameLingo: Dynamic translation fallback to original text: %s"
                                % _gl_tx_err
                            )
                    except Exception:
                        pass

                return renpy.text.text.Text._gl_orig_set_text(
                    self, text, *args, **kwargs
                )

            renpy.text.text.Text.set_text = _gl_set_text
    except Exception as _gl_init_err:
        try:
            if getattr(config, "developer", False):
                renpy.display.log.write(
                    "GameLingo: Text.set_text hook installation deferred: %s"
                    % _gl_init_err
                )
        except Exception:
            pass
```

### Safety Guarantees:
1. **Single-Save Idempotency**: `_gl_orig_set_text` is assigned once, preventing recursion across `Shift+R` script reloads.
2. **Signature Transparency**: `*args, **kwargs` passes all parameters cleanly across Ren'Py 7 (`scope, substitute`) and Ren'Py 8 (`scope, substitute, update`).
3. **Safe Fallback**: Any lookup error logs to `renpy.display.log.write` under `config.developer` and transparently forwards original text to display without game crashes.
4. **Language Deactivation**: Checks `getattr(renpy.game.preferences, "language", None)`. If None, original untranslated text is rendered.

---

## 4. Conservative Detection Implementation Details

### Detection Algorithm (`detect_renpy_runtime` in `src/gamelingo/adapters/renpy.py`)

```python
is_real_engine_verified = version_str == "8.5.0.25111603"

if major_version is not None and major_version < 7:
    support_level = "unsupported"
elif is_real_engine_verified:
    support_level = "verified"
elif major_version == 7:
    in_7x_range = False
    if minor_version is not None:
        if 0 <= minor_version < 6:
            in_7x_range = True
        elif minor_version == 6:
            in_7x_range = patch_version is None or patch_version <= 3
        else:
            in_7x_range = False
    else:
        in_7x_range = True
    support_level = "supported_with_fallback" if in_7x_range else "best_effort"
elif major_version == 8 and minor_version is not None and 0 <= minor_version <= 4:
    support_level = "supported_with_fallback"
elif major_version is not None:
    support_level = "best_effort"
else:
    version_str = "unknown"
    support_level = "best_effort"
```

### Action Policies in Patch Application (`apply_plan`):
1. **`verified`**: Emits `native_strings_rpy + verified_real_engine_hook`, zero warnings.
2. **`supported_with_fallback`**: Emits `native_strings_rpy + polyglot_fallback_hook`, notes documented fallback in diagnostics.
3. **`best_effort`**: Emits `best_effort_polyglot_fallback`. Appends warning to `report["warnings"]`:
   - If version is known: `"Ren'Py version <ver> is unverified / untested (<reason>). Best-effort fallback applied."`
   - If version is unknown: `"Ren'Py version is unknown (<reason>). Best-effort fallback applied."`
4. **`unsupported`**: Preflight halts immediately with error. No files or archives are written.

---

## 5. Automated Regression Test Suite

All 212 tests pass cleanly with 100% success rate:

```
tests/unit/test_renpy_compatibility.py ...........................      [ 12%]
tests/unit/test_renpy_strings.py ............                            [ 18%]
tests/unit/test_renpy.py .........................                       [ 30%]
tests/unit/test_rpgmaker.py ...................................          [ 46%]
...
============================= 212 passed in 15.59s =============================
```

### Dedicated Version-Boundary Regression Tests:
1. `test_detect_renpy_runtime_8_5_verified`: Asserts `8.5.0.25111603` -> `verified`.
2. `test_detect_renpy_runtime_different_8_5_build_not_verified`: Asserts `8.5.0.12345678` -> `best_effort` (NOT `verified`).
3. `test_detect_renpy_runtime_newer_and_future_versions_best_effort`: Parameterized across `8.5.1`, `8.6.0`, and `9.0.0` -> all yield `best_effort`.
4. `test_detect_renpy_runtime_8_4_supported_with_fallback`: Asserts `8.4.1.24030701` -> `supported_with_fallback`.
5. `test_detect_renpy_runtime_7_6_3_supported_with_fallback`: Asserts `7.6.3.2140` -> `supported_with_fallback`.
6. `test_detect_renpy_runtime_7_6_4_best_effort`: Asserts `7.6.4.9999` -> `best_effort` (outside 7.0.0–7.6.3 range).
7. `test_detect_renpy_runtime_6x_unsupported`: Asserts `6.99.12.4` -> `unsupported`.
8. `test_detect_renpy_runtime_unknown_fallback`: Asserts missing metadata -> `best_effort` with `version = "unknown"`.
9. `test_diagnostics_for_unverified_known_version_in_apply_plan`: Asserts `8.5.1` generates warning mentioning `8.5.1 is unverified / untested`.
10. `test_unsupported_renpy_version_aborts_patch`: Asserts `< 7.0` halts with status `failed` before modifying files.

---

## 6. Build Integrity & Distribution

- **Repository**: `kunal-gswm/GameLingo`
- **Branch**: `main`
- **Windows Distribution Zip**: `dist/GameLingo-Windows-x64.zip`
- **SHA-256 Checksum**:
  `659D3A3B4C6152F8EF4C8A6A27C3F56069F8868BB058D65B34C693066CBF8842`
- **Checksum File**: `dist/GameLingo-Windows-x64.zip.sha256`

---

## 7. Summary of Tested Engines & Remaining Limitations

### Tested Engines:
- **Ren'Py 8.5.0.25111603 (Python 3.12.7)**: Real-engine fixture execution in live game environment. All 6 tests passed cleanly.
- **Ren'Py 8.0.0 – 8.4.x**: Tested via mock AST syntax, keyword parameter forwarding, and translation simulation.
- **Ren'Py 7.0.0 – 7.6.3**: Tested via Python 2.7 AST parser, unicode token checks, and polyglot activation structure.

### Remaining Limitations:
1. **Ren'Py < 7.0**: Unsupported by design due to Screen Language 1 AST incompatibility.
2. **Pre-rendered Text in Graphic Assets**: Japanese text rendered into `.png`/`.jpg` images cannot be translated by text displayable hooks and requires manual image replacement.
3. **Custom C-extension Displayables**: If a visual novel bypasses `renpy.text.text.Text` entirely using custom Cython or C renderer routines, the hook will not intercept strings.

---
*Report finalized for GL-038.2: Enforce Exact Ren'Py Support Boundaries.*
