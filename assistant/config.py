"""Loads config.yaml (aliases, folders, profiles, and later every other setting)."""
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
        folders = data.get("folders") or {}
        profiles = data.get("chrome_profiles") or {}
        data["aliases"] = {str(k).lower(): str(v).lower() for k, v in aliases.items()}
        data["app_aliases"] = {str(k).lower(): str(v) for k, v in app_aliases.items()}
        data["folders"] = {str(k).lower(): str(v) for k, v in folders.items()}
        data["chrome_profiles"] = {str(k).lower(): str(v) for k, v in profiles.items()}
        data["app_search_folders"] = [str(f) for f in (data.get("app_search_folders") or [])]
        data["screenshot_folder"] = data.get("screenshot_folder") or None
        _cache[path] = data
    return _cache[path]