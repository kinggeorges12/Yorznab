python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\server\requirements.txt
python -m pip install pywinpty
deactivate