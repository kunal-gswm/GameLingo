# GL-RPGM-009A.2: RPG Maker MV/MZ Real-Game Compatibility Matrix

**Repository:** `kunal-gswm/GameLingo`  
**Application Baseline Commit:** `4ef9b9035008d9c3433da6cb717924ecca1572c7`  
**Harness Source Commit:** `ecea8df31fcff36ebcd38192d5b79f1dd6fb9341`  
**Harness Version:** `GL-RPGM-009A.2`  
**Date:** October 16, 2026  
**Status:** **VERIFIED & CALIBRATED**  

---

## Executive Summary

Milestone **GL-RPGM-009A.2** establishes a calibrated empirical compatibility evaluation across GameLingo's RPG Maker MV and MZ localization workflow. Evaluating five distinct real-world game projects (spanning official Kadokawa samples, commercial Japanese visual novels, indie Western titles, and heavily modded plugin ecosystems), the evaluation independently assesses ten discrete stages of the localization lifecycle on read-only original directories and isolated disposable copies.

### Key Calibrated Metrics

- **Project-Level Core Workflow Success Rate:** **5/5 (100.0%)**
- **Locator Validation Rate:** **119,719 / 119,719 (100.0000%)** (100.0% exhaustive AST resolution across all five projects)
- **Total Real-World Translatable Units Extracted:** **119,719 units** across 5 projects
- **Conditional Branch Structural Coverage:** **14,917** `code: 111` commands and **73,561 qualifying branch command nodes** enumerated across 5 projects
- **Representative Branch Patch Validation:** **35 units** actually patched across maps and common events, confirming **recursive allowlisted diff compliance**, **100% parameter immutability**, and **100% byte-exact restoration**
- **Restoration & Recovery Fidelity:** **100.0% byte-for-byte SHA-256 match** verified across multi-file disposable patch-and-restore cycles in all five projects
- **Third-Party Plugin Scope:** Standard-schema core extraction and patch safety verified across 5 project datasets; third-party plugin commands (`code: 356/357`), custom plugin parameters, and plugin-defined note fields are explicitly **UNTESTED / OUT OF CORE ENGINE SCOPE** (with native runtime verified only for Pilot 6B Map 7).

---

## 1. Project Diversity & Provenance Catalog

The evaluation suite covers five distinct real projects with diverse engine architectures, languages, map scales, and plugin environments. All paths are sanitized to project identifiers:

| Project Identifier | Project Name | Engine & Version | Language | Layout | Files | Extracted Units | Provenance & Architectural Profile |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | **Do Disciplinary Committee Members Dream of Succubi** | RPG Maker MV (conf=1.00) | Japanese | `www/data` | 555 files | 66,405 | Commercial Japanese RPG Maker MV (v1.6.1) with www/data layout and 40+ maps |
| `mz_sample_nannnimo` | **Official MZ Sample (Nannnimo / Karakuri Town)** | RPG Maker MZ (conf=1.00) | Japanese | `data` | 20 files | 1,143 | Official Kadokawa RPG Maker MZ v1.8.0 sample game, canonical clean schema |
| `mz_indie_playful_parcels` | **Playful Parcels** | RPG Maker MZ (conf=1.00) | English | `data` | 34 files | 8,223 | Modern indie RPG Maker MZ project with 8,223 units and heavy conditional branching |
| `mz_modded_waifu_trap_house` | **Waifu Trap House** | RPG Maker MZ (conf=1.00) | English | `data` | 68 files | 6,353 | Feature-heavy MZ project modded with Yanfly YEP, EliMZ, Galv, and MYTH Card Game Core |
| `mz_commercial_fallen_gf` | **Fallen GF (Full Ver.)** | RPG Maker MZ (conf=1.00) | Japanese | `data` | 344 files | 37,595 | High-volume commercial MZ release with 385 maps, 344 data files, and TRP Skit portrait plugins |

---

## 2. 10-Stage Calibrated Compatibility Matrix

Every project was independently subjected to the 10-stage evaluation protocol:

