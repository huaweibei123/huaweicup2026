# P1 Stage B: frozen structural switch, Windows, 2026-09-24

All eight planned candidates passed unchanged official E0. The structural switch wins on two graphs and loses on two; it is not a universally better replacement for fixed64. All positive and negative results are in the feed. This is a new, separately frozen public development panel informed by Stage A, not a held-out test or a continuation of its spent budget.

1. **Goal**: test `structural-switch` against the original fixed64-propose on 019/048/071/080 at k=4. The switch counts graph weak components, selects component-pack when count >= k and chain-wave otherwise. No measured score is queried online. Scope and authorization: [Issue 98](https://github.com/huaweibei123/huaweicup2026/issues/98), [Stage B task card](../../../../tasks/a/Q1-RESEARCH-YUANZHIFANG.md).
2. **Inputs**: source `50263673b6c40f5978e8d00afa90cc10ffffbbd1`, baseline `4dff90ef699fd51845cf482951e8477066f5f566`, runner/exporter `467e99b94574a35c8fea8a22c895e9eb0bb27af4`. Graph/config/ten official code hashes were verified before launch and are recorded in `protocol.json`. The existing matching official singlecore results are reused, with zero new singlecore evaluations.
3. **Outputs**: eight independent attempt directories preserve plan, full original result and trace in lossless gzip, official text log, complete process stdout/stderr, diagnostics and actual run receipt. `comparison.csv`, `summary.json`, and `board-feed-20260924T143000Z-stage-b.json` derive solely from those bytes. The selected branch is recorded both in each switch diagnostic and feed `parameters.selected_variant`.
4. **Limits and cost**: frozen maximum 8 solver + 8 external E0, 0 E1/E2, one serial worker, 20 s/40 s timeout, 300 s batch cap, no retry. Actual: 8+8, all successful, no failures/timeouts/retries; T0 `2026-09-24T14:28:54.726069Z`, T1 `2026-09-24T14:29:23.323232Z`, 28.597459 s including per-attempt preservation. Parent relayed P2 T1 14:19:42.107062Z and P3 T1 14:24:21.238255Z before releasing the window; `coordination.json` explicitly distinguishes their reports from our observation. No claim of full host isolation.
5. **Checks**: fixed source/input checks, AST parse, four-core plan contract, 8/8 actual E0 exit 0, result scene/core/value/type checks, lossless compression checks, and local board `valid=true / eligible=8`. Fixed Git evidence precheck is recorded in `precheck-fixed-commit.json`. `.gitattributes` preserves actual Windows plan/log bytes rather than normalizing their line endings. Metadata scan found no `._*`, `.DS_Store` or `__MACOSX`; `dot_clean` unavailable on Windows.
6. **Delivery**: same independent branch `codex/q1-wave-benchmark-yuanzhifang-20260924`, producer `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`. Parent coordinates interpretation, PR and central owner registration. The board's source registration, received/visible state, independent rerun and scientific acceptance remain separate from this local eligibility check.

| Case | Chosen branch | fixed64 cycles | switch cycles | Cycle change | fixed64 / switch solver seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| 019 | component-pack | 73284 | 24099 | -67.12% | 0.714634 / 0.570151 |
| 048 | chain-wave | 226990 | 362034 | +59.49% | 0.864376 / 3.438304 |
| 071 | chain-wave | 21586 | 43499 | +101.51% | 1.299074 / 0.752704 |
| 080 | component-pack | 354762 | 91774 | -74.13% | 1.051024 / 0.460620 |

048 has 692 Tasks/250 levels, versus 27 fixed64 Tasks, and extra movement grows from 706372 to 3182926 bytes. 071 has 112 Tasks/30 levels versus 12 Tasks, and extra movement rises from 586698 to 1060008 bytes. These are observed mechanism diagnostics, not a proof that a single feature explains the entire cycle difference. On 048 the switch is worse in both cycles and measured solver wall. On 071 it is faster but produces worse quality. A mean alone would hide these regressions.

For completeness, mean per-case official singlecore/current ratios (n=4/100) are 0.946540887 for fixed64 and 1.899770671 for the switch. They are arithmetic means of ratios, not ratios of sums or full-100 scores. Solver P50/P95/max seconds are 0.957700/1.261867/1.299074 and 0.661428/3.035464/3.438304; P95 linearly interpolates at 0.95*(n-1). One trial per method, no repeated latency validation.

The same independently synced Stage A Python 3.12.14 environment is reused (Windows, AMD Ryzen 5 5600H, 12 logical CPUs, 17024741376 bytes RAM, no GPU). Initial dependency installation reported 43.79 s once before Stage A; no new dependency install, training, compile, or graph-specific offline work for B. Peak process RSS is unknown and marked as such. Cold start means a new interpreter process, not flushed OS caches.

Solver wall includes launch, imports, graph/config reading, graph analysis, selected construction, official local Task compilation for fixed64, structural checks, final plan/diagnostic writing and process exit. External E0 wall separately includes CLI launch and full result/trace/log creation. Neither constructor uses a full online E0/E1/E2 scoring call. Makespan remains simulated cycles, not these measured seconds; the official 5–10 minute recommendation is not a hard 600-second elimination rule or an efficiency target to stop at.

Reproduction uses a fresh worktree with an absent Stage B output directory and the fixed sources above. Set the two variables to a clean baseline checkout and verified graph directory:

```powershell
uv sync --locked
uv run python -X utf8 -B src/q1_yuanzhifang/benchmark_b.py --baseline-root $BASELINE_ROOT --graphs $GRAPH_DIR
uv run python -X utf8 -B src/q1_yuanzhifang/export_b.py --output results/a/q1-yuanzhifang/stage-b-20260924/board-feed-NEW-UNIQUE.json
uv run python -X utf8 -B src/q1_yuanzhifang/export_b.py --report-only
uv run python -X utf8 -B src/benchmark_board/protocol.py results/a/q1-yuanzhifang/stage-b-20260924/board-feed-20260924T143000Z-stage-b.json --submission
```

The runner is a new scoring operation and needs a separate authorized budget; do not rerun for evidence verification. The last command, optionally with `--commit <full artifact SHA>`, only validates existing bytes. Report-only derivation also makes zero solver/evaluator calls and refuses existing CSV/summary files. No further batches were launched.
