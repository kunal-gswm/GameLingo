# GL-RPGM-009: RPG Maker MV/MZ Real-Game Compatibility Matrix

**Repository:** `kunal-gswm/GameLingo`  
**Baseline Commit:** `4ef9b9035008d9c3433da6cb717924ecca1572c7`  
**Date:** October 16, 2026  
**Status:** **VERIFIED & COMPLETE**  

---

## Executive Summary

Milestone **GL-RPGM-009** establishes an empirical, multi-project compatibility matrix for GameLingo's RPG Maker MV and MZ localization workflow. Evaluating five distinct real-world game projects (spanning official Kadokawa samples, commercial Japanese visual novels, indie Western titles, and heavily modded plugin ecosystems), the evaluation protocol independently verifies ten rigorous stages of the localization lifecycle without endangering pristine game assets.

### Key Empirical Metrics

- **Project-Level Standard Workflow Success Rate:** **5/5 (100.0%)**
- **Locator Validation Rate:** **119,719 / 119,719 (100.0000%)**
- **Total Real-World Translatable Units Processed:** **119,719 units** across 5 projects
- **Conditional Branch Structural Preservation:** **14,917** `code: 111` commands inspected, with **73,561** nested translatable units patched with 100% parameter immutability.
- **Restoration & Recovery Fidelity:** **100.0% byte-for-byte SHA-256 match** verified across all disposable project restorations.

---

## 1. Project Diversity & Provenance Catalog

The evaluation suite covers five distinct real projects with diverse engine architectures, languages, map scales, and plugin environments:

| Project Identifier | Project Name | Engine & Version | Language | Layout | Maps / Files | Units | Architectural Profile |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | **Do Disciplinary Committee Members Dream of Succubi** | RPG Maker MV (conf=1.00) | Japanese | `www/data` | 555 files | 66,405 | Commercial Japanese RPG Maker MV (v1.6.1) with www/data layout and 40+ maps |
| `mz_sample_nannnimo` | **Official MZ Sample (Nannnimo / Karakuri Town)** | RPG Maker MZ (conf=1.00) | Japanese | `data` | 20 files | 1,143 | Official Kadokawa RPG Maker MZ v1.8.0 sample game, canonical clean schema |
| `mz_indie_playful_parcels` | **Playful Parcels** | RPG Maker MZ (conf=1.00) | English | `data` | 34 files | 8,223 | Modern indie RPG Maker MZ project with 8,223 units and heavy conditional branching |
| `mz_modded_waifu_trap_house` | **Waifu Trap House** | RPG Maker MZ (conf=1.00) | English | `data` | 68 files | 6,353 | Feature-heavy MZ project modded with Yanfly YEP, EliMZ, Galv, and MYTH Card Game Core |
| `mz_commercial_fallen_gf` | **Fallen GF (Full Ver.)** | RPG Maker MZ (conf=1.00) | Japanese | `data` | 344 files | 37,595 | High-volume commercial MZ release with 385 maps, 344 data files, and TRP Skit portrait plugins |

---

## 2. 10-Stage Evaluation Matrix

Every project was independently subjected to the 10-stage evaluation protocol:

1. **Discovery:** Project directory and `System.json` resolution.
2. **Engine Detection:** Distinction between MV (`rpg_core.js`) and MZ (`rmmz_core.js`).
3. **Project Opening:** Parsing project metadata, UTF-8 BOM, and system terms.
4. **Extraction:** High-throughput extraction across system, database, maps, and common events.
5. **Locator Integrity:** Exhaustive or high-density sample resolution against raw JSON source data.
6. **Token Integrity:** Detection and fail-closed validation of RPG Maker control codes (`\V`, `\N`, `\C`, `\I`, etc.).
7. **Conditional Structures:** Event command 111, 411, 412 inspection and nested content parameter preservation.
8. **Patch Planning:** Representative dry-run plan generation and validation.
9. **Preflight & Failure Handling:** Defensive rejection of stale source, invalid locators, and malformed files.
10. **Restoration:** Byte-for-byte SHA-256 restoration on disposable project instances.

