"""System tools: apps, drives and folders, screenshots, volume, lock screen, time.

Windows only for now. Every tool returns (ok, message): the message is what the
assistant says or prints.
"""
import ctypes
import os
import subprocess
from datetime import datetime
from pathlib import Path

from rapidfuzz import fuzz, process, utils

KNOWN_FOLDERS = {                       # spoken name -> Windows shell folder
    "documents": "shell:Personal",
    "downloads": "shell:Downloads",
    "desktop": "shell:Desktop",
    "pictures": "shell:My Pictures",
    "music": "shell:My Music",
    "videos": "shell:My Video",
}
EXE_SKIP = ("uninstall", "unins", "setup", "install", "update", "helper",
            "crash", "service", "agent", "redist")   # never launch these by guesswork
EXE_MAX_DEPTH = 3

_apps = None   # cached Start menu apps: list of (name, app_id)
_exes = None   # cached .exe files outside the Start menu: list of (name, path)


# ---------- apps ----------

def _load_apps():
    """All Start menu apps, including Microsoft Store apps, via PowerShell."""
    cmd = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
           "Get-StartApps | ForEach-Object { $_.Name + [char]9 + $_.AppID }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="ignore", timeout=30).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
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


def _scan_exes(extra_folders=None):
    """.exe files in the usual install folders (and yours), a few levels deep."""
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
             os.path.join(os.environ["LOCALAPPDATA"], "Programs")
             if os.environ.get("LOCALAPPDATA") else None]
    roots += list(extra_folders or [])
    found = []
    for root in roots:
        if not root or not Path(root).is_dir():
            continue
        base_depth = len(Path(root).parts)
        for dirpath, dirnames, filenames in os.walk(root):
            if len(Path(dirpath).parts) - base_depth >= EXE_MAX_DEPTH:
                dirnames[:] = []                     # don't go deeper
            for filename in filenames:
                low = filename.lower()
                if low.endswith(".exe") and not any(bad in low for bad in EXE_SKIP):
                    found.append((Path(filename).stem, str(Path(dirpath) / filename)))
    return found


def _find_exe(query, extra_folders, cutoff):
    global _exes
    if _exes is None:
        _exes = _scan_exes(extra_folders)
    names = [name for name, _ in _exes]
    hit = process.extractOne(query, names, scorer=fuzz.WRatio,
                             processor=utils.default_process, score_cutoff=cutoff)
    return _exes[hit[2]] if hit else None


def open_app(name, app_aliases=None, search_folders=None):
    query = name.lower()
    found = _find_app(query, app_aliases)
    if found:
        app_name, app_id = found
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return True, f"Opening {app_name}."
    exe = _find_exe((app_aliases or {}).get(query, query), search_folders, cutoff=85)
    if exe:                             # strict cutoff: launching by guesswork is riskier
        exe_name, path = exe
        os.startfile(path)
        return True, f"Opening {exe_name} (found at {path})."
    return False, f"I couldn't find an app called {name}."


def find_app(name, app_aliases=None, search_folders=None):
    """Say whether an app is installed, without opening it."""
    global _apps
    query = (app_aliases or {}).get(name.lower(), name.lower())
    if _apps is None:
        _apps = _load_apps()
    hits = process.extract(query, [n for n, _ in _apps], scorer=fuzz.WRatio,
                           processor=utils.default_process, score_cutoff=75, limit=3)
    if hits:
        return True, "Yes, found: " + ", ".join(h[0] for h in hits) + "."
    exe = _find_exe(query, search_folders, cutoff=80)
    if exe:
        return True, f"Found {exe[0]} outside the Start menu, at {exe[1]}."
    return False, f"I couldn't find an app like {name}."


# ---------- drives and folders ----------

def open_drive(letter):
    path = f"{letter.upper()}:\\"
    if not os.path.exists(path):
        return False, f"I can't find a drive {letter.upper()} on this PC."
    os.startfile(path)
    return True, f"Opening local disk {letter.upper()}."


def open_this_pc():
    subprocess.Popen(["explorer.exe", "shell:MyComputerFolder"])
    return True, "Opening This PC."


def open_folder(name, folders=None):
    key = name.lower()
    configured = (folders or {}).get(key)
    if configured:
        path = os.path.expandvars(os.path.expanduser(configured))
        if not os.path.isdir(path):
            return False, f"The folder for {name} doesn't exist yet: {path}"
        os.startfile(path)
        return True, f"Opening {name}."
    if key in KNOWN_FOLDERS:
        subprocess.Popen(["explorer.exe", KNOWN_FOLDERS[key]])
        return True, f"Opening {name}."
    return False, f"I don't know a folder called {name}."


# ---------- screenshots ----------

def screenshot_path(folder=None, now=None):
    """Where to save a screenshot taken now."""
    if folder:
        base = Path(os.path.expandvars(os.path.expanduser(folder)))
    else:
        base = Path.home() / "Pictures" / "Screenshots" / "Splice"
    stamp = (now or datetime.now()).strftime("screenshot_%Y-%m-%d_%H-%M-%S.png")
    return base / stamp


def _make_dpi_aware():
    """Without this, screen coordinates are wrong on scaled (125%/150%) displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _active_window_box():
    """(left, top, right, bottom) of the window you're using, or None."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = wintypes.RECT()
    # extended frame bounds = the visible window, without the invisible shadow border
    status = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect))
    if status != 0:
        user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _copy_image_to_clipboard(path):
    safe = str(path).replace("'", "''")
    script = ("Add-Type -AssemblyName System.Windows.Forms, System.Drawing; "
              f"$img=[System.Drawing.Image]::FromFile('{safe}'); "
              "[System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose()")
    done = subprocess.run(["powershell", "-STA", "-NoProfile", "-Command", script],
                          capture_output=True, text=True, timeout=30)
    return done.returncode == 0


def take_screenshot(target="screen", clipboard=False, folder=None):
    from PIL import ImageGrab
    _make_dpi_aware()
    box = _active_window_box() if target == "window" else None
    image = ImageGrab.grab(bbox=box, all_screens=True)
    path = screenshot_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    what = "window" if (target == "window" and box) else "screen"
    message = f"Saved a {what} screenshot: {path}"
    if clipboard:
        message += (" It's also on your clipboard." if _copy_image_to_clipboard(path)
                    else " (I couldn't copy it to the clipboard.)")
    return True, message


# ---------- volume, lock, time ----------

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