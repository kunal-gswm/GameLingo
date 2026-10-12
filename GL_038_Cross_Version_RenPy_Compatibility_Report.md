# GL-038 / GL-038.4: Verified Ren'Py Engine Support Matrix & Strict Metadata Validation Report

**Repository**: `kunal-gswm/GameLingo`  
**Task ID**: GL-038.4 (Strict Ren’Py Version Metadata Validation)  
**Date**: October 12, 2026  
**Status**: Verified & Complete  

---

## Executive Summary

GL-038.4 enforces strict validation on Ren’Py version metadata format, completely eliminating numeric-prefix regex parsing (`re.match(r"^(\d+)", p)`). Malformed version metadata (such as `7.6.3garbage`, `8.4.1alpha`, or `7.x.3`) cannot qualify for verified or supported-with-fallback tiers. Legitimate multi-part numeric build versions (such as `8.5.0.25111603` and `7.6.3.2140`) remain accepted and classified according to verified empirical boundaries.

### Key Outcomes:
1. **Strict Format Validation Enforced**:
   - Version metadata strings must consist exclusively of dot-separated decimal integers (`all(p.isdigit() for p in raw_parts)`).
   - Numeric-prefix parsing that previously extracted numeric leading characters from tokens like `3garbage` or `1alpha` has been eliminated.
   - Legitimate standard and build-suffixed releases (`8.5.0.25111603`, `7.6.3.2140`, `7.4.11.2266`, `8.4.1.24030701`, `8.3.2.24102902`) remain accepted and correctly categorized.
2. **Defensive Rejection of Malformed Versions**:
   - Malformed values such as `7.6.3garbage`, `8.4.1alpha`, and `7.x.3` are rejected from documented support tiers (`verified` and `supported_with_fallback`) and classified as **Untested / best-effort**.
   - Malformed versions with reliable evidence that the engine is below the supported minimum (< 7.0.0, e.g. `6.99.12garbage`) remain classified as **Unsupported** and fail preflight immediately.
   - Clear diagnostic warnings are appended: `"Ren'Py version metadata '<ver>' is malformed or non-standard; cannot verify documented support tiers. Best-effort polyglot fallback applied."`
3. **Comprehensive Regression Test Suite**:
   - Expanded `tests/unit/test_renpy_compatibility.py` to **42 focused tests** (227 tests total in repository test suite, all passing).
   - Added parameterized tests for malformed versions (`7.6.3garbage`, `8.4.1alpha`, `7.x.3`, `8.5.0.25111603garbage`, `8.4.1-rc1`), malformed legacy versions (`6.99.12garbage`), and valid build-suffixed versions (`8.5.0.25111603`, `7.6.3.2140`, `7.4.11.2266`, `8.4.1.24030701`, `8.3.2.24102902`).
4. **Build & Package Integrity**:
   - Rebuilt Windows distribution package (`dist/GameLingo-Windows-x64.zip`, SHA-256: `5FBF2BC375449894353D91EFE6A893242FE9795D5B97EA4E9BA98A31D6541306`).

---

## 1. Audit of Support Matrix & Strict Version Boundaries

### Classification Tiers & Verification Evidence

| Support Tier | Scope / Exact Range | Python Runtime | Verification Basis | Patching Policy & Reported Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Verified on real engine** | Exact build **`8.5.0.25111603`** | Python 3.12.7 (64-bit) | Live fixture execution in `island-1.0-win` (`fixture_result.json`, `log.txt`, `vc_version.py`). All 6 tests passed. | Allowed: `native_strings_rpy + verified_real_engine_hook` |
| **Supported with documented fallback** | Fully identified **`8.0.0 – 8.4.x`** | Python 3.9+ | Explicit `vc_version.py` matching major 8, minor 0..4 with full `major.minor.patch` (strictly digits). Mock signature tests. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Supported with documented fallback** | Fully identified **`7.0.0 – 7.6.3`** | Python 2.7.x | Explicit `vc_version.py` matching major 7, minor 0..6 with `patch <= 3` (strictly digits). Python 2.7 AST validation. | Allowed: `native_strings_rpy + polyglot_fallback_hook` |
| **Untested / best-effort** | Malformed versions (`7.6.3garbage`, `8.4.1alpha`, `7.x.3`), incomplete strings (`7`, `7.6`), inferred from `lib/` or bytecode, unlisted `8.5.0` builds, `8.5.1+`, `8.6.x`, `9.0.x+`, unknown | Python 2/3 / unknown | Malformed metadata, incomplete metadata, unlisted releases, or engine families lacking build metadata. | Allowed with diagnostic warning: `best_effort_polyglot_fallback` |
| **Unsupported** | **Ren'Py < 7.0.0** (e.g. `6.x`, `6.99.12garbage`) | Legacy Python 2 | Obsolete Screen Language 1 AST, lacks unified string translation dictionary. | **Blocked**: Halts in preflight, rejects patch application. |

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

## 4. Strict Detection Implementation Details

### Strict Validation Algorithm (`detect_renpy_runtime` in `src/gamelingo/adapters/renpy.py`)

