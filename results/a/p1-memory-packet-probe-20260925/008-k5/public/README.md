# MEM response probe: P1 008/K5

One constructor followed by one official E0, in separate windows. This is the first real full-graph numeric check for this MEM model and only validates this exact plan. It is not full-matrix evidence or an algorithm-wide equivalence claim.

The model predicted quotient Makespan 114352, scheduled DDR 5,419,224 B, extra DDR 2,764,800 B, spill 0. Official E0 returned the same values exactly. The DP score 114452 includes the 100-cycle gate; the quotient replay and E0 Makespan are 114352. The old restricted-subdomain quotient Makespan was 134736 (its DP score including the 100-cycle gate was 134836). The v4 K5 reference Makespan is 100603, so E0 M=114352 is a 13.66659% regression against that five-core result. The separately archived official single-core baseline is M=487605 and is not the denominator for that comparison; this candidate is not accepted for production.

Solver CLI wall was 2.361198 s (including model and Task compilation); separate E0 wall was 0.140526 s. Calls: 1 constructor, 1 E0, 0 E1/E2/retries; 1727 Task compilations, 557 cache hits, 0 rejected states.

Frozen solver source commit `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c` (`src/q1/memory_packet_probe.py`). E0 source version is tied to the same frozen worktree HEAD through the tracked source manifest and exact official code aggregate SHA `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`; entrypoint SHA is recorded in the E0 receipt. Input, plan, diagnostics, result/trace, receipts and baseline hashes are in `manifest.json`.
