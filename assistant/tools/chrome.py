"""Open Chrome in a specific profile (yours, your mother's, ...).

Run  python -m assistant.tools.chrome  to list the Chrome profiles on this PC.
"""
import json
import os
import subprocess
from pathlib import Path

# Different ways of saying the same person, so "mom's", "mother" and "mum" all match.
OWNER_WORDS = {
    "mother": "mom", "mothers": "mom", "moms": "mom", "mum": "mom", "mums": "mom",
    "mummy": "mom", "mommy": "mom", "mama": "mom", "mamas": "mom",
    "me": "my", "mine": "my", "myself": "my", "own": "my", "personal": "my",
}


def canon(word):
    """The standard form of an owner word ('moms' -> 'mom', 'me' -> 'my')."""
    word = word.lower().strip()
    return OWNER_WORDS.get(word, word)


def user_data_dir():
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Google" / "Chrome" / "User Data" if base else None


def list_profiles():
    """Chrome's profiles: [{'dir': 'Profile 1', 'name': ..., 'email': ..., 'gaia_name': ...}]."""
    root = user_data_dir()
    state = root / "Local State" if root else None
    if not state or not state.exists():
        return []
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    cache = (data.get("profile") or {}).get("info_cache") or {}
    return [{"dir": folder,
             "name": info.get("name", ""),
             "email": info.get("user_name", ""),
             "gaia_name": info.get("gaia_name", "")}
            for folder, info in cache.items()]


def resolve_profile(target, profiles=None):
    """Find a profile by folder name, display name, email or Google name."""
    profiles = list_profiles() if profiles is None else profiles
    wanted = target.strip().lower()
    if not wanted:
        return None
    for p in profiles:                                     # exact matches first
        if wanted in (p["dir"].lower(), p["name"].lower(),
                      p["email"].lower(), p["gaia_name"].lower()):
            return p
    for p in profiles:                                     # then partial matches
        if any(wanted in value.lower() for value in (p["name"], p["gaia_name"], p["email"]) if value):
            return p
    return None


def find_chrome():
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            path = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if path.exists():
                return str(path)
    return None


def open_profile(owner, profile_map, url=None):
    """Open Chrome in the profile configured for this owner (optionally at a web address)."""
    wanted = canon(owner)
    target = next((value for key, value in (profile_map or {}).items()
                   if canon(key) == wanted), None)
    if target is None:
        return False, (f"I don't have a Chrome profile for {owner}. "
                       "Add it under chrome_profiles in config.yaml.")
    profile = resolve_profile(target)
    if profile is None:
        return False, (f"I couldn't find a Chrome profile matching '{target}'. "
                       "Run: python -m assistant.tools.chrome")
    chrome = find_chrome()
    if chrome is None:
        return False, "I couldn't find Chrome on this PC."
    command = [chrome, f"--profile-directory={profile['dir']}"]
    if url:
        command.append(url)
    subprocess.Popen(command)
    return True, f"Opening Chrome with the {profile['name'] or profile['dir']} profile."


if __name__ == "__main__":
    found = list_profiles()
    if not found:
        print("No Chrome profiles found (is Chrome installed for this Windows user?).")
    for p in found:
        print(f"folder: {p['dir']:<12} name: {p['name']:<20} email: {p['email']}")