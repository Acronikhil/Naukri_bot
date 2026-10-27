@echo off
rem Builds the installer. Runs build.ps1 without needing to change the PowerShell execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)
pause
