Decision: small.en with a vocabulary prompt: 9/9 spoken clips correct plus the silence test (clip 09, deliberately silent) correctly returned empty, \~1.1 s per command, \~430 MB RAM. base.en with the prompt (7/9, \~0.3 s, \~205 MB) is the low-RAM profile. Hotwords mode did not beat the prompt. The VAD filter prevented made-up text on silence.

|Model|Exact|Similarity|Avg time (s)|Slowest (s)|Load (s)|RAM after load (MB)|RAM after run (MB)|
|-|-|-|-|-|-|-|-|
|base.en|5/10|86%|0.7|0.8|1.5|201|248|
|small.en|7/10|87%|1.5|1.7|2.0|422|468|
|base.en \[norm=1 vad=1 hint=0]|5/10|85%|0.5|1.4|1.4|201|246|
|base.en \[norm=1 vad=1 hint=1]|7/10|89%|0.3|0.4|0.8|205|253|
|base.en \[norm=1 vad=1 hint=2]|6/10|88%|0.3|0.4|0.9|201|244|
|small.en \[norm=1 vad=1 hint=0]|7/10|87%|1.4|4.2|1.5|428|470|
|small.en \[norm=1 vad=1 hint=1]|9/10|90%|1.1|1.2|1.4|426|463|