1. **Discovery:** Project directory and `System.json` resolution.
2. **Engine Detection:** Distinction between MV (`rpg_core.js`) and MZ (`rmmz_core.js`).
3. **Project Opening:** Parsing project metadata, UTF-8 BOM, and system terms.
4. **Extraction:** High-throughput extraction across system, database, maps, and common events.
5. **Locator Integrity:** Exhaustive in-memory resolution of every extracted locator against raw JSON data AST.
6. **Token Integrity:** Detection and multi-token fail-closed rejection of dropped control codes (`\V`, `\N`, `\C`, `\I`, etc.).
7. **Conditional Structures:** Event command 111, 411, 412 inspection, representative branch patching, and parameter immutability.
8. **Patch Planning:** Stratified dry-run plan generation across diverse file categories.
9. **Preflight & Failure Handling:** Defensive rejection of stale source, invalid locators, and malformed files.
10. **Restoration:** Byte-for-byte SHA-256 restoration on multi-file disposable project instances.

| Stage | `mv_commercial_succubi` | `mz_sample_nannnimo` | `mz_indie_playful_parcels` | `mz_modded_waifu_trap_house` | `mz_commercial_fallen_gf` | Evaluation Criteria & Operational Boundary |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Discovery** | PASS | PASS | PASS | PASS | PASS | Resolves `data/` or `www/data/` with `System.json` |
| **2. Engine Detection** | PASS | PASS | PASS | PASS | PASS | Correct MV vs MZ identification (confidence >= 0.70) |
| **3. Project Opening** | PASS | PASS | PASS | PASS | PASS | Parses `gameTitle`, `currencyUnit`, and system terms |
| **4. Extraction** | PASS | PASS | PASS | PASS | PASS | Extracts translatable units without unhandled exception |
| **5. Locator Integrity** | PASS | PASS | PASS | PASS | PASS | 100.0% exhaustive locator resolution against raw JSON source data |
| **6. Token Integrity** | PASS | PASS | PASS | PASS | PASS | Control codes extracted; dropping each detected form triggers validation rejection |
| **7. Conditional Structures** | PASS | PASS | PASS | PASS | PASS | Nested branch locators valid; representative patching preserves 111/411/412 parameters |
| **8. Patch Planning** | PASS | PASS | PASS | PASS | PASS | Generates valid stratified dry-run patch plan across multiple file categories |
| **9. Failure Handling** | PASS | PASS | PASS | PASS | PASS | Stale sources & invalid locators rejected fail-closed; malformed files handled safely |
| **10. Restoration** | PASS | PASS | PASS | PASS | PASS | Multi-file byte-exact SHA-256 restoration on disposable copy |

---

## 3. Extraction & Command Type Breakdown

Detailed yield breakdown across file categories and RPG Maker event command codes:

| Project Identifier | System | Database | Maps | CommonEvents | MapInfos | Total Units | Extraction Time | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 98 | 3,903 | 40,382 | 21,491 | 531 | **66,405** | 12.312s | 5,394 units/s |
| `mz_sample_nannnimo` | 99 | 821 | 213 | 4 | 6 | **1,143** | 0.248s | 4,607 units/s |
| `mz_indie_playful_parcels` | 99 | 831 | 7,236 | 37 | 20 | **8,223** | 0.444s | 18,535 units/s |
| `mz_modded_waifu_trap_house` | 98 | 1,012 | 5,055 | 134 | 54 | **6,353** | 0.924s | 6,877 units/s |
| `mz_commercial_fallen_gf` | 99 | 810 | 33,433 | 2,923 | 330 | **37,595** | 4.503s | 8,349 units/s |

### Event Command Code Distribution

| Project Identifier | Code 101 (Speaker) | Code 401 (Show Text) | Code 102 (Choices) | Code 402 (When) | Code 405 (Scroll) | Code 320/324/325 (Actor) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 0 | 56,775 | 2,413 | 2,413 | 0 | 0 |
| `mz_sample_nannnimo` | 0 | 144 | 32 | 32 | 9 | 0 |
| `mz_indie_playful_parcels` | 2,768 | 4,426 | 33 | 33 | 0 | 0 |
| `mz_modded_waifu_trap_house` | 1,817 | 3,169 | 150 | 150 | 0 | 0 |
| `mz_commercial_fallen_gf` | 7,488 | 25,693 | 1,534 | 1,534 | 0 | 0 |

---

## 4. Conditional Branch Structural Coverage & Real-Game Patch Validation

All five projects feature event command `111` (Conditional Branch). The table below distinguishes units counted inside conditional structures from units actually patched during representative validation:

