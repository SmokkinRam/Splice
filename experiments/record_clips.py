"""Stage 4: record your 10 test clips into clips/ and save what you meant to say.

The microphone stream is opened ONCE and kept running, so the driver's
start-up delay (about 1 s on many laptops) never eats the start of your speech.
Enter starts a clip, Enter again stops it.

Usage:
    python experiments/record_clips.py        # default microphone
    python experiments/record_clips.py 1      # microphone index 1
"""
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

RATE = 16000      # Whisper expects 16 kHz mono
WARMUP = 2.0      # seconds to let the microphone start delivering real audio
TRIM_END = 0.15   # seconds cut from the end to drop the Enter key click
OUT = Path("clips")

PHRASES = [
    "Open Chrome.",
    "Set the volume to forty.",
    "Send an email to Rahul.",
    "Find my DBMS assignment.",
    "What's the weather today?",
    "Build me a portfolio website.",
    "Track the price of this laptop.",
    "Call me when the build finishes.",
    "Lock the screen.",
    "Open the folder named Splice.",
]


def save_wav(path, audio):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(audio.tobytes())


def main():
    device = int(sys.argv[1]) if len(sys.argv) > 1 else None
    OUT.mkdir(exist_ok=True)

    chunks = []
    state = {"on": False}

    def on_audio(indata, frames, time_info, status):
        if state["on"]:
            chunks.append(indata.copy())

    try:
        stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                                device=device, callback=on_audio)
        stream.start()
    except sd.PortAudioError as err:
        sys.exit(f"Could not open the microphone: {err}\nTry another index.")

    expected = {}
    try:
        print(f"Warming up the microphone ({WARMUP:.0f} s)...")
        time.sleep(WARMUP)
        print("Ready. Enter = start recording, Enter again = stop.")

        for i, phrase in enumerate(PHRASES, 1):
            name = f"clip{i:02d}"
            expected[name] = phrase
            while True:
                input(f'\n[{i}/{len(PHRASES)}] Press Enter to START, then say: "{phrase}" ')
                time.sleep(0.3)          # let the key-press click die away
                chunks.clear()
                state["on"] = True
                t0 = time.time()
                input("  Recording... speak, then press Enter to STOP ")
                state["on"] = False
                secs = time.time() - t0

                audio = np.concatenate(chunks) if chunks else np.zeros((0, 1), "int16")
                audio = audio[:max(0, len(audio) - int(TRIM_END * RATE))]
                peak = int(np.abs(audio).max()) if len(audio) else 0
                lead = int(np.abs(audio[:RATE // 10]).max()) if len(audio) else 0
                save_wav(OUT / f"{name}.wav", audio)
                print(f"  Saved {name}.wav ({secs:.1f} s, loudest sample {peak}/32767)")
                if peak < 500:
                    print("  Very quiet - check the microphone or input volume.")
                if lead > 1500:
                    print("  Sound was already loud at the very start - "
                          "pause a beat before speaking.")
                if input("  Enter = keep, r = record again: ").strip().lower() != "r":
                    break
    finally:
        stream.stop()
        stream.close()

    (OUT / "expected.json").write_text(json.dumps(expected, indent=2),
                                       encoding="utf-8")
    print(f"\nDone. {len(PHRASES)} clips and expected.json are in {OUT}/")


if __name__ == "__main__":
    main()