import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "data_config.json"


def load_config():
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH) as f:
        return json.load(f)


def get_path(key):
    """Return a configured path string, or '' if the key is missing."""
    return load_config().get(key, "")
