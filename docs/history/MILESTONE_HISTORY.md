# GameLingo Milestone & Acceptance History

This document consolidates historical acceptance testing, provenance verification, and release records for GameLingo milestones (GL-022 through GL-033.1).

---

## 1. Verified Release Artifact Registry

All verified distributable Windows x64 package builds (`dist\GameLingo-Windows-x64.zip`) are cataloged below with exact provenance evidence:

| Milestone | Artifact Filename | Archive Size (Bytes) | SHA-256 Checksum | Source Commit | Verification Status / Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GL-027** | `GameLingo-Windows-x64.zip` | 273,209,329 | `6B70739FD3FB348418C2752E627BB92B1032A9FF062A88BD1FD9193B8A61B0D5` | `5849436` | Historical verified release candidate |
| **GL-028** | `GameLingo-Windows-x64.zip` | 273,071,390 | `597DAF94D270FE109B52701E70F891D11B5FE13FD40FDCB24A6D560F4D089FE9` | `3efb2bc` | Historical verified build |
| **GL-029** | `GameLingo-Windows-x64.zip` | 273,214,028 | `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309` | `ba2cf0d` | Historical verified rebuild |
| **GL-030** | `GameLingo-Windows-x64.zip` | 273,222,059 | `BEB22524FFDEBE044DDA02263C52305809FE54BC4BD4A92070FAAFEEDC8CFDE8` | `1cd6a6a` | Historical verified rebuild |
| **GL-031** | `GameLingo-Windows-x64.zip` | 273,222,060 | `04C63E19ED0F7A6A098E90FFC7F93EAF923053D2A68748D8FE804B07D3E2FBFB` | `6459f53` | Historical verified build |
| **GL-032.1** | `GameLingo-Windows-x64.zip` | 273,230,064 | `E1DB91D8EB62BDEEB7D9D3F951FFEB5A02324905F999D5777FDB296E0C09E050` | `61b93d6` | Historical verified build |
| **GL-033** | `GameLingo-Windows-x64.zip` | 273,272,833 | `269D34C7B30BF31DCE16A94C1DC8381A41BD464F76608F97540FB5717DAC750B` | `5eb22f2` | Historical verified build |
| **GL-033.1** | `GameLingo-Windows-x64.zip` | 273,275,586 | `2E0B40CFFFCD7774FE55BA2F5473AF21E202C762290F168B33A7CD841955957C` | `41895e2` | **Current verified release** |

> **Audit Note on Reconciled Entries:** An unverified draft entry previously citing SHA-256 `80295843...` for commit `ba2cf0d` was investigated in GL-031 and removed from the verified register because no matching build artifact or log existed in committed evidence.

---

## 2. Chronological Milestone Summary

