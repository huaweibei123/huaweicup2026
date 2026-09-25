# Existing full100 K5 trace diagnosis

The script reads and hash-checks all 100 official result artifacts from the
completed c665 full500 batch. It computes per-core M/V busy cycles and the
union of COPY_IN/OUT intervals without running a solver or evaluator.
Input hashes, per-case output hashes, complete coverage and scope are in
`report.json`.

The high-relaxation-gap group has mixed behavior. For example 005, 086 and
088 have COPY-active intervals covering roughly 85–91% of Makespan, while
their busiest M core is active for only about 39–43%. This supports testing
general communication-reducing ownership changes, alongside load balance,
rather than focusing only on the nine recognized templates. It does not
prove COPY work is the critical cause or that any particular move improves
Makespan. COPY-active union is not measured DDR bandwidth utilization.

Use these traces to choose mechanism experiments; do not encode case IDs or
historical winners into the online solver. New full-grid scores still require
one frozen algorithm, input protocol and selector across all cases/cores.
