"""Read saved evidence only; no candidate construction or evaluation."""
from decimal import Decimal, getcontext
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
FEED_COMMIT = "19bebf35205d23fdd832781540f8879da52eeb62"
FEED_PATH = "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s07-revision2.json"
SUMMARY_COMMIT = "8c9780d32ad4291bbd8fdf139c25a4cffa99db77"
SUMMARY_PATH = "results/a/q3-nikolastarx/forest-current-headroom-20260925/summary.json"
getcontext().prec = 40


def raw(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)


def read_ref(ref):
    value = raw(FEED_COMMIT, ref["path"])
    assert hashlib.sha256(value).hexdigest() == ref["sha256"]
    return json.loads(gzip.decompress(value) if ref["path"].endswith(".gz") else value)


feed = raw(FEED_COMMIT, FEED_PATH)
record = next(r for r in json.loads(feed)["records"]
              if (r["problem"], r["case_id"], r["cores"]) == ("P3", "067", 5))
refs = dict(baseline=record["baseline"]["result"],
            P2=record["cache_pair"]["result"], P3=record["artifacts"]["result"],
            plan=record["artifacts"]["plan"])
objects = {k: read_ref(ref) for k, ref in refs.items()}
assert refs["plan"]["sha256"] == record["identity"]["plan_sha256"]
assert record["cache_pair"]["plan_sha256"] == record["identity"]["plan_sha256"]
for field in ("graph_sha256", "config_sha256", "official_sha256"):
    assert record["identity"][field] == record["baseline"][field] == record["cache_pair"][field]
assert objects["P3"]["makespan"] == record["metrics"]["makespan_cycles"]
assert objects["baseline"]["num_cores"] == 1
assert objects["P2"]["num_cores"] == objects["P3"]["num_cores"] == 5
assert objects["P3"]["cache_mode"] == "read_only"
summary_raw = raw(SUMMARY_COMMIT, SUMMARY_PATH)
summary = json.loads(summary_raw)
assert summary["solver_commit"] == record["solver_commit"]
mean = Decimal(str(summary["by_cores"]["5"]["current_mean_speedup"]))
audit_path = ROOT / "results/a/q3-yuanzhifang/stair-static-20260925/stdout.json.gz"
audit_raw = audit_path.read_bytes()
audit = json.loads(gzip.decompress(audit_raw))
assert audit["graph_sha256"] == record["identity"]["graph_sha256"]
assert audit["config_sha256"] == record["identity"]["config_sha256"]
B, T = (Decimal(objects[k]["makespan"]) for k in ("baseline", "P3"))
bounds = []
for name, bound in (("stair_fixed_order", audit["lower_bound_cycles"]),
                    ("prior_global_head_tail", 11785739)):
    increase = (B / Decimal(bound) - B / T) / 100
    bounds.append(dict(bound_scope=name, bound_cycles=bound,
                       single_cell_speedup_ceiling=str(B / Decimal(bound)),
                       conditional_mean_increase=str(increase),
                       conditional_mean_ceiling=str(mean + increase),
                       still_below_challenge_4_76=mean + increase < Decimal("4.76")))
result = dict(schema="q3-stair-global-value-v1", formula="delta=(B/L-B/T)/100; other 99 cells fixed",
              sources=dict(feed=dict(commit=FEED_COMMIT, path=FEED_PATH, sha256=hashlib.sha256(feed).hexdigest()),
                           summary=dict(commit=SUMMARY_COMMIT, path=SUMMARY_PATH, sha256=hashlib.sha256(summary_raw).hexdigest()),
                           stair_audit=dict(path=audit_path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(audit_raw).hexdigest()),
                           global_bound=dict(commit="09191c18bebc8b93e7751058b7c1b0f67c7d08fe", path="docs/a/q3-yuanzhifang/WHOLE_JOB_BOUND.md")),
              solver_commit=record["solver_commit"], identity=record["identity"], verified_references=refs,
              observed=dict(singlecore_cycles=int(B), P2_cycles=objects["P2"]["makespan"], P3_cycles=int(T),
                            same_plan_cache_gain=str(Decimal(objects["P2"]["makespan"]) / T),
                            P3_movement=objects["P3"]["data_movement_bytes"], P3_cache=objects["P3"]["cache_stats"]),
              captain_reported_full100_mean=str(mean), conditional_bounds=bounds,
              calls=dict(solver=0, derive=0, Step=0, E0=0),
              limits="One-cell artifacts rehashed, no independent full500 rerun/reaggregation. Bounds are optimistic necessary relaxations, not achieved scores. 4.76 is a challenge reference, not independently verified screenshot provenance.")
(OUT / "summary.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(json.dumps(dict(observed=result["observed"], conditional_bounds=bounds), ensure_ascii=False))
