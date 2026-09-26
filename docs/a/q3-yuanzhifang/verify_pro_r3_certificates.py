"""Independently check Pro R3 witnesses using supplied bytes, never evaluators.

This verifier deliberately does not import the Pro scripts or optimize a plan.
It reconstructs necessary original-compute dependencies and checks each proposed
window witness directly. It does not certify that the chosen window is strongest.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import heapq
import io
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, label):
    if not condition:
        raise ValueError(label)


def graph_view(graph):
    original = {op["id"]: op for op in graph["ops"]}
    tensors = {t["id"] for t in graph["tensors"]}
    compute = {u: op for u, op in original.items()
               if op["op"] not in ("COPY_IN", "COPY_OUT")}
    need(len(original) == len(graph["ops"]), "unique original operations")
    need(not (original.keys() & tensors), "disjoint tensor/operation IDs")
    successors = {u: set() for u in compute}
    producers = {t: set() for t in tensors}
    consumers = {t: set() for t in tensors}
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in compute and v in compute:
            need(u != v, "no compute self edge")
            successors[u].add(v)
        elif u in original and v in tensors:
            producers[v].add(u)
        elif u in tensors and v in original:
            consumers[u].add(v)
        else:
            need(u in original and v in original, "recognized edge endpoints")
    for tid in tensors:
        need(len(producers[tid]) <= 1, "single tensor producer")
        for u in producers[tid] & compute.keys():
            successors[u].update(consumers[tid] & compute.keys())
    duration = {}
    work = Counter()
    for u, op in compute.items():
        need(type(op["cycles"]) is int and op["cycles"] > 0,
             "positive integer original compute cycles")
        need(op["pipe"] in ("PIPE_M", "PIPE_V"), "original compute pipe")
        duration[u] = op["cycles"]
        work[op["pipe"]] += op["cycles"]
    degree = dict.fromkeys(compute, 0)
    for following in successors.values():
        for v in following:
            degree[v] += 1
    ready = [u for u in compute if degree[u] == 0]
    heapq.heapify(ready)
    heads = dict.fromkeys(compute, 0)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in successors[u]:
            heads[v] = max(heads[v], heads[u] + duration[u])
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    need(len(order) == len(compute), "original compute DAG")
    tails = dict.fromkeys(compute, 0)
    for u in reversed(order):
        for v in successors[u]:
            tails[u] = max(tails[u], duration[v] + tails[v])
    return compute, successors, duration, work, heads, tails


def main():
    import zipfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--pro-archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.input_archive.read_bytes()
    pro_raw = args.pro_archive.read_bytes()
    need(digest(raw) == "9d50a4260ff72981ea902c115cd39aa109f6fc8f88ee69ae0c0e9f759295ea4f",
         "frozen submitted archive")
    need(digest(pro_raw) == "67f33d331eaa77d0d66d1bb993b83b60a1f67050fdcbbc6ca8b9e0169447e1a1",
         "downloaded Pro archive")
    source = zipfile.ZipFile(io.BytesIO(raw))
    pro = zipfile.ZipFile(io.BytesIO(pro_raw))
    for archive, manifest_name in [(source, "MANIFEST.json"),
                                   (pro, "OUTPUT_MANIFEST.json")]:
        for item in json.loads(archive.read(manifest_name))["files"]:
            data = archive.read(item["path"])
            need(len(data) == item["bytes"] and digest(data) == item["sha256"],
                 "manifest: " + item["path"])
    raw_graphs = zipfile.ZipFile(io.BytesIO(
        source.read("data/raw/a/official-cases.zip")))
    input_manifest = json.loads(source.read("MANIFEST.json"))
    source_manifest = json.loads(source.read("docs/a/source-manifest.json"))
    original_files = {item["path"]: item for item in source_manifest["files"]}
    proofs = json.loads(pro.read("proofs_100.json"))
    pro_rows = list(csv.DictReader(io.StringIO(
        pro.read("cells_500.csv").decode("utf-8-sig"))))
    pro_cells = {(r["case_id"], int(r["cores"])): r for r in pro_rows}
    joined_rows = list(csv.DictReader(io.StringIO(
        source.read("derived/current-gap.csv").decode("utf-8-sig"))))
    joined = {(r["case_id"], int(r["cores"])): r for r in joined_rows}
    feed = {}
    for name in source.namelist():
        if "/board-feed-s" in name and name.endswith("-revision2.json"):
            for record in json.loads(source.read(name))["records"]:
                key = record["case_id"], record["cores"]
                need(key not in feed, "no duplicate feed")
                feed[key] = record
    need(len(feed) == len(joined) == len(joined_rows) == len(pro_cells) ==
         len(pro_rows) == 500 and len(proofs) == 100, "100 graphs, 500 cells")
    checked = []
    compute_count = 0
    for number in range(1, 101):
        case = f"{number:03d}"
        name = f"data/case_{case}.json"
        data = raw_graphs.read(name)
        gh = digest(data)
        need(gh == original_files[name]["sha256"], "raw graph hash")
        compute, succ, d, work, h, t = graph_view(json.loads(data))
        compute_count += len(compute)
        claimed = proofs[case]
        cp = max(h[u] + d[u] for u in compute)
        need(claimed["graph_sha256"] == gh and
             claimed["compute_ops"] == len(compute) and
             claimed["pipe_work"] == dict(work) and claimed["cp"] == cp,
             case + " graph quantities")
        path = claimed["cp_path"]
        need(sum(d[u] for u in path) == cp and
             all(v in succ[u] for u, v in zip(path, path[1:])),
             case + " critical path witness")
        for k in range(1, 6):
            key = case, k
            record, row, old = feed[key], pro_cells[key], joined[key]
            cert = claimed["certificates"][str(k)]
            need(record["status"] == "ok" and
                 record["evaluator"]["route"] == "E0" and
                 record["solver_commit"] == "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1",
                 "author feed identity")
            need(record["identity"]["graph_sha256"] == gh, "feed graph")
            for identity_key in ("official_sha256", "config_sha256"):
                need(record["identity"][identity_key] ==
                     input_manifest[identity_key] == row[identity_key],
                     identity_key)
            need(record["identity"]["plan_sha256"] ==
                 old["current_plan_sha256"] == row["plan_sha256"],
                 "plan join")
            old_bound = max(cp, max((w + k - 1) // k for w in work.values()))
            need(old_bound == cert["old_L0"] ==
                 int(old["published_global_lower_L"]) ==
                 int(row["L0_recomputed"]), "old global bound")
            window = cert["window"]
            a, b, pipe = window["a"], window["b"], window["pipe"]
            members = sorted(u for u in compute
                             if compute[u]["pipe"] == pipe and h[u] >= a and t[u] >= b)
            energy = sum(d[u] for u in members)
            need(bool(members) and len(members) == window["members_count"] and
                 energy == window["work_sum"], "window membership and work")
            need(digest(json.dumps(members, separators=(",", ":")).encode()) ==
                 window["members_sha256"], "window membership hash")
            window_bound = a + b + (energy + k - 1) // k
            need(window_bound == window["value"] == int(row["L_window"]),
                 "window integer inequality")
            atomic = 0
            for p in work:
                ranked = sorted((d[u] for u in compute if compute[u]["pipe"] == p),
                                reverse=True)
                atomic = max(atomic, max(((j + k - 1) // k) * value
                                         for j, value in enumerate(ranked, 1)))
            need(atomic == cert["atomic"]["value"] == int(row["L_atomic"]),
                 "atomic counting bound")
            lower = max(old_bound, window_bound, atomic)
            upper = record["metrics"]["makespan_cycles"]
            baseline = int(old["baseline_B"])
            need(lower == cert["global_integer_compute_L1"] == int(row["L1_proved"]),
                 "new certified bound")
            need(upper == int(old["current_official_M3_U"]) ==
                 int(row["U_feed_M3"]) and baseline == int(row["B_published"]),
                 "published value joins")
            need(0 < lower <= upper, "certified interval")
            checked.append(dict(case_id=case, cores=k, B=baseline, U=upper,
                                L0=old_bound, L_plus=lower, graph_sha256=gh))
    means = {}
    for k in range(1, 6):
        subset = [r for r in checked if r["cores"] == k]
        current = sum((Fraction(r["B"], r["U"]) for r in subset), Fraction()) / 100
        ceiling = sum((Fraction(r["B"], r["L_plus"]) for r in subset), Fraction()) / 100
        means[str(k)] = dict(current_mean_B_over_U=float(current),
                            upper_mean_B_over_L=float(ceiling),
                            gain_upper_ratio_points=float(ceiling - current),
                            strengthened=sum(r["L_plus"] > r["L0"] for r in subset),
                            exact_optimality_certificates=sum(r["L_plus"] == r["U"] for r in subset))
    # Static AST comparison only, never import/execute official functions.
    frontend = {}
    for fn in ("_prioritize_task_seq", "_build_scene_b_tasks"):
        values = []
        for p in (2, 3):
            tree = ast.parse(source.read(
                f"data/raw/a/official/code/multicore_cut_evaluate_problem_{p}.py"))
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn)
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                node.body = node.body[1:]
            values.append(ast.dump(node, include_attributes=False))
        frontend[fn] = values[0] == values[1]
        need(frontend[fn], "P2/P3 common frontend AST")
    # Examine saved 044 results without re-running its plan.
    pref = "results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/"
    receipt_hashes = json.loads(source.read(pref + "SHA256SUMS.json"))
    checked_receipt = 0
    for name, sha in receipt_hashes.items():
        if pref + name in source.namelist():
            need(digest(source.read(pref + name)) == sha, "044 receipt hash")
            checked_receipt += 1
    saved = {}
    for label, name in [("control_p2", "control-p2.json.gz"),
                        ("control_p3", "reused-full-prefix-044-p3.json.gz"),
                        ("candidate_p2", "candidate-p2.json.gz"),
                        ("candidate_p3", "candidate-p3.json.gz")]:
        saved[label] = json.loads(gzip.decompress(source.read(pref + "artifacts/" + name)))
    mechanism = dict(saved_makespans={label: r["makespan"] for label, r in saved.items()},
                     receipt_files_hash_checked=checked_receipt)
    need(mechanism["saved_makespans"] ==
         dict(control_p2=38024, control_p3=38024, candidate_p2=37060, candidate_p3=37060),
         "044 saved makespans")
    mechanism["M_reduction_cycles"] = 964
    mechanism["G_control"] = mechanism["G_candidate"] = 1
    out = dict(input_archive_sha256=digest(raw), pro_archive_sha256=digest(pro_raw),
               verifier_sha256=digest(Path(__file__).read_bytes()),
               checked_graphs=100, checked_compute_operations=compute_count,
               checked_cells=500, per_core=means, common_frontend_AST=frontend,
               saved_044=mechanism,
               new_calls=dict(solver=0, Task=0, Step=0, E0=0, E1=0, E2=0),
               limitations=[
                   "Witness validation proves the reported window lower bound, not maximum strength over all thresholds.",
                   "U and B remain hash-bound published evidence; no new official reevaluation.",
                   "Common frontend AST does not alone prove every surrounding call parameter is identical.",
                   "044 timing causation and all 6712 operation records were not revalidated by this verifier.",
                   "Machine-semantic validity relies on the separately recorded source proof for integer non-COPY durations and causal preservation."])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "independent-certificate-check.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.out / "independent-cells.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(checked[0]))
        writer.writeheader()
        writer.writerows(checked)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
