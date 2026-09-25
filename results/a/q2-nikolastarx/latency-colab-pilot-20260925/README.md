# Colab CPU latency placement pilot

## Completed result

The capsule and result ZIP bytes were retrieved and verified. All three cold constructions and unmodified official E0 calls completed on a 2-CPU Colab Linux x86_64 runtime (Python 3.13.15). Experiment batch wall was 14.197 seconds. The runtime has been stopped; no local evaluator or native E2 was run.

| Case / cores | Previous c665 E0 | New candidate E0 | Makespan reduction | Old → new cross-core transfer pairs |
|---|---:|---:|---:|---:|
| 005 / 5 | 33515 | 33292 | +0.665% | 728 → 647 |
| 009 / 5 | 51905 | 47018 | +9.415% | 751 → 664 |
| 015 / 5 | 40828 | 45139 | −10.559% | 0 → 120 |

This compares a cold gap+latency-cut+retime candidate with c665's selected complete plan, not with an independently scored identical gap seed; it does not isolate the causal contribution of latency weights. In 015 the new candidate introduced cross-core transfers that the old selected plan avoided. The proxy reduction does not establish a Makespan reduction. Do not replace the existing constructor unconditionally, choose per-case historical winners, extrapolate these three cells to a full score, or change the current certified full500 means. A future frozen online candidate-selection rule needs independent full500 validation.

[report.json](report.json) contains exact hashes and per-stage costs; [capsule-manifest.json](capsule-manifest.json), [capsule.zip](capsule.zip), and [results.zip](results.zip) preserve the actual fixed inputs/source and raw outputs. Source is 1c00079aadbd071de62db17686d5ba3fed1da0f2; remote runner is 17f0e203bc51506321f4f1157213782eb795bd95. Downloaded result ZIP SHA-256 is fa417f834b79e7f3cb3d4c06432043acafcb91199615f2ae4da31eac7d01c098. The local audit checked artifact hashes, manifest equality, terminal child process receipts, graph identity and plan legality without rerunning E0.

Allocation, CLI repair, upload and download times and CU cost were not instrumented and are excluded from batch_seconds; they are not claimed to be free or hidden inside a reported end-to-end solver speedup. `launch.py` and `environment.py` preserve the actual remote driver and initial environment probe.

Infrastructure owner supplied Google's pinned jupyter-kernel-client fork f18e982c3265df5e923aa9def101ab3fd737e139 in an isolated local import overlay. A process-specific PYTHONPATH successfully enabled remote `colab exec`; the shared CLI installation was unchanged. The alternate raw TTY was cleanly detached before the actual experiment. The original failed exec and first missing-file upload dispatched zero remote evaluations.

The shared local evaluator window is occupied. This separate E0-only three-cell mechanism experiment uses a standard Colab CPU runtime and cold graph-driven construction, with no macOS native E2 binary, historical plan seed, GPU or high-memory request. Fixed cases: 005/009/015, five cores; fixed region width 16. One worker, at most three constructions and three independent official E0 calls, zero E2, zero retries, 60 seconds per stage, 360 seconds per batch, 4 GiB observed process-tree RSS. A failure stops further cells.

The capsule pins all solver sources to commit 1c00079aadbd071de62db17686d5ba3fed1da0f2 and every official source/input to the frozen source manifest. Its separate manifest records file SHA-256 values, runner commit and the previous c665 official comparison values from the completed full500 audit. Source/runtime setup costs and experiment wall are separate. The runner checks the entire capsule before any construction. This is a partial mechanism test; it does not update the frozen c665 algorithm or constitute a full500 score. Different-host wall times cannot establish a speedup over macOS.

Initial CLI observation: google-colab-cli 0.7.2 allocated the standard CPU runtime, but `colab exec` failed locally because its pinned jupyter-kernel-client 0.8.0 lacks JupyterSubprotocol. No remote candidate/evaluation ran from that failed command. The CLI's documented raw TTY console is a separate connection path. No global package was modified.