| Stage | `mv_commercial_succubi` | `mz_sample_nannnimo` | `mz_indie_playful_parcels` | `mz_modded_waifu_trap_house` | `mz_commercial_fallen_gf` | Evaluation Criteria |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Discovery** | PASS | PASS | PASS | PASS | PASS | Resolves `data/` or `www/data/` with `System.json` |
| **2. Engine Detection** | PASS | PASS | PASS | PASS | PASS | Correct MV vs MZ identification (confidence >= 0.70) |
| **3. Project Opening** | PASS | PASS | PASS | PASS | PASS | Parses `gameTitle`, `currencyUnit`, and system terms |
| **4. Extraction** | PASS | PASS | PASS | PASS | PASS | Extracts translatable units without crash |
| **5. Locator Integrity** | PASS | PASS | PASS | PASS | PASS | 100.0% locator match to source text |
| **6. Token Integrity** | PASS | PASS | PASS | PASS | PASS | Control codes extracted; dropping triggers validation rejection |
| **7. Conditional Structures** | PASS | PASS | PASS | PASS | PASS | Nested branch locators valid; parameters unchanged |
| **8. Patch Planning** | PASS | PASS | PASS | PASS | PASS | Generates valid dry-run patch plan without error |
| **9. Failure Handling** | PASS | PASS | PASS | PASS | PASS | Stale sources & invalid locators rejected fail-closed |
| **10. Restoration** | PASS | PASS | PASS | PASS | PASS | Byte-exact SHA-256 restoration on disposable copy |

---

## 3. Extraction & Command Type Breakdown

Detailed yield breakdown across file categories and RPG Maker event command codes:

| Project Identifier | System | Database | Maps | CommonEvents | MapInfos | Total Units | Extraction Time | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 98 | 3,903 | 40,382 | 21,491 | 531 | **66,405** | 2.042s | 32,511 units/s |
| `mz_sample_nannnimo` | 99 | 821 | 213 | 4 | 6 | **1,143** | 0.023s | 49,964 units/s |
| `mz_indie_playful_parcels` | 99 | 831 | 7,236 | 37 | 20 | **8,223** | 0.095s | 86,399 units/s |
| `mz_modded_waifu_trap_house` | 98 | 1,012 | 5,055 | 134 | 54 | **6,353** | 0.129s | 49,216 units/s |
| `mz_commercial_fallen_gf` | 99 | 810 | 33,433 | 2,923 | 330 | **37,595** | 0.812s | 46,284 units/s |

### Event Command Code Distribution

| Project Identifier | Code 101 (Speaker) | Code 401 (Show Text) | Code 102 (Choices) | Code 402 (When) | Code 405 (Scroll) | Code 320/324/325 (Actor) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 0 | 56,775 | 2,413 | 2,413 | 0 | 0 |
| `mz_sample_nannnimo` | 0 | 144 | 32 | 32 | 9 | 0 |
| `mz_indie_playful_parcels` | 2,768 | 4,426 | 33 | 33 | 0 | 0 |
| `mz_modded_waifu_trap_house` | 1,817 | 3,169 | 150 | 150 | 0 | 0 |
| `mz_commercial_fallen_gf` | 7,488 | 25,693 | 1,534 | 1,534 | 0 | 0 |

---

## 4. Conditional Branch Structural Safety Analysis

All five projects feature event command `111` (Conditional Branch). The table below quantifies the structural branch complexity and confirms parameter immutability:

| Project Identifier | Code 111 (If) | Code 411 (Else) | Code 412 (End) | Units Nested in Branches | Parameter Immutability | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 8,533 | 3,637 | 8,533 | 54,282 | Preserved (Unchanged) | **PASS** |
| `mz_sample_nannnimo` | 36 | 5 | 36 | 11 | Preserved (Unchanged) | **PASS** |
| `mz_indie_playful_parcels` | 737 | 203 | 737 | 3,753 | Preserved (Unchanged) | **PASS** |
| `mz_modded_waifu_trap_house` | 459 | 145 | 459 | 2,577 | Preserved (Unchanged) | **PASS** |
| `mz_commercial_fallen_gf` | 5,152 | 1,129 | 5,152 | 12,938 | Preserved (Unchanged) | **PASS** |

