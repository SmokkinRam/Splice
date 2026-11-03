"""Splice entry point.   Run from the project root:   python -m assistant.main"""
import time

from assistant.input.hotkey import listen_once
from assistant.input.stt import get_model, transcribe


def main():
    get_model()   # preload for now; the memory manager will decide this later
    print("Hold F9 and speak; release to transcribe. Ctrl+C quits.")
    try:
        while True:
            audio = listen_once()
            t0 = time.time()
            text = transcribe(audio)
            print(f"You said: {text!r}   "
                  f"({len(audio) / 16000:.1f} s of audio, {time.time() - t0:.1f} s to transcribe)")
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()