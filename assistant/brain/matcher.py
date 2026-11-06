"""Fast command matcher: turns a transcript into a known command with no AI model.

match(text)  -> Match(name, params) or None      (pure logic, easy to test)
handle(text) -> Result or None                    (also runs the action)
Anything that doesn't match returns None, so the LLM brain (Step 3) can take over.
"""
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from assistant.config import load_config

from assistant.tools.chrome import canon

FILLER_RE = re.compile(
    r"\b(please|kindly|hey|okay|ok|could you|can you|would you|will you|for me)\b")

UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}

KNOWN_FOLDER_NAMES = ("documents", "downloads", "desktop", "pictures", "music", "videos")
LETTER_WORDS = {"see": "c", "sea": "c", "cee": "c", "dee": "d"}   # how letters get misheard

# Phrases for commands without parameters, used for fuzzy matching.
PHRASES = {
    "lock_screen": ["lock the screen", "lock my screen", "lock the computer",
                    "lock my computer", "lock my pc", "lock my laptop", "lock it"],
    "current_time": ["what time is it", "what is the time", "whats the time",
                     "tell me the time", "current time"],
}
FUZZY_CUTOFF = 88

SHOT_RE = re.compile(r"\b(screen\s?shots?|screen capture|"
                     r"capture (?:the |my )?screen|snapshot of (?:the |my )?screen)\b")
FIND_APP_PATTERNS = (
    r"^(?:find|search for|look for|locate)\s+(?:the\s+)?(?:app|application|program)"
    r"\s+(?:called\s+|named\s+)?(.+)$",
    r"^do i have\s+(.+?)\s+installed$",
    r"^do i have\s+(.+?)\s+on my\s+(?:pc|computer|laptop)$",
    r"^is\s+(.+?)\s+installed(?:\s+on my\s+(?:pc|computer|laptop))?$",
    r"^where is\s+(.+?)\s+installed$",
)


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


def _drive_letter(word):
    if len(word) == 1 and word.isalpha():
        return word
    return LETTER_WORDS.get(word)


def _match_drive(t):
    """'open local disk d', 'open the c drive', 'open drive e'."""
    found = re.match(r"^(?:open|show|go to)\s+(?:the\s+)?(?:local\s+)?(?:disk|drive|volume)"
                     r"\s+(?:letter\s+)?([a-z]+)(?:\s+(?:drive|disk))?$", t)
    if not found:
        found = re.match(r"^(?:open|show|go to)\s+(?:the\s+)?(?:local\s+disk\s+)?"
                         r"([a-z]+)\s+(?:drive|disk)$", t)
    if found:
        letter = _drive_letter(found.group(1))
        if letter:
            return Match("open_drive", {"letter": letter})
    return None


def _match_folder(t, folders):
    found = re.match(r"^(?:open|show|go to)\s+(?:the\s+|my\s+)?(.+?)(?:\s+folder)?$", t)
    if found:
        name = found.group(1).strip()
        if name in KNOWN_FOLDER_NAMES or name in (folders or {}):
            return Match("open_folder", {"name": name})
    return None


def _match_screenshot(t):
    if re.match(r"^(open|show|find|where)\b", t) or not SHOT_RE.search(t):
        return None
    target = "window" if re.search(
        r"\b(window|this app|active|current|foreground)\b", t) else "screen"
    clipboard = bool(re.search(r"\b(clipboard|copy)\b", t))
    return Match("take_screenshot", {"target": target, "clipboard": clipboard})


def _match_find_app(t):
    for pattern in FIND_APP_PATTERNS:
        found = re.match(pattern, t)
        if found:
            return Match("find_app", {"app": _clean_app_name(found.group(1))})
    return None


NOT_OWNERS = {"chrome", "google", "the", "a", "new", "another"}
def _match_chrome(t, profile_keys):
    """'open chrome with my profile', 'open moms chrome', 'open chrome for mom'."""
    not_owners = {"chrome", "google", "the", "a", "new", "another"}
    keys = {canon(k) for k in (profile_keys or [])}
    for pattern in (
            r"^(?:open|launch)\s+(?:google\s+)?chrome\s+(?:with|in|for|using|on|as)"
            r"\s+(?:the\s+)?(\w+)\s+(?:profile|account)$",
            r"^(?:open|launch|switch to)\s+(\w+)\s+(?:chrome\s+)?(?:profile|account)$"):
        found = re.match(pattern, t)
        if found and found.group(1) not in not_owners:
            return Match("open_chrome_profile", {"owner": found.group(1)})
    for pattern in (
            r"^(?:open|launch)\s+(?:google\s+)?chrome\s+(?:with|in|for|using|on|as)"
            r"\s+(?:the\s+)?(\w+)$",
            r"^(?:open|launch)\s+(\w+)\s+(?:google\s+)?chrome$"):
        found = re.match(pattern, t)
        if found and canon(found.group(1)) in keys:
            return Match("open_chrome_profile", {"owner": found.group(1)})
    return None


def match(text, aliases=None, folders=None, profiles=None):
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

    found = _match_chrome(t, profiles)
    if found:
        return found

    for finder in (_match_find_app, _match_screenshot, _match_drive):
        found = finder(t)
        if found:
            return found

    if re.fullmatch(r"(open|show)\s+(this pc|my pc|this computer|my computer)", t):
        return Match("open_this_pc")

    found = _match_folder(t, folders)
    if found:
        return found

    opened = re.match(r"^(open|launch)\s+(.+)$", t)
    if opened:
        app = _clean_app_name(opened.group(2))
        # other folders and files belong to the file manager, not to app launching
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
    found = match(text, config["aliases"], config["folders"], config["chrome_profiles"])
    if found is None:
        return None
    from assistant.tools import chrome, system   # imported late so tests need no Windows APIs

    actions = {
        "open_app": lambda p: system.open_app(
            p["app"], config["app_aliases"], config["app_search_folders"]),
        "find_app": lambda p: system.find_app(
            p["app"], config["app_aliases"], config["app_search_folders"]),
        "take_screenshot": lambda p: system.take_screenshot(
            p["target"], p["clipboard"], config["screenshot_folder"]),
        "open_drive": lambda p: system.open_drive(p["letter"]),
        "open_this_pc": lambda p: system.open_this_pc(),
        "open_folder": lambda p: system.open_folder(p["name"], config["folders"]),
        "open_chrome_profile": lambda p: chrome.open_profile(
            p["owner"], config["chrome_profiles"]),
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