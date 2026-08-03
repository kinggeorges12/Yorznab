@echo off
setlocal
cd /d "%~dp0"

where pwsh >nul 2>nul
if %errorlevel% equ 0 (
    echo pwsh found, running PowerShell script...
    pwsh -ExecutionPolicy Bypass -File "start.ps1"
    goto :eof
)

where powershell >nul 2>nul
if %errorlevel% equ 0 (
    echo powershell found, running PowerShell script...
    powershell -ExecutionPolicy Bypass -File "start.ps1"
    goto :eof
)

echo PowerShell not found, running in batch mode...

REM 1. Create virtual environment
python -m venv .venv
call .venv\Scripts\activate

REM 2. Install yorznab
pip install -e .

REM 3. Run the app
yorznab

endlocal