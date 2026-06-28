clear
$env:SEARCH_FILTER = "filters.yaml"
$env:PYTHONPATH = "${pwd}"
$env:CONFIG_DIR="${pwd}\config"
$env:LOG_DIR="${pwd}\server\logs"
Push-Location server
try{
    python -m uvicorn run:app --host 0.0.0.0 --port 8080 --log-level debug
} finally {
    Pop-Location
}