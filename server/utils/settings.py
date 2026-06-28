from pathlib import Path
import json
import os
import uuid

def load_settings(defaults: dict[str, str], keys: list[str]) -> dict[str, str]:
    """Accepts a dict containing strings for named global variables. Will not accept user variables not found in the default config."""
    # Load user config if it exists
    config_file = Path(os.getenv("SETTINGS_JSON", "/app/config/settings.json"))
    if config_file.exists():
        with config_file.open() as f:
            user_config = json.load(f)
    else:
        user_config = {}

    # Generate random UUID if a required key is missing or empty
    for gen_key in keys:
        if not user_config.get(gen_key):
            user_config[gen_key] = str(uuid.uuid4())
            # Save updated config back to file
            config_file.parent.mkdir(parents=True, exist_ok=True)  # ensure directory exists
            with config_file.open("w") as f:
                json.dump(user_config, f, indent=2)
            print(f"Generated new {gen_key} and saved to {config_file}")

    # Only take keys from user_config that exist in defaults
    filtered_user_config = {k: v for k, v in user_config.items() if k in defaults}

    return {**defaults, **filtered_user_config}
