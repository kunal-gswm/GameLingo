@echo off
cd /d "%~dp0"

if exist "dist\GameLingo.exe" (
    echo Starting GameLingo from dist\GameLingo.exe...
    start "" "dist\GameLingo.exe"
    exit /b 0
)

echo Starting GameLingo from source...
uv run --extra gui gamelingo gui
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Launch failed.
    echo Please ensure dependencies are installed by running:
    echo     uv sync --extra gui
    echo.
    pause
)
