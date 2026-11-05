"""System tools: open apps, volume, lock screen, time. Windows only for now.

Every tool returns (ok, message): the message is what the assistant says or prints.
"""
import ctypes
import subprocess
from datetime import datetime

from rapidfuzz import fuzz, process, utils

_apps = None   # cached list of (name, app_id) from the Start menu


def _load_apps():
    """All Start menu apps, including Microsoft Store apps, via PowerShell."""
    cmd = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
           "Get-StartApps | ForEach-Object { $_.Name + [char]9 + $_.AppID }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="ignore", timeout=30).stdout
    apps = []
    for line in out.splitlines():
        if "\t" in line:
            name, app_id = line.split("\t", 1)
            if name.strip() and app_id.strip():
                apps.append((name.strip(), app_id.strip()))
    return apps


def _lookup(query):
    names = [name for name, _ in _apps]
    hit = process.extractOne(query, names, scorer=fuzz.WRatio,
                             processor=utils.default_process, score_cutoff=80)
    return _apps[hit[2]] if hit else None


def _find_app(query, app_aliases):
    global _apps
    query = (app_aliases or {}).get(query, query)
    fresh = _apps is None
    if fresh:
        _apps = _load_apps()
    found = _lookup(query)
    if not found and not fresh:        # maybe an app was installed since we cached
        _apps = _load_apps()
        found = _lookup(query)
    return found


def open_app(name, app_aliases=None):
    found = _find_app(name.lower(), app_aliases)
    if not found:
        return False, f"I couldn't find an app called {name}."
    app_name, app_id = found
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
    return True, f"Opening {app_name}."


def _endpoint():
    """Windows master-volume control (works with old and new pycaw versions)."""
    from pycaw.pycaw import AudioUtilities
    device = AudioUtilities.GetSpeakers()
    if hasattr(device, "EndpointVolume"):          # newer pycaw
        return device.EndpointVolume
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def set_volume(percent):
    _endpoint().SetMasterVolumeLevelScalar(percent / 100, None)
    return True, f"Volume set to {percent} percent."


def change_volume(delta):
    volume = _endpoint()
    current = round(volume.GetMasterVolumeLevelScalar() * 100)
    new = max(0, min(100, current + delta))
    volume.SetMasterVolumeLevelScalar(new / 100, None)
    return True, f"Volume {'up' if delta > 0 else 'down'} to {new} percent."


def set_mute(muted):
    _endpoint().SetMute(1 if muted else 0, None)
    return True, "Muted." if muted else "Unmuted."


def lock_screen():
    ctypes.windll.user32.LockWorkStation()
    return True, "Locking the screen."


def current_time():
    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    return True, f"It's {now}."