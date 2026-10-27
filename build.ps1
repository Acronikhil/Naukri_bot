# Builds dist\NaukriProfileBot-Setup-<version>.exe
# Requires: Python 3.11+, Inno Setup 6 (https://jrsoftware.org/isinfo.php)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (Select-String -Path config.py -Pattern 'APP_VERSION = "(.+)"').Matches[0].Groups[1].Value
Write-Host "Building Naukri Profile Bot $version" -ForegroundColor Cyan

python -m pip install --quiet -r requirements.txt pyinstaller
if ($LASTEXITCODE) { throw "pip install failed" }

# 1. Bundle the app (one folder, no console window).
python -m PyInstaller --noconfirm --clean --windowed `
    --name NaukriProfileBot `
    --icon assets\icon.ico `
    --add-data "assets\icon.ico;assets" `
    --collect-data customtkinter `
    --collect-data babel `
    --hidden-import babel.numbers `
    --hidden-import keyring.backends.Windows `
    main.py
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# 2. Wrap it in an installer.
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup" }

& $iscc /Qp "/DMyAppVersion=$version" installer\NaukriProfileBot.iss
if ($LASTEXITCODE) { throw "Inno Setup failed" }

Write-Host "Done: dist\NaukriProfileBot-Setup-$version.exe" -ForegroundColor Green
