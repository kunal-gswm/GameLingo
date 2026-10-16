# Milestone Report: GL-RPGM-PILOT-2 — Interactive Runtime Acceptance Verification

## Executive Summary

| Attribute | Details |
|---|---|
| **Milestone** | `GL-RPGM-PILOT-2` |
| **Target Engine** | RPG Maker MV (v1.6.1 / NW.js runtime) |
| **Verified Title** | *Do Disciplinary Committee Members Dream of Succubi?* v1.04 |
| **Isolation Root** | `E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c` |
| **Read-Only Baseline** | `D:\New folder\[RYuugames] RY-4233960_V1.04\4233960 V1.04\Do Disciplinary Committee Members Dream of Succubi` |
| **Status** | **PASSED** (100% Gates Achieved) |
| **Date** | 2026-10-16 |
| **Test Suite Status** | 371 passed in 27.01s (`uv run pytest`) |
| **Lint & Format Status** | Clean (`ruff check .`, `ruff format --check .`) |

---

## 1. Problem Statement & Diagnosis of Earlier Blind Spots

The preceding milestone (`GL-RPGM-PILOT`) successfully verified schema extraction (66,405 units), 100/100 locator resolution, Argos machine translation on 25 units, patch planning, dry-run safety, and exact rollback. However, its native runtime launch produced a blank/black frame (`gl_rpgm_pilot_runtime_window.png`) because:

1. **Cold-Boot Splash Screen Fade-in**:
   In RPG Maker MV titles packaged with third-party splash plugins (specifically `splash.js` in this Kagura Games release), the engine sequentially displays three fullscreen logos (`DisclaimerLogo`, `KaguraLogo`, `DevLogo`). Each logo runs for 60 fade-in frames, 150 wait frames, and 40 fade-out frames (~250 frames / ~4.16 seconds per logo), totaling over 12.5 seconds of non-interactive splash screens. Capturing at 4–6 seconds post-boot caught the engine in the midst of the initial black fade-in of Logo 1.
2. **Screen Capture API Context**:
   The standard .NET `CopyFromScreen` API fails in background console sessions with `ERROR_INVALID_HANDLE` (Win32 Error 6). This was diagnosed and resolved by switching to Win32 GDI `PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT=2)` with `user32.SetForegroundWindow(hwnd)`.
3. **Missing Interactive Scene Navigation**:
   No input automation was present in the original pilot to skip splash screens, load gameplay state, and trigger rendering of translated dialogue, menus, and banners.

---

## 2. Interactive Navigation Architecture & Methodology

Using Win32 input automation (`user32.PostMessageW` with `WM_KEYDOWN` / `WM_KEYUP`), GameLingo automated four distinct gameplay stages to verify rendering across multiple UI layers:

```
[Cold Boot] 
    │
    ▼ (Skip 3 Logos: 3x VK_RETURN pulses)
[Scene 1: Load Game Screen]  <─── Captures: "Select Save File to Load [GameLingo]"
    │
    ▼ (Load Save File 1: VK_RETURN)
[Map 118: 2F Corridor]
    │
    ▼ (Open Main Menu: VK_ESCAPE)
[Scene 2: In-Game Main Menu] <─── Captures: "Iroha Himeno [TL]", Terms & Status
    │
    ▼ (Open Inventory: VK_RETURN)
[Scene 3: Items Sub-Menu]    <─── Captures: \I[2324]Items [TL], \I[2775]Weaponry,
    │                                       \I[2776]Protective Gear, \I[2777]Special Items
    ▼ (Exit Menus: 2x VK_ESCAPE)
[Corridor Navigation] (18 steps Right, 2 steps Down)
    │
    ▼ (Map Transfer Event 3 -> Map 123)
[Scene 4: Girls' Restroom]   <─── Captures Animated Banner: "2F Girls' Restroom [TL]"
```

---

## 3. Sample Translation & Human Review Table

A focused sample of 11 translation units was selected across `System.json`, `Actors.json`, `Map122.json`, and `Map123.json`. Each unit was processed through Argos Translate NMT, subjected to token-preservation analysis, and reviewed to ensure distinctive visual strings while strictly retaining engine tokens (`\I[2324]`, `\I[2775]`, `\I[2776]`, `\I[2777]`).

| File | Locator | Source Text | Argos Draft | Reviewed Target | Tokens | Val. Errs | Review Decision |
|---|---|---|---|---|---|---|---|
| `System.json` | `terms.messages.loadMessage` | `Load which file?` | `Load which file?` | `Select Save File to Load [GameLingo]` | None | 0 | **Approved** (Clear screen indicator) |
| `Actors.json` | `[1].name` | `Iroha Himeno` | `Iroha Himeno` | `Iroha Himeno [TL]` | None | 0 | **Approved** (Heroine name indicator) |
| `System.json` | `terms.commands[9]` | `Save` | `Save` | `Save Data [TL]` | None | 0 | **Approved** (Menu command) |
| `System.json` | `terms.commands[10]` | `End Game` | `End Game` | `Quit Game [TL]` | None | 0 | **Approved** (Menu command) |
| `System.json` | `terms.commands[11]` | `Options` | `Options` | `Settings [TL]` | None | 0 | **Approved** (Menu command) |
| `System.json` | `terms.commands[4]` | `\I[2324]Item` | `\I[2324]Item` | `\I[2324]Items [TL]` | `\I[2324]` | 0 | **Approved** (Icon preserved) |
| `System.json` | `terms.commands[12]` | `\I[2775]Weapons` | `\I[2775]Weapons` | `\I[2775]Weaponry` | `\I[2775]` | 0 | **Approved** (Icon preserved) |
| `System.json` | `terms.commands[13]` | `\I[2776]Armor` | `\I[2776]Armor` | `\I[2776]Protective Gear` | `\I[2776]` | 0 | **Approved** (Icon preserved) |
| `System.json` | `terms.commands[14]` | `\I[2777]Key Items` | `\I[2777]Key Items` | `\I[2777]Special Items` | `\I[2777]` | 0 | **Approved** (Icon preserved) |
| `Map122.json` | `displayName` | `2F Girls' Bathroom` | `2F Girls' Bathroom` | `2F Girls' Restroom [TL]` | None | 0 | **Approved** (Screen banner) |
| `Map123.json` | `displayName` | `2F Girls' Bathroom` | `2F Girls' Bathroom` | `2F Girls' Restroom [TL]` | None | 0 | **Approved** (Active map banner) |

