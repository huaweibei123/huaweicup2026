"""Recheck P2 R4 saved arithmetic and downloaded artifacts; no evaluator imports."""
from __future__ import annotations
import argparse, ast, csv, hashlib, io, json, math, zipfile
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[5]
CHAT = ROOT / "AI chats/P2-capacity-ddr-6ab57979"
HERE = Path(__file__).resolve().parent
BOUNDS = "results/a/q2-nikolastarx/goal-20260924/global-bounds.json"
SUMMARY = "results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json"
BASELINE = "results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv"
CONFIG = "data/raw/a/official/data/config.txt"

def sha(b): return hashlib.sha256(b).hexdigest()
def csvrows(b): return list(csv.DictReader(io.StringIO(b.decode("utf-8"))))
def avg(xs):
    vals = list(xs)
    return sum(vals, F(0)) / len(vals)
def checkclose(actual, expected):
    assert math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-10), (actual, expected)
def indexed(rows, case="case"):
    out = {}
    for r in rows:
        key = (r[case], int(r["cores"]))
        assert key not in out, key
        out[key] = r
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence-zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    source_blob = args.evidence_zip.read_bytes()
    receipt = json.loads((HERE / "bundle-receipt.json").read_bytes())
    assert sha(source_blob) == receipt["sha256"]
    z = zipfile.ZipFile(io.BytesIO(source_blob))
    assert z.testzip() is None
    manifest = json.loads(z.read("MANIFEST.json"))
    assert manifest == json.loads((HERE / "input-manifest.json").read_bytes())
    for entry in manifest["entries"]:
        b = z.read(entry["path"])
        assert len(b) == entry["bytes"] and sha(b) == entry["sha256"], entry["path"]
    prodir = CHAT / "附件"
    pro_manifest = json.loads((prodir / "r4-R4-ARTIFACT-MANIFEST.json").read_bytes())
    for entry in pro_manifest["files"]:
        b = (prodir / ("r4-" + entry["path"])).read_bytes()
        assert len(b) == entry["bytes"] and sha(b) == entry["sha256"], entry["path"]
    for line in (prodir / "r4-SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        assert sha((prodir / ("r4-" + name.lstrip("* "))).read_bytes()) == digest
    for name in ("r4-r4_saved_audit.py", "r4-r4_event_bound.py"):
        ast.parse((prodir / name).read_text(encoding="utf-8"), filename=name)
    bounds = json.loads(z.read(BOUNDS))
    for name, digest in bounds["official_source_sha256"].items():
        assert sha(z.read("data/raw/a/official/code/" + name)) == digest
    assert sha(z.read("src/q2_nikolastarx/global_bounds.py")) == bounds["certificate_source_sha256"]
    cfgsha = sha(z.read(CONFIG))
    results = indexed(json.loads(z.read(SUMMARY))["rows"])
    baselines = indexed(csvrows(z.read(BASELINE)), "case_id")
    pro = indexed(csvrows((prodir / "r4-r4-cells.csv").read_bytes()))
    previous = indexed(csvrows((HERE / "gap-cells.csv").read_bytes()))
    expected = {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    assert set(results) == set(baselines) == set(pro) == set(previous) == expected
    records, witnesses = {}, Counter()
    for graph in bounds["records"]:
        case = Path(graph["graph_file"]).stem.split("_")[-1]
        assert graph["supported"] and graph["precedence_supported"]
        assert not graph["multiple_eligible_producer_tensor_ids"]
        assert len({int(baselines[case, k]["baseline_cycles"]) for k in range(1, 6)}) == 1
        for bound in graph["by_core_count"]:
            k = bound["cores"]; key = (case, k)
            assert key not in records
            parts = [graph["retained_compute_critical_path_cycles"]]
            for pipe, w in bound["pipe_load_bounds"].items():
                parts.append(w["cycles"]); witnesses[w["kind"]] += 1
                work = graph["pipe_work"][pipe]
                assert w["cycles"] >= (work + k - 1) // k
                if w["kind"] == "total_work":
                    assert w["cycles"] == (work + k - 1) // k
                else:
                    assert w["largest_jobs"] == (w["jobs_on_one_core"] - 1) * k + 1
                    assert w["cycles"] == w["smallest_q_sum"]
            for pipe, w in bound["pipe_window_bounds"].items():
                parts.append(w["cycles"])
                if w["cycles"]:
                    witnesses["nonempty_window"] += 1
                    assert w["cycles"] == w["threshold"] + (w["selected_pipe_work"] + k - 1) // k + w["minimum_other"]
                    assert w["selected_pipe_work"] <= graph["pipe_work"][pipe]
            L = max(parts)
            assert L == bound["makespan_lower_bound_cycles"]
            raw, r, old = results[key], pro[key], previous[key]
            A = int(baselines[key]["baseline_cycles"]); U = raw["official"]["makespan"]
            assert (A, L, U) == (int(r["A"]), int(r["L"]), int(r["U"]))
            assert (A, L, U) == (int(old["baseline_cycles"]), int(old["lower_bound_cycles"]), int(old["makespan_cycles"]))
            assert 0 < L <= U and A > 0
            assert raw["status"] == "accepted"
            assert raw["solver_process"]["status"] == raw["e0_process"]["status"] == "ok"
            assert r["graph_sha256"] == graph["graph_sha256"] == raw["graph_sha256"]
            assert r["config_sha256"] == raw["config_sha256"] == cfgsha
            assert r["plan_sha256"] == raw["plan_sha256"]
            assert r["result_sha256"] == raw["official"]["result_sha256"]
            quantities = {"speedup":F(A,U), "speedup_ceiling":F(A,L),
                "speedup_gap":F(A,L)-F(A,U), "mean_gap_contribution":(F(A,L)-F(A,U))/100,
                "makespan_reduction_cap_pct":100*F(U-L,U), "speedup_relative_gain_cap_pct":100*(F(U,L)-1)}
            for name, value in quantities.items(): checkclose(r[name], value)
            for pct in (1, 5, 10):
                assert (r[f"within_{pct}pct"] == "True") == (100*U <= (100+pct)*L)
            io_counts = graph["mandatory_boundary_io"]
            count = max((graph["pipe_work"]["PIPE_MTE2"] + io_counts["input_tensor_count"] + k - 1)//k,
                        (graph["pipe_work"]["PIPE_MTE3"] + io_counts["output_tensor_count"] + k - 1)//k)
            assert count == int(r["boundary_event_count_bound"])
            assert max(count, L) == int(r["count_strengthened_L"])
            movement = raw["official"]["movement"]
            assert movement["scheduled_copy_bytes"] - movement["original_graph_copy_bytes"] == movement["added_copy_bytes"]
            assert movement["added_copy_bytes"] == movement["partition_added_copy_bytes"] + movement["spill_added_copy_bytes"]
            for field, source in (("scheduled_copy_bytes","scheduled_copy_bytes"),("extra_ddr_bytes","added_copy_bytes"),("spill_bytes","spill_added_copy_bytes")):
                assert int(r[field]) == movement[source]
            records[key] = dict(A=A,L=L,U=U,count=count,**quantities)
    assert set(records) == expected
    audit = json.loads((prodir / "r4-r4-audit.json").read_bytes())
    assert dict(witnesses) == audit["witness_arithmetic_checks"]
    checked_aggregates = []
    for k in range(1, 6):
        xs = [r for (case, core), r in records.items() if core == k]
        s, c = avg(x["speedup"] for x in xs), avg(x["speedup_ceiling"] for x in xs)
        agg = {"cores":k,"n":100,"mean_speedup":s,"mean_ceiling":c,"mean_gap":c-s,
            "relative_mean_speedup_gain_cap_pct":100*(c/s-1),
            "mean_per_case_makespan_reduction_cap_pct":avg(x["makespan_reduction_cap_pct"] for x in xs),
            "median_per_case_makespan_reduction_cap_pct":median(x["makespan_reduction_cap_pct"] for x in xs),
            "mean_per_case_speedup_gain_cap_pct":avg(x["speedup_relative_gain_cap_pct"] for x in xs),
            "median_per_case_speedup_gain_cap_pct":median(x["speedup_relative_gain_cap_pct"] for x in xs),
            "exact_count":sum(x["U"] == x["L"] for x in xs)}
        for pct in (1,5,10): agg[f"near_{pct}pct_count"] = sum(100*x["U"] <= (100+pct)*x["L"] for x in xs)
        for name, val in agg.items(): checkclose(audit["by_core"][k-1][name], val)
        checked_aggregates.append({key:float(val) if isinstance(val,F) else val for key,val in agg.items()})
    ranked = sorted((key for key in records if key[1] == 5), key=lambda key:(-records[key]["speedup_gap"],key[0]))
    pro_ranked = csvrows((prodir / "r4-r4-k5-ranked.csv").read_bytes())
    assert [r["case"] for r in pro_ranked] == [key[0] for key in ranked]
    total = sum((records[key]["speedup_gap"] for key in ranked), F(0))
    for n in (5,10,20):
        checkclose(audit["k5_top_gap_shares_pct"][str(n)],100*sum((records[key]["speedup_gap"] for key in ranked[:n]),F(0))/total)
    dist = csvrows((prodir / "r4-r4-k5-distribution.csv").read_bytes())
    for row, lo, hi in zip(dist, (0,1,5,10,25,50,100), (1,5,10,25,50,100,None)):
        keys = [key for key in ranked if records[key]["speedup_relative_gain_cap_pct"] > lo and (hi is None or records[key]["speedup_relative_gain_cap_pct"] <= hi)]
        assert len(keys) == int(row["count"]) and row["cases"].split(",") == [key[0] for key in keys]
        part = sum((records[key]["speedup_gap"] for key in keys),F(0))
        checkclose(row["mean_gap_contribution"],part/100); checkclose(row["share_of_gap_pct"],100*part/total)
    count_improved = sum(r["count"] > r["L"] for r in records.values())
    assert count_improved == audit["safe_boundary_count_improved_cells"] == 0
    result = {"scope":"Independent saved-data and source-identity arithmetic; no original-graph recertification or evaluator execution.",
        "source_zip_sha256":sha(source_blob),"manifest_entries_checked":len(manifest["entries"]),
        "downloaded_original_files":12,"author_manifest_hashes_checked":10,
        "coverage":len(records),"witness_arithmetic_checks":dict(witnesses),"by_core":checked_aggregates,
        "k5_top10_cases":[key[0] for key in ranked[:10]],"k5_top_gap_shares_pct":audit["k5_top_gap_shares_pct"],
        "boundary_count_improved_cells":count_improved,"all_comparisons_passed":True,
        "Pro_scripts_executed":0,"new_plan_constructor_prepare_E0_E1_E2_calls":0,
        "not_verified":["New augmented bound on all original graphs","Frozen weighted DDR service lemma","Universal E2=E0","Previously archived raw result files anew"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(result,f,ensure_ascii=False,indent=2); f.write("\n")
    print(json.dumps({"coverage":len(records),"all_comparisons_passed":True,"witnesses":dict(witnesses),"count_bound_improved":count_improved,"new_evaluator_calls":0}))

if __name__ == "__main__": main()

