"""Read-only case008 structure audit of the archived Pro proposal; zero E0 calls.

Recognition uses the explicitly identified author module. Interface sums and the
integer cut-count bound are recomputed independently below, not copied from its
certificate. This is an assumption check, not proof of arbitrary program behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import zipfile


def audit(root: Path) -> dict:
    source = root / "AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py"
    spec = importlib.util.spec_from_file_location("archived_p1_phase_cut", source)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    archive = root / "data/raw/a/official-cases.zip"
    with zipfile.ZipFile(archive) as z:
        raw = z.read("data/case_008.json")
    graph = json.loads(raw)
    view, chains, _, _, _ = mod.recognize(graph)
    eligible = {u for chain in chains for u in chain}
    rows = []
    all_signatures = []
    for chain in chains:
        cuts = []
        for j in range(len(chain) - 1):
            left, right = set(chain[:j + 1]), set(chain[j + 1:])
            crossed = [tid for tid in view.tensors
                       if view.producers[tid] & left and view.consumers[tid] & right]
            cuts.append({
                "after_index": j,
                "tensor_ids": sorted(crossed),
                "bytes": sum(view.tensors[t]["size"] for t in crossed),
                "extra_service": 2 * sum(max(1, (view.tensors[t]["size"] + 59) // 60)
                                         for t in crossed),
            })
        all_signatures.append([(x["bytes"], x["extra_service"]) for x in cuts])
        rows.append({"chain": chain, "cuts": cuts})
    assert all(s == all_signatures[0] for s in all_signatures)
    author_cuts = mod.cut_table(graph, chains[0], 60)
    assert [(x["internal_cut_bytes"], x["universal_extra_service_min"])
            for x in author_cuts] == all_signatures[0]
    necessary = []
    for t in view.tensors:
        ps, cs = view.producers[t] & eligible, view.consumers[t] & eligible
        output_tap = any(view.ops[u]["op"] == "COPY_OUT" for u in view.consumers[t])
        if (not ps and cs) or (ps and (not cs or output_tap)):
            necessary.append(t)
    d0 = sum(max(1, (view.tensors[t]["size"] + 59) // 60) for t in necessary)
    chain = chains[0]
    a = max(1, view.ops[chain[0]]["cycles"])
    c = max(1, view.ops[chain[-1]]["cycles"])
    b = sum(max(1, view.ops[u]["cycles"]) for u in chain[1:-1])
    n, ell = len(chains), a + b + c
    delta = min(x[1] for x in all_signatures[0])
    bounds = []
    for k in range(1, 6):
        choices = [dict(split=s, bound=max((n * ell - s * b + k - 1) // k,
                    ell * ((n - s + k - 1) // k), d0 + s * delta))
                   for s in range(n + 1)]
        best = min(choices, key=lambda x: (x["bound"], x["split"]))
        bounds.append({"cores": k, "restricted_uncut_lower_bound": ell * ((n + k - 1) // k),
                       "conditional_cut_or_blocking_lower_bound": best})
    return {
        "kind": "static_assumption_audit_NOT_E0_NOT_solver",
        "graph_sha256": hashlib.sha256(raw).hexdigest(),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "author_recognizer_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "recognized": True, "chains": n, "a": a, "b": b, "c": c,
        "necessary_boundary_service_cycles": d0, "minimum_cut_extra_service_cycles": delta,
        "all_chain_interface_signatures_equal": True,
        "independent_sums_match_author_cut_table": True,
        "bounds_conditional_on_intact_chain_FIFO_theorem": bounds,
        "chain_interfaces": rows,
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.perf_counter()
    result = audit(Path(__file__).resolve().parents[2])
    result["static_wall_seconds"] = time.perf_counter() - t0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "chain_interfaces"}, ensure_ascii=False))
