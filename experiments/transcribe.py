"""Stage 3: transcribe a WAV file with faster-whisper, and time it.

Usage:
    python experiments/transcribe.py                  # test.wav, base.en
    python experiments/transcribe.py test.wav tiny.en
"""
import sys
import time

import psutil
from faster_whisper import WhisperModel

path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"
size = sys.argv[2] if len(sys.argv) > 2 else "base.en"


def ram_mb():
    return psutil.Process().memory_info().rss / (1024 * 1024)


print(f"RAM before model: {ram_mb():.0f} MB")
t0 = time.time()
model = WhisperModel(size, device="cpu", compute_type="int8")
print(f"Loaded {size} in {time.time() - t0:.1f} s, RAM {ram_mb():.0f} MB")

t0 = time.time()
segments, info = model.transcribe(path, language="en", vad_filter=True)
text = " ".join(s.text.strip() for s in segments)  # this loop does the real work
print(f"Transcribed in {time.time() - t0:.1f} s")
print(f"Text: {text!r}")
