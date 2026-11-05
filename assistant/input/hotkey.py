"""Hold-to-talk: keep the microphone open, record while F9 is held, return the audio.

The stream stays open the whole time, so the driver's start-up delay never cuts off
your first word, and a short pre-roll keeps the moment just before you press F9.
"""
import collections
import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from pynput import keyboard

RATE = 16000
BLOCK = 1024                      # samples per audio callback (about 64 ms)
HOTKEY = keyboard.Key.f9
PREROLL_S = 0.4                   # audio kept from just before the key press
MIN_S = 0.3                       # ignore taps shorter than this
WARMUP_S = 2.0                    # let the microphone wake up
# Set the MIC environment variable to your microphone's index (yours: 1).
DEVICE = int(os.environ["MIC"]) if "MIC" in os.environ else None

_ready = queue.Queue()
_lock = threading.Lock()
_held = False
_preroll = collections.deque(maxlen=max(1, int(PREROLL_S * RATE / BLOCK)))
_chunks = []
_stream = None
_listener = None


def _on_audio(indata, frames, time_info, status):
    block = indata[:, 0].copy()
    with _lock:
        if _held:
            _chunks.append(block)
        else:
            _preroll.append(block)


def _on_press(key):
    global _held
    if key != HOTKEY:
        return
    with _lock:
        if _held:                  # key auto-repeat while held
            return
        _chunks.clear()
        _chunks.extend(_preroll)
        _held = True
    print("Listening...")


def _on_release(key):
    global _held
    if key != HOTKEY:
        return
    with _lock:
        if not _held:
            return
        _held = False
        audio = np.concatenate(_chunks) if _chunks else np.zeros(0, np.float32)
        _chunks.clear()
    _ready.put(audio)


def start():
    global _stream, _listener
    if _stream is not None:
        return
    _stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                             blocksize=BLOCK, device=DEVICE, callback=_on_audio)
    _stream.start()
    _listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    _listener.start()
    print(f"Warming up the microphone ({WARMUP_S:.0f} s)...")
    time.sleep(WARMUP_S)


def listen_once():
    """Block until F9 is held and released; return the audio (float32, 16 kHz)."""
    start()
    while True:
        try:
            audio = _ready.get(timeout=0.5)   # timeout so Ctrl+C works on Windows
        except queue.Empty:
            continue
        if len(audio) >= MIN_S * RATE:
            return audio