| Project Identifier | Code 111 (If) | Code 411 (Else) | Code 412 (End) | Qualifying Branch Command Nodes | Representative Units Patched | Command Types Tested | Allowlisted Diff | Immutability Verified | Byte-Exact Restore |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 8,533 | 3,637 | 8,533 | 54,282 | **6** | `code_401_else, code_401_if, code_402_choice, nested_depth_ge_2` | **PASS (0 violations)** | **100% Immutable** | **100% Exact** |
| `mz_sample_nannnimo` | 36 | 5 | 36 | 11 | **2** | `code_401_if` | **PASS (0 violations)** | **100% Immutable** | **100% Exact** |
| `mz_indie_playful_parcels` | 737 | 203 | 737 | 3,753 | **9** | `code_101_speaker, code_401_else, code_401_if, code_402_choice, nested_depth_ge_2` | **PASS (0 violations)** | **100% Immutable** | **100% Exact** |
| `mz_modded_waifu_trap_house` | 459 | 145 | 459 | 2,577 | **10** | `code_101_speaker, code_401_else, code_401_if, code_402_choice, nested_depth_ge_2` | **PASS (0 violations)** | **100% Immutable** | **100% Exact** |
| `mz_commercial_fallen_gf` | 5,152 | 1,129 | 5,152 | 12,938 | **8** | `code_101_speaker, code_401_else, code_401_if, code_402_choice, nested_depth_ge_2` | **PASS (0 violations)** | **100% Immutable** | **100% Exact** |

> [!NOTE] Distinction: Counted Branch Command Nodes vs. Representative Patch Testing
> Across the 5 real projects, **73,561 qualifying branch command nodes** (event command opcodes 101, 401, 102, 402, 405, 320, 324, 325) reside inside conditional branches (54,282 in Succubi, 11 in MZ Sample, 3,753 in Playful Parcels, 2,577 in Waifu Trap House, 12,938 in Fallen GF). > Rather than claiming all 73,561 command nodes were modified, the evaluation executed representative patch validation on **35 targeted units** across maps and common events. > For each patched unit, an allowlisted recursive JSON AST diff check proved that only the targeted text/speaker parameter path changed to the exact expected translated value; all condition codes, comparator arguments, switch/variable IDs, branch markers, indents, and event sequences remained 100% byte-for-byte immutable.

> [!IMPORTANT] Runtime Boundary
> Representative branch patching confirms structural safety, locator validity, and rollback fidelity. > Live native runtime execution of conditional branches within NW.js gameplay sessions was verified on Map 7 in GL-RPGM-PILOT-6B, and is not claimed for every conditional branch type across all projects.

---

## 5. Third-Party Plugin Audit & Boundary Definition

The evaluation evaluated plugin environments across all titles to delineate core engine support from plugin limitations:

| Project Identifier | Registered Plugins | Active Plugins | Detected Plugin Suites | Code 356 (MV Cmd) | Code 357 (MZ Cmd) | Database Notes | Standard Schema Extraction & Patch | Plugin Runtime Interoperability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 218 | 210 | Galv Scripts, Moghunter (Atelier RGSS), Mokusei Penguin (MPP), TRP Skit Suite, Yanfly Engine Plugins (YEP) | 2,127 | 0 | 2,977 | **PASS (Standard Core)** | UNTESTED (Out of Scope) |
| `mz_sample_nannnimo` | 0 | 0 | None | 0 | 0 | 3 | **PASS (Standard Core)** | UNTESTED (Out of Scope) |
| `mz_indie_playful_parcels` | 6 | 6 | Eli Plugins (Hakuen Studio) | 0 | 2 | 7 | **PASS (Standard Core)** | VERIFIED (Pilot 6B Map 7; others UNTESTED) |
| `mz_modded_waifu_trap_house` | 17 | 11 | Galv Scripts | 0 | 66 | 5 | **PASS (Standard Core)** | UNTESTED (Out of Scope) |
| `mz_commercial_fallen_gf` | 40 | 40 | Moghunter (Atelier RGSS), Mokusei Penguin (MPP), TRP Skit Suite | 0 | 3,197 | 7 | **PASS (Standard Core)** | UNTESTED (Out of Scope) |

> [!WARNING] Calibrated Plugin Policy: Standard Schema Verified; Custom Plugins Untested
> - **What Was Tested (Standard Core Schema):** Extraction, locator integrity, stratified dry-run planning, representative branch patching, and byte-exact restoration operate reliably across all 5 evaluated datasets containing third-party plugin suites.
> - **Third-Party Plugin Runtime Interoperability:** Native runtime execution of third-party plugins is **UNTESTED**, except for the specific Map 7 conditional branch / dialogue execution verified in Pilot 6B.
> - **Excluded Scope (Unsupported):** Custom plugin parameters in `plugins.js`, arbitrary plugin commands (`code: 356/357`), arbitrary script executions (`code: 355`), and plugin-defined metadata in database note tags (e.g. formula scripts, `<Help: ...>`) are intentionally excluded from localization translation units to prevent game script corruption.

