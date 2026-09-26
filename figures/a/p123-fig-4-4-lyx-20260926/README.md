# Figure 4-4 delivery

This directory contains the independent redraw requested for P1 multicore average speedup and per-case distribution.

- Source table: `results/a/p123-full500-lyx-20260925/per_case.json`
- Source SHA-256: `074bfa55b25acb60504780ff3107f9c28fef3ba58ef750bee1bbb0996fb9cdfc`
- Algorithm commit: `a0537aeb72dc702af86d67d3194587d581ac207c`
- Run: `20260924T1952Z-s59ee`
- Coverage: 100 cases x 5 core counts (500 cells)
- Git blob source SHA-256: `122da1335cf8f70e3db472ff84270cb3fc17690fcb3200607555c9dad7545847`; Windows working-copy SHA-256: `074bfa55b25acb60504780ff3107f9c28fef3ba58ef750bee1bbb0996fb9cdfc`
- Target paper width: 165 mm; layout inspected at that width.
- Reproduce: `uv run python src/analysis/p123_fig44_lyx/plot_fig44.py`
- Outputs: `fig44_p1_speedup.png`, `fig44_p1_speedup.svg`, `fig44_p1_speedup.pdf`

The main k=1 point is fixed to the prescribed value 1.0. The observed single-core ratios are retained separately in `metrics.csv` and `summary.csv` for audit. No solver or evaluator was invoked.
