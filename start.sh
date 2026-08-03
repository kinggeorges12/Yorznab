#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install yorznab
pip install -e .

# 3. Run the app
yorznab