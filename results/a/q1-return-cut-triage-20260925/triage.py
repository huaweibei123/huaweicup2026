"""One-process, recognition/integer-only triage. Run only in a confirmed static slot.

No plan, placement, model, compiler or evaluator is imported or called. The only
Pro code available consists of recognition definitions in strict_recognizer.py.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import re
import signal
import time
import zipfile

import strict_recognizer as recognizer

ROOT = Path(__file__).resolve().parents[3]
CONFIG_SHA256 = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"


def config_values(data):
    if hashlib.sha256(data).hexdigest() != CONFIG_SHA256:
        raise ValueError("Frozen official config byte identity mismatch")
    sections, section = {}, None
    for line in data.decode().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line.strip("[]")
            sections[section] = {}
        else:
            key, value = line.split()
            sections[section][key] = int(value)
    return sections


def frac(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator, "exact": str(value)}


def service(size, bandwidth):
    return max(1, (size + bandwidth - 1) // bandwidth)


def ratio(numerator, denominator):
    return frac(Fraction(numerator, denominator)) if denominator else None


def routing_metrics(v):
    """Whole COPY-contracted compute components and external-input structure."""
    eligible = {u for u, op in v.ops.items() if op["op"] not in recognizer.COPY}
    order = recognizer.topo(v.pred, v.succ)
    nearest = {}
    for u in reversed(order):
        if u in eligible:
            nearest[u] = {u}
        else:
            nearest[u] = set().union(*(nearest[s] for s in v.succ[u])) if v.succ[u] else set()
    succ = {u: set().union(*(nearest[s] for s in v.succ[u])) if v.succ[u] else set() for u in eligible}
    pred = {u: set() for u in eligible}
    for u, successors in succ.items():
        for s in successors:
            pred[s].add(u)
    unseen = set(eligible)
    components, owner = [], {}
    for root in sorted(eligible):
        if root not in unseen:
            continue
        unseen.remove(root)
        stack, nodes = [root], []
        while stack:
            u = stack.pop()
            nodes.append(u)
            owner[u] = len(components)
            for s in pred[u] | succ[u]:
                if s in unseen:
                    unseen.remove(s)
                    stack.append(s)
        components.append(nodes)
    inputs = [set() for _ in components]
    for tid in v.tensors:
        producers = {owner[u] for u in v.producers[tid] & eligible}
        consumers = {owner[u] for u in v.consumers[tid] & eligible}
        for component in consumers - producers:
            inputs[component].add(tid)
    union = set().union(*inputs) if inputs else set()
    common = set.intersection(*inputs) if inputs else set()
    by_component, pipe_counts, type_counts, words = [], [], [], []
    compute_topo = recognizer.topo(pred, succ) if eligible else []
    component_words = [[] for _ in components]
    for u in compute_topo:
        component_words[owner[u]].append(v.ops[u]["pipe"])
    for i, nodes in enumerate(components):
        work, pipes, types = Counter(), Counter(), Counter()
        for u in nodes:
            op = v.ops[u]
            work[op["pipe"]] += max(1, op["cycles"])
            pipes[op["pipe"]] += 1
            types[op["op"]] += 1
        by_component.append({"anchor": min(nodes), "compute_ops": len(nodes),
                             "pipe_work": dict(sorted(work.items())),
                             "external_input_tensor_count": len(inputs[i]),
                             "external_input_bytes": sum(v.tensors[t]["size"] for t in inputs[i])})
        pipe_counts.append(tuple(sorted(pipes.items())))
        type_counts.append(tuple(sorted(types.items())))
        words.append(tuple(component_words[i]))
    input_union_bytes = sum(v.tensors[t]["size"] for t in union)
    input_intersection_bytes = sum(v.tensors[t]["size"] for t in common)
    return {"component_definition": "Nearest-compute COPY contraction, weak components; no plan generated",
            "component_count": len(components),
            "external_input_union_bytes": input_union_bytes,
            "external_input_intersection_bytes": input_intersection_bytes,
            "external_input_union_count": len(union), "external_input_intersection_count": len(common),
            "intersection_over_union_bytes": ratio(input_intersection_bytes, input_union_bytes),
            "total_compute_work_by_pipe": {pipe: sum(r["pipe_work"].get(pipe, 0) for r in by_component)
                                           for pipe in recognizer.PIPES},
            "per_pipe_component_work_range": {
                pipe: {"min": min((r["pipe_work"].get(pipe, 0) for r in by_component), default=0),
                       "max": max((r["pipe_work"].get(pipe, 0) for r in by_component), default=0)}
                for pipe in recognizer.PIPES},
            "compute_pipe_counts_equal": bool(components) and len(set(pipe_counts)) == 1,
            "compute_op_type_counts_equal": bool(components) and len(set(type_counts)) == 1,
            "id_tiebreak_topological_pipe_words_equal": bool(components) and len(set(words)) == 1,
            "pipe_word_scope": "One deterministic topological word, not a DAG isomorphism certificate",
            "components": by_component}


def strict_metrics(view, capacity, bandwidth, gate):
    v, chains, owned_tensors, _, _ = recognizer.recognize_prebuilt(view)
    eligible = {u for chain in chains for u in chain}
    chain = chains[0]
    idx = {u: i for i, u in enumerate(chain)}
    n, length = len(chains), len(chain)
    a = max(1, v.ops[chain[0]]["cycles"])
    b = sum(max(1, v.ops[u]["cycles"]) for u in chain[1:-1])
    c = max(1, v.ops[chain[-1]]["cycles"])
    ell = a + b + c

    # Every distinct internal tensor spans [producer, last consumer). External
    # input spans [first consumer, last consumer), causing one duplicated read.
    # Difference arrays include long skip tensors, not only adjacent outputs.
    internal_bytes = [0] * length
    internal_service = [0] * length
    external_bytes = [0] * length
    external_service = [0] * length
    for tid in owned_tensors[0]:
        tensor = v.tensors[tid]
        ps = v.producers[tid] & idx.keys()
        cs = v.consumers[tid] & idx.keys()
        if not cs:
            continue
        unit = service(tensor["size"], bandwidth)
        if ps:
            assert len(ps) == 1
            lo, hi = idx[next(iter(ps))], max(idx[u] for u in cs)
            assert lo < hi
            internal_bytes[lo] += tensor["size"]
            internal_bytes[hi] -= tensor["size"]
            internal_service[lo] += 2 * unit
            internal_service[hi] -= 2 * unit
        else:
            assert not (v.producers[tid] & eligible)
            lo, hi = min(idx[u] for u in cs), max(idx[u] for u in cs)
            external_bytes[lo] += tensor["size"]
            external_bytes[hi] -= tensor["size"]
            external_service[lo] += unit
            external_service[hi] -= unit
    for values in [internal_bytes, internal_service, external_bytes, external_service]:
        for j in range(1, length):
            values[j] += values[j - 1]
    cuts = [{"after_index": j, "producer_side_last_compute": chain[j],
             "complete_internal_interface_bytes": internal_bytes[j],
             "internal_extra_copy_bytes": 2 * internal_bytes[j],
             "internal_extra_service_cycles": internal_service[j],
             "external_input_duplicate_bytes": external_bytes[j],
             "external_input_duplicate_service_cycles": external_service[j],
             "exact_single_cut_extra_copy_bytes": 2 * internal_bytes[j] + external_bytes[j],
             "exact_single_cut_extra_service_cycles": internal_service[j] + external_service[j]}
            for j in range(length - 1)]

    necessary = {"input_count": 0, "output_count": 0, "bytes": 0, "service_cycles": 0}
    for tid, tensor in v.tensors.items():
        ps, cs = v.producers[tid] & eligible, v.consumers[tid] & eligible
        tap = any(v.ops[u]["op"] == "COPY_OUT" for u in v.consumers[tid])
        nin = int(bool(cs) and not ps)
        nout = int(bool(ps) and (not cs or tap))
        count = nin + nout
        necessary["input_count"] += nin
        necessary["output_count"] += nout
        necessary["bytes"] += count * tensor["size"]
        necessary["service_cycles"] += count * service(tensor["size"], bandwidth)
    assert all(necessary[key] % n == 0 for key in necessary)
    necessary["per_chain"] = {key: value // n for key, value in necessary.items()}

    def footprint(nodes):
        used = set()
        for u in nodes:
            used.update(v.in_t[u])
            used.update(v.out_t[u])
        return {pos: sum(v.tensors[t]["size"] for t in used
                         if ("UB" if v.tensors[t]["pos"] == "DDR" else v.tensors[t]["pos"]) == pos)
                for pos in capacity}

    prefix, tail, whole = footprint(chain[:-1]), footprint(chain[-1:]), footprint(chain)
    mixed = {p: prefix[p] + tail[p] for p in capacity}
    def q_limit(footprints):
        constraints = {p: capacity[p] // size for p, size in footprints.items() if size}
        return {"per_position": constraints,
                "q_raw_upper": min(constraints.values()) if constraints else None,
                "q_up_to_N": min(n, min(constraints.values())) if constraints else n,
                "unbounded_by_tensor_sum": not constraints}
    mixed_limit, whole_limit = q_limit(mixed), q_limit(whole)
    minimums = {}
    for name in ["complete_internal_interface_bytes", "internal_extra_service_cycles",
                 "exact_single_cut_extra_copy_bytes", "exact_single_cut_extra_service_cycles"]:
        minimum = min(x[name] for x in cuts)
        minimums[name] = {"value": minimum, "after_indices": [x["after_index"] for x in cuts if x[name] == minimum]}
    return_cut = cuts[-1]
    # Resource-overlap ceiling only. It ignores FIFO order, filling/draining,
    # external copies and gates, so it never predicts official improvement.
    overlap_ceiling = min(a + c, b)
    by_k = []
    for k in range(1, 6):
        ncore = (n + k - 1) // k
        q = min(mixed_limit["q_up_to_N"], ncore)
        min_delta = minimums["exact_single_cut_extra_service_cycles"]["value"]
        return_delta = return_cut["exact_single_cut_extra_service_cycles"]
        finite = None
        if q:
            fq = max(q * (a + c), a + b + (q - 1) * max(a, b))
            finite = {"q": q, "ideal_Fq_given_prefix_before_return_FIFO": fq,
                      "ideal_steady_saving_per_chain_ignoring_fill_drain": frac(Fraction(q * ell - fq, q)),
                      "ideal_steady_saving_after_gate_ignoring_fill_drain": frac(Fraction(q * ell - fq - gate, q)),
                      "FIFO_order_verified": False}
        by_k.append({"cores": k, "ceil_chains_per_core": ncore,
                     "uncut_compute_lower_bound_conditional_on_strict_FIFO_theorem": ncore * ell,
                     "capacity_sufficient_q_up_to_ncore": q,
                     "K_times_min_full_cut_extra_service": k * min_delta,
                     "K_times_return_cut_extra_service": k * return_delta,
                     "overlap_ceiling_to_K_min_cut_service": ratio(overlap_ceiling, k * min_delta),
                     "overlap_ceiling_to_K_return_cut_service": ratio(overlap_ceiling, k * return_delta),
                     "zero_min_cut_service": min_delta == 0,
                     "zero_return_cut_service": return_delta == 0,
                     "capacity_limited_ideal_arithmetic_not_a_plan": finite})
    return {"strict_match": True, "reason": None, "N": n, "a": a, "b": b, "c": c,
            "compute_length_per_chain": ell, "compute_ops_per_chain": length,
            "representative_chain": chain, "has_multiple_chains": n > 1,
            "signature_identical": True, "minimum_cut_metrics": minimums,
            "return_cut": return_cut, "representative_complete_cut_table": cuts,
            "necessary_DDR": necessary,
            "virgin_capacity_sufficient_condition": {"capacity_bytes": capacity,
                "prefix_footprint": prefix, "return_footprint": tail, "whole_footprint": whole,
                "mixed_footprint_per_q": mixed, "mixed_q": mixed_limit, "whole_q": whole_limit,
                "meaning": "Sufficient total distinct local tensor sum only; failure does not imply spill."},
            "asymptotic_M_V_overlap_ceiling_per_chain": overlap_ceiling,
            "by_cores": by_k,
            "scope": "Structural and integer/rational costs only. No return FIFO, schedule or E0 certification."}


class StaticDeadline(TimeoutError):
    pass


def synthetic_checks(capacity, bandwidth, gate):
    """Tiny static fixtures, in the same eventual process, before any ZIP read."""
    g = {"ops": [], "tensors": [], "edges": []}
    for base, tb in [(1, 100), (11, 200)]:
        g["ops"].extend({"id": base + i, "op": "Compute", "pipe": pipe, "cycles": cycles}
                        for i, (pipe, cycles) in enumerate([("PIPE_M", 100), ("PIPE_V", 150), ("PIPE_M", 100)]))
        g["tensors"].extend({"id": tb + i, "pos": "UB", "size": size}
                            for i, size in enumerate([60, 60, 60, 30000, 60]))
        pairs = [(tb, base), (tb, base + 2), (base, tb + 1), (tb + 1, base + 1),
                 (base + 1, tb + 2), (tb + 2, base + 2), (base, tb + 3),
                 (tb + 3, base + 2), (base + 2, tb + 4)]
        g["edges"].extend({"source": a, "target": b} for a, b in pairs)
    view = recognizer.views(g)
    chain = strict_metrics(view, capacity, bandwidth, gate)
    assert chain["N"] == 2 and chain["a"] == 100 and chain["b"] == 150 and chain["c"] == 100
    assert chain["return_cut"]["complete_internal_interface_bytes"] == 30060
    assert chain["return_cut"]["internal_extra_service_cycles"] == 1002
    assert chain["return_cut"]["exact_single_cut_extra_service_cycles"] == 1003
    assert chain["necessary_DDR"]["service_cycles"] == 4
    route = routing_metrics(view)
    assert route["component_count"] == 2 and route["external_input_union_bytes"] == 120
    assert route["external_input_intersection_bytes"] == 0
    # Share only the external input, preserving two compute weak components.
    shared = {"ops": g["ops"], "tensors": [t for t in g["tensors"] if t["id"] != 200],
              "edges": [{"source": 100 if e["source"] == 200 else e["source"], "target": e["target"]}
                        for e in g["edges"]]}
    shared_view = recognizer.views(shared)
    route = routing_metrics(shared_view)
    assert route["component_count"] == 2 and route["external_input_intersection_bytes"] == 60
    assert route["external_input_union_bytes"] == 60
    try:
        recognizer.recognize_prebuilt(shared_view)
    except recognizer.Unsupported as exc:
        assert "shared external tensor" in str(exc)
    else:
        raise AssertionError("Strict private recognizer accepted a shared input")
    assert service(0, bandwidth) == 1
    return {"passed": True, "fixtures": 2, "checks": ["full_skip_interface", "external_input_duplication",
            "mandatory_DDR", "shared_input_intersection_union", "strict_shared_input_rejection", "zero_byte_service"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "data/raw/a/official-cases.zip")
    parser.add_argument("--config", type=Path, default=ROOT / "data/raw/a/official/data/config.txt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirmed-static-slot", action="store_true",
                        help="Supply only after s59/root confirms the resource slot; never self-authorize.")
    args = parser.parse_args()
    if not args.confirmed_static_slot:
        parser.error("A confirmed static slot is required; no archive was read")
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite triage output")
    started = time.monotonic()
    report = {"kind": "strict_private_chain_static_triage_NOT_solver_NOT_performance",
              "status": "running", "complete_100": False,
              "recognizer_source_commit": recognizer.SOURCE_COMMIT,
              "recognizer_source_path": recognizer.SOURCE_PATH,
              "recognizer_source_sha256": recognizer.SOURCE_SHA256,
              "local_code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in [Path(__file__), Path(recognizer.__file__)]},
              "limits": {"worker_processes": 1, "zip_scans": 1, "internal_scan_deadline_seconds": 28,
                         "production_hard_process_budget_seconds": 30},
              "calls": {"constructor": 0, "choose": 0, "encode": 0, "model_plan": 0,
                        "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
              "case_members_read": 0, "cases": []}
    def timeout(_sig, _frame):
        raise StaticDeadline("28 second internal deadline; leave remaining process budget for output/exit")
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 28)
    try:
        config = args.config.read_bytes()
        settings = config_values(config)
        reference = json.loads(Path(__file__).with_name("reference_008.json").read_text())
        report["existing_008_audit_reference"] = reference
        report["config_sha256"] = hashlib.sha256(config).hexdigest()
        capacity = settings["capacity"]
        bw = settings["bandwidth"]["bandwidth"]
        gate = settings["multicore_scene_a"]["task_same_core_wait_cycles"]
        report["synthetic_static_checks"] = synthetic_checks(capacity, bw, gate)
        archive_bytes = args.archive.read_bytes()  # One physical ZIP read.
        report["archive_sha256"] = hashlib.sha256(archive_bytes).hexdigest()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = {}
            for name in archive.namelist():
                match = re.fullmatch(r"data/case_(\d{3})\.json", name)
                if match:
                    if match[1] in members:
                        raise ValueError("Duplicate case member")
                    members[match[1]] = name
            if set(members) != {f"{i:03d}" for i in range(1, 101)}:
                raise ValueError("Archive does not contain exactly the expected 100 case members")
            for case, member in sorted(members.items()):
                raw = archive.read(member)  # Each graph member is read once.
                report["case_members_read"] += 1
                g = json.loads(raw)
                row = {"case": case, "member": member, "input_sha256": hashlib.sha256(raw).hexdigest(),
                       "original_ops": len(g["ops"]), "original_tensors": len(g["tensors"]),
                       "focus": case in {"084", "095"}, "prior_reference_case": case == "008"}
                view = recognizer.views(g)
                row["routing_structure"] = routing_metrics(view)
                try:
                    row.update(strict_metrics(view, capacity, bw, gate))
                except recognizer.Unsupported as exc:
                    row.update(strict_match=False, reason=str(exc), N=None, a=None, b=None, c=None)
                if case == "008":
                    expected = reference["expected_008"]
                    assert row["input_sha256"] == expected["graph_sha256"]
                    assert row["strict_match"]
                    assert row["N"] == expected["chains"]
                    assert all(row[key] == expected[key] for key in ["a", "b", "c"])
                    assert row["necessary_DDR"]["service_cycles"] == expected["necessary_boundary_service_cycles"]
                    assert row["minimum_cut_metrics"]["internal_extra_service_cycles"]["value"] == expected["minimum_cut_extra_service_cycles"]
                    row["matches_existing_static_008_audit"] = True
                report["cases"].append(row)
        report.update(status="complete", complete_100=len(report["cases"]) == 100)
    except StaticDeadline as exc:
        report.update(status="deadline_partial", failure=str(exc))
    except Exception as exc:
        report.update(status="error_partial", failure=type(exc).__name__ + ": " + str(exc))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    report["static_wall_seconds_before_output"] = time.monotonic() - started
    report["strict_matching_cases"] = [x["case"] for x in report["cases"] if x["strict_match"]]
    report["not_008_matching_cases"] = [x for x in report["strict_matching_cases"] if x != "008"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in ["status", "complete_100", "case_members_read", "strict_matching_cases"]}))
    return 0 if report["complete_100"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
