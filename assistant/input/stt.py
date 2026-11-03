"""Speech-to-text: loads the Whisper model on first use and transcribes audio arrays."""
import gc
import os
import time

import numpy as np

MODEL_SIZE = os.environ.get("STT_MODEL", "small.en")   # chosen from our benchmark

_model = None


def _hint():
    """Vocabulary hint from vocabulary.txt etc. (None if that module isn't set up)."""
    try:
        from assistant.input.vocabulary import build_hint, load_vocabulary
    except ImportError:
        return None
    return build_hint(load_vocabulary()) or None


def get_model():
    """Load the model once, on first use."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        t0 = time.time()
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print(f"[stt] loaded {MODEL_SIZE} in {time.time() - t0:.1f} s")
    return _model


def unload():
    """Free the model's memory. The memory manager will call this later."""
    global _model
    _model = None
    gc.collect()


def transcribe(audio):
    """audio: 16 kHz mono float32 numpy array in [-1, 1]. Returns the text."""
    if audio is None or len(audio) < 4800:            # shorter than 0.3 s
        return ""
    audio = np.asarray(audio, dtype=np.float32).flatten()
    peak = float(np.abs(audio).max())
    if peak > 0:
        audio = audio * min(0.9 / peak, 20.0)         # boost quiet speech
    segments, _ = get_model().transcribe(
        audio, language="en", vad_filter=True, beam_size=5, initial_prompt=_hint())
    return " ".join(s.text.strip() for s in segments).strip()