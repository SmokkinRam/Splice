"""Loads config.yaml (aliases and, later, every other setting)."""
from pathlib import Path

import yaml

_cache = {}


def load_config(path="config.yaml", reload=False):
    """Return the config as a dict. Missing or empty files give safe defaults."""
    if reload or path not in _cache:
        data = {}
        p = Path(path)
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        aliases = data.get("aliases") or {}
        app_aliases = data.get("app_aliases") or {}
        data["aliases"] = {str(k).lower(): str(v).lower() for k, v in aliases.items()}
        data["app_aliases"] = {str(k).lower(): str(v) for k, v in app_aliases.items()}
        _cache[path] = data
    return _cache[path]