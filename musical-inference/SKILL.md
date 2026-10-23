---
name: musical-inference
description: Turn explicitly selected local inference-process GPU activity into music, or render a labelled synthetic audio demonstration. Use for musical hardware monitoring; not speech synthesis or inference benchmarking.
---

# Musical inference

Use the bundled Windows Python collector to sonify the GPU engine activity of one user-selected process. Require Python 3.10+, NumPy and psutil already available, or ask before installing dependencies. Do not download models or start inference to obtain a signal.

1. Run `python scripts/monitor.py --discover` to enumerate live DXGI hardware adapters. Ask for the intended process when it is ambiguous. Never assume GPU zero or select an unrelated process.
2. Start with `python scripts/monitor.py --pid PID --adapter-index INDEX --seconds 5`. This collects only and writes local telemetry. Check PID creation identity, matched counters and validity before reporting success. Absence of counters is unavailable, not zero load.
3. For requested audible monitoring, add `--play`. Default duration is 10 seconds, maximum 600. Start at low system volume. Ctrl+C stops this collector and its audio; it never stops inference. A second monitor using the same output folder is refused.
4. For a hardware-independent renderer test use `python scripts/monitor.py --demo`. This writes a short **synthetic** WAV; no live playback or inference is implied.

Output defaults to `runs/` in the current directory. Keep it private: telemetry contains process IDs and adapter identities. Bounded live audio retains at most the last 120 seconds. Do not upload local telemetry, model paths, prompts, responses, credentials or machine configuration. Do not connect the static public demo to a local hardware endpoint.

PDH engine utilization drives pitch and timbre. It measures engine activity, not model tokens/second, computational correctness, GPU residency, TFLOP/s or TOPS. Memory, power and temperature remain unavailable in this collector. An audio callback completing does not prove the user heard it. Non-Windows live capture is unsupported; demo rendering is portable.

For Windows overhead and NPU helper comparisons, read [the campaign protocol](../docs/windows-overhead.md). NPU GEMM success does not establish graph compatibility, operator placement or full-memory access.
