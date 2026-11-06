"""Text-to-speech: lets the assistant talk back.

Uses the voices built into Windows (no download, no extra RAM while idle).
Piper, for more natural offline voices, is the planned upgrade; only this file changes.

List the voices on your PC with:   python -m assistant.output.tts
"""
import os
import re
import subprocess

_proc = None

# The text, voice and speed travel in environment variables, so no quoting problems.
_SCRIPT = ("Add-Type -AssemblyName System.Speech; "
           "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
           "if ($env:SPLICE_VOICE) { try { $s.SelectVoice($env:SPLICE_VOICE) } catch {} }; "
           "$s.Rate = [int]$env:SPLICE_RATE; "
           "$s.Speak($env:SPLICE_SAY)")
NO_WINDOW = 0x08000000   # Windows flag: don't flash a console window


def to_speech(message, max_chars=240):
    """Turn an on-screen message into something short that sounds natural aloud."""
    text = re.sub(r"\(found at[^)]*\)", "", message)        # parenthetical file paths
    text = re.sub(r"\s*:?\s*[A-Za-z]:\\\S*", ".", text)         # Windows paths are not read out
    text = re.sub(r",?\s+at\.", ".", text)                    # "..., at." left by a removed path
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"https?://\S+", "", text)
    text = " ".join(text.split())
    text = re.sub(r"\s+([.!?,;:])", r"\1", text)             # "mytool ." -> "mytool."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    spoken = ""
    for sentence in sentences:
        if spoken and len(spoken) + len(sentence) + 1 > max_chars:
            break
        spoken = f"{spoken} {sentence}".strip()
    if len(spoken) > max_chars:                              # one very long sentence
        spoken = spoken[:max_chars].rsplit(" ", 1)[0]
    spoken = re.sub(r"[:;,\s]+$", "", spoken)
    if spoken and spoken[-1] not in ".!?":
        spoken += "."
    return spoken


def stop():
    """Stop talking right now (used when you press F9 to speak)."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
    _proc = None


def is_speaking():
    return _proc is not None and _proc.poll() is None


def speak(text, rate=0, voice="", wait=False):
    """Say the text. Returns False if speaking isn't possible here."""
    global _proc
    stop()
    if not text or not text.strip():
        return False
    env = dict(os.environ, SPLICE_SAY=text, SPLICE_RATE=str(int(rate)), SPLICE_VOICE=voice or "")
    try:
        _proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", _SCRIPT],
                                 env=env, creationflags=NO_WINDOW if os.name == "nt" else 0,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError):
        _proc = None
        return False
    if wait:
        _proc.wait()
    return True


def list_voices():
    script = ("Add-Type -AssemblyName System.Speech; "
              "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() "
              "| ForEach-Object { $_.VoiceInfo.Name + ' | ' + $_.VoiceInfo.Culture.Name }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=30).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


if __name__ == "__main__":
    voices = list_voices()
    print("\n".join(voices) if voices else "No voices found (this works on Windows only).")
    if voices:
        speak("Hello. This is how I sound.", wait=True)