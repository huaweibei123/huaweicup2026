# P2 certified pruning follow-up — official E0 results

Frozen solver: `405024df0532b72e916306399278d5ad6c2413c7`; execution runner: `1c663e275b632cbdae73829a2b3310633362ab91`.

Comparison data: `5e5d688ca473a80b7d72b26b397ce568ac70f534`. Original first-batch plan/result bytes are read directly from that Git commit.

UTC 2026-09-24T14:24:54.492160Z to 2026-09-24T14:25:09.774208Z; execution batch wall 15.282048875 s before compression/export.

Actual calls: 6 fresh solver processes, 18 online E0 and 6 independent final E0, E1/E2=0. Online calls fall 24→18 (25%); total including confirmation falls 30→24 (20%). Unused six-call allowance is not transferred or spent. No retry, failed execution, timeout, or duplicate skip.

All 24 proposal plan bytes match batch one. All 18 executed candidate result bytes and all 6 final complete result bytes match batch one; final plan bytes match in 6/6 cases. No new solution-quality or holdout claim is made. The six bound-pruned candidates retain their plan and certificate, with no fabricated E0 result.

| Case | Final Makespan | Actual strategy | Online E0 | Pruned | First solver s | Pruned solver s | Final E0 s |
|---|---:|---|---:|---:|---:|---:|---:|
| 002 | 72795 | chain_critical | 2 | 2 | 1.389680 | 0.608574 | 0.297893 |
| 008 | 63768 | resource_word | 4 | 0 | 0.768711 | 0.702394 | 0.218089 |
| 044 | 66901 | pipe_ready | 4 | 0 | 0.764710 | 0.750591 | 0.231685 |
| 064 | 16615 | pipe_ready | 4 | 0 | 0.704884 | 0.688806 | 0.172661 |
| 051 | 207134 | chain_critical | 2 | 2 | 0.946559 | 0.515371 | 0.249019 |
| 016 | 2556787 | chain_critical | 2 | 2 | 20.745567 | 6.032934 | 3.565557 |

| Pruned case / candidate | Assigned-pipe bound | Successful incumbent |
|---|---:|---:|
| 002 / affine_eighth | 240000 | 72795 |
| 002 / guarded_reentry | 240000 | 72795 |
| 051 / affine_eighth | 607080 | 207134 |
| 051 / guarded_reentry | 607080 | 207134 |
| 016 / affine_eighth | 7714975 | 2556787 |
| 016 / guarded_reentry | 7714975 | 2556787 |

Bounds were independently recomputed from original non-COPY integer cycles and submitted group/core ownership for all 24 plans. Each skipped bound is at least the prior successful incumbent, while each measured result is no smaller than its bound. This numerical check supports the frozen proof on these cases; the general proof remains in PRUNING.md. The old official scores for skipped proposals appear only as explicitly labeled first-batch references in verification.json.

Wall times measure subprocess startup through observed exit and cleanup, including all online official scoring; independent final E0 is outside solver wall. Target RSS sampling is 50 ms with ps/cleanup overhead. This is an observed concurrent-machine comparison, not an isolated causal speed benchmark. Fresh interpreter processes are used but OS caches are not flushed. No Colab/GPU run occurred.

Machine: Apple M5 Pro, macOS 27 arm64, 48 GiB RAM, Python 3.12.13, one worker. Limits remain 60 s/E0, 240 s/solver, 1200 s/batch, observed 4 GiB RSS including observer. Descendant monitoring and cancellation follow E0 processes that create separate sessions. Sampled peaks can miss short spikes; all own process trees exited without survivors.

All 48 compressed result/trace JSON files round-trip to recorded original hashes; official files are unchanged. 18 stdout informational checkout prefixes are replaced with `${REPO_ROOT}` in shared copies, with raw/derived hashes in stdout-redaction.json and raw originals retained outside Git. Full plan/result/trace bytes are not redacted.

board-feed.json uses six end-to-end portfolio records with new variant `e0-protected-four-constructors-bound-pruned`, new run/attempt identities, actual frozen solver and runner sources, and verified existing official singlecore denominators. Producer-side read-only precheck: 6 records / 6 eligible. No central import, push, PR, mirror sync or scientific acceptance is claimed by this worker.
