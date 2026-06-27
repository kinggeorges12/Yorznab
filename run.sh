#!/bin/bash
if [ "$PWD" != "$(dirname "$0")" ]; then
    echo "Standard install: /srv/dev/yorznab/app"
    echo "Current directory: $PWD"
    read -p "Are you in the correct directory? yes(Y)/[no(N)]/go(G) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Gg]$ ]]; then
        cd /srv/dev/yorznab/app
        echo "Switching directory: $PWD"
    elif [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelling..."
        exit 1
    fi
    echo "Continuing..."
fi

if [ ! -d ".venv" ]; then
    ./build.sh
fi
if [ ! -f "config/settings.yaml" ]; then
    ./setup.sh
fi
export SEARCH_FILTER="filters.yaml"
export PYTHONPATH="${PWD}"
export CONFIG_DIR="${PWD}/config"
export LOG_DIR="${PWD}/logs"
(
    source .venv/bin/activate
    cd server || exit
    python -m uvicorn run:app --host 0.0.0.0 --port 8080 --log-level debug
)