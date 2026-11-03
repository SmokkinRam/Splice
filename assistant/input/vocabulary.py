"""Vocabulary hints: words Whisper should expect (apps, people, folders, subjects).

Sources, in priority order:
  1. vocabulary.txt       your hand-written words (never overwritten)
  2. contacts.txt         names of people you email or call, one per line (optional)
  3. vocabulary.auto.txt  apps and folders found by vocab_builder.py
"""
from pathlib import Path

MANUAL = Path("vocabulary.txt")
CONTACTS = Path("contacts.txt")
AUTO = Path("vocabulary.auto.txt")

PREFIX = "Voice commands for a PC assistant. Words: "
MAX_CHARS = 400  # Whisper only reads a limited prompt, so keep the hint short


def _read(path):
    """One word or phrase per line; skip blank lines and # comments."""
    path = Path(path)
    if not path.exists():
        return []
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def _dedupe(words):
    seen, out = set(), []
    for word in words:
        key = word.lower()
        if key not in seen:
            seen.add(key)
            out.append(word)
    return out


def load_vocabulary(path=None):
    """Return the full word list. With no path, merge all sources in priority order.

    Auto-found names are sorted so short, simple ones (the kind people actually
    say aloud, like 'Spotify') come before long ones.
    """
    if path is not None:
        return _dedupe(_read(path))
    auto = sorted(_read(AUTO), key=lambda w: (len(w.split()), len(w)))
    return _dedupe(_read(MANUAL) + _read(CONTACTS) + auto)


def build_hint(words):
    """Turn a word list into a short prompt string ('' if there are no words).

    Only the first words that fit in MAX_CHARS are used, so order matters.
    """
    kept = []
    for word in words:
        candidate = PREFIX + ", ".join(kept + [word]) + "."
        if len(candidate) > MAX_CHARS:
            break
        kept.append(word)
    return PREFIX + ", ".join(kept) + "." if kept else ""