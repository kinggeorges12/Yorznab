#!/bin/bash

script_name=$(basename "${BASH_SOURCE[0]}")
script_dir=$(dirname "${BASH_SOURCE[0]}")
if [ "$PWD" != "$script_dir" ]; then
    echo "Directory of $script_name: $script_dir"
    echo "Your current directory: $PWD"
    read -p "Are you in the correct directory? yes(Y)/[no(N)]/go(G) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Gg]$ ]]; then
        cd $script_dir
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
    python -m uvicorn run:app --host 0.0.0.0 --port 9116
)