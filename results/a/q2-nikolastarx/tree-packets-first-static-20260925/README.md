# Tree packets-first static candidate

This directory records one deterministic order intervention on062 k2/k4/k5.
Read `docs/a/q2-nikolastarx/TREE_PACKETS_FIRST.md` for proof scope and limits.

`check.py` constructs each cell once and records `report.json`, full plan and
full detail per cell. It verifies original/core-order acyclicity, unchanged
ownership/pieces/cut bytes, and the new raw memory peaks. Inputs, config, source,
runner and plans are fixed by SHA-256. The old FIFO bound agrees with the prior
trace diagnosis. No randomness; no E0/E1/E2 or official task compilation.

Run the command in `check.py` from the repository root. Existing evidence is not
overwritten. Function construction time excludes launch/read/write and is not
end-to-end solver latency. Lower bounds/raw peaks are not new official scores.
All three cells, including the k2 bound increase and k5 unchanged bound, remain.
