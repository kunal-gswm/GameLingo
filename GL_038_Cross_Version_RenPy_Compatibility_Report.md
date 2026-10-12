# GL-038 / GL-038.1: Verified Ren'Py Engine Support Matrix & Compatibility Report

**Repository**: `kunal-gswm/GameLingo`  
**Task ID**: GL-038.1 (Verification and Finalization of Ren'Py Engine Support Matrix)  
**Date**: October 12, 2026  
**Status**: Verified & Complete  

---

## Executive Summary

GL-038.1 turns GameLingo's Ren'Py compatibility matrix into a defensible, empirically verified support contract backed by real-engine testing, conservative runtime detection, version-aware hook safety, and honest support tiers.

### Key Outcomes:
1. **Empirical Engine Audit**: Audited engine evidence and discovered that the live test game (`island-1.0-win` / `island-1.0-win-disposable`) runs **Ren'Py 8.5.0.25111603** with **Python 3.12.7** (`renpy/vc_version.py`, `log.txt`), rather than Ren'Py 8.3.2 as hypothesized in earlier prompts. Ren'Py 8.5.0 is established as the sole live-verified engine on this host. Ren'Py 8.3.2, 8.0–8.4, and 7.6.3 (Python 2.7) are honestly categorized under the **Supported with Fallback** tier backed by AST analysis and mock test suites, rather than falsely claiming live real-engine verification where no local SDK exists.
2. **Real-Engine Fixture Verification**: Executed a comprehensive compatibility fixture (`zz_compatibility_fixture.rpy`) under the live Ren'Py 8.5.0.25111603 runtime. All 6 functional domains passed cleanly:
   - Static strings from `strings.rpy` lookup
   - Dynamic screen variable translation via `Text.set_text` hook
   - Menu button & conditional expression evaluation
   - Unicode text, Ren'Py tags (`{size=...}`), and placeholder preservation
   - Reload idempotency and prevention of recursive re-wrapping
   - Runtime language switching and translation deactivation/reactivation
3. **Defensive Runtime Hook**: Audited the `renpy.text.text.Text.set_text` runtime hook. Maintained single-save idempotency (`_gl_orig_set_text`), complete signature transparency (`*args, **kwargs`), `(list, tuple)` sequence handling, and silent fallback to the original untranslated text with developer logging (`renpy.display.log.write`) active only when `config.developer` is enabled.
4. **Conservative Detection & Honest Support Tiers**: Replaced blanket version claims with 4 distinct tiers:
   - **Verified on real engine**: Ren'Py 8.5.0.25111603.
   - **Supported with documented fallback**: Ren'Py 7.0.0 – 7.6.3 (Python 2.7) and Ren'Py 8.0.0 – 8.4.x (Python 3 point releases).
   - **Untested / best-effort**: Unidentified engine versions (`version = "unknown"`), applying the universal polyglot hook with diagnostic warnings.
   - **Unsupported**: Ren'Py < 7.0 (Screen Language 1), failing preflight and halting patch application.
5. **Quality & Build Integrity**: 204 unit and integration tests passing (100%), Ruff linter and formatter passing cleanly, and Windows distribution rebuilt (`dist/GameLingo-Windows-x64.zip`, SHA-256: `1FDA58D336F1B77FF1ABC7E07CB18B2328B1519927491DE84A4082208038B0F8`).

---

## 1. Audit of Claimed Support Matrix & Engine Baseline

### Distinction Across Test Categories

| Engine Version | Runtime / Python | Test Classification | Local Evidence / Test Artifacts | Support Tier |
| :--- | :--- | :--- | :--- | :--- |
| **Ren'Py 8.5.0.25111603** | Python 3.12.7 (64-bit) | **Verified in real Ren'Py runtime on full game** | `island-1.0-win-disposable/log.txt`<br>`island-1.0-win/renpy/vc_version.py`<br>`island-1.0-win-disposable/fixture_result.json` | **Verified on real engine** |
| **Ren'Py 8.3.2** | Python 3.9.x | **Mocked tests only** | `tests/unit/test_renpy_compatibility.py`<br>(No local 8.3.2 SDK or runtime present on host) | **Supported with documented fallback** |
| **Ren'Py 8.0.0 – 8.4.x** | Python 3.9+ | **Mocked tests only** | Mock signature tests, AST syntax tests | **Supported with documented fallback** |
| **Ren'Py 7.0.0 – 7.6.3** | Python 2.7.x | **Mocked tests & AST validator** | `tests/unit/test_renpy_compatibility.py` (AST parse, token scan, unicode polyglot checks) | **Supported with documented fallback** |
| **Unidentified Engines** | Unknown | **Untested** | Fallback to universal polyglot script | **Untested / best-effort** |
| **Ren'Py < 7.0.0** | Python 2.7 / legacy | **Blocked (Pre-flight test)** | `test_unsupported_renpy_version_aborts_patch` | **Unsupported** |

### The 8.3.2 vs. 8.5.0 Reality Check
Previous tasks and problem descriptions assumed that `island-1.0-win` was built with Ren'Py 8.3.2. A physical inspection of the game files on disk revealed:
```python
# renpy/vc_version.py
branch = "master"
nightly = False
official = True
version = "8.5.0.25111603"
version_name = "In Good Health"
```
Furthermore, the engine startup log (`log.txt`) recorded:
```
Windows-11-10.0.26300-SP0
Ren'Py 8.5.0.25111603
Set script version to: (8, 5, 0)
```
No standalone Ren'Py 8.3.2 or Ren'Py 7.6.3 SDK exists in the local environment. Conforming to the GL-038.1 mandate ("Do not claim tests ran where no usable SDK was available"):
- **Ren'Py 8.5.0.25111603** is the sole engine confirmed via live runtime execution.
- **Ren'Py 8.3.2** is downgraded from live-game baseline to `supported_with_fallback` (validated via mock tests and signature compatibility).
- Open-ended claims like "8.5.x+" have been removed in favor of explicit, defensible boundaries.

---

## 2. Real-Engine Compatibility Fixture Execution

A disposable Ren'Py fixture (`zz_compatibility_fixture.rpy`) was installed in `D:\New folder\island-1.0-win-disposable` and executed directly by `island.exe` under Ren'Py 8.5.0.25111603 / Python 3.12.7.

### Fixture Test Results (`fixture_result.json`)

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

### Observations from Real Engine Execution:
1. **Static Strings**: Ren'Py's native `renpy.translation.translate_string()` reliably translates static UI strings defined in `strings.rpy` when the language preference is active.
2. **Dynamic Screen Variables**: Variables and evaluated expressions passed to `renpy.text.text.Text.set_text` are intercepted by GameLingo's wrapper and mapped against the translation database in real time.
3. **Menu Buttons & Conditional UI**: Screen elements generated conditionally or inside loops resolve without latency.
4. **Tags & Interpolation**: Tags such as `{size=17}HP{/size}` pass through `translate_string()` without corrupting styling markup.
5. **Reload Idempotency**: Simulating repeated script initialization and hook execution verified that `_gl_orig_set_text` is saved only once. No recursive function nesting or double-translation occurred.
6. **Language Switching**: When `renpy.game.preferences.language` is set to `None`, the hook reverts seamlessly to rendering original Japanese strings (`"探索に出る"`). When reset to `"english"`, translation resumes immediately (`"Go Exploring"`).
7. **Clean Engine Startup**: `gamelingo_activate.rpy` compiled to `gamelingo_activate.rpyc` in 23 ms during engine boot. `log.txt` confirmed total init took 58 ms, translation table init took 1 ms, and interface started cleanly with zero tracebacks.

---

## 3. Reassessment of the Global Runtime Hook

### Why Public APIs Alone Are Insufficient
In compiled visual novels, dynamic UI text (e.g. action buttons created from Python lists, inventory items, or status screens) is passed to `renpy.text.text.Text` as evaluated Python objects rather than static string literals wrapped in `_()`. Because the game script is compiled, modifying every screen source file is impossible or fragile. The runtime hook intercepts these strings at the displayable layer.

### Hook Safety Architecture

The activation script generated by `generate_activation_rpy()` incorporates multiple architectural safeguards:

```python
# -*- coding: utf-8 -*-
init python:
    if config.default_language is None:
        config.default_language = "english"

default preferences.language = "english"

init 100 python:
    try:
        # 1. Polyglot string types for Python 2.7 (unicode, str) and Python 3 (str)
        try:
            _gl_string_types = (str, unicode)
        except NameError:
            _gl_string_types = (str,)

        # 2. Idempotent installation: saved exactly once, immune to Shift+R reload
        if not hasattr(renpy.text.text.Text, "_gl_orig_set_text"):
            renpy.text.text.Text._gl_orig_set_text = renpy.text.text.Text.set_text

            def _gl_set_text(self, text, *args, **kwargs):
                try:
                    in_init = False
                    try:
                        in_init = renpy.game.context().init_phase
                    except Exception:
                        pass

                    # 3. Only translate when not in init phase and language is active
                    if not in_init and getattr(renpy.game.preferences, "language", None):
                        if isinstance(text, _gl_string_types):
                            text = renpy.translation.translate_string(text)
                        elif isinstance(text, (list, tuple)):
                            text = [
                                renpy.translation.translate_string(x) if isinstance(x, _gl_string_types) else x
                                for x in text
                            ]
                except Exception as _gl_tx_err:
                    # 4. Developer logging rather than blind pass
                    try:
                        if getattr(config, "developer", False):
                            renpy.display.log.write("GameLingo: Dynamic translation fallback to original text: %s" % _gl_tx_err)
                    except Exception:
                        pass

                # 5. Always forward to original method with all arguments intact
                return renpy.text.text.Text._gl_orig_set_text(self, text, *args, **kwargs)

            renpy.text.text.Text.set_text = _gl_set_text
    except Exception as _gl_init_err:
        try:
            if getattr(config, "developer", False):
                renpy.display.log.write("GameLingo: Text.set_text hook installation deferred: %s" % _gl_init_err)
        except Exception:
            pass
```

### Safety Guarantees:
1. **Single Save & No Recursive Wrapping**: `_gl_orig_set_text` is assigned only if not already present on `renpy.text.text.Text`. Subsequent script reloads (`Shift+R`) skip re-wrapping.
2. **Transparent Argument Forwarding**: By capturing `*args, **kwargs`, the wrapper accommodates signature differences between Ren'Py 7 (`text, scope=None, substitute=False`) and Ren'Py 8 (`text, scope=None, substitute=False, update=True`).
3. **Fail-Safe Display**: If any error occurs inside the translation lookup, the exception is logged to `renpy.display.log.write` (when `config.developer` is enabled) and the original `text` parameter is passed unaltered to `_gl_orig_set_text`. Translation failure never breaks display rendering.
4. **Selector Respect**: The hook checks `getattr(renpy.game.preferences, "language", None)`. When the player selects original Japanese via game menus, `preferences.language` is `None` or empty, so no translation occurs.
5. **No Double-Translation**: `translate_string(text)` queries the active translation table. If `text` is already English (or absent from the dictionary), Ren'Py returns `text` unchanged.

---

## 4. Conservative Runtime Detection & Support Tiers

### Detection Workflow (`detect_renpy_runtime`)
The adapter inspects the game distribution in prioritized order:
1. `renpy/vc_version.py` -> extracts exact engine version string and tuple.
2. `lib/` directory structure:
   - `py3-*` folders -> `python3` runtime family.
   - `windows-i686` or standard `windows-x86_64` (without `py3-`) -> `python2` runtime family.
3. `.rpyc` bytecode inspection.

### Support Tiers & Action Policies

| Tier | Engine Detection Criteria | Action / Patching Policy | Strategy Name Reported |
| :--- | :--- | :--- | :--- |
| **Verified on real engine** | Ren'Py 8.5.0.25111603 | Patching proceeds with verified runtime hook | `native_strings_rpy + verified_real_engine_hook` |
| **Supported with documented fallback** | Ren'Py 7.0.0 – 7.6.3 or Ren'Py 8.0.0 – 8.4.x | Patching proceeds with polyglot fallback hook | `native_strings_rpy + polyglot_fallback_hook` |
| **Untested / best-effort** | Unknown version (`version = "unknown"`) | Proceed with universal polyglot hook; emit warning in diagnostics report | `best_effort_polyglot_fallback` |
| **Unsupported** | Ren'Py < 7.0.0 | Patching blocked immediately in preflight; no files modified | Halts with error |

### Diagnostics Example
When an unknown engine is analyzed, the diagnostics output clearly informs the user:
```json
{
  "engine": "renpy",
  "detected_version": "unknown",
  "python_family": "auto",
  "support_level": "best_effort",
  "translation_strategy": "best_effort_polyglot_fallback",
  "dynamic_text_fallback_installed": true
}
```
And `report["warnings"]` records:
`"Ren'Py version is unknown (Ren'Py version could not be determined; using universal polyglot fallback). Best-effort fallback applied."`

When an incompatible legacy engine (< 7.0) is detected:
`"Ren'Py version 6.99 (< 7.0) is not supported. Ren'Py 7.0+ or 8.0+ is required."`
The patch operation is aborted cleanly with zero modifications to game archives or save files.

---

## 5. Automated Regression Test Suite

All 204 unit and integration tests pass cleanly with 100% success rate:

```
tests/unit/test_renpy_compatibility.py ...................               [  9%]
tests/unit/test_renpy_strings.py ............                            [ 15%]
tests/unit/test_renpy.py .........................                       [ 27%]
tests/unit/test_rpgmaker.py ...................................          [ 44%]
...
============================= 204 passed in 15.39s =============================
```

### Coverage of Compatibility Cases:
1. **Python 2.7 / 3 AST Compliance**: Verifies absence of f-strings, type annotations, and walrus operators in `generate_activation_rpy()`.
2. **String Type Tuples**: Simulates Python 2 `(str, unicode)` and Python 3 `(str,)`.
3. **Idempotent Monkey-Patching**: Simulates multiple init cycles and asserts `Text.set_text` wrapper is installed once.
4. **Signature Variations**: Verifies forwarding of both Ren'Py 7 and Ren'Py 8 keyword parameter combinations (`scope`, `substitute`, `update`).
5. **Sequence Translation**: Verifies `(list, tuple)` displayables are processed correctly.
6. **Fail-Safe Pass-Through**: Verifies that translation exceptions never prevent the original text from rendering.
7. **Runtime Detection Tests**:
   - `test_detect_renpy_runtime_8_5_verified`: Verifies `verified` tier for 8.5.0.
   - `test_detect_renpy_runtime_8x_from_vc_version`: Verifies `supported_with_fallback` tier for 8.3.2.
   - `test_detect_renpy_runtime_7x_from_vc_version`: Verifies `supported_with_fallback` tier for 7.6.3.
   - `test_detect_renpy_runtime_unknown_fallback`: Verifies `best_effort` tier and warning for unknown versions.
   - `test_unsupported_renpy_version_aborts_patch`: Verifies preflight blocking for < 7.0.

---

## 6. Build Integrity & Distribution

- **Repository**: `kunal-gswm/GameLingo`
- **Branch**: `main`
- **Windows Distribution Zip**: `dist/GameLingo-Windows-x64.zip`
- **SHA-256 Checksum**:
  `1FDA58D336F1B77FF1ABC7E07CB18B2328B1519927491DE84A4082208038B0F8`
- **Checksum File**: `dist/GameLingo-Windows-x64.zip.sha256`

---

## 7. Summary of Tested Engines & Remaining Limitations

### Engines Tested:
- **Ren'Py 8.5.0.25111603 (Python 3.12.7)**: Real-engine fixture execution in live game environment. All 6 tests passed cleanly.
- **Ren'Py 8.3.2 / 8.0–8.4**: Tested via mock AST syntax, keyword parameter forwarding, and translation simulation.
- **Ren'Py 7.6.3 / 7.0–7.6**: Tested via Python 2.7 AST parser, unicode token checks, and polyglot activation structure.

### Known Limitations:
1. **Ren'Py < 7.0**: Unsupported by design due to Screen Language 1 AST incompatibility.
2. **Pre-rendered Text in Graphic Assets**: Japanese text rendered into `.png`/`.jpg` images cannot be translated by text displayable hooks and requires manual image replacement.
3. **Custom C-extension Displayables**: If a visual novel bypasses `renpy.text.text.Text` entirely using custom Cython or C renderer routines, the hook will not intercept strings.

---
*Report finalized for GL-038.1: Verify and Finalize the Ren'Py Engine Support Matrix.*
