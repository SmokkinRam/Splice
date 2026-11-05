import pytest

from assistant.brain import matcher
from assistant.brain.matcher import match, normalize, words_to_number

ALIASES = {"crows": "chrome", "throat": "chrome"}

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
]

NO_MATCH = [
    "",
    "Send an email to Rahul.",
    "Open the folder named Splice.",    # folders belong to the file manager
    "Find my DBMS assignment.",
    "What's the weather today?",
    "How are you doing?",
    "Track the price of this laptop.",
]


@pytest.mark.parametrize("text,name,params", CASES)
def test_known_commands(text, name, params):
    found = match(text, ALIASES)
    assert found is not None, f"no match for {text!r}"
    assert (found.name, found.params) == (name, params)


@pytest.mark.parametrize("text", NO_MATCH)
def test_unknown_text_is_left_for_the_brain(text):
    assert match(text, ALIASES) is None


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