# P1 v4: make frontier packing available on all multicore graphs

The v1–v3 controller only tried Fang's frontier construction when there were
fewer compute components than cores and at least one fork. That condition is
not required by the construction. Without forks, fork rank is zero, serial
chains still contract, and frontier packing can choose a different assignment
using pipe work and shared inputs. An in-tree without a fork can also expose a
useful frontier. No case identifier or recorded result is used to select it.

V4 preserves every v3 candidate attempt and its order, then attempts frontier
packing last if the old route has not already attempted it. Earlier failures
and byte-duplicates count as attempts, so F is never retried. Exact plan-byte
deduplication and the first-score-failure rule remain unchanged. A failed extra
score therefore preserves the earlier checked winner. Single-core construction
still emits only the bounded plan and never calls E1.

The maximum distinct count is six by direct route counting: B, H, O, at most
one old shared/F route, return R, and at most one newly appended F. If the old
route was F, no extra F is appended. This bound does not depend on assumptions
about component shape or two candidates being equal. The shared candidate and
E1 worker-lifetime constant is six. Existing 60-second E1 request and 10-second
startup limits, one worker and zero scoring retries are retained. The new
variant is `structural-six-plan-general-frontier-v4`.

The cache change reuses successful B/S/H constructions within one call. It
does not cache failures or alter the individual constructors' direct outputs.
The narrow 12-chain prefetch template and the negative split-core construction
are not included. This is a fixed small family of graph-derived constructions,
not a sweep over parameters. Six candidate scores are a larger online budget
than v2/v3; fewer repeated constructions alone do not establish a wall-time win.

Validation: 43 synthetic unit tests pass, including varying disconnected
chain width/depth, legal coverage, all-six-route accounting, deduplication,
first scoring failure, and not retrying a failed old F attempt. These are
development fixtures, not a held-out performance set. No real v4 solver or
E0/E1 run has occurred. Formal quality and runtime claims remain those of v1.

Next proposed bounded development probe: 039/k4 and 080/k4 (the missed-domain
diagnostic examples), 084/k5 (preserve the known return improvement), and
008/k5 (guard a known return regression). At most 4 solver, 24 E1 and 4 external
E0 calls, zero retries. This targeted check can reject a bad integration; it
cannot establish generalization or replace a frozen full500 run. Dispatch
requires fixed source/manifest and a resource window, as usual.
