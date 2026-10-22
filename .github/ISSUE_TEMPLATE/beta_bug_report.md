---
name: "Beta Bug Report"
about: "Report a defect, crash, or unexpected behavior encountered during the GameLingo beta"
title: "[BUG]: "
labels: ["beta", "triage"]
assignees: []
---

<!-- 
IMPORTANT: DO NOT upload copyrighted commercial game files, proprietary scripts, 
dialogue dumps, or full game archives. Use synthetic examples (e.g. "Hero: Hello \C[1]World\C[0]").
-->

### 1. Environment & Build Details
- **Operating System:** Windows 10 (64-bit) / Windows 11 (64-bit) [specify build/version]
- **GameLingo Version:** v0.1.0-beta
- **Binary Provenance:** [ ] Downloaded `GameLingo-Windows-x64.zip` / [ ] Built from source
- **Checksum Verified:** [ ] Yes, SHA-256 matched `SHA256SUMS.txt` / [ ] Not verified

### 2. Game Engine Details
- **Engine Family:** 
  - [ ] RPG Maker MZ (Live-Runtime Verified tier)
  - [ ] Ren'Py 7.x / 8.x (Live-Runtime Verified tier)
  - [ ] RPG Maker MV (Format & AST Round-Trip tier)
  - [ ] RPG Maker VX Ace (Format & AST Round-Trip tier)
  - [ ] RPG Maker VX / XP / 2003 (Format & AST Round-Trip tier)
  - [ ] Other / Unknown
- **Game Engine Version (if known):** e.g. RPG Maker MZ 1.8.0, Ren'Py 8.2.1
- **Asset Status:** [ ] Unpacked / Decrypted / Loose files / [ ] Encrypted archive (pre-decrypted)

### 3. Issue Severity
Please select the severity level matching the defect:
- [ ] **Critical:** Original game data loss, writes outside target game root, unrecoverable corruption, or application startup crash. *(Triggers Stop-Ship evaluation)*
- [ ] **High:** Core workflow blocked (extraction, patch generation, or CSV export fails completely) or recoverable patch/restore failure.
- [ ] **Medium:** Feature malfunction with a viable workaround (e.g. display glitch, search filtering defect, non-blocking CSV parsing issue).
- [ ] **Low:** Cosmetic defect, minor UI alignment issue, or wording/typo.

### 4. Reproducibility
- [ ] Always (100% reproducible on every attempt)
- [ ] Intermittent (occurs sometimes under specific conditions)
- [ ] Occurred once (unable to reproduce consistently)

### 5. Steps to Reproduce
1. Open GameLingo workspace at `...`
2. Select game folder at `...` (dedicated test copy)
3. Click `...`
4. Observe error `...`

### 6. Expected Behavior
A concise description of what should have happened.

### 7. Actual Observed Behavior
A concise description of what actually happened (including any UI error banners, red indicators, or console output).

### 8. Sanitized Logs & Error Messages
```text
Paste console tracebacks, exception text, or error logs here.
Please ensure all personal username paths (e.g. C:\Users\<Username>\...) and proprietary game script content are sanitized before submitting.
```

### 9. Safety & Copyright Confirmation
- [ ] I confirm that I tested GameLingo against a **dedicated copy** of the game and not my original or Steam directory.
- [ ] I confirm that **no commercial game assets, copyrighted dialogue, or proprietary files** are attached to this report.
