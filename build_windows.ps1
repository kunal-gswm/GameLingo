$ErrorActionPreference = "Stop"

Write-Host "Syncing dependencies..."
uv sync --locked --extra gui --extra argos --group build
uv run pytest
uv run ruff check .
uv run ruff format --check .

Write-Host "Building with PyInstaller..."
# Remove old dist and build
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

uv run --python 3.12 pyinstaller GameLingo.spec --noconfirm

Write-Host "Build complete! Preparing distribution..."
Copy-Item README.md dist/GameLingo/
Copy-Item LICENSE dist/GameLingo/
Copy-Item THIRD_PARTY_NOTICES.txt dist/GameLingo/
Compress-Archive -Path "dist\GameLingo" -DestinationPath "dist\GameLingo-Windows-x64.zip" -Force

Write-Host "Generating Checksum..."
$hash = Get-FileHash "dist\GameLingo-Windows-x64.zip" -Algorithm SHA256
$hash.Hash | Out-File "dist\GameLingo-Windows-x64.zip.sha256" -Encoding UTF8

Write-Host "Done!"
