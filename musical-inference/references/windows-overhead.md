# Windows overhead and NPU placement campaign

Keep the secure, everyday configuration as the reference. A proposed cause is not a finding. Never disable Defender, VBS, Memory Integrity, Controlled Folder Access, sync, ACLs or power protections automatically. Do not elevate inference or change the pagefile to hide a failed allocation.

## Environment evidence

Record OS build/boot, updates, Defender engine and signatures, protection and CFA state, VBS configured/running state, power plan and AC supply, OEM cooling profile, process QoS, clocks/temperature/limits, available physical and commit memory, competing CPU/GPU/I/O activity, and model/runtime hashes. Mark unavailable metrics explicitly. Private raw results may contain usernames and paths.

The lab companion provides `windows_environment_snapshot` via MCP and dashboard. Its diagnostic-file read/write probe verifies only its own diagnostic folder; it does not prove model/compiler-cache permissions. Its passive baseline is not a controlled inference benchmark. A newly started process does not prove a cold filesystem cache.

## Matched experiments

Freeze the model, quantization, exact runtime/device, prompt hashes, context, cache precision, concurrency, accepted output budgets and helper work. Keep at least 8 GiB physical RAM available. Launch active tests through the lab's shared job controller, not a second competing benchmark. Do not terminate user applications to manufacture a quiet desktop.

Measure baseline variability, then interleave baseline/candidate AB and BA pairs, at least three complete pairs. Preserve warmups, repetitions, timestamps, environmental snapshots and raw logs. Record load seconds, uncached prefill tokens/second, first-token seconds, sustained committed generation tokens/second, and whole-task seconds/success separately. Check observed prefix reuse; unique wording alone does not prove an uncached prompt. Change one environmental factor at a time. Repeat promising results across fresh sessions and normal low-overhead telemetry.

1. Profile antivirus scanning without disabling protection. Separate scan elapsed time from application stalls and overlapping work.
2. Compare identical, fully local files on the same SSD against the existing workspace. Hash both copies, record hydration, sync and cache state. Call the initial result a placement comparison, not an ACL or OneDrive causal effect.
3. Record AC, cooling, power/QoS and background memory/I/O consumers. Screen quiet conditions, then isolate contributors.
4. Trace actual runtime cache paths for repeated denied access, sharing violations or compilation retries. Fix a demonstrated path problem only; do not run everything as administrator.
5. Compare dashboard/music off, collection only, and music enabled with the same workload. Collector CPU time alone is not the effect on inference throughput.

## Diagnostic tools

[Defender Performance Analyzer](https://learn.microsoft.com/en-us/defender-endpoint/performance-analyzer-reference) requires an administrator recording session. Use an explicitly selected local trace path, reproduce one bounded phase, and stop recording. Analyze with `Get-MpPerformanceReport`. Traces remain private; do not add model/executable exclusions by default.

[Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon) can filter filesystem/registry activity to the selected inference process, descendants and cache paths. An optional-file lookup failure alone is not a bottleneck. Bound the capture and retain a sanitized summary separately.

[Windows QoS](https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service) can influence placement and power management. Record actual settings before considering any separately authorized change. No fixed performance penalty is assumed.

## NPU helper assessment

Use one actually supported helper model/runtime, with the same useful work and a quality target. Compare main model alone, helper at existing placement, NPU helper loaded idle, and NPU helper active. Record helper model/runtime/driver hashes, intended and observed operator placement, CPU fallback, cache state, memory, transfers/waits, helper latency/quality, main-model rate and complete-workflow time.

No NPU graph execution, full-memory access or speculative-draft compatibility follows from INT8 GEMM. Do not turn TOPS into token-rate predictions. If no useful helper task is present, adding one does not accelerate the same text generation job. Missing model/runtime or placement evidence means unavailable, not passed.

## Comparison record

The lab's local `windows_environment.compare(records)` requires 6–100 records with complete AB/BA pairs and exact keys: `pair_id`, `condition` (baseline/candidate), `order` (AB/BA), `recipe_sha256`, `model_sha256`, `runtime_sha256`, `uncached_verified`, `load_seconds`, `prefill_tps`, `ttft_seconds`, `generation_tps`, `task_seconds`, `task_success`. These are caller-supplied measurements; verify provenance against raw evidence. It rejects failed, cached-unverified, mismatched, duplicate or incomplete comparisons. Medians and observed ranges do not establish statistical significance or causality.
