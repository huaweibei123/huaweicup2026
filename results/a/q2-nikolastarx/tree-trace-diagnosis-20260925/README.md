# Existing tree062 trace diagnosis

Read `docs/a/q2-nikolastarx/TREE_TRACE_DIAGNOSIS.md` for conclusions and limits.

- `diagnose.py`: reads frozen graph, three saved plans/details/results/traces;
  verifies every op time; computes candidate-specific FIFO lower bounds and
  recorded-duration tight paths. No solver/official compiler/evaluator imports.
- `core_idle.py`: unions all recorded Pipe intervals to establish actual whole
  core idle windows; does not count trailing idle after a core finishes.
- `report.json`: source/input/script hashes and principal bound table.
- `062-k*-diagnosis.json`: all core/Pipe work/idle, packet spans, cross transfers.
- `062-k*-paths.json`: complete op-level longest-path witnesses, with timestamps.
- `core-idle.json`: all-Pipe idle windows.

Run the commands in the scripts from the repository root. Output files reject
overwriting existing evidence. They analyze only existing result bytes; no new
plans or scores are produced. No randomness/seed or solver/evaluator calls.
