"""Splice entry point.   Run from the project root:   python -m assistant.main"""
import time

from assistant.brain.matcher import handle
from assistant.config import load_config
from assistant.input import hotkey
from assistant.input.hotkey import listen_once, start
from assistant.input.stt import get_model, transcribe
from assistant.output import tts


def main():
    speech = load_config()["speech"]
    get_model()   # preload for now; the memory manager will decide this later
    start()       # open the microphone and wait for it to warm up
    hotkey.PRESS_HOOKS.append(tts.stop)   # pressing F9 interrupts the assistant's voice
    print("Ready. Hold F9 and speak; release to run. Ctrl+C quits.")
    try:
        while True:
            audio = listen_once()
            t0 = time.time()
            text = transcribe(audio)
            print(f"You said: {text!r}   "
                  f"({len(audio) / 16000:.1f} s of audio, {time.time() - t0:.1f} s to transcribe)")
            result = handle(text)
            if result is None:
                print("  (no quick command matched; the LLM brain will handle this in Step 3)")
            else:
                print(f"  -> {result.message}")
                if speech["enabled"]:
                    tts.speak(tts.to_speech(result.message), speech["rate"], speech["voice"])
    except KeyboardInterrupt:
        tts.stop()
        print("\nBye.")


if __name__ == "__main__":
    main()