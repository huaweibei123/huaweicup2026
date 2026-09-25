"""Independently check P1 R4 integer witnesses against fixed Git graph bytes.

Stdlib only. Does not import or execute any downloaded/official/solver module.
This is a witness and saved-data audit, not an evaluator or plan search.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import io
import json
import math
import platform
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

BASE = "a0537aeb72dc702af86d67d3194587d581ac207c"
FEED_REV = "9c5f87548cc7588465a638e032993969b5cac891"
AUDIT_REV = "ad670c2f2414007cad80589b1f02621cea4037e8"
FEED_PATH = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
AUDIT_PATH = "results/a/q1-yuanzhifang/v4-reuse-audit-20260925/reusable-index.json"
PRO_PATH = "AI chats/P1-fork-join-yuanzhifang/附件"
PREFIX = "r4-f6ff2015-"
FEED_SHA = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
CONFIG_SHA = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
OFFICIAL_SHA = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
E0_SHA = "2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f"
ZIP_SHA = "073e5064c40f2da81725a018df67f16df7071c87a31fd33aa58dee3be863750a"
PIPES = ("PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, context):
    if not condition:
        raise ValueError(context)


def keyed(rows):
    result = {(r["case_id"], r["cores"]): r for r in rows}
    expected = {(f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    require(len(rows) == 500 and set(result) == expected, "500 unique graph/core cells")
    return result


def retained_graph(graph):
    ops = {op["id"]: op for op in graph["ops"] if op["op"] not in ("COPY_IN", "COPY_OUT")}
    tensors = {t["id"] for t in graph["tensors"]}
    require(not set(ops) & tensors, "disjoint compute/tensor IDs")
    children = {u: set() for u in ops}
    parents = {u: set() for u in ops}
    producers = {t: set() for t in tensors}
    consumers = {t: set() for t in tensors}
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in ops and v in ops:
            children[u].add(v)
        elif u in ops and v in tensors:
            producers[v].add(u)
        elif u in tensors and v in ops:
            consumers[u].add(v)
    for t in tensors:
        for u in producers[t]:
            children[u].update(consumers[t])
    for u in children:
        for v in children[u]:
            parents[v].add(u)
    degree = {u: len(ps) for u, ps in parents.items()}
    ready = [u for u in ops if degree[u] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in children[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    require(len(order) == len(ops), "retained graph must be a DAG")
    require(all(type(o["cycles"]) is int and o["pipe"] in PIPES for o in ops.values()), "integer durations / known pipe")
    d = {u: max(1, ops[u]["cycles"]) for u in ops}
    r, q = {}, {}
    for u in order:
        r[u] = max((r[v] + d[v] for v in parents[u]), default=0)
    for u in reversed(order):
        q[u] = max((q[v] + d[v] for v in children[u]), default=0)
    return ops, children, parents, order, d, r, q


def reachable(root, adjacency):
    """Full reachability independently checks each claimed universal anchor."""
    found, todo = {root}, [root]
    while todo:
        u = todo.pop()
        for v in adjacency[u]:
            if v not in found:
                found.add(v)
                todo.append(v)
    return found


def minimum_capacity_time(work, cores, endpoints, tau):
    """Invert capacity by integer bisection, independently of Pro's closed form."""
    lo, hi = 0, work
    while lo < hi:
        mid = (lo + hi) // 2
        capacity = cores * mid if endpoints == 0 else mid + (cores - 1) * max(0, mid - endpoints * tau)
        if capacity >= work:
            hi = mid
        else:
            lo = mid + 1
    return lo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; refuses overwrite")
    args = parser.parse_args()
    start = time.perf_counter()
    require(not args.output_dir.exists(), "output directory already exists")

    def blob(rev, path):
        return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=args.repo)

    originals = args.repo / PRO_PATH
    read_pro = lambda name: json.loads((originals / (PREFIX + name)).read_bytes())
    zbytes = (originals / (PREFIX + "p1_r4_theory_and_certificates.zip")).read_bytes()
    require(sha(zbytes) == ZIP_SHA, "Pro ZIP digest")
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        require(z.testzip() is None and len(z.namelist()) == 20, "Pro ZIP CRC / count")
        for member in z.namelist():
            require((originals / (PREFIX + Path(member).name)).read_bytes() == z.read(member), member)
    output_manifest = read_pro("OUTPUT_MANIFEST.json")
    require(len(output_manifest) == 19, "Pro inner manifest count")
    for item in output_manifest:
        data = (originals / (PREFIX + item["path"])).read_bytes()
        require(len(data) == item["size_bytes"] and sha(data) == item["sha256"], item["path"])

    cfg = blob(BASE, "data/raw/a/official/data/config.txt")
    require(sha(cfg) == CONFIG_SHA, "config hash")
    tau = int(next(line.split()[1] for line in cfg.decode().splitlines() if line.startswith("task_cross_core_wait_cycles ")))
    require(tau == 1000, "cross-core gate")
    require(sha(blob(BASE, "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py")) == E0_SHA, "E0 source hash")
    feed_bytes = blob(FEED_REV, FEED_PATH)
    require(sha(feed_bytes) == FEED_SHA, "fixed feed hash")
    feed = keyed(json.loads(feed_bytes)["records"])
    baselines = {r["case_id"]: r for r in json.loads(blob(AUDIT_REV, AUDIT_PATH))["k4"]}
    require(len(baselines) == 100, "baseline audit count")
    pro_table = read_pro("audit_tables.json")
    pro_rows = keyed(pro_table["rows"])
    windows = keyed(read_pro("window_certificates.json"))
    separators = keyed(read_pro("separator_certificates.json"))
    rows, graph_receipts = [], []
    memberships = block_checks = anchor_checks = 0
    raw_zip = blob(BASE, "data/raw/a/official-cases.zip")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        names = [n for n in z.namelist() if n.endswith(".json") and not n.startswith("__MACOSX/")]
        require(len(names) == 100, "100 raw graphs")
        for name in sorted(names):
            cid = Path(name).stem[-3:]
            raw = z.read(name)
            gh = sha(raw)
            ops, children, parents, order, d, r, q = retained_graph(json.loads(raw))
            cp = max((r[u] + d[u] for u in ops), default=0)
            require(cp > 0, (cid, "nonempty compute"))
            anchors = separators[cid, 1]["anchors"]
            positions = {u: i for i, u in enumerate(order)}
            require(len(anchors) == len(set(anchors)) and anchors == sorted(anchors, key=positions.__getitem__), (cid, "anchor order"))
            for a in anchors:
                before, after = reachable(a, parents), reachable(a, children)
                require(before | after == set(ops) and before & after == {a}, (cid, a, "universal reachability"))
                anchor_checks += 1
            anchor_set = set(anchors)
            blocks, left, count, work = [], None, 0, dict.fromkeys(PIPES, 0)
            for u in order:
                if u in anchor_set:
                    blocks.append((left, u, count, work))
                    left, count, work = u, 0, dict.fromkeys(PIPES, 0)
                else:
                    count += 1
                    work[ops[u]["pipe"]] += d[u]
            blocks.append((left, None, count, work))
            aw = sum(d[u] for u in anchors)
            population = {p: [u for u in ops if ops[u]["pipe"] == p] for p in PIPES}
            for k in range(1, 6):
                key = cid, k
                w, s, f, p = windows[key], separators[key], feed[key], pro_rows[key]
                b = baselines[cid]
                for obj in (w, s, p, b, f["identity"], f["baseline"]):
                    require(obj["graph_sha256"] == gh, (key, "graph identity"))
                for obj in (w, s, p, f["identity"], f["baseline"]):
                    require(obj["config_sha256"] == CONFIG_SHA, (key, "config identity"))
                require(w["official_P1_sha256"] == s["official_P1_sha256"] == E0_SHA, (key, "certificate source"))
                require(f["identity"]["official_sha256"] == f["baseline"]["official_sha256"] == OFFICIAL_SHA, (key, "official identity"))
                require(f["status"] == "ok" and f["solver_commit"] == BASE and f["evaluator"]["route"] == "E0", (key, "saved E0 provenance"))
                B, U = b["baseline_makespan_cycles"], f["metrics"]["makespan_cycles"]
                require(type(B) is int and type(U) is int and B > 0 and U > 0 and (p["B"], p["U"]) == (B, U), (key, "B/U"))
                require(w["cp"] == cp and set(w["windows"]) == set(PIPES), (key, "CP / pipes"))
                window_values = [cp]
                for pipe in PIPES:
                    cert = w["windows"][pipe]
                    if cert.get("empty"):
                        require(not population[pipe] and cert["bound"] == 0, (key, pipe, "empty"))
                        continue
                    a, tail = cert["a"], cert["b"]
                    require(type(a) is int and type(tail) is int and a >= 0 and tail >= 0, (key, pipe, "thresholds"))
                    selected = sorted(u for u in population[pipe] if r[u] >= a and q[u] >= tail)
                    W = sum(d[u] for u in selected)
                    value = a + tail + (W + k - 1) // k
                    require(selected and cert["selected_count"] == len(selected) and cert["selected_work"] == W, (key, pipe, "membership"))
                    require(cert["selected_id_sha256"] == sha(json.dumps(selected, separators=(",", ":")).encode()), (key, pipe, "ID hash"))
                    require(cert["bound"] == value, (key, pipe, "window value"))
                    window_values.append(value)
                    memberships += len(selected)
                Lw = max(window_values)
                require(Lw == w["L"] == p["L_safe_compute_window"], (key, "window aggregate"))
                require(s["anchors"] == anchors and s["anchor_work"] == aw and len(s["blocks"]) == len(blocks), (key, "separator partition"))
                Ls = aw
                for record, (a, bnode, count, work) in zip(s["blocks"], blocks):
                    h = int(a is not None) + int(bnode is not None)
                    vals = {pipe: minimum_capacity_time(W, k, h, tau) for pipe, W in work.items()}
                    require((record["left"], record["right"], record["op_count"], record["endpoints"]) == (a, bnode, count, h), (key, "block identity"))
                    require(record["pipe_work"] == work and record["bounds"] == vals and record["bound"] == max(vals.values()), (key, "capacity inversion"))
                    Ls += max(vals.values())
                    block_checks += 1
                require(Ls == s["bound"] == p["L_safe_separator"], (key, "separator aggregate"))
                L = max(Lw, Ls)
                require(L == p["L_safe_global"] and 0 < L <= U, (key, "global interval"))
                for metric in ("extra_ddr_bytes", "spill_bytes"):
                    require(p[metric] == f["metrics"][metric], (key, metric))
                require(p["selected"] == f["parameters"]["selected"], (key, "selected"))
                rows.append(dict(case_id=cid, cores=k, graph_sha256=gh, B=B, U=U, L=L,
                    window_L=Lw, separator_L=Ls, current_speedup=float(Fraction(B, U)),
                    speedup_upper=float(Fraction(B, L)), max_makespan_reduction=float(1-Fraction(L, U)),
                    max_relative_speedup_gain=float(Fraction(U, L)-1), extra_ddr_bytes=p["extra_ddr_bytes"],
                    spill_bytes=p["spill_bytes"], selected=p["selected"],
                    old_conditional_scalar=p["L_conditional_archived"],
                    old_scalar_certified_by_domination=L >= p["L_conditional_archived"]))
            graph_receipts.append(dict(case_id=cid, member=name, graph_sha256=gh,
                compute_nodes=len(ops), retained_edges=sum(map(len, children.values())), universal_anchors=len(anchors)))

    require(len(rows) == 500, "output cells")
    summaries = []
    for k in range(1, 6):
        cells = [r for r in rows if r["cores"] == k]
        A = sum((Fraction(r["B"], r["U"]) for r in cells), Fraction()) / 100
        C = sum((Fraction(r["B"], r["L"]) for r in cells), Fraction()) / 100
        pro = next(x for x in pro_table["summary"]["official_integer_global"] if x["cores"] == k)
        require(Fraction(pro["C_fraction"]) == C, (k, "exact upper mean"))
        require(Fraction(pro["A_fraction"]) == (1 if k == 1 else A), (k, "exact current mean"))
        require(math.isclose(pro["current_candidate_A"], float(A), rel_tol=1e-14), (k, "candidate mean"))
        summaries.append(dict(cores=k, n=100, official_curve_A=1.0 if k == 1 else float(A),
            current_candidate_A=float(A), C=float(C), C_minus_candidate_A=float(C-A),
            relative_mean_gain_cap=float(C/A-1), A_exact=str(A), C_exact=str(C),
            exact_matches=sum(r["L"] == r["U"] for r in cells),
            positive_spill_cells=sum(r["spill_bytes"] > 0 for r in cells)))
    result = dict(status="pass", created_utc=datetime.now(timezone.utc).isoformat(),
        verifier_sha256=sha(Path(__file__).read_bytes()), source_commits=dict(official=BASE, feed=FEED_REV, baseline_audit=AUDIT_REV),
        feed_sha256=FEED_SHA, config_sha256=CONFIG_SHA, official_P1_sha256=E0_SHA,
        graph_zip_sha256=sha(raw_zip), pro_zip_sha256=ZIP_SHA,
        platform=platform.platform(), python=platform.python_version(),
        calls=dict(solver=0, Task_compiler=0, response_simulator=0, E0=0, E1=0, E2=0),
        checks=dict(graphs=100, cells=500, window_resources=2000, selected_memberships=memberships,
            separator_blocks=block_checks, universal_anchor_full_reachability_checks=anchor_checks,
            pro_zip_members_byte_equal=20, pro_inner_manifest_hashes=19,
            old_scalars_certified_by_domination=sum(r["old_scalar_certified_by_domination"] for r in rows),
            separator_strict_improvement_cells=sum(r["separator_L"] > r["window_L"] for r in rows),
            positive_spill_cells=sum(r["spill_bytes"] > 0 for r in rows), exact_matches=sum(r["L"] == r["U"] for r in rows)),
        scope="Static witness arithmetic and saved feed identity audit. Proof needs the accompanying source review. No independent replay of 500 plans/results/traces; no proof of witness-search maximality, E1 equivalence, DDR floating-service conservation, or global convergence.",
        groups=summaries, graph_receipts=graph_receipts, wall_seconds=time.perf_counter()-start)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    with (args.output_dir / "paired-500.csv").open("w", encoding="utf8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps({"status": result["status"], "checks": result["checks"], "wall_seconds": result["wall_seconds"],
        "groups": [{k: v for k, v in g.items() if not k.endswith("_exact")} for g in summaries]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
