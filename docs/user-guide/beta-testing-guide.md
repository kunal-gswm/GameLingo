# GameLingo Public Beta: User Testing & Verification Guide

Welcome to the **GameLingo Public Beta (v0.1.0)**! This guide explains how to install, verify, and safely test GameLingo against Japanese games built on RPG Maker or Ren'Py.

---

## 1. Download & Cryptographic Verification

All official portable Windows distribution binaries are hosted on the [GitHub Releases](https://github.com/kunal-gswm/GameLingo/releases) page.

### Published Artifacts
- `GameLingo-Windows-x64.zip` (Complete portable archive containing executable, license, and notices)
- `GameLingo.exe` (Single-file portable executable)
- `SHA256SUMS.txt` (UTF-8 cryptographic checksum manifest)

### Verification Instructions
Always verify the authenticity and integrity of your download before launching:

#### Using PowerShell:
```powershell
# Compute SHA-256 hash of the downloaded zip
(Get-FileHash GameLingo-Windows-x64.zip -Algorithm SHA256).Hash

# Compare with published checksum manifest
Get-Content SHA256SUMS.txt
```

#### Using Linux/WSL or Git Bash:
```bash
sha256sum -c SHA256SUMS.txt
```

Verify that the output reports `GameLingo-Windows-x64.zip: OK`.

---

## 2. Installation & Launch

### System Requirements
- **Operating System:** Windows 10 (64-bit) or Windows 11 (64-bit).
- **Architecture:** x86_64.
- **Runtime:** Microsoft Visual C++ 2015–2022 Redistributable (x64). This is pre-installed on most modern Windows systems. If you experience a missing `vcruntime140.dll` or `msvcp140.dll` error, download and install the official redistributable from Microsoft.
- **Dependencies:** GameLingo is completely self-contained. **No Python installation, uv, or Git is required.**

### Installation Steps
1. Extract `GameLingo-Windows-x64.zip` to a regular, writable folder (e.g. `C:\Tools\GameLingo\` or `C:\Users\<YourUser>\Documents\GameLingo\`).
   > [!CAUTION]
   > Do **not** extract to `C:\Program Files` or system directories that require administrator privileges. GameLingo writes its workspace databases and backup snapshots locally.
2. Double-click `GameLingo.exe`.

### Windows SmartScreen Note
Because GameLingo is an open-source project and the beta binaries are not signed with a paid commercial code-signing certificate, Windows SmartScreen may show an alert on first launch (*"Windows protected your PC"*).
1. Click **More info**.
2. Confirm the publisher says *Unknown publisher* and the file name matches `GameLingo.exe`.
3. Click **Run anyway**.

---

## 3. The Golden Rule: Safe Game Testing

> [!IMPORTANT]
> **ALWAYS TEST ON A COPY OF YOUR GAME!**  
> Never run GameLingo directly against your primary game archive, your only copy, or an active Steam / DLsite installation directory.

### Recommended Safety Protocol
1. Create a dedicated testing folder, for example `C:\GameTesting\MyGame_TestCopy\`.
2. Copy the entire game folder into this directory.
3. Point GameLingo to `C:\GameTesting\MyGame_TestCopy\`.
4. Keep the original game folder completely untouched.

---

## 4. First Project & Translation Walkthrough

### Step 1: Open or Create a Workspace
1. Launch GameLingo.
2. Select a workspace folder where GameLingo will save your translation memory database and pre-patch backups (e.g., `C:\GameTesting\Workspace\`).

### Step 2: Extract Strings
1. Click **Extract** in the navigation sidebar.
2. Drag and drop or browse to your game's root directory (e.g. the folder containing `Game.exe` or `package.json` for RPG Maker, or the folder containing `game/` for Ren'Py).
3. GameLingo will detect the engine family and display confidence diagnostics.
4. Click **Extract All Text**. Progress and extracted unit counts will display.

### Step 3: Translate & Review
1. Navigate to **Translate** to review translatable units.
2. Search and filter by status (`Draft`, `Needs Review`, `Approved`).
3. Click any dialogue unit to open the editor.
4. Note that GameLingo features **Real-Time Token Validation**: if an RPG Maker or Ren'Py escape sequence (e.g. `\V[1]`, `\C[2]`, `\N[1]`) is missing or malformed in your translation, the editor will display a blocking red warning and disable approval until corrected.
5. Save drafts with `Ctrl+S` and approve with `Ctrl+Return` (or `Ctrl+Enter`).

### Step 4: Patching & Rollback
1. Navigate to **Patch & Export**.
2. Click **Create Patch Plan**. GameLingo performs preflight checks and generates a detailed dry-run preview showing exactly which files will be modified.
3. Click **Apply Patch to Game**.
4. GameLingo automatically takes a cryptographic SHA-256 backup snapshot into `backups/<uuid>/` before modifying any game file.
5. Launch the game executable in your test copy folder to verify in-game dialogue display.

---

## 5. Restoration & Rollback Guidance

If you want to revert your game to its pre-patched state at any time:

### Reverting via GUI
1. Navigate to **Patch & Export** $\rightarrow$ **Backups & Restore**.
2. Select the backup snapshot corresponding to your patch run.
3. Review the preview of files to restore.
4. Click **Restore Selected Snapshot**. GameLingo verifies SHA-256 checksums and performs an atomic restoration.

### Reverting via Command Line (CLI)
You can also run restoration from PowerShell or Command Prompt:
```powershell
# Preview restore without modifying files
.\GameLingo.exe restore <backup-id-or-path> --target "C:\GameTesting\MyGame_TestCopy"

# Execute restoration with overwrite confirmation
.\GameLingo.exe restore <backup-id-or-path> --target "C:\GameTesting\MyGame_TestCopy" --execute --yes
```

---

## 6. How to Report a Bug (Protecting Game Copyright)

If you encounter a bug, formatting error, or unexpected crash during beta testing, please open an issue on the [GameLingo Issue Tracker](https://github.com/kunal-gswm/GameLingo/issues).

> [!CAUTION]
> **DO NOT upload commercial game data, copyrighted images, or proprietary scripts to GitHub issues.**

### What to Include in a Bug Report
1. **Engine and Version:** The detected engine family (e.g. RPG Maker MZ, RPG Maker MV, RPG Maker VX Ace, or Ren'Py 8.x).
2. **Reproduction Steps:** Exact steps to reproduce the issue (e.g. "Extracted text, edited unit with Japanese newline, clicked Save Draft").
3. **Synthetic / Sanitized Strings:** Provide an example using synthetic, non-copyrighted text (e.g. `"Hello \C[1]World\C[0]"`).
4. **Error Logs:** Copy the console output or exception message reported by the application.
5. **Sanitized CSV Export:** If reporting a data parsing issue, export a minimal 1–2 row CSV using GameLingo's export feature and verify it contains no private or proprietary material.
