"""Stage 4: accuracy + speed benchmark of ONE Whisper model on your clips.

Run it once per model, in separate processes (gives honest RAM numbers):
    python experiments/benchmark.py tiny.en
    python experiments/benchmark.py base.en
    python experiments/benchmark.py small.en
Each run prints per-clip results and appends a row to docs/stt_benchmark.md
"""
import difflib
import json
import re
import sys
import time
from pathlib import Path

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


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python experiments/benchmark.py <model>   e.g. base.en")
    size = sys.argv[1]

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
        segments, _ = model.transcribe(str(path), language="en", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()  # loop = real work
        return text, time.time() - t

    transcribe(files[0])  # warm-up run, ignored

    print(f"\nModel: {size}   (load {load_s:.1f} s, RAM {ram_loaded:.0f} MB)\n")
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
    print(f"\n{size}: {correct}/{n} exact, similarity {avg_sim:.0f}%, "
          f"avg {sum(times) / n:.1f} s, slowest {max(times):.1f} s")

    OUT.parent.mkdir(exist_ok=True)
    if not OUT.exists():
        OUT.write_text(
            "| Model | Exact | Similarity | Avg time (s) | Slowest (s) | "
            "Load (s) | RAM after load (MB) | RAM after run (MB) |\n"
            "|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"| {size} | {correct}/{n} | {avg_sim:.0f}% | "
                f"{sum(times) / n:.1f} | {max(times):.1f} | {load_s:.1f} | "
                f"{ram_loaded:.0f} | {ram_after:.0f} |\n")
    print(f"Row added to {OUT}  (RAM before load was {ram_before:.0f} MB)")


if __name__ == "__main__":
    main()