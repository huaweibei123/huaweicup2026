# Stage E-4 independent measurement

The frozen 100-case four-core batch finished within its original budget. All 100 cold solvers succeeded, but eight external E0 attempts timed out. The uniform algorithm's official full-100 arithmetic mean remains **null**. Its conditional optimistic full-100 mean is at most **3.0700749859830347**, below both the historical target 3.14 and the later user target 3.42710. This upper bound is a static certificate for these fixed outputs, not a measured score or a replacement for the eight missing results.

## Frozen identities and scope

- Solver: `311431da987f20158ad9453f5c0d558179aa9549`; runner: `76c22845b3f0127a06aeedffd70c6047afc75e65`.
- Exporter: `0a0627f382b0ce5238c6b4162bd6b82f318393a3`; static bound verifier: `710c3ee2636207ea07b24f92c8100d122c4d418f`.
- Official source aggregate SHA-256: `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; fixed config SHA-256: `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`.
- Evidence index SHA-256: `b685923cb63ca3d20a3eb5929df17dc731f619fa027beab67b5e45afd9ef782d`.
- Official cases 001–100, P1, k=4, in that order. All are exposed development data. No claim about held-out data, other core counts, real hardware acceleration, or the best algorithm across all team history.
- One new solver process per case reads the graph, constructs bounded factor4/trigger4096/chunk1024 and fork grain4/core-Task candidates, chooses strictly lower compute/gate plus mandatory-DDR proxy, writes its final plan and exits. Ties retain bounded. The proxy sum is neither an E0 prediction nor a Makespan lower bound. There is no online E0/E1/E2, Task compilation, training, plan lookup or case-specific exception.
- Selection counts: 81 bounded, 19 fork. Fresh-process timing includes both candidate constructions and all solver work through process exit. Cold interpreter does not imply flushed OS file caches.

## Actual calls and wall time

The parent's START followed P2's prior T1 at `2026-09-24T16:50:21.169583Z`. Actual batch T0 was `2026-09-24T16:56:00.338309Z`; actual T1 was `2026-09-24T17:14:10.325759Z`. The last solver exited at `17:14:09.309890Z`. T1 was sent to the parent immediately, before archival work.

| Measurement | Actual |
| --- | ---: |
| Cold solver calls / successful exits | 100 / 100 |
| New external E0 calls / successful results / timeouts | 15 / 7 / 8 |
| Historical exact-byte E0 reuse | 85 |
| Online E0, all E1/E2, retries, unrun cases | 0 |
| Batch wall | 1089.987851 s |
| Cold solver wall sum | 188.206677 s |
| Cold solver P50 / P95 / max | 1.226354 / 5.477677 / 9.883878 s |
| New E0 wall sum | 843.398437 s |
| New E0 successful / timeout wall sum | 122.153917 / 721.244521 s |
| Other batch work: evidence verification/copy/compression/logging | 58.382736 s |
| Execution preflight, outside batch T0–T1 | 7.312313 s |

P95 uses linear interpolation at `(n-1)*p`. Timeout wall can slightly exceed its 90 s limit while the supervisor terminates and collects the child. The frozen limits were 100 solvers, at most 100 new E0 calls, solver 30 s, E0 90 s, batch 1800 s, one worker and zero retries. They were not relaxed. Reused E0 has **zero new E0 calls and null current evaluation wall**; original timing is retained separately in its historical receipt and CSV column.

Windows 11 build 26200, AMD Ryzen 5 5600H, 12 logical CPUs, RAM 17,024,741,376 bytes, Python 3.12.14, no GPU. The interpreter was reused from the parent's locked environment; 14 installed packages passed `uv pip check`. The lock hash is `7b03fee57044ac272d8895533cbdca6d70a29d2da955f98a5552e72ef944fdc4`. OMP/OpenBLAS/MKL caps were 1. Actual process thread count and peak RSS were not sampled. No M5 Pro/Windows wall-time ratio is presented as solver speedup.

The machine was not exclusive. During this batch the user separately authorized parallel P2 production. The parent ultimately supplied the following actual intervals from P2 task reports, all on 2026-09-24 UTC:

| Other workload | Actual T0 | Actual T1 | Reported calls |
| --- | --- | --- | --- |
| P2 5C | 17:08:26.29728Z | 17:08:34.117251Z | stopped on its own ledger `os.replace` WinError5; reported not OOM |
| P2 k1 r6a | 17:08:56.910088Z | 17:14:11.239460Z | 33 solver + 33 E0 |
| P2 k2 r7a | 17:11:51.384154Z | 17:15:48.533995Z | 33 solver + 33 E0 |

These intervals intersect the E4 batch for a union of 321.235642 s, including 138.941605 s with two reported P2 workers while E4 retained one worker. Twenty-nine E4 child processes have confirmed overlap; the overlapping E0 timeout cases are 076/079/091. The first five E0 timeouts, including014/041, precede the supplied new parallel windows. No timeout is causally attributed to another job and no wall time is corrected. No P2 live ledger was read. The original [coordination.json](coordination.json) and [resource-overlap.csv](resource-overlap.csv) preserve the earlier incomplete timing information; the authoritative timing addendum is [coordination-addendum.json](coordination-addendum.json), with all 115 E4 child processes crossed against the three reported windows in [resource-overlap-confirmed.csv](resource-overlap-confirmed.csv). These reported batch windows do not constitute exhaustive host monitoring or a peak-RSS measurement.

## Observed quality and every changed result

| Quality aggregate | Value |
| --- | ---: |
| Uniform algorithm official full-100 mean | null (92/100 available) |
| Success-only 92-case mean | 2.9842663585904123 |
| Captain bounded mean on the exact same 92 cases | 2.8632483008100937 |
| Captain bounded audited original full-100 mean | 2.9490823179997054 |
| Wins / losses / ties / unavailable versus captain | 10 / 1 / 81 / 8 |
| Portfolio extra DDR, available 92-case sum | 1,177,578,376 bytes |
| Captain extra DDR, same 92-case sum | 961,412,248 bytes |

Means are arithmetic means of each official singlecore denominator divided by that case's multicore Makespan. The 92-case mean is not comparable as a full-100 score to the screenshots or captain's full-100 mean. Quality improvements can increase extra DDR; neither the failed cases nor the DDR tradeoffs are removed from the report. Historical best-of-two/full-history averages are not substituted for the uniform algorithm.

| Case | Result | Captain cycles | Portfolio cycles | Captain extra DDR bytes | Portfolio extra DDR bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| 003 | win | 539155 | 273956 | 294912 | 8231106 |
| 016 | win | 7715523 | 3241338 | 0 | 119555344 |
| 024 | win | 2555343 | 1072818 | 0 | 39327448 |
| 030 | loss | 700342 | 702148 | 10404864 | 8232960 |
| 039 | win | 395323 | 368961 | 17604608 | 14536704 |
| 047 | win | 326508 | 198032 | 0 | 4838778 |
| 051 | win | 607628 | 254308 | 0 | 9045350 |
| 075 | win | 1441809 | 656348 | 0 | 11605112 |
| 080 | win | 111314 | 91774 | 4190208 | 2666496 |
| 082 | win | 721041 | 300381 | 0 | 5521260 |
| 085 | win | 3187899 | 1119721 | 0 | 25100162 |

Case030 regresses by 1,806 cycles while using fewer extra DDR bytes. All 81 ties are bounded selections with identical plan bytes and official quality. The complete per-case table, including current and historical evaluation timing separately, is [comparison.csv](comparison.csv).

## Eight incomplete cases and target certificate

All eight failures occurred in external E0 after a successful solver exit and retained final plan. Each received exactly one 90 s E0 attempt; none was retried or declared illegal merely because of timeout.

For a missing case, let `L = max(task_gate_lower_bound_cycles, boundary_ddr_service_cycles, global_pipe_work_lower_bound_cycles)` for its **chosen fixed plan**. All eight are dominated by the task-gate bound. The selector's gate-plus-DDR **sum is not used**. If the fixed plan ultimately has a legal finite E0 result, its speedup is at most `official_singlecore / L`.

| Case | Singlecore cycles | Task-gate LB | Mandatory-DDR LB | Global pipe-work LB | Speedup upper bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| 014 | 17698626 | 4323756 | 658834 | 4306437 | 4.0933452304 |
| 041 | 6003957 | 1483532 | 316843 | 1473810 | 4.0470694262 |
| 058 | 4539717 | 1094016 | 381948 | 1089742.5 | 4.1495892199 |
| 062 | 2854809 | 768676 | 225553 | 654600 | 3.7139301865 |
| 072 | 23897828 | 5796056 | 730466 | 5732023.5 | 4.1231188933 |
| 076 | 6185113 | 1517152 | 266110 | 1515411 | 4.0767919101 |
| 079 | 31052251 | 7356096 | 340200 | 7356096 | 4.2212949641 |
| 091 | 9186769 | 2279678 | 448025 | 2245340 | 4.0298537776 |

The 92 observed speedups sum to 274.5525049903179. Adding the eight optimistic ratios and dividing by 100 gives **U = 3.0700749859830347**. Exact rational arithmetic, raw term identities and plan/diagnostic hashes are in [target-upper-bound.json](target-upper-bound.json). U is 0.0699250140 below 3.14 and 0.3570250140 below 3.42710. Therefore this frozen algorithm cannot reach either target even under these optimistic missing-case outcomes. This conclusion does not require another E0 call; it does not establish eight legal results or an official mean, and it does not constrain a different algorithm.

The later 3.42710 is a user-provided external target, not an independently verified opposing-team score. The original frozen protocol retained 3.14. [target-comparison.json](target-comparison.json) also preserves the weaker arithmetic necessary-condition check made before the bound: the missing eight would need mean speedup 4.9309368762 or 8.5196868762 respectively. Those required values alone are not feasibility claims.

Static verification read only these eight graphs and existing plans, re-ran the frozen read-only gate and boundary functions, and matched all diagnostic values. It checked every pinned solver/official source hash and every denominator/result artifact used in the arithmetic. It did not construct a candidate, compile a Task, invoke E0/E1/E2, or scan all 100 graphs. The successful static pass took 20.147445 s. The Task bound follows one in-flight op per pipe, original local compute paths without contracted COPY bridges, official Task dependencies, and serial-core waits. Mandatory COPY predicates and unit shared-DDR service follow the unchanged official scene-A source. Bounds combine by maximum because resources can overlap.

## Evidence, validation and reproduction

[run/protocol.json](run/protocol.json), [run/completion.json](run/completion.json), [run/events.jsonl](run/events.jsonl), and each case's `run.json` preserve actual launch/exit/timeout receipts. Each fresh plan and diagnostic remains archived. Successful E0 result/trace originals are compressed losslessly with raw and stored hashes. Failed E0s retain stdout/stderr and failure receipts; missing results are not fabricated.

The initial read-only evidence audit verified 109 historical plan/result/trace/run sets and all 100 fixed singlecore denominators in 8.350397 s with no scoring. Captain k4 sources are `ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9` (99 cases) and `4d374dc25b5698491ddbb92837789a23a4ad3102` (case014). Stage C fork sources are `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` (nine available k4 cases). Exact plan byte comparison, graph/config/official identities, original trace endpoint/result agreement, raw/stored hashes and original success receipts are required before reuse. New solver time is always measured again. No JSON normalization or semantic-equivalence reuse is permitted.

The independent exporter checked 100 records, all available artifact hashes, all 92 successful result/trace/plan/run sets, all eight failures and all 100 denominator originals. Its only post-run code correction copies authoritative Git singlecore receipts into this byte-preserving result directory; a CRLF-translated shared checkout is not treated as byte-identical. The runtime runner/solver stayed fixed. The bound verifier's initial development check stopped on integer Task keys versus their JSON string representation; the correction affects only diagnostic value comparison and never normalizes plan evidence. All these postprocessing attempts made zero scoring calls.

[readback.json](readback.json) and [independent-checks.json](independent-checks.json) record raw readback and all 100 strict-selection-rule checks. Both [local board precheck](board-precheck-local.json) and [fixed-Git board precheck](board-precheck-fixed-git.json) passed with 100 records, 92 eligible and eight preserved timeout records. The fixed artifact commit is `739b6ad17bbdc3761e2467cb286005669a6a9a49`; 371 fixed blobs were read through the unchanged board schema/`validate_feed`/`Ledger` rules in 13.284804 s. The original CLI's per-file Git spawning did not finish within an outer 120 s validation deadline. The dedicated verifier uses one read-only `git cat-file --batch` process instead, with the same path/size rules and a temporary ledger beneath the supplied task-specific temporary root. It makes no production write. Validator source/schema checkout differences were verified as CRLF/LF only with both hashes retained; no measured evidence is normalized. These static checks are not solver/E0 retries. Format eligibility is distinct from complete scientific acceptance. The feed is [board-feed-stage-e-4.json](board-feed-stage-e-4.json); no central production board or website was modified by this benchmark subagent.

The actual run used the parent's verified interpreter and graph directory supplied as command arguments. Repository-relative source and result locations are portable. Reproduction entry points, requiring a new separately authorized measurement directory/budget for any scoring run, are:

```text
python -X utf8 -B src/q1_yuanzhifang/benchmark_e.py --graphs <verified-official-data> --execute --window-token <coordinated-START>
python -X utf8 -B src/q1_yuanzhifang/export_e.py
python -X utf8 -B src/q1_yuanzhifang/verify_e_bounds.py --graphs <verified-official-data>
python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-e-4-20260925/board-feed-stage-e-4.json --submission
python -X utf8 -B src/q1_yuanzhifang/verify_e_git.py --commit <artifact-commit> --feed results/a/q1-yuanzhifang/stage-e-4-20260925/board-feed-stage-e-4.json --temp-root <task-temp-root> --output <new-verification-receipt>
```

Outputs use exclusive creation; these commands are not a request to overwrite or rerun this completed batch. The board precheck also supports `--commit <artifact-commit>` for fixed-Git evidence verification. [Delivery checks](delivery-checks.json) include unchanged raw Git object bytes for all 1,195 fixed result files except this updated README, scope/syntax/link checks, file sizes and a clean metadata scan. `dot_clean` is unavailable on Windows. [Validation development](validation-development.json) preserves the static-check stops and their fixes. No paid CI, GitHub Actions, additional core count, or follow-up E0 batch was started.

## Paper-ready scoped statement

在全部 100 个官方公开图的四核开发集上，冻结的双构造选择器每例均以独立冷进程重新生成两种候选方案，100 次求解全部成功，端到端求解时间中位数为 1.226 s、P95 为 5.478 s、最大为 9.884 s。依照严格字节身份复用 85 例历史官方 E0 结果，另执行 15 次官方 E0，其中 7 例成功、8 例在本轮 90 s 预算下超时。在有正式结果的同一 92 图集合上，逐图单核基线与多核 Makespan 比值的算术平均为 2.984266，固定队长基线为 2.863248；逐例比较为 10 胜、1 负、81 平，且部分改进增加了额外 DDR 搬运量。全 100 图正式均值尚不可报告。对八个未完成复评的固定计划，以计算及任务门控下界、强制边界 DDR 服务下界和全局流水线工作量下界的最大值进行静态核验；若这些计划最终合法，则完整均值不超过 3.070075，因而本冻结方法无法达到 3.14 或 3.42710 目标。实验后段存在同机 P2 资源重叠，实测墙钟不构成独占资源或跨硬件速度比较。
