# Historical integration artifact: provenance incomplete

The original local file `failure.json` is preserved byte-for-byte. Despite its
filename, the embedded status is `ok`, engine `p1-exact-batch-v1`, and reported
Makespan 269157. It is **not** established evidence of a failing case or a new
benchmark result.

- Original byte length: 2,515,196.
- SHA-256: `68ee276cc368113bc9b48f7cf20ae0f0bb0d6da82f3d7b40fb4dac82b3767cc3`.
- Embedded official code hash:
  `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`.
- Missing/recovery pending: actual graph and plan identities, executed source
  and runner commit, complete argv, measurement UTC, and interpretation of the
  old filename. Filesystem mtime is not substituted for execution time.

This archival step performs zero solver/E0/E1/E2 calls. The file is excluded
from the board feed, quality comparisons, timing claims and scientific
acceptance until provenance is recovered. Raw operation timelines and engine
diagnostics may help a future source investigation. No values were corrected
or relabeled to make them eligible.
