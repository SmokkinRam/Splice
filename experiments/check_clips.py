"""Show how loud the first 1.5 s of each clip is, in 0.1 s steps."""
import glob
import wave

import numpy as np

RATE = 16000
WIN = RATE // 10  # 0.1 s windows

for path in sorted(glob.glob("clips/clip*.wav")):
    with wave.open(path) as w:
        a = np.abs(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)).astype(int)
    levels = [int(a[i:i + WIN].max()) for i in range(0, len(a) - WIN, WIN)]
    loud = [i for i, v in enumerate(levels) if v > 1500]
    start = loud[0] / 10 if loud else None
    print(path, "| peak", a.max(), "| speech starts at", start, "s")
    print("   first 1.5 s:", levels[:15])