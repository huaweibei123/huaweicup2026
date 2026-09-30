# Q2 stage A checks

`python -B -m unittest discover -s tests/q2 -p test_*.py -v` checks real Windows
working-set sampling, timeout reaping, resource-limit reaping, fail-closed
sampling, no-launch checks and durable reservation limits. It invokes **zero**
official Q2 evaluations. Children only print/sleep; injected memory readings
exercise control paths without allocating dangerous amounts of memory.

`fixtures.py` contains readable synthetic graph definitions. Scientific checks
are performed by the bounded `src.q2.stage_a` command documented in
`docs/a/q2/STAGE_A.md`; those count toward the twelve-call authorization. This is
not an unrestricted regression suite to rerun outside the allotted budget.
