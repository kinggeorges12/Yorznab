if (-not (Test-Path ".venv" -PathType Container)) {
    ./build.ps1
}
if (-not (Test-Path "config/settings.yaml" -PathType Leaf)) {
    ./setup.ps1
}
$env:SEARCH_FILTER = "filters.yaml"
$env:PYTHONPATH = "${pwd}"
$env:CONFIG_DIR="${pwd}\config"
$env:LOG_DIR="${pwd}\logs"
Push-Location server
try{
    python -m uvicorn run:app --host 0.0.0.0 --port 8080 --log-level debug
} finally {
    Pop-Location
}