# GL-028: Argos Model Setup, First-Run UX and Offline Readiness

## Objective
Make GameLingo's Japanese-to-English translation provider usable by a Windows desktop user who has just installed the application and has never installed an Argos translation model. 

## Implementation Details

### 1. Argos Setup Service
- Created `gamelingo.translation.argos_setup.ArgosSetupService` to cleanly handle model discovery, status checking, and installation without breaking existing user installations or making implicit network calls.
- `check_status(source_lang, target_lang)` determines if the library is available, the language package is installed, and if a translation route exists—entirely offline and efficiently.

### 2. First-Run UX
- Updated `translation_page.py` to check model readiness upon rendering.
- Replaced the single mock installation button with two distinct explicit setup workflows:
  - **Download & Install**: Fetches the model from the official Argos index online.
  - **Install from Local File (.argosmodel)**: Allows fully offline users to select a previously downloaded package via a file dialog.
- Enforced checks in the CLI (`app.py`) to prevent translation or job resumption if the model is absent.

### 3. Predictable Offline Behavior
- Argos package lookup (`check_status`) relies on local indices and `get_installed_languages()`. Network calls (`update_package_index()` and `urlopen`) are constrained strictly to the explicit "Download & Install" codepath. 
- Graceful degradation: The application catches network errors, insufficient space errors, and invalid ZIP errors, reporting them intelligently via the UI.

### 4. Provenance and Licensing
- The default Japanese-to-English model (`ja -> en` v1.1) provided by the official Argos Open Tech index originates from OPUS data.
- **Provider**: Argos Open Tech
- **License**: The software operates under the MIT License. Models trained by Argos Open Tech on OPUS data are CC0 (Public Domain), effectively free for offline commercial and non-commercial use. GameLingo does not bundle or redistribute model weights; it simply orchestrates standard API calls to pull them from the public index at the user's explicit request.
- The model ZIP (`.argosmodel`) contains a `metadata.json` declaring the package structure, the SentencePiece tokenizer model, and the OpenNMT CTranslate2 models. GameLingo stores this natively in the user's `~/.argos-translate` (or local AppData) packages directory (the default) to preserve existing setups.

## Quality Assurance

### Automated Testing
- `tests/unit/test_argos_setup.py`: Validates model status detection, local zip file ingestion (rejecting invalid/corrupt zips), and mocked network downloads.
- `tests/integration/test_gui.py`: Mocked `ArgosSetupService` to ensure integration tests run cleanly without attempting to hit the Argos servers. Test suite (85 tests) passes successfully with robust worker synchronization to prevent GUI race conditions.

### Real Model Verification
- Verified real model capabilities using `ArgosSetupService`.
- **Package Identity**: `translate-ja_en` (version 1.1)
- **Downloaded Checksum (SHA-256)**: `623e3477959a815eb0a5ef53e09079ae8f1f9d3bbcd230473baf28c03fb83335`
- **Installed Location**: `C:\Users\amvbl\.local\share\argos-translate\packages\ja_en`
- **Translation Validation**: Translated `こんにちは` successfully to `Hello!`.
- GameLingo successfully detects this installed language pair on startup without performing network checks.

### End-to-End Acceptance (Windows Packaged Build)
- Built `GameLingo.exe` using `pyinstaller` (via `build_windows.ps1`).
- Executed `--smoke-test` and `--test-workflow` successfully against the packaged executable.
- Packaged Zip Checksum (SHA-256): `57175BFD554F6C46FE246ED52172679CB267B7B57ABDAB5283FAB6AF55876470`
- Provenance Source Commit: `09c679e`

## Conclusion
GL-028 completes the offline translation capability requirement, bridging the gap between local application usage and first-run model provisioning. No automatic silent downloads are triggered, preserving bandwidth and user consent. GameLingo remains 100% offline-ready for users bringing their own `.argosmodel` packages.
