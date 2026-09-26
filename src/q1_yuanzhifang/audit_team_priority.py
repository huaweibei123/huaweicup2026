"""Read-only team-priority arithmetic; no solver, Task compilation or scoring."""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = "9c5f87548cc7588465a638e032993969b5cac891"
FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
FEED_SHA = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
INDEX = "results/a/q1-yuanzhifang/v4-reuse-audit-20260925/reusable-index.json"
BOUNDS = "results/a/q1-yuanzhifang/barrier-audit-20260924/full/bounds-100x5.json.gz"
TARGETS = {2: "2.19150", 3: "2.83820", 4: "3.42710", 5: "3.90660"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit():
    raw = subprocess.check_output(["git", "show", f"{ARCHIVE}:{FEED}"], cwd=ROOT)
    if sha(raw) != FEED_SHA:
        raise ValueError("fixed captain feed identity differs")
    records = json.loads(raw)["records"]
    if len(records) != 500 or len({(r["case_id"], r["cores"]) for r in records}) != 500:
        raise ValueError("expected 100 distinct graphs at each of five core counts")
    index_raw, bounds_raw = ((ROOT / p).read_bytes() for p in (INDEX, BOUNDS))
    index = {r["case_id"]: r for r in json.loads(index_raw)["k4"]}
    bounds = json.loads(gzip.decompress(bounds_raw))
    if len(index) != 100 or len(bounds) != 100:
        raise ValueError("baseline/bound coverage differs")
    output = dict(
        scope="Read-only arithmetic on the fixed 500-record feed and independently audited k4/baseline index; not a new 500-artifact audit or an achieved algorithm mean",
        new_calls={"solver": 0, "Task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
        source={"archive_commit": ARCHIVE, "feed_path": FEED, "feed_sha256": sha(raw),
                "baseline_index": INDEX, "baseline_index_sha256": sha(index_raw),
                "bounds_path": BOUNDS, "bounds_sha256": sha(bounds_raw)},
        means={}, rankings={}, bound_violations=[],
    )
    with localcontext() as context:
        context.prec = 40
        for cores in range(1, 6):
            rows = [r for r in records if r["cores"] == cores]
            if len(rows) != 100:
                raise ValueError("core coverage differs")
            ratios, ranking = [], []
            for r in rows:
                case = r["case_id"]
                base = index[case]
                if (r["status"] != "ok" or
                    r["solver_commit"] != "a0537aeb72dc702af86d67d3194587d581ac207c" or
                    r["identity"]["graph_sha256"] != base["graph_sha256"] or
                    r["baseline"]["result"]["sha256"] != base["baseline_gzip_sha256"] or
                    r["baseline"]["result"]["path"] != base["baseline_result_path"]):
                    raise ValueError(f"fixed case/baseline identity differs: {case}/k{cores}")
                for field in ("graph_sha256", "config_sha256", "official_sha256"):
                    if r["identity"][field] != r["baseline"][field]:
                        raise ValueError(f"baseline configuration differs: {case}/k{cores}")
                current = r["metrics"]["makespan_cycles"]
                baseline = base["baseline_makespan_cycles"]
                lower = bounds[case][str(cores)]["lower_bound_cycles"]
                if min(current, baseline, lower) <= 0:
                    raise ValueError("nonpositive cycle count")
                if lower > current:
                    output["bound_violations"].append([case, cores, lower, current])
                ratios.append(Decimal(baseline) / current)
                ranking.append(dict(case=case, current_makespan=current,
                    baseline_makespan=baseline, lower_bound_cycles=lower,
                    optimistic_mean_headroom=str((Decimal(baseline)/lower - ratios[-1])/100)))
            mean = sum(ratios) / 100
            row = {"mean": str(mean), "sample_count": 100}
            if cores in TARGETS:
                row.update(target=TARGETS[cores], margin=str(mean-Decimal(TARGETS[cores])))
            output["means"][str(cores)] = row
            output["rankings"][str(cores)] = sorted(ranking,
                key=lambda r: Decimal(r["optimistic_mean_headroom"]), reverse=True)
        baseline_051 = index["051"]["baseline_makespan_cycles"]
        # This is the contribution of separately measured development cells,
        # not a splice reported as a unified solver's newly measured mean.
        output["measured_051_development_contributions"] = []
        for cores, current in ((3, 278618), (4, 244533), (5, 231551)):
            old = next(r["metrics"]["makespan_cycles"] for r in records
                       if r["case_id"] == "051" and r["cores"] == cores)
            output["measured_051_development_contributions"].append(dict(
                cores=cores, captain_cycles=old, development_cycles=current,
                baseline_cycles=baseline_051,
                mean_contribution_if_other_99_unchanged=str(
                    (Decimal(baseline_051)/current-Decimal(baseline_051)/old)/100),
                result_commit=("059056ce1ee999e634049e5e5baf72566832effe" if cores<5
                    else "335ecb189693671f840d18ae9e52b98b35c54b1c")))
        output["screenshot_consistency"] = dict(
            scope="Conventional sorted-sample median, maximum and arithmetic mean; rounding does not explain the gap",
            reported_k2_mean="2.19150", reported_k2_median="1.98950", reported_k2_max="2.24600",
            necessary_mean_upper_bound=str((Decimal("1.98950")+Decimal("2.24600"))/2),
            conclusion="Inconsistent as one sample; keep the requested mean as an unverified numerical challenge, not verified competition evidence")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"means": result["means"],
                      "top_k2": result["rankings"]["2"][:6],
                      "top_k3": result["rankings"]["3"][:6],
                      "development": result["measured_051_development_contributions"],
                      "bound_violations": result["bound_violations"]}))


if __name__ == "__main__":
    main()
