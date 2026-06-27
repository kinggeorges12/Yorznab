#!/bin/bash
clear
export SEARCH_FILTER="filters.yaml"
export PYTHONPATH="${PWD}"
export CONFIG_DIR="${PWD}/config"
export LOG_DIR="${PWD}/logs"
(
    source .venv/bin/activate
    cd server || exit
    python -m uvicorn run:app --host 0.0.0.0 --port 8080 --log-level debug
)