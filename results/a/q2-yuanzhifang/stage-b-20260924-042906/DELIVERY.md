# Stage B delivery notes

Depends on unmerged Stage A Draft PR #40 and commit
`9d51da742723f87bb6264c51d1d06f8445b29977`. Stage B is a separate incremental
Draft PR, with the Stage A branch as base; no claim of final Q2 acceptance.

Evaluated code: `9b544ad28b9515f9ab53070d457774b1d8f65a58` for case002/008;
`e503e61daed67c97cb09629a6f315b14cae2cca1` for case044. Reporting and figures
were generated later from saved evidence and have their own source hashes.

The main entry is REPORT.md. metrics.csv and candidates.csv are generated from
the official outputs. Every unit ZIP preserves the complete original files;
evidence_manifest.json lists each archive/member byte size and SHA-256.
delivery_manifest.json covers the final report, figures, pause/controller files,
source-check receipt, tests and packages, excluding itself.

Original expanded experiment folders remain local and unchanged, ignored solely
to avoid duplicate trace storage. Private path prefixes in root/controller and
developer-test tracebacks are redacted in shared copies. Exact raw logs remain
outside all Git worktrees; redaction_manifest.json records raw/shared hashes and
the substitution rules. Shared sanitized logs are not byte-identical originals.
The nine official unit ZIPs remain unchanged. No credentials or private runtime
state are included.

Stage B consumed 122 calls; Stage A remains separately at 12. No further E0
was used for packaging, graph plots, verification or control tests. New control
validation under `control-validation/` uses dummy processes/mocked workers only,
and is labelled developer validation, not coordinator independent execution.

A later process-test rerun failed once with WinError32 during immediate stderr
cleanup (4/4 controller and 9/10 process checks passed). Both this failure and an
intermediate passing run with a ResourceWarning are retained. Delivery-only
commit e2b4c5ad76f2b8f3021f2442c03111ba3d3b2db2 adds bounded handle waits and
closure; final 4 controller and 12 process/ledger checks passed, including 12
forced-stop repetitions. It was not used for any official graph evaluation.
Finite regression success is not a universal file-lock guarantee.

Coordination receipt sources:
- Original Stage B authorization: Issue #33 comment 5802432056.
- Pause, correction and resume: comment 5802787468; explicit local coordinator
  review approved the fixed e503e61 continuation for the unspent three units.
- Captain alignment / Stage A still awaiting merge: comment 5802857567.

Metadata check: Windows has no dot_clean. Before final commit the specific
Q2 source, test, docs, paper and new result directories were scanned read-only
for `._*`, `.DS_Store` and `__MACOSX`; no residual metadata found. The final
post-write scan is included in the delivery verification workflow.
