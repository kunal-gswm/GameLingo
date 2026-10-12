# GL-038 / GL-038.3: Verified Ren'Py Engine Support Matrix & Unambiguous Metadata Report

**Repository**: `kunal-gswm/GameLingo`  
**Task ID**: GL-038.3 (Reject Ambiguous Ren'Py Version Metadata)  
**Date**: October 12, 2026  
**Status**: Verified & Complete  

---

## Executive Summary

GL-038.3 eliminates all remaining ambiguity in GameLingo's Ren'Py runtime detection. Incomplete version strings (such as `"7"` or `"7.6"`) and major versions inferred solely from `lib/` directory layout or `.rpyc` bytecode without concrete build metadata cannot qualify for a documented fallback tier.

### Key Outcomes:
1. **Strict Release Identification Requirement**:
   - **`is_fully_identified`**: A release is treated as fully identified only when at least major, minor, and patch numbers are parsed from explicit version metadata (e.g. `7.6.3` or `8.4.1`).
   - **Incomplete Strings Classified as Best-Effort**: Strings missing patch components (e.g. `"7"` or `"7.6"`) are classified under **Untested / best-effort** with an explicit diagnostic warning (`"Ren'Py version '...' is incomplete; cannot verify documented release range"`).
   - **Inferred Runtimes Classified as Best-Effort**: Versions inferred only from runtime library directories (e.g. `lib/windows-i686` with `python27.dll`) or bytecode without `vc_version.py` cannot guarantee compatibility within `7.0.0–7.6.3` and are assigned **Untested / best-effort**.
   - **Documented Fallback Runtimes Protected**: Fully identified releases within `7.0.0–7.6.3` and `8.0.0–8.4.x` remain **Supported with documented fallback**.
   - **Exact Verified Build Preserved**: Build `8.5.0.25111603` remains the sole **Verified on real engine** release.
   - **Unsupported Preflight Protected**: Versions below `7.0.0` (Screen Language 1) fail preflight and abort immediately before modifying game files.
2. **Diagnostic Warning Alignment**:
   - `apply_plan()` detects incomplete, unverified, or inferred versions and appends clear diagnostics to `report["warnings"]`. Best-effort execution is never disguised as verified support.
3. **Comprehensive Regression Test Suite**:
   - Extended `tests/unit/test_renpy_compatibility.py` to 30 focused tests, covering incomplete strings (`7`, `7.6`), `lib/`-only inference, exact boundaries (`7.6.3` fallback vs `7.6.4` best-effort), exact verified build (`8.5.0.25111603`), unverified minor/major versions (`8.5.1`, `8.6.0`, `9.0.0`), and preflight rejection of legacy engines.
   - All **215 tests** passing across the full repository test suite.
4. **Build & Package Integrity**:
   - Rebuilt Windows distribution package (`dist/GameLingo-Windows-x64.zip`, SHA-256: `729C85F691190CAC13F75788F9D53218F4CF72143C2C1E3FC499FC5557F201C2`).

---

## 1. Audit of Support Matrix & Unambiguous Version Boundaries

### Classification Tiers & Verification Evidence

| Support Tier | Scope / Exact Range | Python Runtime | Verification Basis | Patching Policy & Reported Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Verified on real engine** | Exact build **`8.5.0.25111603`** | Python 3.12.7 (64-bit) | Live fixture execution in `island-1.0-win` (`fixture_result.json`, `log.txt`, `vc_version.py`). All 6 tests passed. | Allowed: `native_strings_rpy + verified_real_engine_hook` |
| **Supported with documented fallback** | Fully identified **`8.0.0 – 8.4.x`** | Python 3.9+ | Explicit `vc_version.py` matching major 8, minor 0..4 with full `major.minor.patch`. Mock signature tests. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Supported with documented fallback** | Fully identified **`7.0.0 – 7.6.3`** | Python 2.7.x | Explicit `vc_version.py` matching major 7, minor 0..6 with `patch <= 3`. Python 2.7 AST validation. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Untested / best-effort** | Incomplete strings (`7`, `7.6`), inferred from `lib/` or bytecode, unlisted `8.5.0` builds, `8.5.1+`, `8.6.x`, `9.0.x+`, unknown | Python 2/3 / unknown | Incomplete metadata, unlisted releases, or engine families lacking build metadata. | Allowed with diagnostic warning: `best_effort_polyglot_fallback` |
| **Unsupported** | **Ren'Py < 7.0.0** (e.g. `6.x`) | Legacy Python 2 | Obsolete Screen Language 1 AST, lacks unified string translation dictionary. | **Blocked**: Halts in preflight, rejects patch application. |

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

---

## 4. Conservative Detection Implementation Details

### Detection Algorithm (`detect_renpy_runtime` in `src/gamelingo/adapters/renpy.py`)

```python
# A release is fully identified only when it has at least major, minor, and patch numbers (e.g. 7.6.3 or 8.4.1)
is_fully_identified = bool(version_str and len(numeric_parts) >= 3)
is_real_engine_verified = version_str == "8.5.0.25111603"

if major_version is not None and major_version < 7:
    support_level = "unsupported"
elif is_real_engine_verified:
    support_level = "verified"
elif is_fully_identified and major_version == 7:
    in_7x_range = False
    if minor_version is not None and patch_version is not None:
        if 0 <= minor_version < 6:
            in_7x_range = True
        elif minor_version == 6:
            in_7x_range = patch_version <= 3
    support_level = "supported_with_fallback" if in_7x_range else "best_effort"
elif (
    is_fully_identified
    and major_version == 8
    and minor_version is not None
    and 0 <= minor_version <= 4
):
    support_level = "supported_with_fallback"
elif version_str and version_str != "unknown":
    support_level = "best_effort"
    if len(numeric_parts) < 3:
        support_reason = (
            f"Ren'Py version '{version_str}' is incomplete; cannot verify documented release range. "
            "Best-effort polyglot fallback applied."
        )
    else:
        support_reason = (
            f"Ren'Py {version_str} ({python_family}) is an unverified / unlisted engine version; "
            "best-effort polyglot fallback applied."
        )
else:
    version_str = "unknown"
    support_level = "best_effort"
```

### Action Policies in Patch Application (`apply_plan`):
1. **`verified`**: Emits `native_strings_rpy + verified_real_engine_hook`, zero warnings.
2. **`supported_with_fallback`**: Emits `native_strings_rpy + polyglot_fallback_hook`, notes documented fallback in diagnostics.
3. **`best_effort`**: Emits `best_effort_polyglot_fallback`. Appends warning to `report["warnings"]`:
   - If version is known: `"Ren'Py version <ver> is unverified / untested (<reason>). Best-effort fallback applied."`
   - If version is incomplete: `"Ren'Py version <ver> is unverified / untested (Ren'Py version '<ver>' is incomplete; cannot verify documented release range...). Best-effort fallback applied."`
   - If version is unknown: `"Ren'Py version is unknown (<reason>). Best-effort fallback applied."`
4. **`unsupported`**: Preflight halts immediately with error. No files or archives are written.

---

## 5. Automated Regression Test Suite

All 215 tests pass cleanly with 100% success rate:

```
tests/unit/test_renpy_compatibility.py ..............................   [ 14%]
tests/unit/test_renpy_strings.py ............                            [ 19%]
tests/unit/test_renpy.py .........................                       [ 31%]
tests/unit/test_rpgmaker.py ...................................          [ 47%]
...
============================= 215 passed in 15.40s =============================
```

### Coverage of GL-038.3 Version Boundary Cases:
1. `test_detect_renpy_runtime_7x_from_lib`: Verifies Ren'Py 7 inferred only from Python 2 runtime directories without `vc_version.py` is `best_effort` (`version = "unknown"`).
2. `test_detect_renpy_runtime_incomplete_version_strings_best_effort`: Parameterized across incomplete strings `"7"` and `"7.6"`, verifying both result in `best_effort` with `"incomplete"` diagnostic reason.
3. `test_detect_renpy_runtime_7_6_3_supported_with_fallback`: Verifies fully identified `7.6.3` remains `supported_with_fallback`.
4. `test_detect_renpy_runtime_7_6_4_best_effort`: Verifies `7.6.4` (outside declared range) is `best_effort`.
5. `test_detect_renpy_runtime_8_4_supported_with_fallback`: Verifies confirmed in-range Ren'Py 8 release (`8.4.1.24030701`) remains `supported_with_fallback`.
6. `test_detect_renpy_runtime_8x_from_vc_version`: Verifies `8.3.2.24102902` remains `supported_with_fallback`.
7. `test_detect_renpy_runtime_8_5_verified`: Verifies exact build `8.5.0.25111603` is `verified`.
8. `test_detect_renpy_runtime_different_8_5_build_not_verified`: Verifies different `8.5.0` build is `best_effort`.
9. `test_diagnostics_for_incomplete_version_in_apply_plan`: Verifies incomplete version `"7.6"` generates diagnostic warning mentioning `"incomplete"` in `report["warnings"]`.
10. `test_unsupported_renpy_version_aborts_patch`: Verifies versions below 7.0.0 abort patch application before modifying game files.

---

## 6. Build Integrity & Distribution

- **Repository**: `kunal-gswm/GameLingo`
- **Branch**: `main`
- **Windows Distribution Zip**: `dist/GameLingo-Windows-x64.zip`
- **SHA-256 Checksum**:
  `729C85F691190CAC13F75788F9D53218F4CF72143C2C1E3FC499FC5557F201C2`
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
*Report finalized for GL-038.3: Reject Ambiguous Ren'Py Version Metadata.*
