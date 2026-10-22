# GameLingo Public Beta: User Testing & Verification Guide

Welcome to the **GameLingo Controlled Beta (v0.1.0)**! This guide explains how to download, verify, configure, and safely test GameLingo against Japanese games built on RPG Maker or Ren'Py.

---

## 1. Engine Support & Verification Levels

To set accurate expectations, GameLingo maintains an evidence-based distinction between engine verification tiers:

| Engine Family | Source Format | Patch Output | Verification Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **RPG Maker MZ** | `data/*.json` | Serialized JSON | **Live Runtime Verified** | Tested end-to-end against live engine runtime with verified dialogue rendering and screenshots. |
| **Ren'Py (7.x / 8.x)** | `game/**/*.rpy`, `.rpa`, `.rpyc` | `game/tl/<lang>/strings.rpy` | **Live Runtime Verified** | Tested against live Ren'Py engine processes with native string translation and fallback hooks. |
| **RPG Maker MV** | `data/*.json`, `www/data/*.json` | Serialized JSON | **Format & AST Verified** | Tested via syntax-tree parsing, serialization fidelity, and round-trip checksums. Not runtime pilot tested. |
| **RPG Maker VX Ace** | `Data/*.rvdata2` | Ruby Marshal 4.8 | **Format & AST Verified** | Pure-Python Ruby Marshal parsing and IVAR round-trip verified. Not runtime pilot tested. |
| **RPG Maker VX** | `Data/*.rvdata` | Ruby Marshal 4.8 | **Format & AST Verified** | Ruby Marshal parsing with CP932 encoding round-trip verified. Not runtime pilot tested. |
| **RPG Maker XP** | `Data/*.rxdata` | Ruby Marshal 4.8 | **Format & AST Verified** | RGSS1 Ruby Marshal parsing and round-trip verified. Not runtime pilot tested. |
| **RPG Maker 2003** | `*.ldb`, `*.lmt`, `*.lmu` | LCF Binary | **Format & AST Verified** | LCF binary format parsing and round-trip verified. Not runtime pilot tested. |

> [!NOTE]
> Encrypted archives (`.rpgmvp`, `.rpgmvm`, `RGSS3A`, `RGSS2A`, `RGSSAD`) must be extracted/decrypted using third-party tools prior to translation. GameLingo does not bypass encryption or DRM.

---

## 2. Download & Cryptographic Verification

All official portable Windows distribution binaries are hosted on GitHub.

### Official Distribution Files
- `GameLingo-Windows-x64.zip` — Complete portable distribution archive containing `GameLingo.exe`, `LICENSE`, `README.md`, and `THIRD_PARTY_NOTICES.txt`.
- `GameLingo.exe` — Standalone portable Windows x64 executable.
- `SHA256SUMS.txt` — Cryptographic checksum manifest (UTF-8, No BOM).

### Verification Instructions

Always verify the authenticity and integrity of your download before launching:

#### Using Windows PowerShell:
```powershell
# Compute SHA-256 hash of the downloaded zip
(Get-FileHash GameLingo-Windows-x64.zip -Algorithm SHA256).Hash

# Compute SHA-256 hash of the standalone executable
(Get-FileHash GameLingo.exe -Algorithm SHA256).Hash

# Compare with published checksum manifest
Get-Content SHA256SUMS.txt
```

#### Using Linux/WSL or Git Bash:
```bash
sha256sum -c SHA256SUMS.txt
```
Verify that the output reports `GameLingo-Windows-x64.zip: OK`.

---

## 3. Installation & System Requirements

### System Requirements
- **Operating System:** Windows 10 (64-bit) or Windows 11 (64-bit).
- **Architecture:** x86_64.
- **Runtime:** Microsoft Visual C++ 2015–2022 Redistributable (x64). Pre-installed on most modern Windows systems. If you encounter a missing `vcruntime140.dll` error, install the official Microsoft redistributable.
- **Dependencies:** Self-contained executable. **No Python, uv, or Git installation required.**

