# RPG Maker Compatibility Matrix

This document defines the localization, extraction, translation, and patch application capabilities of GameLingo across all six RPG Maker engine families.

---

## 1. Engine Families Overview

| Engine Family | Era / Release | Serialization Format | Primary File Extensions | Default Character Encoding | Support Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RPG Maker MZ** | 2020–Present | JSON AST | `data/*.json` | UTF-8 / UTF-8 with BOM | **Full Support** |
| **RPG Maker MV** | 2015–Present | JSON AST | `data/*.json`, `www/data/*.json` | UTF-8 / UTF-8 with BOM | **Full Support** |
| **RPG Maker VX Ace** | 2011–Present | RGSS3 Ruby Marshal 4.8 | `Data/*.rvdata2` | UTF-8 / CP932 / Windows-31J | **Full Support** |
| **RPG Maker VX** | 2007–2011 | RGSS2 Ruby Marshal 4.8 | `Data/*.rvdata` | CP932 / UTF-8 | **Full Support** |
| **RPG Maker XP** | 2004–2007 | RGSS1 Ruby Marshal 4.8 | `Data/*.rxdata` | CP932 / Windows-31J / UTF-8 | **Full Support** |
| **RPG Maker 2003** | 2003–Present | LCF Binary Structs / Arrays | `RPG_RT.ldb`, `RPG_RT.lmt`, `Map*.lmu` | Shift_JIS (CP932) / Windows-1252 | **Full Support** |

---

## 2. Text Extraction Coverage

GameLingo extracts translatable text while preserving structural game data, scripts, and non-text event commands across all engines:

| Content Category | MZ / MV (JSON) | VX Ace (`.rvdata2`) | VX (`.rvdata`) | XP (`.rxdata`) | 2003 (LCF) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dialogue & Messages** | Codes 101, 401, 405 (speaker names + multiline text) | Codes 101, 401 | Codes 101, 401 | Codes 101, 401 | Codes 10110, 20110 |
| **Choices & Branches** | Code 102 (choice arrays), Code 402 (`when` labels) | Code 102, Code 402 | Code 102, Code 402 | Code 102, Code 402 | Code 10140 (Choices) |
| **Actor Profiles & Names** | `name`, `nickname`, `profile` in `Actors.json` | `@name`, `@nickname`, `@profile` in `Actors.rvdata2` | `@name`, `@nickname`, `@profile` in `Actors.rvdata` | `@name` in `Actors.rxdata` | `name`, `title` in `RPG_RT.ldb` [11] |
| **Database Entries** | `name`, `description` (Skills, Items, Weapons, Armors, Enemies, States) | `@name`, `@description` (Skills, Items, Weapons, Armors, Enemies, States) | `@name`, `@description` (Skills, Items, Weapons, Armors, Enemies, States) | `@name`, `@description` (Skills, Items, Weapons, Armors, Enemies, States) | `name`, `description` (Skills, Items, Enemies, States) |
| **System Terms & Title** | `gameTitle`, `currencyUnit`, `terms.basic`, `terms.commands`, `terms.messages` | `game_title`, `currency_unit`, `terms` | `game_title`, `currency_unit`, `terms` | `game_title`, `words` (gold, hp, sp, stats) | `system.game_title` in `RPG_RT.ldb` [22] |
| **Map Tree & Names** | `MapInfos.json` (`name`) | `MapInfos.rvdata2` (`@name`) | `MapInfos.rvdata` (`@name`) | `MapInfos.rxdata` (`@name`) | `maps[id].name` in `RPG_RT.lmt` |
| **Map Events & Common Events** | `Map###.json`, `CommonEvents.json` | `Map###.rvdata2`, `CommonEvents.rvdata2` | `Map###.rvdata`, `CommonEvents.rvdata` | `Map###.rxdata`, `CommonEvents.rxdata` | `Map####.lmu`, `RPG_RT.ldb` [21] |

---

## 3. Encoding Handling and Preservation

GameLingo enforces strict encoding preservation on writeback to ensure that patched games do not crash or display corrupted characters (mojibake):

- **RPG Maker MZ / MV**: UTF-8 encoded. GameLingo detects Byte Order Marks (`\xef\xbb\xbf`) on load and preserves BOM or non-BOM formatting identically upon saving.
- **RPG Maker VX Ace**: Ruby 1.9+ Marshal objects with `:E` (encoding) instance variable indicators. UTF-8 strings are serialized with `:E => True`, and raw bytes are written back cleanly.
- **RPG Maker VX / XP**: Ruby 1.8 Marshal objects. Japanese games use Shift_JIS / CP932 raw bytes or UTF-8. The `RubyString` wrapper stores both `raw_bytes` and `encoding`, guaranteeing exact round-trip byte preservation.
- **RPG Maker 2003**: LCF format. Text strings are stored as BER variable-length quantity prefixed byte sequences. Japanese games use CP932 (Shift_JIS). Detection inspects byte distributions and falls back to CP932 or Latin-1, maintaining character set integrity when patched.

---

## 4. Control Code and Token Protection

RPG Maker text contains inline control codes that alter fonts, play sounds, reference variables, and display icons:

- **Tokens Detected**: `\V[n]`, `\N[n]`, `\P[n]`, `\C[n]`, `\I[n]`, `\G`, `\$`, `\{`, `\}`, `\!`, `\>`, `\<`, `\|`, `\.`, `\^`, `\FS[n]`, `\PX[n]`, `\PY[n]`, `\OC[n]`, `\OW[n]`.
- **Validation**:
  - `MISSING_PLACEHOLDER`: Triggers an error if a token present in the source is omitted from the translation.
  - `DUPLICATED_PLACEHOLDER`: Triggers an error if a token is repeated unintentionally.
  - `UNEXPECTED_PLACEHOLDER`: Triggers an error if unknown escape sequences are introduced.
  - Bracket tolerance: Square brackets in RPG Maker are treated as natural text and are not erroneously flagged as Ren'Py string interpolation tags.

---

## 5. Patch Application & Safety Architecture

All patch applications follow a multi-stage safety protocol:

```
[Preflight Validation]
         ↓
[Deterministic Backup] ──→ Byte-for-byte SHA256 recorded in manifest.json
         ↓
[Staged AST Modification] ──→ Writes to temporary file (`gamelingo_*.tmp`)
         ↓
[Staged Re-Parse Verification] ──→ Re-reads temporary file from disk & validates locators
         ↓
[Atomic Replacement] ──→ `os.replace` replaces target file
         ↓
[Post-Write Verification] ──→ Verifies target file integrity on disk
         ↓ (On Any Error)
[Automated Rollback] ──→ Restores original files from backup manifest
```

---

## 6. Known Boundaries and Limitations

1. **Encrypted Archives**:
   - `Game.rgss3a` (VX Ace), `Game.rgss2a` (VX), and `Game.rgssad` (XP) archives cannot be patched directly.
   - When only encrypted archives are found, GameLingo flags the project with `Encrypted Archive Detected` and instructs the user to extract the `.rvdata2`, `.rvdata`, or `.rxdata` data files before extraction.
2. **Third-Party Binary Plugins / DLLs**:
   - Proprietary native DLLs (`RGSS*.dll`) and external executables (`Game.exe`, `RPG_RT.exe`) are not modified.
3. **Save Game Files**:
   - Save files (`*.rpgsave`, `Save*.rxdata`, `Save*.rvdata2`, `Save*.lsd`) represent dynamic player progress and are outside translation scope.
4. **Graphical Assets & Media**:
   - Baked-in image text (`img/`, `Graphics/`), audio (`audio/`), and video files are excluded from text extraction.
