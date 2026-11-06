from assistant.output import tts


def test_paths_are_not_read_aloud():
    message = r"Saved a screen screenshot: D:\Splice\screenshots\screenshot_2026-11-07_09-05-03.png"
    assert tts.to_speech(message) == "Saved a screen screenshot."


def test_found_at_paths_are_dropped():
    message = r"Opening mytool (found at C:\Program Files\MyTool\mytool.exe)."
    assert tts.to_speech(message) == "Opening mytool."


def test_short_messages_pass_through():
    assert tts.to_speech("Volume set to 30 percent.") == "Volume set to 30 percent."
    assert tts.to_speech("Muted") == "Muted."


def test_long_messages_are_trimmed_at_a_sentence():
    message = "First sentence is here. " + "Another sentence follows here. " * 20
    spoken = tts.to_speech(message, max_chars=60)
    assert spoken.startswith("First sentence is here.") and len(spoken) <= 60


def test_one_huge_sentence_is_cut_at_a_word():
    spoken = tts.to_speech("word " * 100, max_chars=50)
    assert len(spoken) <= 51 and not spoken.endswith(" ")


def test_empty_text_is_not_spoken(monkeypatch):
    monkeypatch.setattr(tts.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert tts.speak("   ") is False


class FakeProcess:
    def __init__(self):
        self.terminated = False
        self.waited = False

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self):
        self.terminated = True

    def wait(self):
        self.waited = True


def test_speak_passes_text_in_the_environment(monkeypatch):
    seen = {}

    def fake_popen(cmd, env=None, **kwargs):
        seen.update(cmd=cmd, env=env)
        return FakeProcess()

    monkeypatch.setattr(tts.subprocess, "Popen", fake_popen)
    assert tts.speak('He said "hi" and left', rate=2, voice="Microsoft Zira Desktop")
    assert seen["env"]["SPLICE_SAY"] == 'He said "hi" and left'     # no quoting problems
    assert seen["env"]["SPLICE_RATE"] == "2"
    assert seen["env"]["SPLICE_VOICE"] == "Microsoft Zira Desktop"
    assert seen["cmd"][0] == "powershell"
    tts.stop()


def test_stop_interrupts_the_current_speech(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(tts.subprocess, "Popen", lambda *a, **k: process)
    tts.speak("a long sentence")
    assert tts.is_speaking()
    tts.stop()
    assert process.terminated and not tts.is_speaking()


def test_a_new_message_replaces_the_old_one(monkeypatch):
    processes = [FakeProcess(), FakeProcess()]
    monkeypatch.setattr(tts.subprocess, "Popen", lambda *a, **k: processes.pop(0))
    first_process = processes[0]
    tts.speak("first")
    tts.speak("second")
    assert first_process.terminated
    tts.stop()


def test_missing_powershell_is_handled(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(tts.subprocess, "Popen", boom)
    assert tts.speak("hello") is False


def test_a_path_in_the_middle_leaves_clean_sentences():
    message = r"Saved a window screenshot: D:\Splice\screenshots\a.png It's also on your clipboard."
    assert tts.to_speech(message) == "Saved a window screenshot. It's also on your clipboard."


def test_a_dangling_at_is_removed():
    message = r"Found mytool outside the Start menu, at C:\Apps\mytool.exe."
    assert tts.to_speech(message) == "Found mytool outside the Start menu."