### Installation Steps
1. Extract `GameLingo-Windows-x64.zip` to a regular, writable folder (e.g. `C:\Tools\GameLingo\` or `C:\Users\<User>\Documents\GameLingo\`).
   > [!CAUTION]
   > Do **not** extract to `C:\Program Files` or system directories that require administrator privileges. GameLingo writes its workspace databases and backup snapshots locally.
2. Double-click `GameLingo.exe`.

### Windows SmartScreen Notice
Because GameLingo is an open-source project and beta binaries are not signed with an expensive commercial code-signing certificate, Windows SmartScreen may show an alert on first launch (*"Windows protected your PC"*):
1. Click **More info**.
2. Confirm the publisher says *Unknown publisher* and the file name is `GameLingo.exe`.
3. Click **Run anyway**.

---

## 4. Offline Translation & Model Availability Notice

GameLingo supports local, offline translation powered by Argos Translate / CTranslate2.

> [!IMPORTANT]
> **Configuring an offline translation provider does NOT mean its language model is pre-installed.**  
> Pre-trained translation models (such as Japanese-to-English `ja_en`) are large binary packages (100MB–500MB) that are **not** bundled into the initial lightweight executable.  
> - On first use, navigate to **Settings** $\rightarrow$ **Translation Models** and download the `ja_en` package while connected to the internet.  
> - Once downloaded, all subsequent translation jobs run completely offline without internet access.  
> - If you prefer not to download local neural models, you can export text to CSV, translate externally (or with spreadsheet tools), and import the translated CSV back into GameLingo.

---

## 5. Safe Game Testing Protocol (The Golden Rule)

> [!CAUTION]
> **ALWAYS TEST ON A DEDICATED COPY OF YOUR GAME!**  
> Never point GameLingo directly at your primary game archive, your only copy, or an active Steam / DLsite installation directory.

### Recommended Sandbox Setup
1. Create a dedicated testing folder, for example `C:\GameTesting\MyGame_TestCopy\`.
2. Copy the entire game folder into this directory.
3. Confirm the test copy launches and plays in original Japanese.
4. Point GameLingo to `C:\GameTesting\MyGame_TestCopy\`.
5. Keep the original game folder completely untouched as your permanent baseline.

---

## 6. End-to-End Walkthrough

### Step 1: Initialize Workspace
1. Launch GameLingo.
2. Select a workspace folder (e.g. `C:\GameTesting\Workspace\`). GameLingo initializes `gamelingo.db` and backup storage automatically.

### Step 2: Detect & Extract Strings
1. Click **Extract** in the sidebar.
2. Select your game root folder (e.g. `C:\GameTesting\MyGame_TestCopy\`).
3. GameLingo analyzes file signatures and displays engine diagnostics.
4. Click **Extract All Text**. Progress bars and unit counts will update in real time.

### Step 3: Translate & Review
1. Navigate to **Translate** to view extracted units.
2. Use **Review** to inspect dialogue, search, and edit translations.
3. **Placeholder & Token Guard:** GameLingo validates escape sequences (`\V[1]`, `\C[2]`, `\N[1]`, `{b}`, `{/b}`). If an escape token is damaged or missing, a blocking warning appears and approval is disabled.
4. Save drafts (`Ctrl+S`) and approve reviewed translations (`Ctrl+Enter`).

### Step 4: Export & Import for External Review
1. Go to **Patch & Export** $\rightarrow$ **Spreadsheet Interchange**.
2. Click **Export CSV** to generate a UTF-8-BOM spreadsheet compatible with Microsoft Excel.
3. Edit translations in Excel or share with reviewers.
4. Click **Import CSV (Preview)**. GameLingo validates that immutable locators, source texts, and hashes have not been tampered with.
5. Click **Apply Import** to update translation memory.

### Step 5: Patch the Game Copy
1. Navigate to **Patch & Export**.
2. Click **Create Patch Plan**. GameLingo runs preflight checks and displays a preview of exactly which files will be modified.
3. Click **Apply Patch to Game**.
4. GameLingo automatically creates a cryptographic SHA-256 backup snapshot in `backups/<uuid>/` before modifying any game file.
5. Launch the game executable in your test folder to verify in-game dialogue.

---

## 7. Restoration & Rollback Guidance

If you want to revert your game to its pre-patched state:

### Reverting via GUI
1. Navigate to **Patch & Export** $\rightarrow$ **Backups & Restore**.
2. Select the backup snapshot corresponding to your patch run.
3. Review the preview of files to restore.
4. Click **Restore Selected Snapshot**. GameLingo verifies SHA-256 checksums and performs atomic restoration.

### Reverting via Command Line (CLI)
```powershell
# Preview restore without modifying files
.\GameLingo.exe restore <backup-id-or-path> --target "C:\GameTesting\MyGame_TestCopy"

# Execute restoration with overwrite confirmation
.\GameLingo.exe restore <backup-id-or-path> --target "C:\GameTesting\MyGame_TestCopy" --execute --yes
```

---

## 8. Reporting Bugs Safely (Protecting Game Copyright)

If you encounter an issue during testing, please submit a bug report on the [GameLingo Issue Tracker](https://github.com/kunal-gswm/GameLingo/issues).

> [!CAUTION]
> **DO NOT upload commercial game data, copyrighted images, proprietary scripts, or game archives to GitHub issues.**

### Required Information for Bug Reports
1. **Operating System:** Windows version (e.g. Windows 11 x64 23H2).
2. **Engine Family & Version:** The detected engine (e.g. RPG Maker MZ 1.8.0, Ren'Py 8.1.3).
3. **Reproduction Steps:** Step-by-step description of what you did.
4. **Sanitized Dialogue Snippet:** Use generic synthetic text (e.g. `"Hero: Hello \C[1]World\C[0]"`).
5. **Console Output / Logs:** Copy exception text or console errors.

---

## 9. External Beta Pilot Protocol & Feedback Template

> [!IMPORTANT]
> **Current Pilot Status:** **`NOT YET RUN`**  
> External human pilot validation has not yet been executed. Automated tests and synthetic test suites do not substitute for external tester feedback.

### Beta Tester Checklist
- [ ] Windows 10/11 x64 environment confirmed.
- [ ] VC++ 2015–2022 redistributable present.
- [ ] ZIP archive SHA-256 verified against `SHA256SUMS.txt`.
- [ ] Standalone test copy of game created (original untouched).
- [ ] Engine detection matched actual game engine.
- [ ] Text extraction completed without error.
- [ ] Protected tokens (`\V[...]`, `\C[...]`, etc.) preserved properly.
- [ ] CSV export and re-import verified.
- [ ] Patch plan created and applied successfully.
- [ ] In-game dialogue verified in the game test copy.
- [ ] Restoration from backup snapshot tested and verified.

### Tester Feedback Template
Copy and fill out this markdown template when submitting feedback:

```markdown
### GameLingo Beta Pilot Feedback Report

- **Tester OS:** Windows 10 / Windows 11 (build: _____)
- **Engine Family:** RPG Maker MZ / MV / VX Ace / VX / XP / 2003 / Ren'Py
- **Game Name (or genre):** ___________________________
- **Game Engine Version:** ____________________________
- **GameLingo Version:** v0.1.0 (Commit: _____________)

#### 1. Setup & Launch
- [ ] Executable launched without SmartScreen blocker
- [ ] Executable launched with SmartScreen override
- [ ] Startup error encountered (details below)

#### 2. Engine Detection & Extraction
- Detected Engine: ____________________
- Expected Engine: ____________________
- Number of extracted units: ___________
- Any missing text or failed files? [ ] Yes  [ ] No
- Notes: 

#### 3. Translation & Token Protection
- Translation method used: [ ] Manual  [ ] CSV Interchange  [ ] Local Argos NMT
- Did token validation catch broken tags? [ ] Yes  [ ] No  [ ] N/A
- Notes:

#### 4. Patch Application & In-Game Verification
- Patch applied cleanly: [ ] Yes  [ ] Partial  [ ] Failed
- Did the game launch with patched text? [ ] Yes  [ ] No  [ ] Crashed
- Dialogue rendering appearance: [ ] Good  [ ] Truncated  [ ] Glitched
- Notes:

#### 5. Backup & Restoration
- Did backup snapshot save before patch? [ ] Yes  [ ] No
- Did restore revert game copy to original? [ ] Yes  [ ] No
- Notes:

#### 6. Summary & Usability
- Overall stability rating (1-5): ___
- Usability rating (1-5): ___
- Key suggestions or issues:
```
