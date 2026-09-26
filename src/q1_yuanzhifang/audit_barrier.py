"""Independent evidence audit of frozen barrier bound; never run any scorer.

--smoke checks arithmetic/edge cases only. --full additionally examines the
small multipipe operation-level relaxation and the existing 100 + 60 results.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
from itertools import permutations, product
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
THEORY = "f16746ff2ab112ae8e802711e90d74829c419eb9"
OUTPUT = "results/a/q1-yuanzhifang/barrier-audit-20260924/full"
PARTIAL_COMMIT = "29eaa4e3fdae2997976a34ecce5cf531ca2cee2c"
PARTIAL_OUTPUT_SHA256 = {
    "bounds-100x5.json": "965c75080cbeb8b748502b1af2e29e3748dded6f952bec9d88016dd5d4ab519e",
    "synthetic-checks.json": "83bb0c8a7ebda55b5453d8a329e0009cdda35d54fba59804c2b73387629831cd",
}
BATCHES = (
    ("A", "9b07b791cbbb950410d56d2c8c02407fde013982", "stage-a-20260924/board-feed-20260924T141300Z-stage-a.json"),
    ("B", "0441891f60b07a456a0f21ed74a024987edd8cd9", "stage-b-20260924/board-feed-20260924T143000Z-stage-b.json"),
    ("C", "88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a", "stage-c-20260924/board-feed-20260924T153000Z-stage-c.json"),
    ("D", "a7f51f2d5ca7d735899addd8bc14900045484fc3", "stage-d-20260924/board-feed-20260924T155800Z-stage-d.json"),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False); out.write("\n")


class Blobs:
    def __init__(self, commit):
        self.commit, self.raw = commit, {}
        self.checkout_differences = []

    def load(self, paths):
        paths = sorted(set(paths) - self.raw.keys())
        if not paths:
            return
        data = subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT,
                  input="".join(self.commit + ":" + p + "\n" for p in paths).encode())
        cursor = 0
        for path in paths:
            end = data.index(b"\n", cursor)
            _, kind, size = data[cursor:end].split()
            assert kind == b"blob", path
            cursor = end + 1
            self.raw[path] = data[cursor:cursor + int(size)]
            cursor += int(size)
            assert data[cursor:cursor + 1] == b"\n"; cursor += 1
            if (ROOT / path).exists():
                local = (ROOT / path).read_bytes()
                if local != self.raw[path]:
                    # These historical text receipts were checked out through
                    # autocrlf. Always consume the fixed Git blob. No exception
                    # applies to official source, input, plan or result bytes.
                    assert self.commit == THEORY and path.startswith("results/benchmark-board/official-singlecore-20260924/") and path.endswith("/run.json"), path
                    assert local.replace(b"\r\n", b"\n") == self.raw[path], path
                    self.checkout_differences.append({"path": path, "difference": "CRLF checkout only",
                                                      "local_sha256": sha(local), "fixed_git_sha256": sha(self.raw[path])})
        assert cursor == len(data)

    def json(self, path):
        self.load([path]); raw = self.raw[path]
        return json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)


def load_fixed_module():
    paths = ["src/q1_yuanzhifang/barrier_bound.py", "src/q1_yuanzhifang/construct.py",
             "docs/a/q1-yuanzhifang/BARRIER_BOUND.md"]
    hashes = {}
    for path in paths:
        raw = (ROOT / path).read_bytes()
        assert raw == git("show", THEORY + ":" + path), path
        hashes[path] = sha(raw)
    manifest_local = (ROOT / "docs/a/source-manifest.json").read_bytes()
    manifest_raw = git("show", THEORY + ":docs/a/source-manifest.json")
    # The manifest is a text index, not an official input. Read its fixed Git
    # blob; permit and record only CRLF checkout conversion in the local copy.
    assert manifest_local.replace(b"\r\n", b"\n") == manifest_raw
    manifest_identity = {"fixed_git_sha256": sha(manifest_raw), "local_sha256": sha(manifest_local),
                         "fixed_git_bytes": len(manifest_raw), "local_bytes": len(manifest_local),
                         "difference": "identical" if manifest_local == manifest_raw else "CRLF checkout only",
                         "authority": THEORY + ":docs/a/source-manifest.json"}
    hashes["docs/a/source-manifest.json"] = sha(manifest_raw)
    manifest = json.loads(manifest_raw)
    official = {}
    for item in manifest["files"]:
        if item["path"].startswith("code/"):
            path = "data/raw/a/official/" + item["path"]
            raw = (ROOT / path).read_bytes()
            assert sha(raw) == item["sha256"]
            assert raw == git("show", THEORY + ":" + path)
            hashes[path] = sha(raw)
            official[item["path"]] = sha(raw)
    assert len(official) == 10
    assert sha("".join(p + "\t" + h + "\n" for p, h in sorted(official.items())).encode()) == manifest["official_code_hash"]
    # Import only after checking the exact author/theorem dependencies. The
    # lower_bound function does not call construct or any evaluator/compiler.
    sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
    import barrier_bound
    return barrier_bound, hashes, manifest, manifest_identity


def graph(edges, pipes=("PIPE_V",) * 4, weights=(0, 3, 2, 4)):
    return {"ops": [{"id": u, "op": "ADD", "pipe": p, "cycles": weights[u]} for u, p in enumerate(pipes)],
            "tensors": [], "edges": [{"source": u, "target": v} for u, v in edges]}


def smoke(module):
    inverse_checks = endpoint_checks = 0
    for k, lag, ends, work in product(range(1, 6), range(6), range(3), range(41)):
        want = next(d for d in range(work + 1) if work <= d + (k - 1) * max(d - ends * lag, 0))
        assert module.gate_capacity_inverse(work, k, lag, ends) == want
        inverse_checks += 1
    for k, lag, d in product(range(2, 6), range(8), range(50)):
        same = d + (k - 1) * max(d - 2 * lag, 0)
        different = 2 * max(d - lag, 0) + (k - 2) * max(d - 2 * lag, 0)
        assert different <= same
        endpoint_checks += 1
    empty = {"ops": [], "tensors": [], "edges": []}
    assert module.lower_bound(empty, 5)["lower_bound_cycles"] == 0
    chain = graph([(0, 1)], ("PIPE_M", "PIPE_V"), (7, 11))
    tensor_chain = {**chain, "tensors": [{"id": 100, "pos": "UB", "size": 2}],
                    "edges": [{"source": 0, "target": 100}, {"source": 100, "target": 1}]}
    assert module.lower_bound(chain, 5)["lower_bound_cycles"] == 18
    assert module.lower_bound(tensor_chain, 5)["lower_bound_cycles"] == 18
    independent = graph([], ("PIPE_M", "PIPE_V"), (7, 11))
    assert module.lower_bound(independent, 1)["lower_bound_cycles"] == 11
    bridge = graph([(0, 1), (1, 2), (2, 3)], ("PIPE_M", "PIPE_MTE3", "PIPE_MTE2", "PIPE_V"), (7, 0, 0, 11))
    bridge["ops"][1]["op"], bridge["ops"][2]["op"] = "COPY_OUT", "COPY_IN"
    assert module.lower_bound(bridge, 5)["lower_bound_cycles"] == 11
    zero = graph([], ("PIPE_V",), (0,))
    assert module.lower_bound(zero, 5)["lower_bound_cycles"] == 1
    return {"capacity_inverse_checks": inverse_checks, "different_endpoint_capacity_checks": endpoint_checks,
            "edge_cases": ["empty graph", "empty inter-barrier intervals", "direct retained edge", "retained tensor edge",
                           "different pipes are not summed absent dependency", "COPY bridge deliberately not contracted", "zero cycles clamped to one"]}


def relaxed_checks(module):
    """Enumerate a superset of legal P1 compute schedules, not candidate plans.

    Keep only per-op retained dependencies with delta on different-core edges
    and one slot per (core,pipe). Drop Task occupancy/gates, memory and COPY.
    Every legal P1 result projects to these constraints even when a Task spans
    barriers. Projected total op orders cover the resource-order choices.
    """
    possible = [(u, v) for u in range(4) for v in range(u + 1, 4)]
    schedules, layouts, closure_checks, minimum_margin = 0, 0, 0, None
    weights = [1, 3, 2, 4]
    for mask in range(64):
        edges = [e for bit, e in enumerate(possible) if mask & (1 << bit)]
        pred = {v: [u for u, w in edges if w == v] for v in range(4)}
        succ = {u: {v for w, v in edges if w == u} for u in range(4)}
        reach = set(edges)
        for via in range(4):
            for u, v in product(range(4), repeat=2):
                if (u, via) in reach and (via, v) in reach:
                    reach.add((u, v))
        expected = [u for u in range(4) if all(v == u or (u, v) in reach or (v, u) in reach for v in range(4))]
        assert module.comparable_barriers(range(4), pred, succ) == expected
        closure_checks += 1
        orders = [order for order in permutations(range(4))
                  if all(order.index(u) < order.index(v) for u, v in edges)]
        for pipes in product(("PIPE_M", "PIPE_V"), repeat=4):
            g = graph(edges, pipes)
            bound = module.lower_bound(g, 2, 2)["lower_bound_cycles"]
            layouts += 1
            for owner in product(range(2), repeat=4):
                for order in orders:
                    ends, slots = {}, defaultdict(int)
                    for u in order:
                        start = max([slots[(owner[u], pipes[u])],
                                     *(ends[p] + (2 if owner[p] != owner[u] else 0) for p in pred[u])])
                        ends[u] = start + weights[u]; slots[(owner[u], pipes[u])] = ends[u]
                    actual = max(ends.values()); margin = actual - bound
                    assert margin >= 0, {"edges": edges, "pipes": pipes, "owner": owner, "order": order,
                                         "bound": bound, "relaxed_makespan": actual}
                    minimum_margin = margin if minimum_margin is None else min(minimum_margin, margin)
                    schedules += 1
    return {"dag_count": 64, "pipe_layouts_checked": layouts, "relaxed_schedules_checked": schedules,
            "closure_checks": closure_checks, "minimum_margin_cycles": minimum_margin,
            "scope": "All forward four-node DAGs, all two-pipe assignments, all two-core op allocations and compatible projected total orders; weights 1/3/2/4, delta 2. This is finite falsification, not a general proof or a submitted solver."}


def compact(bound):
    return {"lower_bound_cycles": bound["lower_bound_cycles"],
            "global_pipe_load_bound_cycles": bound["global_pipe_load_bound_cycles"],
            "components": [{"anchor": c["anchor"], "compute_ops": c["compute_ops"], "barrier_count": len(c["barriers"]),
                            "lower_bound_cycles": c["lower_bound_cycles"]} for c in bound["components"]],
            "full_recomputable_bound_sha256": sha(json.dumps(bound, sort_keys=True, separators=(",", ":")).encode())}


def audit(args, module, source_hashes, manifest, manifest_identity):
    started, tick = utc(), time.perf_counter()
    config_raw = (args.graphs / "config.txt").read_bytes()
    expected = {i["path"]: i["sha256"] for i in manifest["files"]}
    assert sha(config_raw) == expected["data/config.txt"]
    config = module.read_scene_a_config(str(args.graphs / "config.txt"))
    delta = config["task_cross_core_wait_cycles"]
    assert delta == 1000
    out = ROOT / OUTPUT
    if args.resume_existing:
        assert set(p.name for p in out.iterdir()) == set(PARTIAL_OUTPUT_SHA256)
        for name, digest in PARTIAL_OUTPUT_SHA256.items():
            assert sha((out / name).read_bytes()) == digest, name
        checks = json.loads((out / "synthetic-checks.json").read_bytes())
        prior_bounds = json.loads((out / "bounds-100x5.json").read_bytes())
    else:
        out.mkdir(parents=True, exist_ok=False)
        checks = smoke(module); checks["multipipe_relaxation"] = relaxed_checks(module)
        dump(out / "synthetic-checks.json", checks)
    bounds, input_hashes = {}, {}
    for case in (f"{n:03d}" for n in range(1, 101)):
        raw = (args.graphs / f"case_{case}.json").read_bytes()
        assert sha(raw) == expected[f"data/case_{case}.json"]
        input_hashes[case] = sha(raw)
        if args.resume_existing:
            bounds[case] = prior_bounds[case]
        else:
            g = json.loads(raw)
            bounds[case] = {str(k): compact(module.lower_bound(g, k, delta)) for k in range(1, 6)}
    if not args.resume_existing:
        dump(out / "bounds-100x5.json", bounds)
    compared, failed, feeds, artifacts = [], [], [], []
    for label, commit, suffix in BATCHES:
        path = "results/a/q1-yuanzhifang/" + suffix
        snapshot = Blobs(commit); feed = snapshot.json(path)
        paths = {a["path"] for r in feed["records"] for a in r["artifacts"].values()}
        snapshot.load(paths)
        feeds.append({"stage": label, "commit": commit, "path": path, "sha256": sha(snapshot.raw[path]), "records": len(feed["records"])})
        for r in feed["records"]:
            case, k = r["case_id"], r["cores"]
            assert r["identity"]["graph_sha256"] == input_hashes[case]
            assert r["identity"]["config_sha256"] == sha(config_raw)
            assert r["identity"]["official_sha256"] == manifest["official_code_hash"]
            for kind, item in r["artifacts"].items():
                raw = snapshot.raw[item["path"]]
                assert sha(raw) == item["sha256"]
                artifacts.append({"commit": commit, "path": item["path"], "sha256": sha(raw)})
            run = snapshot.json(r["artifacts"]["run"]["path"])
            for item in run["artifacts"].values():
                assert sha(gzip.decompress(snapshot.raw[item["path"]])) == item["raw_sha256"]
            if r["status"] != "ok":
                assert r["metrics"]["makespan_cycles"] is None
                failed.append({"stage": label, "attempt_id": r["attempt_id"], "case_id": case, "cores": k, "status": r["status"], "failure": r["provenance"]["measurement"]["failure"]})
                continue
            plan = snapshot.json(r["artifacts"]["plan"]["path"])
            assert sha(snapshot.raw[r["artifacts"]["plan"]["path"]]) == r["identity"]["plan_sha256"]
            assert set(plan) == {"node_to_subgraph", "core_schedules"} and len(plan["core_schedules"]) == k
            result = snapshot.json(r["artifacts"]["result"]["path"])
            assert result["scene"] == "A" and result["num_cores"] == k
            assert result["makespan"] == r["metrics"]["makespan_cycles"]
            b = bounds[case][str(k)]["lower_bound_cycles"]
            compared.append({"kind": "multicore", "stage": label, "case_id": case, "cores": k, "attempt_id": r["attempt_id"],
                             "bound_cycles": b, "e0_cycles": result["makespan"], "margin_cycles": result["makespan"] - b,
                             "u_over_l": result["makespan"] / b, "bound_le_e0": b <= result["makespan"],
                             "artifact_commit": commit, "result_sha256": r["artifacts"]["result"]["sha256"]})
    # Same official singlecore receipts, fixed at the audited theorem commit.
    single = Blobs(THEORY)
    single_paths = [f"results/benchmark-board/official-singlecore-20260924/{i:03d}/run.json" for i in range(1, 101)]
    single.load(single_paths)
    single_results = [single.json(p)["artifacts"]["result.json"]["path"] for p in single_paths]
    single.load(single_results)
    for path in single_paths:
        run = single.json(path); case = run["case_id"]
        assert run["graph_sha256"] == input_hashes[case]
        assert run["config_sha256"] == sha(config_raw) and run["official_code_hash"] == manifest["official_code_hash"]
        assert run["status"] == "ok" and run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
        ref = run["artifacts"]["result.json"]; packed = single.raw[ref["path"]]; raw = gzip.decompress(packed)
        assert sha(packed) == ref["sha256"] and sha(raw) == ref["raw_sha256"]
        result = json.loads(raw); assert result["makespan"] == run["makespan_cycles"]
        b = bounds[case]["1"]["lower_bound_cycles"]
        compared.append({"kind": "official_singlecore", "stage": "existing", "case_id": case, "cores": 1,
                         "attempt_id": "official-singlecore-20260924-" + case, "bound_cycles": b, "e0_cycles": result["makespan"],
                         "margin_cycles": result["makespan"] - b, "u_over_l": result["makespan"] / b,
                         "bound_le_e0": b <= result["makespan"], "artifact_commit": THEORY, "result_sha256": ref["sha256"]})
        artifacts.extend([{"commit": THEORY, "path": path, "sha256": sha(single.raw[path])},
                          {"commit": THEORY, "path": ref["path"], "sha256": sha(packed), "raw_sha256": sha(raw)}])
    assert len(compared) == 160 and len(failed) == 1
    violations = [r for r in compared if not r["bound_le_e0"]]
    dump(out / "comparisons.json", compared)
    dump(out / "failed-attempts.json", failed)
    with (out / "comparisons.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(compared[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(compared)
    evidence = {"theorem_commit": THEORY, "audit_commit": git("rev-parse", "HEAD").decode().strip(), "source_sha256": source_hashes,
                "config_sha256": sha(config_raw), "official_code_hash": manifest["official_code_hash"], "input_sha256": input_hashes,
                "manifest_identity": manifest_identity,
                "singlecore_receipt_checkout_differences": single.checkout_differences,
                "bounds_generation_commit": PARTIAL_COMMIT if args.resume_existing else git("rev-parse", "HEAD").decode().strip(),
                "resumed_existing_outputs": PARTIAL_OUTPUT_SHA256 if args.resume_existing else None,
                "timing_scope": "Evidence continuation only; original bounds/finite checks reused byte-identically" if args.resume_existing else "Full audit",
                "feeds": feeds, "artifacts": artifacts,
                "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0, "task_compiler": 0},
                "comparisons": 160, "successful_multicore": 60, "official_singlecore": 100, "failed_not_numeric": 1,
                "violations": violations, "started_at": started, "finished_at": utc(), "wall_seconds": time.perf_counter() - tick,
                "scope": "Consistency with existing E0 evidence is necessary but does not prove the universal theorem. No new official evaluation or solver execution.",
                "dot_clean": "unavailable on Windows"}
    dump(out / "verification.json", evidence)
    print(json.dumps({"comparisons": 160, "violations": len(violations), "failed_not_numeric": len(failed), "calls": evidence["calls"], "wall_seconds": evidence["wall_seconds"]}))
    if violations:
        raise SystemExit(2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graphs", type=Path)
    mode = p.add_mutually_exclusive_group(required=True); mode.add_argument("--smoke", action="store_true"); mode.add_argument("--full", action="store_true")
    p.add_argument("--resume-existing", action="store_true", help="Continue evidence checks from the fixed, hashed partial outputs without recomputing bounds")
    args = p.parse_args()
    module, hashes, manifest, manifest_identity = load_fixed_module()
    if args.smoke:
        print(json.dumps({"checks": smoke(module), "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}))
        return
    if args.graphs is None:
        p.error("--full requires --graphs")
    own_path = "src/q1_yuanzhifang/audit_barrier.py"
    assert (ROOT / own_path).read_bytes() == git("show", "HEAD:" + own_path)
    hashes[own_path] = sha((ROOT / own_path).read_bytes())
    audit(args, module, hashes, manifest, manifest_identity)


if __name__ == "__main__":
    main()
