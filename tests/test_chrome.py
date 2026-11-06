import json

import pytest

from assistant.brain.matcher import match
from assistant.tools import chrome

PROFILES = {"my": "Preetam", "mom": "mom@example.com"}

CHROME_CASES = [
    ("Open Chrome with my profile", "my"),
    ("Open Chrome with mom's profile", "moms"),
    ("Open chrome in mother's profile", "mothers"),
    ("Open my profile", "my"),
    ("Open mom's Chrome", "moms"),
    ("Open Chrome for mom", "mom"),
    ("Launch my Chrome", "my"),
]


@pytest.mark.parametrize("text,owner", CHROME_CASES)
def test_chrome_profile_commands(text, owner):
    found = match(text, None, None, PROFILES)
    assert found is not None, f"no match for {text!r}"
    assert found.name == "open_chrome_profile" and found.params == {"owner": owner}


def test_plain_chrome_commands_still_open_the_app():
    assert match("Open Chrome", None, None, PROFILES).name == "open_app"
    assert match("Open the Chrome", None, None, PROFILES).name == "open_app"
    assert match("Open Chrome profile", None, None, PROFILES).name == "open_app"


def test_unknown_owner_needs_the_word_profile():
    # without the word "profile", an unknown name is not treated as a profile
    assert match("Open Chrome for dad", None, None, PROFILES) is None or \
        match("Open Chrome for dad", None, None, PROFILES).name != "open_chrome_profile"
    found = match("Open Chrome with dad's profile", None, None, PROFILES)
    assert found.name == "open_chrome_profile"       # the tool will explain it has no such profile


def test_owner_synonyms():
    assert chrome.canon("Mom's".replace("'", "")) == "mom"
    assert chrome.canon("mother") == "mom" and chrome.canon("me") == "my"
    assert chrome.canon("dad") == "dad"


@pytest.fixture
def fake_chrome(tmp_path, monkeypatch):
    local = tmp_path / "local"
    user_data = local / "Google" / "Chrome" / "User Data"
    user_data.mkdir(parents=True)
    state = {"profile": {"info_cache": {
        "Default": {"name": "Preetam", "user_name": "me@example.com", "gaia_name": "Preetam N"},
        "Profile 1": {"name": "Person 2", "user_name": "mom@example.com", "gaia_name": "Mom"},
    }}}
    (user_data / "Local State").write_text(json.dumps(state), encoding="utf-8")
    programs = tmp_path / "programs"
    exe = programs / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("ProgramFiles", str(programs))
    return exe


def test_list_and_resolve_profiles(fake_chrome):
    profiles = chrome.list_profiles()
    assert {p["dir"] for p in profiles} == {"Default", "Profile 1"}
    assert chrome.resolve_profile("preetam")["dir"] == "Default"             # by name
    assert chrome.resolve_profile("mom@example.com")["dir"] == "Profile 1"   # by email
    assert chrome.resolve_profile("Profile 1")["dir"] == "Profile 1"         # by folder
    assert chrome.resolve_profile("mom")["dir"] == "Profile 1"               # partial
    assert chrome.resolve_profile("nobody") is None


def test_open_profile_launches_chrome_with_the_right_profile(fake_chrome, monkeypatch):
    launched = []
    monkeypatch.setattr(chrome.subprocess, "Popen", lambda cmd: launched.append(cmd))
    ok, message = chrome.open_profile("moms", {"my": "Preetam", "mom": "mom@example.com"},
                                      url="https://mail.google.com")
    assert ok and "Person 2" in message
    assert launched == [[str(fake_chrome), "--profile-directory=Profile 1",
                         "https://mail.google.com"]]


def test_open_profile_reports_missing_things(fake_chrome, monkeypatch):
    monkeypatch.setattr(chrome.subprocess, "Popen", lambda cmd: None)
    ok, message = chrome.open_profile("dad", {"my": "Preetam"})
    assert not ok and "chrome_profiles" in message
    ok, message = chrome.open_profile("my", {"my": "Nobody Here"})
    assert not ok and "python -m assistant.tools.chrome" in message