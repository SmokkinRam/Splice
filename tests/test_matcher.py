import os
from datetime import datetime

import pytest

from assistant.brain import matcher
from assistant.brain.matcher import match, normalize, words_to_number

ALIASES = {"crows": "chrome", "throat": "chrome"}
FOLDERS = {"splice": "D:/Splice/Splice", "screenshots": "D:/Splice/screenshots"}

CASES = [
    ("Open Chrome.", "open_app", {"app": "chrome"}),
    ("Okay, open crows.", "open_app", {"app": "chrome"}),          # mishearing fixed
    ("Please launch the browser", "open_app", {"app": "browser"}),
    ("Set the volume to 40.", "set_volume", {"percent": 40}),
    ("Set the volume to forty five", "set_volume", {"percent": 45}),
    ("Lower the volume to thirty", "set_volume", {"percent": 30}),
    ("Turn the volume up", "change_volume", {"delta": 10}),
    ("Volume down by twenty", "change_volume", {"delta": -20}),
    ("Make it louder", "change_volume", {"delta": 10}),
    ("Mute", "set_mute", {"muted": True}),
    ("Unmute the sound", "set_mute", {"muted": False}),
    ("Lock the screen.", "lock_screen", {}),
    ("lok the screen", "lock_screen", {}),                          # fuzzy match
    ("What's the time?", "current_time", {}),
    # drives and folders
    ("Open local disk D.", "open_drive", {"letter": "d"}),
    ("Open Local Disk (C:)", "open_drive", {"letter": "c"}),
    ("Open the D drive", "open_drive", {"letter": "d"}),
    ("Open drive e", "open_drive", {"letter": "e"}),
    ("Open the see drive", "open_drive", {"letter": "c"}),          # "C" misheard
    ("Open this PC", "open_this_pc", {}),
    ("Open downloads", "open_folder", {"name": "downloads"}),
    ("Open the documents folder", "open_folder", {"name": "documents"}),
    ("Open splice", "open_folder", {"name": "splice"}),             # from config
    # screenshots
    ("Take a screenshot", "take_screenshot", {"target": "screen", "clipboard": False}),
    ("Take a screen shot.", "take_screenshot", {"target": "screen", "clipboard": False}),
    ("Screenshot this window", "take_screenshot", {"target": "window", "clipboard": False}),
    ("Take a screenshot and copy it to the clipboard", "take_screenshot",
     {"target": "screen", "clipboard": True}),
    # find app
    ("Find the app Photoshop", "find_app", {"app": "photoshop"}),
    ("Do I have Spotify installed?", "find_app", {"app": "spotify"}),
    ("Is Python installed on my laptop", "find_app", {"app": "python"}),
]

NO_MATCH = [
    "",
    "Send an email to Rahul.",
    "Open the folder named Splice.",    # folders by name belong to the file manager
    "Find my DBMS assignment.",
    "What's the weather today?",
    "How are you doing?",
    "Track the price of this laptop.",
    "Do I have any meetings today?",    # a question for the LLM, not an app search
]


@pytest.mark.parametrize("text,name,params", CASES)
def test_known_commands(text, name, params):
    found = match(text, ALIASES, FOLDERS)
    assert found is not None, f"no match for {text!r}"
    assert (found.name, found.params) == (name, params)


@pytest.mark.parametrize("text", NO_MATCH)
def test_unknown_text_is_left_for_the_brain(text):
    assert match(text, ALIASES, FOLDERS) is None


def test_opening_the_screenshots_folder_is_not_taking_a_screenshot():
    assert match("Open screenshots", None, FOLDERS).name == "open_folder"
    assert match("Show screenshots") is None          # not a screenshot request either


def test_open_the_drive_is_an_app_not_a_drive_letter():
    found = match("Open the drive")                   # could be the Google Drive app
    assert found.name == "open_app" and found.params == {"app": "drive"}


def test_words_to_number():
    assert words_to_number("40") == 40
    assert words_to_number("forty five") == 45
    assert words_to_number("one hundred") == 100
    assert words_to_number("no numbers here") is None


def test_normalize_removes_filler_and_fixes_aliases():
    assert normalize("Okay, please open crows!", ALIASES) == "open chrome"


def test_handle_runs_the_tool(monkeypatch):
    from assistant.tools import system
    calls = []
    monkeypatch.setattr(system, "set_volume", lambda p: calls.append(p) or (True, "ok"))
    result = matcher.handle("set the volume to 40")
    assert calls == [40]
    assert result.ok and result.command == "set_volume"


def test_a_failing_tool_does_not_crash(monkeypatch):
    from assistant.tools import system

    def boom(percent):
        raise RuntimeError("no audio device")

    monkeypatch.setattr(system, "set_volume", boom)
    result = matcher.handle("set the volume to 40")
    assert result.ok is False and "no audio device" in result.message


# ---- tool-level tests (no Windows needed) ----

def test_known_folder_lists_agree():
    from assistant.tools import system
    assert set(system.KNOWN_FOLDERS) == set(matcher.KNOWN_FOLDER_NAMES)


def test_screenshot_path(tmp_path):
    from assistant.tools import system
    path = system.screenshot_path(str(tmp_path), now=datetime(2026, 11, 7, 9, 5, 3))
    assert path == tmp_path / "screenshot_2026-11-07_09-05-03.png"


def test_exe_scan_skips_installers_and_deep_folders(tmp_path):
    from assistant.tools import system
    (tmp_path / "MyTool").mkdir()
    (tmp_path / "MyTool" / "mytool.exe").write_text("x")
    (tmp_path / "MyTool" / "uninstall.exe").write_text("x")
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "toodeep.exe").write_text("x")
    names = [name for name, _ in system._scan_exes([str(tmp_path)])]
    assert "mytool" in names
    assert "uninstall" not in names and "toodeep" not in names


def test_find_app_uses_the_start_menu(monkeypatch):
    from assistant.tools import system
    monkeypatch.setattr(system, "_apps", [("Google Chrome", "id1"), ("Microsoft Teams", "id2")])
    ok, message = system.find_app("chrome")
    assert ok and "Google Chrome" in message


def test_open_drive_reports_a_missing_drive(monkeypatch):
    from assistant.tools import system
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    ok, message = system.open_drive("z")
    assert not ok and "Z" in message


def test_open_drive_opens_an_existing_drive(monkeypatch):
    from assistant.tools import system
    opened = []
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    ok, _ = system.open_drive("d")
    assert ok and opened == ["D:\\"]