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
New-Item -ItemType Directory -Force -Path "dist\GameLingo"
Copy-Item "dist\GameLingo.exe" "dist\GameLingo\"
Copy-Item README.md "dist\GameLingo\"
Copy-Item LICENSE "dist\GameLingo\"
Copy-Item THIRD_PARTY_NOTICES.txt "dist\GameLingo\"
Start-Sleep -Seconds 2

Compress-Archive -Path "dist\GameLingo\*" -DestinationPath "dist\GameLingo-Windows-x64.zip" -Force
Copy-Item "dist\GameLingo-Windows-x64.zip" "dist\GameLingo-v0.1-windows-x64.zip" -Force

Write-Host "Generating Checksums..."
$hashZip = (Get-FileHash "dist\GameLingo-Windows-x64.zip" -Algorithm SHA256).Hash
$hashExe = (Get-FileHash "dist\GameLingo.exe" -Algorithm SHA256).Hash
$hashV01Zip = (Get-FileHash "dist\GameLingo-v0.1-windows-x64.zip" -Algorithm SHA256).Hash

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText("dist\GameLingo-Windows-x64.zip.sha256", "$hashZip  GameLingo-Windows-x64.zip`r`n", $utf8NoBom)

$checksumLines = "$hashExe  GameLingo.exe`r`n$hashZip  GameLingo-Windows-x64.zip`r`n$hashV01Zip  GameLingo-v0.1-windows-x64.zip"
[System.IO.File]::WriteAllText("dist\SHA256SUMS.txt", "$checksumLines`r`n", $utf8NoBom)

Write-Host "Done!"
