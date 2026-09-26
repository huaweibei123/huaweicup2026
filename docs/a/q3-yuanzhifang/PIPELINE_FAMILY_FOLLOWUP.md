# Pipeline family missing-cell followup (2026-09-25)

The first frozen six-case batch stopped after 044/046 completed cold construction
and official P2. Its runner incorrectly required the official P2 result to
contain `problem: 2`; P2 has no `problem` field. The original failed batch,
receipts, feed and source commit `ba3f848492b213d5f3ec93cf12b0da0cc79eea8f`
remain unchanged. This followup fills only the missing cells and retains the
same candidate `pipeline_stages.py` at
`6bae8dfa317bc71226068344b59dd65d2612c32b`.

The new output is `results/a/q3-yuanzhifang/pipeline-family-followup-20260925`
with run ID `yuanzhifang-q3-pipeline-family-followup-20260925`.
044 and 046 reuse their old plans, cold receipts and full P2 result/trace/log
archives after comparison with the fixed source commit and both compressed and
raw SHA-256 values. Their only new call is P3. Cases 067, 073, 083 and 092
each receive one new cold construction followed by P2 and P3. Thus the cap is
four new cold calls and ten new external E0 calls. There are no E1/E2 calls,
historical control reruns or retries. The old 044/046 cold wall time is shown
as historical timing in their P3 rows; `measurement.calls.solver` is zero.

The two workers, 2 GiB available RAM and 2 GiB free disk checks, Windows below
normal process priority, 30-second call limit, 270-second dispatch cutoff and
300-second total cap match the first batch. Each case runs its new calls in
order. A first failure stops new dispatch and preserves completed evidence.

Before execution, commit the new runner, exporter and this note, then run:

```powershell
python -B src/q3_yuanzhifang/pipeline_family_followup_benchmark.py --check-only
```

That check verifies source commit bytes, official input/config/code hashes,
source command and call receipts, the two complete P2 artifacts, fixed hardware
parameters and positive P2 Makespan. It also checks an archived P2/P3 header
pair: P2 is accepted without `problem`; P3 requires `problem: 3` and
`cache_mode: read_only`. It performs no build, derive, Step or E0 call and
creates no run directory.

The coordinated actual run requires `--concurrent-work` with the true host
workload declaration. Export only after the run ends:

```powershell
python -B src/q3_yuanzhifang/pipeline_family_followup_benchmark.py --concurrent-work P1+P2
python -B src/q3_yuanzhifang/pipeline_family_followup_export.py
```

The standard feed contains at most ten new E0 attempts. A new 044/046 P3 row
links its old official P2 result as `cache_pair`, with old attempt and source
commit recorded in the run receipt. The new call ledger counts only new calls;
the original failed feed remains available for audit. This is structural
family development evidence, not the unified full500 solver result.
