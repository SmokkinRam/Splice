"""Fast command matcher: turns a transcript into a known command with no AI model.

match(text)  -> Match(name, params) or None      (pure logic, easy to test)
handle(text) -> Result or None                    (also runs the action)
Anything that doesn't match returns None, so the LLM brain (Step 3) can take over.
"""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from assistant.config import load_config

FILLER_RE = re.compile(
    r"\b(please|kindly|hey|okay|ok|could you|can you|would you|will you|for me)\b")

UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}

# Phrases for commands without parameters, used for fuzzy matching.
PHRASES = {
    "lock_screen": ["lock the screen", "lock my screen", "lock the computer",
                    "lock my computer", "lock my pc", "lock my laptop", "lock it"],
    "current_time": ["what time is it", "what is the time", "whats the time",
                     "tell me the time", "current time"],
}
FUZZY_CUTOFF = 88


@dataclass
class Match:
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class Result:
    command: str
    ok: bool
    message: str


def words_to_number(text):
    """'40' -> 40, 'forty five' -> 45, 'one hundred' -> 100. None if no number."""
    digits = re.search(r"\b\d+\b", text)
    if digits:
        return int(digits.group())
    total, found = 0, False
    for token in text.split():
        if token in UNITS:
            total, found = total + UNITS[token], True
        elif token in TENS:
            total, found = total + TENS[token], True
        elif token == "hundred":
            total, found = max(total, 1) * 100, True
    return total if found else None


def normalize(text, aliases=None):
    """Lowercase, drop punctuation and filler words, and fix known mishearings."""
    text = re.sub(r"['\u2019]", "", text.lower())
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = FILLER_RE.sub(" ", text)
    aliases = aliases or {}
    words = [aliases.get(word, word) for word in text.split()]
    return " ".join(words)


def _match_volume(t):
    n = words_to_number(t)
    if re.search(r"\bunmute\b", t):
        return Match("set_mute", {"muted": False})
    if re.search(r"\bmute\b", t):
        return Match("set_mute", {"muted": True})
    if n is not None and re.search(r"\b(to|at)\b", t) and not re.search(r"\bby\b", t):
        return Match("set_volume", {"percent": max(0, min(100, n))})
    if re.search(r"\b(up|increase|raise|louder|higher)\b", t):
        return Match("change_volume", {"delta": n if n is not None else 10})
    if re.search(r"\b(down|decrease|lower|quieter|softer|reduce)\b", t):
        return Match("change_volume", {"delta": -(n if n is not None else 10)})
    if n is not None and re.search(r"\b(set|change|make|put)\b", t):
        return Match("set_volume", {"percent": max(0, min(100, n))})
    return None


def _clean_app_name(app):
    previous = None
    while previous != app:
        previous = app
        app = re.sub(r"^(the|my|up|a)\s+", "", app)
        app = re.sub(r"\s+(app|application)$", "", app)
    return app.strip()


def match(text, aliases=None):
    """Return a Match for a known quick command, or None."""
    t = normalize(text, aliases)
    if not t:
        return None

    if (re.search(r"\b(volume|sound|audio)\b", t)
            or re.search(r"\b(mute|unmute|louder|quieter)\b", t)):
        found = _match_volume(t)
        if found:
            return found

    if re.search(r"\block\b", t) and (
            re.search(r"\b(screen|pc|computer|laptop|system|windows)\b", t)
            or len(t.split()) <= 2):
        return Match("lock_screen")

    opened = re.match(r"^(open|launch)\s+(.+)$", t)
    if opened:
        app = _clean_app_name(opened.group(2))
        # folders and files belong to the file manager, not to app launching
        if app and not re.match(r"^(folder|file|document|directory)\b", app):
            return Match("open_app", {"app": app})
        return None

    if re.fullmatch(r"(what time is it|what is the time|whats the time|"
                    r"tell me the time|current time|what time)( now)?", t):
        return Match("current_time")

    # Fuzzy fallback for commands without parameters ("lok the screen")
    for name, phrases in PHRASES.items():
        if process.extractOne(t, phrases, scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF):
            return Match(name)
    return None


def handle(text):
    """Match the text and run the action. Returns a Result, or None if no match."""
    config = load_config()
    found = match(text, config["aliases"])
    if found is None:
        return None
    from assistant.tools import system   # imported late so tests need no Windows APIs

    actions = {
        "open_app": lambda p: system.open_app(p["app"], config["app_aliases"]),
        "set_volume": lambda p: system.set_volume(p["percent"]),
        "change_volume": lambda p: system.change_volume(p["delta"]),
        "set_mute": lambda p: system.set_mute(p["muted"]),
        "lock_screen": lambda p: system.lock_screen(),
        "current_time": lambda p: system.current_time(),
    }
    try:
        ok, message = actions[found.name](found.params)
    except Exception as err:   # a failing tool must never crash the assistant
        ok, message = False, f"{found.name} failed: {err}"
    return Result(found.name, ok, message)