### GL-022: Packaged Application Acceptance Testing
- **Summary:** First packaged Windows application acceptance testing with automated headless verification flags.
- **Key Deliverables:** Added `--smoke-test` and `--test-workflow` execution flags to `GameLingo.exe` (`src/gamelingo/gui/main.py`); verified headless Qt initialization and synthetic pipeline in spaced directory paths.
- **Source Commit:** `f57def1ae147fccbfa0dccd9492c3ba3324e2244`
- **CI Verification:** [Run 38040915801](https://github.com/kunal-gswm/GameLingo/actions/runs/38040915801) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (~267 MB)
- **Limitations:** Model weights not bundled; user must explicitly trigger model download or provide offline `.argosmodel`.

### GL-025: Patch Safety and Backup Isolation
- **Summary:** Hardened patch application safety, UUID-isolated backup directories, and guaranteed staging cleanup.
- **Key Deliverables:** Modified `create_backup` to generate isolated directories under `workspace/backups/<uuid>/`; wrapped staged write in `try/finally` to clean temporary files on early failure; updated CLI and GUI to display `backup_id` and `backup_dir`.
- **Quality Gate:** 73 passed, 1 skipped.

### GL-026: Safe Temporary Staging and Multi-File Rollback
- **Summary:** Collision-free temporary staging using `tempfile.mkstemp` and automated multi-file rollback.
- **Key Deliverables:** Used `gamelingo_*.tmp` prefix via `tempfile.mkstemp`; registered temporary files immediately in cleanup tracking; automated byte-for-byte rollback via `execute_restore` upon injected OS errors during replacement.
- **Source Commit:** `d06cd843b578a13ddd012dfb49cb95de63fe6565`
- **CI Verification:** [Run 38059739760](https://github.com/kunal-gswm/GameLingo/actions/runs/38059739760) (Passed)
- **Quality Gate:** 79 passed, 1 skipped.

### GL-027: Windows Release Candidate and End-to-End Acceptance
- **Summary:** Production and validation of fresh Windows release candidate consolidating GL-024, GL-025, and GL-026.
- **Key Deliverables:** Executed complete synthetic workflow in packaged executable (extraction $\rightarrow$ fake translation $\rightarrow$ CSV export/import $\rightarrow$ patch plan $\rightarrow$ dry run $\rightarrow$ backup $\rightarrow$ atomic patch $\rightarrow$ restore); verified 0 regressions.
- **Source Commit:** `584943601482b7b512443a810b3ac482088c8838`
- **Artifact:** `GameLingo-Windows-x64.zip` (273,209,329 bytes, SHA-256 `6B70739FD3FB348418C2752E627BB92B1032A9FF062A88BD1FD9193B8A61B0D5`)
- **Quality Gate:** 85 passed, 0 skipped.

### GL-028: Argos Model Setup, First-Run UX, and Offline Readiness
- **Summary:** Non-intrusive first-run translation model setup with full offline detection and local package import.
- **Key Deliverables:** Implemented `ArgosSetupService` (`check_status`, download, local package install); added offline status checks and install options in GUI translation page; CLI prevents translation if model missing; 0 unrequested network calls.
- **Source Commit:** `ba2cf0dbd83c732c7cb490960fc6497b4603cd63`
- **CI Verification:** [Run 38112737871](https://github.com/kunal-gswm/GameLingo/actions/runs/38112737871) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,214,028 bytes, SHA-256 `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309`)
- **Quality Gate:** 94 passed, 0 skipped.

### GL-029: Release Verification and Artifact Provenance
- **Summary:** Distributable Windows x64 package rebuild and formal acceptance testing in spaced path.
- **Key Deliverables:** Verified exclusions of model weights, databases, and scratch data; verified headless `--smoke-test` and `--test-workflow` in spaced directory `dist\GL029 acceptance test\`.
- **Source Commit:** `ba2cf0dbd83c732c7cb490960fc6497b4603cd63`
- **CI Verification:** [Run 38112737871](https://github.com/kunal-gswm/GameLingo/actions/runs/38112737871) & [Run 38114583853](https://github.com/kunal-gswm/GameLingo/actions/runs/38114583853) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,214,028 bytes, SHA-256 `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309`)
- **Quality Gate:** 94 passed, 0 skipped.

### GL-030: Real-Game Pilot and Windows GUI Acceptance
- **Summary:** Pilot testing against a real commercial Japanese RPG Maker MV desktop game (*Do Disciplinary Committee Members Dream of Succubi* v1.04).
- **Key Deliverables:** Discovered and fixed release-blocking crash in `RPGMakerMVMZAdapter` when encountering `MapInfos.json` list schema (`_extract_map_infos` handler added); extracted 65,616 units; verified genuine Argos translation on 50 units (49 valid, 1 safely caught by `PlaceholderProtector`); verified atomic patch and 100% byte-for-byte restore.
- **Application Fix Commit:** [`1cd6a6a198aab469d3e1c1b32eed14efa7779aa6`](https://github.com/kunal-gswm/GameLingo/commit/1cd6a6a198aab469d3e1c1b32eed14efa7779aa6)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,222,059 bytes, SHA-256 `BEB22524FFDEBE044DDA02263C52305809FE54BC4BD4A92070FAAFEEDC8CFDE8`)
- **Quality Gate:** 95 passed, 0 skipped.

### GL-031: Manual Windows Acceptance and Release Provenance
- **Summary:** Release provenance audit, package exclusion audit, and historical checksum reconciliation.
- **Key Deliverables:** Established clear boundary between programmatic automated acceptance and desktop interactive testing; audited packaged zip exclusions; investigated and removed unverified hash entry (`80295843...`).
- **Source Commit:** [`6459f53a82b0399747867e43547639642b138bf6`](https://github.com/kunal-gswm/GameLingo/commit/6459f53a82b0399747867e43547639642b138bf6)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,222,060 bytes, SHA-256 `04C63E19ED0F7A6A098E90FFC7F93EAF923053D2A68748D8FE804B07D3E2FBFB`)
- **Quality Gate:** 95 passed, 0 skipped.

### GL-032 / GL-032.1: Desktop UI Redesign, Usability Overhaul, and Status Accuracy
- **Summary:** Complete PySide6 UI overhaul with dark graphite workbench theme, responsive layout, Supported Formats card, and truthful status indicators.
- **Key Deliverables:** Created `theme.py` design system; redesigned Dashboard, Extraction, Translation, Review, and Patch pages; responsive sizing (1180x760 initial, 900x600 minimum); Supported Game Formats card with live structure diagnostics; corrected status semantics ("Local-first", "Game Selected").
- **Source Commit:** [`61b93d6e1e967cd018adf8c114b4af339ec3234e`](https://github.com/kunal-gswm/GameLingo/commit/61b93d6e1e967cd018adf8c114b4af339ec3234e) / [`a158de7`](https://github.com/kunal-gswm/GameLingo/commit/a158de7)
- **CI Verification:** [Run 38136361839](https://github.com/kunal-gswm/GameLingo/actions/runs/38136361839) & [Run 38136894082](https://github.com/kunal-gswm/GameLingo/actions/runs/38136894082) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,230,064 bytes, SHA-256 `E1DB91D8EB62BDEEB7D9D3F951FFEB5A02324905F999D5777FDB296E0C09E050`)
- **Quality Gate:** 103 passed, 0 skipped.

### GL-033 / GL-033.1: Ren'Py Visual Novel Support and Hardening
- **Summary:** Native Ren'Py visual novel support alongside RPG Maker MV/MZ; recursive source discovery, safe language activation, and clean unlinking on restoration.
- **Key Deliverables:** Implemented `gamelingo.adapters.registry` and `RenPyAdapter`; conservative extraction for dialogue, narration, choices, and `_()` strings; Ren'Py variable interpolation (`[player_name]`) and style tag protection; native `game/tl/<language>/strings.rpy` generation without touching `.rpy` scripts; newly created file backup/restore deletion; recursive source discovery (`rglob`); `game/tl/` exclusion; `.rpyc`-only extraction rejection (`RuntimeError`); optional language activation patch (`game/00_gamelingo_activate.rpy`).
- **Feature Commit:** [`41895e2227ec2b30b30bf351934252f36acb3d03`](https://github.com/kunal-gswm/GameLingo/commit/41895e2227ec2b30b30bf351934252f36acb3d03)
- **Documentation Commit:** [`2bd24ef18c9e9fffaca106fcedb7f3efb5a8b14c`](https://github.com/kunal-gswm/GameLingo/commit/2bd24ef18c9e9fffaca106fcedb7f3efb5a8b14c)
- **CI Verification:** [Run 38140117225](https://github.com/kunal-gswm/GameLingo/actions/runs/38140117225), [Run 38143370607](https://github.com/kunal-gswm/GameLingo/actions/runs/38143370607), & [Run 38143514376](https://github.com/kunal-gswm/GameLingo/actions/runs/38143514376) (All jobs passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,275,586 bytes, SHA-256 `2E0B40CFFFCD7774FE55BA2F5473AF21E202C762290F168B33A7CD841955957C`)
- **Quality Gate:** 130 passed, 0 skipped.
- **Known Limitation:** Official Ren'Py SDK is not installed in the Windows test environment; in-engine runtime rendering remains explicitly unverified. See [`docs/releases/GL_033_RenPy_Support_Report.md`](../releases/GL_033_RenPy_Support_Report.md) for full report.