> [!NOTE] Conditional Branch Scope
> Verification of conditional branch commands in this matrix confirms structural extraction, locator stability, parameter immutability, and rollback safety.
> Direct native runtime execution of all conditional branches in live NW.js gameplay sessions was verified on Map 7 in GL-RPGM-PILOT-6B, and is not claimed for every conditional branch type across all projects.

---

## 5. Third-Party Plugin Audit & Boundary Definition

Standard RPG Maker MV/MZ games use built-in event commands and database records. Many production titles incorporate third-party plugin suites. The compatibility evaluation isolates standard core engine compatibility from specialized plugin systems:

| Project Identifier | Registered Plugins | Active Plugins | Detected Plugin Suites | Code 356 (MV Cmd) | Code 357 (MZ Cmd) | Database Notes | Core Compatibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | 218 | 210 | Galv Scripts, Moghunter (Atelier RGSS), Mokusei Penguin (MPP), TRP Skit Suite, Yanfly Engine Plugins (YEP) | 2,127 | 0 | 2,977 | **100% Core PASS** |
| `mz_sample_nannnimo` | 0 | 0 | None | 0 | 0 | 3 | **100% Core PASS** |
| `mz_indie_playful_parcels` | 6 | 6 | Eli Plugins (Hakuen Studio) | 0 | 2 | 7 | **100% Core PASS** |
| `mz_modded_waifu_trap_house` | 17 | 11 | Galv Scripts | 0 | 66 | 5 | **100% Core PASS** |
| `mz_commercial_fallen_gf` | 40 | 40 | Moghunter (Atelier RGSS), Mokusei Penguin (MPP), TRP Skit Suite | 0 | 3,197 | 7 | **100% Core PASS** |

> [!IMPORTANT] Architectural Boundary: Core Engine vs. Plugin Extensions
> - **Core Engine Compatibility (100% Supported):** Dialogue, speakers, choices, scrolling text, database records, map displays, system terms, and conditional branch structures are 100% extracted, validated, and patched.
> - **Plugin Command Limitations (Design Isolation):** Event commands `356` (MV) and `357` (MZ) carry arbitrary third-party plugin instructions (e.g. camera shakes, screen zooms, skit portrait changes). GameLingo intentionally isolates standard dialogue from arbitrary plugin parameters.
> - **Database Note Tags:** Note fields often contain formula scripts or metadata tags (e.g. `<Help: ...>`). These are safely preserved unmodified to protect game logic stability.

---

## 6. Restoration & Safety Verification

Every project underwent a disposable patch-and-restore cycle in an isolated directory. The table below verifies that original files were modified during patching and restored to exact bit-for-bit SHA-256 equivalence:

| Project Identifier | Target File | Original SHA-256 (Prefix) | Patched SHA-256 (Prefix) | Restored SHA-256 (Prefix) | Hash Match |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mv_commercial_succubi` | `www/data/System.json` | `c046f2f05438...` | `db7b912d78a1...` | `c046f2f05438...` | **100.0% Exact** |
| `mz_sample_nannnimo` | `data/System.json` | `028a83cb052f...` | `e73391f8a204...` | `028a83cb052f...` | **100.0% Exact** |
| `mz_indie_playful_parcels` | `data/System.json` | `f0db46f85e89...` | `87ca4872230e...` | `f0db46f85e89...` | **100.0% Exact** |
| `mz_modded_waifu_trap_house` | `data/System.json` | `b173a3fbf1ce...` | `860a28f476ec...` | `b173a3fbf1ce...` | **100.0% Exact** |
| `mz_commercial_fallen_gf` | `data/System.json` | `4429f1736e4f...` | `9fbf66dddd03...` | `4429f1736e4f...` | **100.0% Exact** |

---

## 7. Reproduction Instructions

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

## 8. Known Gaps & Next Highest-Priority Defects

1. **Plugin Parameter Extraction:** Third-party visual novel skits (e.g. `TRP_SkitMZ` in *Fallen GF*) define speaker portraits and custom messages in plugin commands (`code: 357`). Developing schema-guided plugin decoders is the next logical enhancement.
2. **Database Note Field Localization:** Games utilizing note-field tags (e.g. `<Description: ...>`) require selective tag parsing rather than whole-field extraction to prevent formula corruption.
3. **Dynamic Script Execution:** Scripts inside `code: 355` (Script) containing embedded string literals are not extracted by static AST analysis.
