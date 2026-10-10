# GameLingo

GameLingo is a local-first desktop translation-patch workbench for people who want to translate a game's stored text into a playable, editable translation. 

**Note: This is a clean-slate rebuild.** No previous GameLingo code is used. The eventual public product name is not cleared legally and may change.

## Vision and Scope
- **Local-First:** The application will run entirely locally.
- **Zero-Cost:** No paid API, hosted backend, cloud database, subscription, or account is required.
- **Initial Target:** The first supported engine profile targets RPG Maker MV/MZ.
- **MVP Workflow:** Japanese-to-English local translation, persistent progress, human review, and safe patching.
- **Out of Scope:** Save editing, OCR/live overlays, cloud sync, universal engine support, and plugin marketplaces are explicitly outside the initial scope.

## Development Setup

We use Python 3.12+ and `uv` for environment management.

1. **Install dependencies:**
   ```bash
   uv pip install -e .
   uv pip install pytest ruff
   ```

2. **Run the entry point:**
   ```bash
   python -m gamelingo.app
   ```
   Or use the installed script:
   ```bash
   gamelingo
   ```

3. **Run tests:**
   ```bash
   pytest
   ```

4. **Lint and Format:**
   ```bash
   ruff check .
   ruff format .
   ```

## License
First-party code in this project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
