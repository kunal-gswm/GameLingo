GameLingo - First Run Instructions
===================================

Welcome to GameLingo!

1. Extract the `GameLingo-Windows-x64` folder to a writable location (e.g., your Desktop or Documents folder).
2. Double-click `GameLingo.exe` to launch the application.
3. The application operates fully offline and locally. It will ask you to select a workspace directory where it will save its configuration and databases.
4. To translate games, GameLingo supports downloading the free "Argos Translate" Japanese-to-English model (approx. 50MB). You can install it directly from the Translation page inside the GUI.
5. Do NOT place your workspaces or translation jobs inside this `GameLingo-Windows-x64` folder.

GameLingo is an unsigned application. You may encounter a Windows SmartScreen warning (e.g., "Windows protected your PC") on first launch.

Before running the application:
1. Ensure you downloaded this ZIP file exclusively from the official GameLingo GitHub releases page.
2. Verify that the SHA-256 checksum of your downloaded ZIP matches the checksum published on the release page. (Note: A matching checksum confirms the file was downloaded without corruption and matches the published archive, but it is not a guarantee of safety).

If you have verified the source and checksum, you can click "More info" and then "Run anyway" to proceed. Do not proceed if the download source or checksum cannot be verified.

## Tested Platforms
This package has been tested on Windows 10/11 x64 architecture.

## Missing Model Behavior
If you skip the model installation, GameLingo will still launch and let you extract/review/patch games using pre-existing translations, but automatic AI translation will be paused until the model is installed.

## Troubleshooting Startup Failures
- Application does not start: Check if your antivirus falsely quarantined `GameLingo.exe` or bundled `_internal` files.
- Black screen / instant crash: You can run `GameLingo.exe > crash_log.txt 2>&1` in PowerShell/Command Prompt to view the specific crash reason. Ensure your path does not exceed Windows' 260 character limit.
