# Existing-plan consistency evidence for the P1 plan bound

The standalone bound at `f77744fb07b9c854c5cd3f8a80432aacc056849a` was applied once to all 500 already saved selected v1 plans. There were no new plan constructions, solver runs, or E0/E1/E2 calls. The source data and per-record identities are in `audit.json`; a separate zero-evaluation readback matched all 500 identities and Makespans against the fixed source feed, with no duplicates or missing cells.

No lower bound exceeded its recorded official Makespan. This is a consistency check, not a proof over unseen inputs, global optimality, or evidence that candidate pruning speeds up the complete solver. The mean bound-to-Makespan ratios for K=1..5 are 0.8402705, 0.8529324, 0.8534225, 0.8450345 and 0.8345672.

The original read-only audit took 38.116 seconds for its full loop, including file reads, JSON parsing and hashing. The 0.07623 seconds per record must not be interpreted as isolated bound-function latency. Setup before the timed loop is excluded. The 60-second audit deadline was not reached.

`audit-original.py.txt` preserves the exact locally executed script as provenance, not an installed CLI: it was located at `output/p1-unified-control/plan-bound-v1-audit.py` and expected a particular relative worktree plus the already available data checkout. It retains a graph cache; its memory footprint was not independently measured. Re-running from a different layout requires resolving those two roots. No portable CLI or Windows execution is claimed. The algorithm itself and its hand-computed tests live in `src/q1/plan_lower_bound.py` and `tests/q1/test_plan_lower_bound.py`.
