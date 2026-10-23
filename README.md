# ◆ Musical inference

A local, explicit-process Windows GPU soundtrack and a portable synthetic browser demo, part of the 42.uk universe.

Open the [browser demo](https://marroccofella-ops.github.io/musical-inference/). The root `index.html` also runs directly in a browser. It is a synthetic demonstration, not remote hardware access. No CDN, analytics, microphone, model text or network telemetry is used. Live GPU collection runs locally through Python and Windows PDH.

## Use

Install the `musical-inference` directory in your agent's skills directory, or read its SKILL.md. With Python 3.10+, install the declared requirements in a virtual environment you control. Discover adapters with `python musical-inference/scripts/monitor.py --discover`. Select a process and adapter explicitly:

```text
python musical-inference/scripts/monitor.py --pid 1234 --adapter-index 0 --seconds 5
python musical-inference/scripts/monitor.py --pid 1234 --adapter-index 0 --seconds 60 --play
python musical-inference/scripts/monitor.py --demo
```

Start quietly. Ctrl+C stops monitoring, leaving inference running. The first command collects silently. A failed or unavailable counter is not evidence of zero utilization. Demo WAVs are synthetic. Collection measures GPU engine activity, not model throughput, GPU residency or NPU support.

Read [the Windows overhead protocol](docs/windows-overhead.md) before assessing environmental overhead. Keep all machine-specific results private. The public package contains source and documentation only.

## Verification

Run `python tests/test_monitor.py`. Tests exercise synthesis, invalid arguments, exclusive output locks and synthetic evidence boundaries. Windows live collection must be verified separately on the selected process; audible playback requires a listening check.

Find the [repository](https://github.com/marroccofella-ops/musical-inference) and [Discussions](https://github.com/marroccofella-ops/musical-inference/discussions). A successful local test does not establish that Pages or audible playback works in your browser.

MIT licensed. **RELAX. IT'S ALREADY OVER.**
