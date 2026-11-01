"""Stage 2: record a few seconds from the microphone and save test.wav.

Usage:
    python experiments/record.py            # default device, 5 seconds
    python experiments/record.py 1          # device index 1
    python experiments/record.py 1 8        # device 1, 8 seconds
"""
import sys
import wave

import numpy as np
import sounddevice as sd

RATE = 16000  # Whisper expects 16 kHz mono audio

device = int(sys.argv[1]) if len(sys.argv) > 1 else None
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

print(f"Recording {seconds} s... speak now")
try:
    audio = sd.rec(int(seconds * RATE), samplerate=RATE, channels=1,
                   dtype="int16", device=device)
    sd.wait()  # block until the recording is finished
except sd.PortAudioError as err:
    sys.exit(f"Could not record at {RATE} Hz on this device: {err}\n"
             "Try another device index (MME devices are the most forgiving).")

peak = int(np.abs(audio).max())
print(f"Loudest sample: {peak} / 32767")
if peak < 500:
    print("Warning: very quiet. Check the device, mute switch, "
          "or Windows input volume.")

with wave.open("test.wav", "wb") as f:
    f.setnchannels(1)    # mono
    f.setsampwidth(2)    # 2 bytes = 16-bit samples
    f.setframerate(RATE)
    f.writeframes(audio.tobytes())
print("Saved test.wav")