---

## 4. Pipeline Execution & Safety Verification

### Step 1: Safety & Ownership Boundary
- Disposable directory: `E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c`
- Ownership marker verified: valid run ID `run_20261016_003918_6db4980c`, status `completed`.
- Original directory at `D:\...` remained strictly untouched and read-only.

### Step 2: Baseline Hashes
- `System.json`: `c046f2f054380d983d3dd1d04a8b0de9320f7f766b226aea37b7e0430ec9620d`
- `Actors.json`: `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5`
- `Map122.json`: `a634f261aaf26b621235b584376c43acb0ec2b853769f7e7cb29096aebeb11b7`
- `Map123.json`: `d6a43c33ba1f211f0c097dc7cb812296babdca7c9eb1a763022481b306915846`

### Step 3: Patch Planning & Dry-Run
- Plan ID: `b122cc82-20e9-499c-ae46-1365247dd2a2`
- Edits planned: 11
- Dry-run preview status: `preview`, errors: `[]`.
- Re-computed hashes after dry run: **0 filesystem mutations detected**.

### Step 4: Patch Execution & Integrity
- Applied with `execute=True, overwrite=True`.
- Backup created: `4bd45670-37f4-4a73-bb54-808837df6550`.
- All 4 JSON files reloaded with `json.loads` to confirm valid UTF-8 JSON syntax.
- All 11 locators re-resolved on disk to confirm 100% exact replacement matching reviewed values.

---

## 5. Visual Runtime Evidence

| Scene ID | Description | Captured Artifact | Verified On-Screen Strings | Visual Proof Status |
|---|---|---|---|---|
| **Scene 1** | Save File Selection Window | `gl_rpgm_pilot_2_load_screen.png` | `Select Save File to Load [GameLingo]` | **VERIFIED** (Window header) |
| **Scene 2** | In-Game Main Menu | `gl_rpgm_pilot_2_main_menu.png` | `Iroha Himeno [TL]` | **VERIFIED** (Character header) |
| **Scene 3** | Items / Inventory Sub-Menu | `gl_rpgm_pilot_2_items_menu.png` | `\I[2324]Items [TL]`, `\I[2775]Weaponry`, `\I[2776]Protective Gear`, `\I[2777]Special Items`, `Iroha Himeno [TL]` | **VERIFIED** (All 4 item categories with intact graphical icons) |
| **Scene 4** | Map Transition Screen Banner | `gl_rpgm_pilot_2_bathroom_banner.png` | `2F Girls' Restroom [TL]` | **VERIFIED** (Stylized animated banner across top left) |

All 4 high-resolution uncompressed PNG artifacts and structured evidence have been archived in:
- `evidence/gl_rpgm_pilot/`
- `C:\Users\amvbl\.gemini\antigravity\brain\7571864e-483c-4cf2-aba4-7a69942cfe31\gl_rpgm_evidence/`

---

## 6. Rollback & Byte-for-Byte Restoration Verification

Following native runtime capture, the game process was terminated, and `execute_restore` was invoked using backup `4bd45670-37f4-4a73-bb54-808837df6550`:

| File Path | Original SHA-256 | Restored SHA-256 | Match |
|---|---|---|---|
| `www/data/System.json` | `c046f2f054380d983d3dd1d04a8b0de9320f7f766b226aea37b7e0430ec9620d` | `c046f2f054380d983d3dd1d04a8b0de9320f7f766b226aea37b7e0430ec9620d` | **100.0% Byte-for-Byte Match** |
| `www/data/Actors.json` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | **100.0% Byte-for-Byte Match** |
| `www/data/Map122.json` | `a634f261aaf26b621235b584376c43acb0ec2b853769f7e7cb29096aebeb11b7` | `a634f261aaf26b621235b584376c43acb0ec2b853769f7e7cb29096aebeb11b7` | **100.0% Byte-for-Byte Match** |
| `www/data/Map123.json` | `d6a43c33ba1f211f0c097dc7cb812296babdca7c9eb1a763022481b306915846` | `d6a43c33ba1f211f0c097dc7cb812296babdca7c9eb1a763022481b306915846` | **100.0% Byte-for-Byte Match** |

Zero hash discrepancies or lingering mutations exist in the disposable installation.

---

## 7. Quality Gates & Regression Verification

- **Full Test Suite**: `uv run pytest` -> **371 passed in 27.01s** (0 errors, 0 failures, 0 regressions).
- **Linter Check**: `uv run ruff check .` -> **All checks passed!**
- **Formatter Check**: `uv run ruff format --check .` -> **110 files already formatted.**
- **Git Working Tree**: Preserved with 0 commits and 0 pushes.
