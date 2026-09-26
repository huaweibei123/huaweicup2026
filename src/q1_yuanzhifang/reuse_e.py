"""Read-only, fixed-Git evidence audit for Stage E; never imports a solver.

The cache is available only to the outer benchmark after its fresh solver has
exited. A semantic plan match is deliberately insufficient for E0 reuse.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

from benchmark import ROOT, dump, sha, utc

SOLVER = "311431da987f20158ad9453f5c0d558179aa9549"
CAPTAIN = "05f8fa0f7e52f5914f14815f6bdbcb851b631556"
CASES = tuple(f"{i:03d}" for i in range(1, 101))
SOURCES = (
    ("ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9", "results/a/q1-bounded-full4-20260924/20260924T1439Z-boundedfull4-99/board-feed.json", "bounded"),
    ("4d374dc25b5698491ddbb92837789a23a4ad3102", "results/a/q1-bounded-probe-20260924/20260924T1432Z-bounded014/board-feed.json", "bounded"),
    ("88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a", "results/a/q1-yuanzhifang/stage-c-20260924/board-feed-20260924T153000Z-stage-c.json", "fork"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class GitBlobs:
    """One read-only cat-file process avoids hundreds of Git startup costs."""

    def __enter__(self):
        self.process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        return self

    def __exit__(self, *args):
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.wait(timeout=10)

    def read(self, commit, path):
        p = PurePosixPath(path)
        require(re.fullmatch(r"[0-9a-f]{40}", commit), "Full Git commit required")
        require(not p.is_absolute() and ".." not in p.parts and not any(c in path for c in "\\:\r\n"), "Unsafe Git path")
        self.process.stdin.write(f"{commit}:{path}\n".encode())
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode().rstrip().split()
        require(len(header) == 3 and header[1] == "blob", f"Missing fixed blob {commit}:{path}")
        size = int(header[2])
        require(size <= 64 * 1024 * 1024, "Stored evidence blob exceeds 64 MiB")
        data = self.process.stdout.read(size)
        require(len(data) == size and self.process.stdout.read(1) == b"\n", "Truncated Git blob")
        return data


def raw_json(data, path):
    raw = gzip.decompress(data) if path.endswith(".gz") else data
    return raw, json.loads(raw)


def verify_official(blobs, commit, manifest):
    hashes = {}
    for item in manifest["files"]:
        if item["path"].startswith("code/"):
            h = sha(blobs.read(commit, "data/raw/a/official/" + item["path"]))
            require(h == item["sha256"], "Historical official source mismatch")
            hashes[item["path"]] = h
    require(len(hashes) == 10, "Expected ten official source files")
    require(sha("".join(f"{p}\t{hashes[p]}\n" for p in sorted(hashes)).encode()) == manifest["official_code_hash"], "Official aggregate hash mismatch")


def verify_record(blobs, commit, record, manifest):
    """Return checked original bytes plus compact, derived evidence facts."""
    expected = {x["path"]: x["sha256"] for x in manifest["files"]}
    case, cores = record["case_id"], record["cores"]
    require(record["status"] == "ok" and record["problem"] == "P1" and cores == 4, "Not successful P1 k4 evidence")
    for name, value in (("graph_sha256", expected[f"data/case_{case}.json"]),
                        ("config_sha256", expected["data/config.txt"]),
                        ("official_sha256", manifest["official_code_hash"])):
        require(record["identity"][name] == value, "Historical " + name + " mismatch")
    data, parsed, raw_hashes = {}, {}, {}
    for kind in ("plan", "result", "trace", "run"):
        item = record["artifacts"][kind]
        data[kind] = blobs.read(commit, item["path"])
        require(sha(data[kind]) == item["sha256"], "Historical artifact hash mismatch: " + kind)
        raw, parsed[kind] = raw_json(data[kind], item["path"])
        raw_hashes[kind] = sha(raw)
    plan, result, trace, run = (parsed[k] for k in ("plan", "result", "trace", "run"))
    require(record["identity"]["plan_sha256"] == sha(data["plan"]), "Plan identity mismatch")
    require(set(plan) == {"node_to_subgraph", "core_schedules"} and len(plan["core_schedules"]) == cores, "Plan schema mismatch")
    require(result["scene"] == "A" and result["num_cores"] == cores, "Historical result scenario mismatch")
    m = result["makespan"]
    require(type(m) is type(record["metrics"]["makespan_cycles"]) and m == record["metrics"]["makespan_cycles"], "Feed/result makespan mismatch")
    require(run["case_id"] == case and run["cores"] == cores and run["status"] == "ok", "Run identity/status mismatch")
    require(run["plan_sha256"] == sha(data["plan"]), "Run plan hash mismatch")
    require(run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0}, "Historical call receipt mismatch")
    require(run["evaluation"]["status"] == "ok" and run["evaluation"].get("returncode", run["evaluation"].get("exit_code")) == 0, "Historical E0 did not finish successfully")
    require(run["makespan_cycles"] == m and run["data_movement_bytes"] == result["data_movement_bytes"], "Run/result metric mismatch")
    if "graph_sha256" in run:
        require(run["graph_sha256"] == record["identity"]["graph_sha256"], "Run graph mismatch")
    for kind in ("result", "trace"):
        item = run["artifacts"].get(kind, run["artifacts"].get(kind + ".json"))
        require(item and item["sha256"] == sha(data[kind]), "Run artifact mismatch: " + kind)
        if "raw_sha256" in item:
            require(item["raw_sha256"] == raw_hashes[kind], "Run uncompressed artifact mismatch")
    require(max(x["ts"] + x["dur"] for x in trace["traceEvents"] if x.get("ph") == "X") == m, "Trace endpoint/result mismatch")
    require(max(t["end"] for c in result["per_core_timeline"] for t in c["tasks"]) == m, "Task timeline/result mismatch")
    return data, {"raw_sha256": raw_hashes, "makespan_cycles": m,
                  "data_movement_bytes": result["data_movement_bytes"],
                  "task_count": len(result["step3_by_task"]),
                  "historical_evaluation": run["evaluation"]}


def prepare(output):
    t0, started = time.perf_counter(), utc()
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_bytes())
    entries, feeds, singles = [], [], {}
    official_checked = set()
    with GitBlobs() as blobs:
        for commit, path, candidate in SOURCES:
            feed_bytes = blobs.read(commit, path)
            feed = json.loads(feed_bytes)
            selected = [r for r in feed["records"] if r["status"] == "ok" and r["cores"] == 4
                        and (candidate != "fork" or r["variant"] == "chain-atomic-grain4")]
            feeds.append({"commit": commit, "path": path, "sha256": sha(feed_bytes), "selected_records": len(selected), "candidate": candidate})
            for record in selected:
                official_commit = record["evaluator"]["commit"]
                if official_commit not in official_checked:
                    verify_official(blobs, official_commit, manifest)
                    official_checked.add(official_commit)
                _, checked = verify_record(blobs, commit, record, manifest)
                entries.append({"candidate": candidate, "commit": commit, "feed_path": path,
                                "feed_sha256": sha(feed_bytes), "record": record, "checked": checked})
        bounded = [e for e in entries if e["candidate"] == "bounded"]
        require(len(bounded) == 100 and {e["record"]["case_id"] for e in bounded} == set(CASES), "Bounded comparison must cover exactly all 100 cases")
        for case in CASES:
            base = f"results/benchmark-board/official-singlecore-20260924/{case}"
            run_raw = blobs.read(SOLVER, base + "/run.json")
            run = json.loads(run_raw)
            ref = run["artifacts"]["result.json"]
            result_bytes = blobs.read(SOLVER, ref["path"])
            raw, result = raw_json(result_bytes, ref["path"])
            require(sha(result_bytes) == ref["sha256"] and sha(raw) == ref["raw_sha256"], "Singlecore original hash mismatch")
            require(run["status"] == "ok" and run["returncode"] == 0 and run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore", "Not official denominator")
            expected = next(e["record"]["identity"] for e in bounded if e["record"]["case_id"] == case)
            require(all(run[a] == expected[b] for a, b in (("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"), ("official_code_hash", "official_sha256"))), "Singlecore identity mismatch")
            require(result["scene"] == "A" and result["makespan"] == run["makespan_cycles"], "Singlecore result mismatch")
            singles[case] = {"commit": SOLVER, "run": {"path": base + "/run.json", "sha256": sha(run_raw)},
                             "result": ref, "makespan_cycles": result["makespan"], "identity": expected}
    output.parent.mkdir(parents=True, exist_ok=True)
    dump(output, {"schema": "q1-stage-e-exact-byte-evidence-v1", "started_at": started,
                  "finished_at": utc(), "wall_seconds": time.perf_counter() - t0,
                  "solver_commit": SOLVER, "official_code_hash": manifest["official_code_hash"],
                  "feeds": feeds, "entries": entries, "singlecore": singles,
                  "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                  "scope": "Original fixed Git bytes, receipt/identity/metric/trace endpoint audit; not an independent E0 rerun, optimality proof or run-behavior attestation."})
    print(json.dumps({"status": "ok", "entries": len(entries), "bounded": len(bounded), "singlecore": len(singles), "wall_seconds": time.perf_counter() - t0}))


def exact_match(index, case, cores, candidate, plan_bytes):
    digest = sha(plan_bytes)
    matches = [e for e in index["entries"] if e["record"]["case_id"] == case
               and e["record"]["cores"] == cores
               and e["record"]["identity"]["plan_sha256"] == digest]
    # This is an evidence identity choice, never quality-based candidate selection.
    return sorted(matches, key=lambda e: (e["candidate"] != candidate, e["commit"], e["record"]["attempt_id"]))[0] if matches else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
