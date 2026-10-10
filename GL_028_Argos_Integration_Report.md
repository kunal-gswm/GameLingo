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
- **License**: CC0 (Public Domain) / MIT depending on the specific OPUS training set, effectively free for offline commercial and non-commercial use.
- The model ZIP (`.argosmodel`) contains a `metadata.json` declaring the package structure, the SentencePiece tokenizer model, and the OpenNMT CTranslate2 models. GameLingo stores this natively in the user's `~/.argos-translate` packages directory (the default) to preserve existing setups.

## Quality Assurance

### Automated Testing
- `tests/unit/test_argos_setup.py`: Validates model status detection, local zip file ingestion (rejecting invalid/corrupt zips), and mocked network downloads.
- `tests/integration/test_gui.py`: Mocked `ArgosSetupService` to ensure integration tests run cleanly without attempting to hit the Argos servers.

### End-to-End Acceptance
- The Windows package was built and tested against these flows:
  - Validating "Missing Model" state.
  - Rejecting corrupted local `.argosmodel` files.
  - Accepting a valid local `.argosmodel` file.
  - Executing a mock online download flow successfully.

## Conclusion
GL-028 completes the offline translation capability requirement, bridging the gap between local application usage and first-run model provisioning. No automatic silent downloads are triggered, preserving bandwidth and user consent.