```python
# Strictly validate version metadata format.
# Legitimate Ren'Py version metadata strings consist exclusively of dot-separated decimal integers
# (e.g. "8.5.0.25111603", "7.6.3.2140", "7.4.11.2266", "8.3.2.24102902").
# Numeric-prefix matching (e.g. matching "3" from "3garbage" or "1" from "1alpha") is rejected.
numeric_parts: List[int] = []
is_malformed = False

if version_str and version_str != "unknown":
    clean_ver = version_str.strip()
    raw_parts = clean_ver.split(".")
    if raw_parts and all(p.isdigit() for p in raw_parts):
        numeric_parts = [int(p) for p in raw_parts]
    else:
        is_malformed = True
        if len(raw_parts) >= 1 and raw_parts[0].isdigit():
            if major_version is None:
                major_version = int(raw_parts[0])
        if len(raw_parts) >= 2 and raw_parts[1].isdigit():
            if minor_version is None:
                minor_version = int(raw_parts[1])
        else:
            minor_version = None

if len(numeric_parts) >= 1 and major_version is None:
    major_version = numeric_parts[0]
if len(numeric_parts) >= 2 and minor_version is None:
    minor_version = numeric_parts[1]

patch_version = numeric_parts[2] if len(numeric_parts) >= 3 else None

is_fully_identified = bool(not is_malformed and version_str and len(numeric_parts) >= 3)
is_real_engine_verified = bool(not is_malformed and version_str == "8.5.0.25111603")

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
    if is_malformed:
        support_reason = (
            f"Ren'Py version metadata '{version_str}' is malformed or non-standard; "
            "cannot verify documented support tiers. Best-effort polyglot fallback applied."
        )
    elif len(numeric_parts) < 3:
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
   - If version is malformed: `"Ren'Py version <ver> is unverified / untested (Ren'Py version metadata '<ver>' is malformed or non-standard; cannot verify documented support tiers...). Best-effort fallback applied."`
   - If version is incomplete: `"Ren'Py version <ver> is unverified / untested (Ren'Py version '<ver>' is incomplete; cannot verify documented release range...). Best-effort fallback applied."`
   - If version is unknown: `"Ren'Py version is unknown (<reason>). Best-effort fallback applied."`
4. **`unsupported`**: Preflight halts immediately with error. No files or archives are written.

---

## 5. Automated Regression Test Suite

All 227 tests pass cleanly with 100% success rate:

```
tests/unit/test_renpy_compatibility.py .......................................... [ 18%]
tests/unit/test_renpy_strings.py ............                                     [ 23%]
tests/unit/test_renpy.py .........................                                [ 34%]
tests/unit/test_rpgmaker.py ...................................                   [ 49%]
...
============================= 227 passed in 15.88s =============================
```

### Coverage of GL-038.4 Strict Metadata Validation Cases:
1. `test_detect_renpy_runtime_malformed_versions_rejected_from_documented_tiers`: Parameterized across malformed strings (`7.6.3garbage`, `8.4.1alpha`, `7.x.3`, `8.5.0.25111603garbage`, `8.4.1-rc1`), verifying each is rejected from documented tiers and classified as `best_effort` with `malformed or non-standard` reason.
2. `test_detect_renpy_runtime_malformed_below_minimum_unsupported`: Verifies malformed versions below minimum (`6.99.12garbage`) remain classified as `unsupported`.
3. `test_detect_renpy_runtime_valid_build_suffixed_versions_accepted`: Parameterized across valid multi-part numeric builds (`8.5.0.25111603` [verified], `7.6.3.2140`, `7.4.11.2266`, `8.4.1.24030701`, `8.3.2.24102902` [supported_with_fallback]).
4. `test_diagnostics_for_malformed_version_in_apply_plan`: Verifies malformed version strings generate diagnostic warnings mentioning `malformed` in `report["warnings"]`.
5. `test_detect_renpy_runtime_7x_from_lib`: Verifies Ren'Py 7 inferred only from Python 2 runtime directories without `vc_version.py` is `best_effort` (`version = "unknown"`).
6. `test_detect_renpy_runtime_incomplete_version_strings_best_effort`: Parameterized across incomplete strings `"7"` and `"7.6"`, verifying both result in `best_effort` with `"incomplete"` diagnostic reason.
7. `test_detect_renpy_runtime_7_6_3_supported_with_fallback`: Verifies fully identified `7.6.3` remains `supported_with_fallback`.
8. `test_detect_renpy_runtime_7_6_4_best_effort`: Verifies `7.6.4` (outside declared range) is `best_effort`.
9. `test_detect_renpy_runtime_8_4_supported_with_fallback`: Verifies confirmed in-range Ren'Py 8 release (`8.4.1.24030701`) remains `supported_with_fallback`.
10. `test_detect_renpy_runtime_8x_from_vc_version`: Verifies `8.3.2.24102902` remains `supported_with_fallback`.
11. `test_detect_renpy_runtime_8_5_verified`: Verifies exact build `8.5.0.25111603` is `verified`.
12. `test_detect_renpy_runtime_different_8_5_build_not_verified`: Verifies different `8.5.0` build is `best_effort`.
13. `test_diagnostics_for_incomplete_version_in_apply_plan`: Verifies incomplete version `"7.6"` generates diagnostic warning mentioning `"incomplete"` in `report["warnings"]`.
14. `test_unsupported_renpy_version_aborts_patch`: Verifies versions below 7.0.0 abort patch application before modifying game files.

---

## 6. Build Integrity & Distribution

- **Repository**: `kunal-gswm/GameLingo`
- **Branch**: `main`
- **Windows Distribution Zip**: `dist/GameLingo-Windows-x64.zip`
- **SHA-256 Checksum**:
  `5FBF2BC375449894353D91EFE6A893242FE9795D5B97EA4E9BA98A31D6541306`
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
*Report finalized for GL-038.4: Strict Ren’Py Version Metadata Validation.*
