"""Stage 4: accuracy + speed benchmark of ONE Whisper model on your clips.

Run it once per model, in separate processes (gives honest RAM numbers):
    python experiments/benchmark.py base.en
    python experiments/benchmark.py small.en

Options (environment variables, all optional):
    NORM=0   do NOT boost quiet clips to a standard loudness   (default: on)
    VAD=0    do NOT skip silence with the voice-activity filter (default: on)
    HINT=1   vocabulary hint as a prompt   (words from vocabulary.txt etc.)
    HINT=2   vocabulary hint as 'hotwords' (faster-whisper's separate option)
Example:   HINT=1 python experiments/benchmark.py base.en

Each run prints per-clip results and appends a row to docs/stt_benchmark.md
"""
import difflib
import json
import os
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assistant.input.vocabulary import build_hint, load_vocabulary  # noqa: E402

CLIPS = Path("clips")
OUT = Path("docs/stt_benchmark.md")

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]


def number_to_words(n):
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    return TENS[tens] + (" " + ONES[ones] if ones else "")


def normalize(text):
    """Make 'Set the volume to 40!' and 'set the volume to forty' compare equal."""
    text = text.lower().replace("-", " ")
    text = text.replace("e mail", "email")
    text = re.sub(r"\d+", lambda m: number_to_words(int(m.group()))
                  if int(m.group()) < 100 else m.group(), text)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    # "d b m s" -> "dbms"
    text = re.sub(r"\b(?:[a-z] )+[a-z]\b", lambda m: m.group().replace(" ", ""), text)
    return " ".join(text.split())


def load_wav(path, boost):
    """Read a 16-bit mono WAV as float32 in [-1, 1]; optionally boost quiet clips."""
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    if boost and peak > 0:
        audio = audio * min(0.9 / peak, 20.0)   # aim for peak 0.9, cap the boost at 20x
    return audio


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python experiments/benchmark.py <model>   e.g. base.en")
    size = sys.argv[1]
    boost = os.environ.get("NORM", "1") == "1"
    use_vad = os.environ.get("VAD", "1") == "1"
    hint_mode = os.environ.get("HINT", "0")      # 0 = off, 1 = prompt, 2 = hotwords
    words = load_vocabulary() if hint_mode != "0" else []
    if hint_mode != "0" and not words:
        sys.exit("vocabulary.txt is missing or empty.")
    options = f"norm={int(boost)} vad={int(use_vad)} hint={hint_mode}"
    if words:
        print(f"Hint ({len(words)} words known): {build_hint(words)!r}")

    expected_file = CLIPS / "expected.json"
    if not expected_file.exists():
        sys.exit("clips/expected.json not found. Run record_clips.py first.")
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    files = sorted(CLIPS.glob("clip*.wav"))
    if not files:
        sys.exit("No clips found in clips/. Run record_clips.py first.")

    import psutil
    from faster_whisper import WhisperModel

    proc = psutil.Process()

    def ram_mb():
        return proc.memory_info().rss / (1024 * 1024)

    ram_before = ram_mb()
    t0 = time.time()
    model = WhisperModel(size, device="cpu", compute_type="int8")
    load_s = time.time() - t0
    ram_loaded = ram_mb()

    def transcribe(path):
        t = time.time()
        audio = load_wav(path, boost)
        extra = {}
        if hint_mode == "1":
            extra["initial_prompt"] = build_hint(words)
        elif hint_mode == "2":
            extra["hotwords"] = ", ".join(words[:40])
        segments, _ = model.transcribe(audio, language="en", vad_filter=use_vad,
                                       beam_size=5, **extra)
        text = " ".join(s.text.strip() for s in segments).strip()  # loop = real work
        return text, time.time() - t

    transcribe(files[0])  # warm-up run, ignored

    print(f"\nModel: {size} [{options}]   (load {load_s:.1f} s, RAM {ram_loaded:.0f} MB)\n")
    correct, times, sims = 0, [], []
    for f in files:
        want = expected.get(f.stem, "")
        heard, secs = transcribe(f)
        ok = normalize(heard) == normalize(want)
        sims.append(difflib.SequenceMatcher(
            None, normalize(want), normalize(heard)).ratio())
        times.append(secs)
        correct += ok
        status = "OK  " if ok else "MISS"
        print(f"{f.stem} {status} {secs:4.1f}s  heard: {heard!r}")
        if not ok:
            print(f"{'':12}wanted: {want!r}")

    n = len(files)
    ram_after = ram_mb()
    avg_sim = 100 * sum(sims) / n
    print(f"\n{size} [{options}]: {correct}/{n} exact, similarity {avg_sim:.0f}%, "
          f"avg {sum(times) / n:.1f} s, slowest {max(times):.1f} s")

    OUT.parent.mkdir(exist_ok=True)
    if not OUT.exists():
        OUT.write_text(
            "| Model [options] | Exact | Similarity | Avg time (s) | Slowest (s) | "
            "Load (s) | RAM after load (MB) | RAM after run (MB) |\n"
            "|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"| {size} [{options}] | {correct}/{n} | {avg_sim:.0f}% | "
                f"{sum(times) / n:.1f} | {max(times):.1f} | {load_s:.1f} | "
                f"{ram_loaded:.0f} | {ram_after:.0f} |\n")
    print(f"Row added to {OUT}  (RAM before load was {ram_before:.0f} MB)")


if __name__ == "__main__":
    main()