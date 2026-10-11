# GL-036 Milestone Report: Read Archived Ren'Py Game Scripts

**Date:** October 11, 2026  
**Status:** Completed  
**Repository:** https://github.com/kunal-gswm/GameLingo  
**Branch:** `main`  
**Target Game:** `D:\New folder\island-1.0-win` (Ren'Py 8.x packaged game with `game/archive.rpa`)

---

## 1. Executive Summary

Milestone **GL-036** extends GameLingo with an enterprise-grade, read-only extraction and translation pipeline for packaged Ren'Py visual novels. Prior to this milestone, GameLingo recognized Ren'Py game directories but blocked extraction when games were packaged as `.rpa` archives containing compiled `.rpyc` scripts without loose `.rpy` source files.

With GL-036, GameLingo can safely inspect `.rpa` archives (RPA-3.0, RPA-2.0, RPA-1.0), extract script members into an isolated workspace cache, decompile `.rpyc` bytecode into readable Ren'Py script AST using pure-Python AST decompilation, extract all translatable dialogue/narration/menus, and generate native non-destructive Ren'Py translation patches (`game/tl/<language>/strings.rpy`) without ever modifying the original game archives or source files.

The implementation was validated both against a comprehensive synthetic test suite (134 tests passing) and live against the actual packaged commercial game `island-1.0-win`.

---

## 2. Actual-Game Verification (`island-1.0-win`)

Live extraction and patch planning were conducted on the local game installation `D:\New folder\island-1.0-win`:

| Metric | Measured Value | Verification Status |
| :--- | :--- | :--- |
| **Game Directory** | `D:\New folder\island-1.0-win` | Read-only target verified |
| **Archive File** | `game/archive.rpa` | RPA-3.0 format detected |
| **Archive File Size** | 948,453,940 bytes (~904.5 MB) | Exact byte match |
| **Archive Obfuscation Key** | `0x42424242` | Successfully decoded |
| **Total Archive Members** | 999 files (images, audio, scripts) | Fully indexed without decompression |
| **Compiled Scripts in Archive** | 14 `.rpyc` files | All 14 identified and extracted to cache |
| **Loose Source Scripts (.rpy)** | 0 files | Accurately reported |
| **Extracted Units** | **1,916 translation units** | Dialogue, narration, menus recovered |
| **Unique Source Strings** | **1,830 strings** | Fully deduplicated |
| **Extraction Time** | **0.39 seconds** | High-performance selective extraction |
| **Pre-Extraction Archive SHA-256** | `6faca6ff190c3577d1062a3e166da4e7616ae26d58d4360635912051aeeb1dca` | Baseline recorded |
| **Post-Extraction Archive SHA-256** | `6faca6ff190c3577d1062a3e166da4e7616ae26d58d4360635912051aeeb1dca` | **Byte-identical (100% read-only integrity)** |
| **Patch Generation** | `game/tl/english/strings.rpy` + `00_gamelingo_activate.rpy` | Validated non-destructive translation patch |

### Script Breakdown for `island-1.0-win`:
All 14 compiled `.rpyc` scripts were safely decompiled and parsed:
- `script.rpyc`
- `gallery.rpyc`
- `gui.rpyc`
- `images.rpyc`
- `island_battle.rpyc`
- `island_hub.rpyc`
- `island_images.rpyc`
- `island_minigames.rpyc`
- `island_stubs.rpyc`
- `options.rpyc`
- `screens.rpyc`
- `ui_screens.rpyc`
- `zz_album.rpyc`
- `zz_island_ui.rpyc`

---

## 3. Architecture & Security Implementation

### 3.1 Dedicated Read-Only RPA Reader (`src/gamelingo/adapters/renpy_rpa.py`)
- **Format Support:**
  - `RPA-3.0`: Header `RPA-3.0 {index_offset:016x} {key:08x}`. Zlib-compressed pickle index with 32-bit XOR key.
  - `RPA-2.0`: Header `RPA-2.0 {index_offset:016x} {key:08x}`. Zlib-compressed pickle index with 32-bit XOR key.
  - `RPA-1.0`: Zlib-compressed pickle index located at archive EOF without header prefix.
- **Strict Security Unpickler (`SafeRPAUnpickler`):**
  - Untrusted pickle deserialization is a critical security vulnerability if left unconstrained.
  - GameLingo implements `SafeRPAUnpickler` extending `pickle.Unpickler` with an overridden `find_class`.
  - Permitted types are restricted exclusively to safe data constructors: `builtins.bytes`, `builtins.str`, `builtins.int`, `builtins.float`, `builtins.bool`, `builtins.tuple`, `builtins.list`, `builtins.dict`, `builtins.set`, `builtins.frozenset`, `__builtin__.bytes`, `_codecs.encode`.
  - Any attempt to deserialize unauthorized classes, callables, or execution primitives (`os.system`, `subprocess`, `eval`, etc.) triggers an immediate `pickle.UnpicklingError`.
- **Path Traversal Defense:**
  - `validate_member_path(member_path)` enforces strict relative paths: rejects directory traversal components (`..`), absolute paths, Windows drive letters (`C:`), leading slashes, and null bytes (`\x00`).
- **Offset & Bounds Checking:**
  - Chunk offsets and lengths are validated against the actual file size of the archive, rejecting malformed, truncated, or out-of-bounds index records.
- **Selective Script-Only Extraction:**
  - Extraction filters archive members to `.rpy`, `.rpyc`, `.rpym`, and `.rpymc`, ignoring heavy media files (images, audio, videos, fonts) to minimize memory and I/O.
- **Workspace Cache Isolation:**
  - Extracted archive files and decompiled scripts are written strictly to GameLingo's local workspace cache (`cache/renpy_work/...`), never to the game folder.

### 3.2 Decompiler Integration (`src/gamelingo/adapters/renpy_decompiler.py`)
- **Selected Engine:** `rpycdec==0.2.0` (pure-Python, MIT license, author CensoredUsername / Ren'Py community).
- **Licensing & Bundling:**
  - MIT License verified and attributed in `THIRD_PARTY_NOTICES.txt`.
  - Pure Python implementation bundles cleanly with PyInstaller (`--hidden-import rpycdec`) without requiring native external binaries, C compiler runtimes, or launching the game executable.
- **AST Parsing:**
  - Safely handles Ren'Py 7 & 8 AST nodes (Say, Menu, UserStatement, Python, Init, TranslateString).
  - Emits clean, readable `.rpy` source scripts ready for the existing Ren'Py AST adapter.

### 3.3 Extraction Precedence & Adapter Integration (`src/gamelingo/adapters/renpy.py`)
When a game contains overlapping script representations, GameLingo applies a deterministic precedence hierarchy:
1. **Loose `.rpy`** (uncompressed developer source script in game folder)
2. **Loose `.rpyc`** (compiled script in game folder)
3. **Archived `.rpy`** (source script inside `.rpa` archive)
4. **Archived `.rpyc`** (compiled script inside `.rpa` archive)

This eliminates duplicate translation units and ensures the most authoritative source version is extracted.

### 3.4 Translation Patching (`src/gamelingo/patching/planner.py`)
- Native Ren'Py translation architecture is respected:
  - Game scripts and archives are **never modified or rewritten**.
  - Translations are written to `game/tl/<language>/strings.rpy` using standard `translate <language> strings:` blocks.
  - A lightweight bootstrap script `game/00_gamelingo_activate.rpy` configures `config.language = "<language>"`.
  - The patch planner was updated to permit source scripts that reside inside archives, while ensuring destination patch files reside safely inside the target game structure.

### 3.5 UI & Diagnostics Polish
- **Dashboard Supported Engines Card:** Accurately reflects RPA archive reading and `.rpyc` decompiler capabilities.
- **Structure Verification Pill:** Displays `Supported` when an archive with extractable scripts is detected, with a descriptive label: `"Verified Ren'Py project (archive with extractable scripts)"`.
- **Extraction Page:** Seamlessly enables extraction when extractable scripts exist in either loose or archive form.

---

## 4. Test Suite & Verification Results

### 4.1 Pytest Suite
Ran `uv run pytest`:
- **134 passed, 0 failed, 0 skipped** across 15 test suites.
- Dedicated unit test coverage:
  - `tests/test_renpy_rpa.py` (11 tests): RPA-1.0/2.0/3.0 parsing, key XOR decoding, path traversal rejection, safe unpickler security barriers, multi-archive discovery, corrupted archives.
  - `tests/test_renpy_decompiler.py` (7 tests): header validation, decompression, error handling, batch operations, timing.
  - `tests/test_renpy_archive_extraction.py` (4 tests): end-to-end extraction workflow with synthetic RPA archives containing compiled bytecode, precedence resolution, diagnostics accuracy.
  - Preserved all existing RPG Maker MV/MZ and Ren'Py loose script regression tests.

### 4.2 Linter & Formatter
- `uv run ruff check .` passed with 0 errors.
- `uv run ruff format --check .` passed with 75 files formatted.

---

## 5. Artifacts and Verification Summary

- **Source Files Added/Updated:**
  - `src/gamelingo/adapters/renpy_rpa.py` (Safe RPA reader & builder)
  - `src/gamelingo/adapters/renpy_decompiler.py` (RPYC decompiler bridge)
  - `src/gamelingo/adapters/renpy.py` (Archive-aware adapter & diagnostics)
  - `src/gamelingo/patching/planner.py` (Archive-compatible patch planning)
  - `src/gamelingo/gui/pages/dashboard.py` (Accurate status reporting)
  - `src/gamelingo/gui/pages/extraction_page.py` (Archive extraction handling)
  - `src/gamelingo/gui/main.py` (`--test-workflow` includes RPA verification)
  - `pyproject.toml` (`rpycdec>=0.2.0`)
  - `THIRD_PARTY_NOTICES.txt` (`rpycdec` attribution)
  - `README.md` (Updated engine compatibility table & features)
- **Packaged Executable & Distribution:**
  - PyInstaller portable Windows x64 build generated with `rpycdec` bundled.
  - Package Archive: `dist/GameLingo-Windows-x64.zip`
  - Package Size: 273,404,053 bytes (~260.7 MB)
  - Package SHA-256: `480D4663C76E33AA30AF025445DEFE08DFD6EE7288650FE4994A710BEAE1F8B2`
  - Standalone Verification: Passed (`--smoke-test` returncode 0, `--test-workflow` returncode 0).