---

## 6. Multi-File Restoration & Recovery Verification

Every project underwent a disposable patch-and-restore cycle modifying multiple files simultaneously. Original files were verified modified and restored to exact bit-for-bit SHA-256 equivalence:

| Project Identifier | Files Tested | Hash Before Patch | Hash After Patch | Hash After Restore | Byte-Exact Match |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | `www/data/Map001.json`<br>`www/data/System.json` | `51129fc99384...`<br>`c046f2f05438...` | `220358f60a25...`<br>`d7e6e0c3a252...` | `51129fc99384...`<br>`c046f2f05438...` | **100.0% Exact** |
| `mz_sample_nannnimo` | `data/Map001.json`<br>`data/System.json` | `eece65ab0238...`<br>`028a83cb052f...` | `886af7531585...`<br>`2aca732c13ce...` | `eece65ab0238...`<br>`028a83cb052f...` | **100.0% Exact** |
| `mz_indie_playful_parcels` | `data/Map001.json`<br>`data/System.json` | `77fbb014d406...`<br>`f0db46f85e89...` | `ba4884f74317...`<br>`21ab1a318fd4...` | `77fbb014d406...`<br>`f0db46f85e89...` | **100.0% Exact** |
| `mz_modded_waifu_trap_house` | `data/Map001.json`<br>`data/System.json` | `a54022dd18c0...`<br>`b173a3fbf1ce...` | `4bf93fbdc780...`<br>`6e78bbe4c7e1...` | `a54022dd18c0...`<br>`b173a3fbf1ce...` | **100.0% Exact** |
| `mz_commercial_fallen_gf` | `data/Map035.json`<br>`data/System.json` | `8602888bd171...`<br>`4429f1736e4f...` | `1ee4afe822d4...`<br>`e2fa09d67aa7...` | `8602888bd171...`<br>`4429f1736e4f...` | **100.0% Exact** |

---

## 7. Reconciliation of MV Extraction Counts (GL-030 65,616 vs. GL-RPGM-PILOT 66,405)

The historical GL-030 pilot extracted **65,616 units** from *Do Disciplinary Committee Members Dream of Succubi*. The current extraction count of **66,405 units** (+789 units) is substantiated by empirical repository evidence recorded in `docs/releases/GL_RPGM_Pilot_Report.md` (lines 239-241):

- **Expanded System Term Scope:** GameLingo added full extraction for `terms.basic` (Level, HP, MP), `terms.commands` (Fight, Escape, Attack, Defend), `terms.params` (MHP, MMP, ATK, DEF), and `terms.messages` (Action Failure, Actor Damage, etc.).
- **Interactive Choice Structures:** GameLingo expanded extraction to cover choice option arrays (`code: 102`) and choice branch handlers (`code: 402`).
- Together, these structural additions contribute exactly +789 translatable units to the commercial MV game baseline.

---

## 8. Reproduction Instructions

To reproduce the evaluation results:

```bash
# Run the complete real-game compatibility evaluation harness:
uv run python scripts/evaluate_rpgmaker_compatibility.py

# Run with explicit JSON output and markdown report paths:
uv run python scripts/evaluate_rpgmaker_compatibility.py --output-json evidence/gl_rpgm_pilot/gl_rpgm_009_compatibility_matrix.json --output-report docs/releases/GL_RPGM_009_Compatibility_Report.md

# Run synthetic integration test suite:
uv run pytest tests/integration/test_rpgmaker_compatibility_matrix.py
```

---

## 9. Known Limitations & Next Priorities

1. **Plugin Parameter Decoding:** Third-party visual novel skits (e.g. `TRP_SkitMZ` in *Fallen GF*) define speaker portraits and custom messages in plugin commands (`code: 357`). Developing schema-guided plugin decoders is the next logical enhancement.
2. **Database Note Field Localization:** Games utilizing note-field tags (e.g. `<Description: ...>`) require selective tag parsing rather than whole-field extraction to prevent formula corruption.
3. **Dynamic Script Execution:** Scripts inside `code: 355` (Script) containing embedded string literals are not extracted by static AST analysis.
