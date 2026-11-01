import sounddevice as sd

hostapis = sd.query_hostapis()
default_in = sd.default.device[0]

print("Input devices:\n")
for i, dev in enumerate(sd.query_devices()):
    if dev["max_input_channels"] > 0:
        api = hostapis[dev["hostapi"]]["name"]
        mark = "  <-- default" if i == default_in else ""
        print(f"[{i:2d}] {dev['name']}  "
              f"({api}, {dev['max_input_channels']} ch, "
              f"{int(dev['default_samplerate'])} Hz){mark}")
