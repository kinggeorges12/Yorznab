$script_name = Split-Path -Leaf $MyInvocation.MyCommand.Path
$script_dir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ((Get-Location).Path -ne $script_dir) {
    Write-Host "Directory of ${script_name}: ${script_dir}"
    Write-Host "Your current directory: $(Get-Location)"
    
    $reply = Read-Host "Are you in the correct directory? yes(Y)/[no(N)]/go(G)"
    
    if ($reply -match '^[Gg]$') {
        Set-Location "${script_dir}"
        Write-Host "Switching directory: $(Get-Location)"
    } elseif (-not ($reply -match '^[Yy]$')) {
        Write-Host "Cancelling..."
        exit 1
    }
    
    Write-Host "Continuing..."
}
if (-not (Test-Path ".venv" -PathType Container)) {
    ./build.ps1
}
$env:TZ='America/New_York' #'UTC'
$env:PYTHONPATH = "${pwd}"
$env:CONFIG_DIR="${pwd}\config"
$env:LOG_DIR="${pwd}\logs"
$env:LOG_LEVEL='DEBUG'
$env:FEEDS=''
try{
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    Push-Location server
    python -m uvicorn run:app --host 0.0.0.0 --port 9116
} finally {
    Pop-Location
    deactivate
}