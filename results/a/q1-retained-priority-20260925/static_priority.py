"""Inspect frozen Task priority keys only; never construct or place a real plan."""
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT_SHA = "84080acedc0e44fbdebdf7aa4166e8a32003dc80"
SOURCE_SHA = "8f0009ac4a934c2161943b70530e418eb55f9366"
PREFIX = "results/a/q1-overload-activation-20260925/20260924T1636Z-overload16/cells/"
RECEIPTS = {}


def read(sha, path):
    b = subprocess.check_output(["git", "show", sha + ":" + path], cwd=ROOT)
    RECEIPTS[sha + ":" + path] = hashlib.sha256(b).hexdigest()
    return json.loads(gzip.decompress(b) if path.endswith(".gz") else b)


def main():
    audit = read(AUDIT_SHA, "results/a/q1-overload-regression-review-20260925/analysis.json")
    output = []
    for row in audit["cases"]:
        case = row["case"]
        if case not in {"031", "077", "053", "087"}:
            continue
        tasks = {int(t): v for t, v in row["overload"]["tasks"].items()}
        result = read(SOURCE_SHA, PREFIX + case + "/k5/result.json.gz")
        pred = {t: set() for t in tasks}
        succ = {t: set() for t in tasks}
        for e in result["task_dependencies"]:
            pred[e["target"]].add(e["source"])
            succ[e["source"]].add(e["target"])
        degree = {t: len(p) for t, p in pred.items()}
        queue = [t for t in tasks if not degree[t]]
        heapq.heapify(queue)
        topo = []
        while queue:
            t = heapq.heappop(queue)
            topo.append(t)
            for s in sorted(succ[t]):
                degree[s] -= 1
                if not degree[s]:
                    heapq.heappush(queue, s)
        assert len(topo) == len(tasks)
        tail = {}
        for t in reversed(topo):
            tail[t] = tasks[t]["compute_floor"] + max((tail[s] for s in succ[t]), default=0)
        priority = dict(tail)
        comp_work = {c["anchor"]: c["pipe_floor"] for c in row["components"]}
        retained = []
        for t, task in sorted(tasks.items()):
            if task["role"] == "retained":
                assert not pred[t] and not succ[t]
                priority[t] = max(comp_work[c] for c in task["component_anchors"])
                assert 1 <= priority[t] <= task["compute_floor"]
                retained.append({"task": t, "duration_proxy_unchanged": task["compute_floor"],
                                 "old_ready_priority": tail[t], "new_ready_priority": priority[t],
                                 "component_count": len(task["component_anchors"])})
            else:
                assert priority[t] == tail[t]
        ready = [t for t in tasks if not pred[t]]
        def ranking(keys):
            return [{"task": t, "role": tasks[t]["role"], "priority": keys[t]}
                    for t in sorted(ready, key=lambda t: (-keys[t], t))]
        split_roots = [t for t in ready if tasks[t]["role"] == "split"]
        split_tail = max(tail[t] for t in split_roots)
        assert split_tail == row["overload"]["split_only_data_tail_max"]
        output.append({"case": case, "purpose": "target" if case in {"031", "077"} else "already_improved_control",
                       "prior_measured_fallback_M": row["fallback"]["makespan"],
                       "prior_measured_overload_M": row["overload"]["makespan"],
                       "split_root_max_compute_tail": split_tail,
                       "retained_bundles": retained,
                       "initial_ready_ranking_old": ranking(tail),
                       "initial_ready_ranking_candidate": ranking(priority),
                       "retained_initially_above_best_split_before": sum(x["old_ready_priority"] > split_tail for x in retained),
                       "retained_initially_above_best_split_after": sum(x["new_ready_priority"] > split_tail for x in retained),
                       "candidate_makespan": None,
                       "not_a_plan": "Initial ready ranking only; later ready events and EFT assignments are not executed."})
    files = ["src/q1/component_overload.py", "tests/q1/test_retained_priority.py",
             "results/a/q1-retained-priority-20260925/static_priority.py"]
    report = {"kind": "static_candidate_priority_analysis_not_performance",
              "base_algorithm_commit": "3c6e41b938c764d207de45584fb526c64f4eb845",
              "source_commit": SOURCE_SHA, "audit_commit": AUDIT_SHA,
              "source_artifact_sha256": RECEIPTS,
              "candidate_files_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
              "calls": {"real_graph_constructor": 0, "placement": 0, "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
              "cases": output}
    (OUT / "static_priority.json").write_text(json.dumps(report, indent=2) + "\n")
    for row in output:
        print(row["case"], row["purpose"], "split tail", row["split_root_max_compute_tail"],
              "retained above", row["retained_initially_above_best_split_before"],
              "->", row["retained_initially_above_best_split_after"])


if __name__ == "__main__":
    main()
