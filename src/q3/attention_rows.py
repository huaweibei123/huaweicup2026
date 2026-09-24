"""Place closed attention rows and exclusive chains without changing original ops.

The timing model is compute dependency + per-core M/V FIFO + fixed remote
release delay. It is not E0, a cache/DDR model, or a memory-feasibility proof.
Rows restrict placement only; all submitted subgraphs remain singletons.
Optional FFN packing adds closed original M/V/V/M diamonds to that placement
restriction; the final operation-level ready pass still permits interleaving.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq

from .construct import UnsupportedStructure, derive_multicore_plan, topo


class _NotRow(Exception):
    """An expected motif mismatch, never an internal programming error."""


def _match(condition):
    if not condition:
        raise _NotRow


@dataclass(frozen=True)
class _Ports:
    tensors: dict
    producer: dict
    consumers: dict
    inputs: dict
    outputs: dict


def _ports(index):
    """Reject raw edges whose communication the timing model cannot represent."""
    graph = index.graph
    all_ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    if (len(all_ops) != len(graph["ops"]) or len(tensors) != len(graph["tensors"])
            or set(all_ops) & set(tensors)):
        raise UnsupportedStructure("requires unique, disjoint operation/tensor IDs")
    eligible = {u for u, op in all_ops.items()
                if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    if eligible != set(index.ops):
        raise UnsupportedStructure("Index does not match the raw graph's compute operations")
    if not eligible or any(op["pipe"] not in {"PIPE_M", "PIPE_V"}
                           or type(op["cycles"]) is not int or op["cycles"] < 1
                           for op in index.ops.values()):
        raise UnsupportedStructure("requires positive integer M/V compute durations")
    producer = {}
    consumers = defaultdict(set)
    inputs = defaultdict(set)
    outputs = defaultdict(set)
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in tensors and v in all_ops:
            consumers[u].add(v)
            inputs[v].add(u)
        elif u in all_ops and v in tensors:
            if v in producer and producer[v] != u:
                raise UnsupportedStructure("tensor has multiple original producers")
            producer[v] = u
            outputs[u].add(v)
        else:
            raise UnsupportedStructure("requires tensor-mediated edges; direct edges unsupported")
    pred = {u: set() for u in index.ops}
    succ = {u: set() for u in index.ops}
    for v in index.ops:
        for t in inputs[v]:
            u = producer.get(t)
            if u in index.ops:
                pred[v].add(u)
                succ[u].add(v)
    if any(pred[u] != index.pred[u] or succ[u] != index.succ[u] for u in index.ops):
        raise UnsupportedStructure("COPY-contracted dependencies differ from direct tensor dependencies")
    return _Ports(tensors, producer, consumers, inputs, outputs)


def _recognize(index, ports):
    """Find exact multi-entry, single-exit row motifs by original dependencies."""
    kind = lambda u: index.ops[u]["op"]

    def add_tree(root, leaf_kind):
        leaves, inside, stack = set(), set(), [root]
        while stack:
            u = stack.pop()
            if u in inside or u in leaves:
                continue
            if kind(u) == leaf_kind:
                leaves.add(u)
            else:
                _match(kind(u) == "ADD" and len(index.pred[u]) == 2)
                inside.add(u)
                stack.extend(index.pred[u])
        _match(len(leaves) >= 2 and len(inside) == len(leaves) - 1)
        return leaves, inside

    def reverse_until(root, stops):
        inside, found, stack = set(), set(), [root]
        while stack:
            u = stack.pop()
            if u in stops:
                found.add(u)
            elif u not in inside:
                inside.add(u)
                stack.extend(index.pred[u])
        return inside, found

    def try_roles(root, denominator, numerator):
        reds, dadds = add_tree(denominator, "REDUCE")
        mults, nadds = add_tree(numerator, "MATMUL")
        _match(len(reds) == len(mults))
        exp_to_red = {}
        for r in sorted(reds):
            _match(len(index.pred[r]) == 1)
            e = next(iter(index.pred[r]))
            _match(kind(e) == "EXP" and e not in exp_to_red)
            exp_to_red[e] = r
        exps = set(exp_to_red)
        exp_to_mult, vs = {}, set()
        for m in sorted(mults):
            ep = index.pred[m] & exps
            _match(len(ep) == 1 and len(index.pred[m]) == 2)
            e = next(iter(ep))
            v = next(iter(index.pred[m] - ep))
            _match(e not in exp_to_mult and kind(v) == "MATMUL")
            exp_to_mult[e] = m
            vs.add(v)
        _match(set(exp_to_mult) == exps and len(vs) == len(exps))
        shifts, scores, max_roots = set(), set(), set()
        for e in sorted(exps):
            _match(len(index.pred[e]) == 1)
            s = next(iter(index.pred[e]))
            _match(kind(s) == "SUB" and len(index.pred[s]) == 2)
            ds = {p for p in index.pred[s] if kind(p) == "DIV"}
            ms = {p for p in index.pred[s] if kind(p) == "ADD"}
            _match(len(ds) == len(ms) == 1)
            shifts.add(s)
            scores.update(ds)
            max_roots.update(ms)
        _match(len(scores) == len(exps) and len(max_roots) == 1)
        score_mults = set()
        for d in sorted(scores):
            _match(len(index.pred[d]) == 1)
            m = next(iter(index.pred[d]))
            _match(kind(m) == "MATMUL" and len(index.pred[m]) == 2)
            _match(all(kind(p) == "MATMUL" for p in index.pred[m]))
            score_mults.add(m)
        _match(len(score_mults) == len(exps))
        common = set.intersection(*(index.pred[m] for m in score_mults))
        _match(len(common) == 1)
        q = next(iter(common))
        ks = {next(iter(index.pred[m] - {q})) for m in score_mults}
        _match(len(ks) == len(exps) and not (ks & vs) and q not in vs)
        max_root = next(iter(max_roots))
        max_inside, max_scores = reverse_until(max_root, scores)
        _match(max_scores == scores and all(kind(u) in {"REDUCE", "SUB", "RELU", "ADD"}
                                           for u in max_inside))
        stops = {q} | ks | vs
        inside, external = reverse_until(root, stops)
        expected = ({root} | reds | dadds | mults | nadds | exps | shifts
                    | scores | score_mults | max_inside)
        _match(inside == expected and external == stops and len(inside) == 12 * len(exps) - 4)
        # After a motif matches, broken closure is unsafe input, not a skipped row.
        if any(index.succ[u] - inside for u in inside - {root}):
            raise UnsupportedStructure("attention row has an external interior compute consumer")
        incoming = sorted({t for u in inside for t in ports.inputs[u]
                           if ports.producer.get(t) not in inside})
        outgoing = sorted({t for u in inside for t in ports.outputs[u]
                           if ports.consumers[t] - inside})
        if len(outgoing) != 1 or ports.producer[outgoing[0]] != root:
            raise UnsupportedStructure("attention row needs one raw tensor exit at its final DIV")
        compute_inputs = {ports.producer[t] for t in incoming
                          if ports.producer.get(t) in index.ops}
        if compute_inputs != stops:
            raise UnsupportedStructure("unexpected raw compute input in attention row")
        kv_tensors = [t for t in incoming if ports.producer.get(t) in ks | vs]
        q_tensors = [t for t in incoming if ports.producer.get(t) == q]
        extra = [t for t in incoming if ports.producer.get(t) not in stops]
        if (len(kv_tensors) != 2 * len(exps) or len(q_tensors) != 1 or len(extra) != 1
                or ports.tensors[extra[0]]["size"] != 2):
            raise UnsupportedStructure("row boundary requires one tensor per Q/K/V and a 2-byte scalar")
        if not index.succ[q] <= inside:
            raise UnsupportedStructure("row Q projection has an external compute consumer")
        work = {p: sum(index.duration(u) for u in inside if index.ops[u]["pipe"] == p)
                for p in ("PIPE_M", "PIPE_V")}
        return {"nodes": tuple(sorted(inside)), "sink": root, "q": q,
                "k": tuple(sorted(ks)), "v": tuple(sorted(vs)), "work": work,
                "boundary_inputs": tuple(incoming), "boundary_outputs": tuple(outgoing),
                "kv_distinct_boundary_bytes": sum(ports.tensors[t]["size"] for t in kv_tensors),
                "private_q_raw_closed": all(ports.consumers[t] <= inside for t in ports.outputs[q])}

    rows = []
    for root in index.order:
        parents = sorted(index.pred[root])
        if (kind(root) != "DIV" or len(parents) != 2
                or any(kind(p) != "ADD" for p in parents)):
            continue
        for denominator, numerator in (parents, parents[::-1]):
            try:
                row = try_roles(root, denominator, numerator)
            except _NotRow:
                continue
            rows.append(row)
            break
    if not rows:
        raise UnsupportedStructure("no closed attention query row matched")
    occupied = set()
    panels = defaultdict(list)
    for row in rows:
        if occupied.intersection(row["nodes"]):
            raise UnsupportedStructure("attention row interiors overlap")
        occupied.update(row["nodes"])
        panels[(row["k"], row["v"])].append(row)
    for (ks, vs), group in panels.items():
        nodes = {u for row in group for u in row["nodes"]}
        if any(index.succ[u] - nodes for u in ks + vs):
            raise UnsupportedStructure("shared K/V has a consumer outside its recognized panel")
        if any(index.succ[u] & (nodes - set(row["nodes"]))
               for row in group for u in row["nodes"]):
            raise UnsupportedStructure("sibling attention rows are not independent")
    return rows


def recognize(index):
    """Return guarded row records. Q/K/V are boundaries, never row members."""
    ports = _ports(index)
    rows = _recognize(index, ports)
    # Closure alone is not used as a shortcut for a full quotient cycle check.
    _capsules(index, rows)
    return rows


def _capsules(index, rows, ffn_diamonds=()):
    positions = {u: i for i, u in enumerate(index.order)}
    blocks = [{"kind": "attention_row", "nodes": tuple(sorted(row["nodes"], key=positions.get)),
               "row_sink": row["sink"]} for row in rows]
    blocks.extend({"kind": "ffn_diamond", "nodes": tuple(sorted(nodes, key=positions.get))}
                  for nodes in ffn_diamonds)
    remaining = set(index.ops) - {u for block in blocks for u in block["nodes"]}
    assigned = set()
    for u in index.order:
        if u not in remaining or u in assigned:
            continue
        word = [u]
        assigned.add(u)
        while len(index.succ[word[-1]]) == 1:
            v = next(iter(index.succ[word[-1]]))
            if v not in remaining or v in assigned or len(index.pred[v]) != 1:
                break
            word.append(v)
            assigned.add(v)
        blocks.append({"kind": "exclusive_chain", "nodes": tuple(word)})
    blocks.sort(key=lambda b: positions[b["nodes"][0]])
    owner = {u: j for j, block in enumerate(blocks) for u in block["nodes"]}
    if len(owner) != len(index.ops) or sum(len(b["nodes"]) for b in blocks) != len(index.ops):
        raise AssertionError("capsule cover is incomplete or overlapping")
    successors = {j: set() for j in range(len(blocks))}
    predecessors = {j: set() for j in range(len(blocks))}
    for u in index.order:
        for v in index.succ[u]:
            a, b = owner[u], owner[v]
            if a != b:
                successors[a].add(b)
                predecessors[b].add(a)
    try:
        border_order = topo(successors, successors)
    except ValueError as error:
        # This is the explicit quotient cycle check, not a motif-mismatch catch.
        family = "attention/FFN/chain" if ffn_diamonds else "attention/chain"
        raise UnsupportedStructure(f"{family} quotient contains a cycle") from error
    return blocks, owner, predecessors, successors, border_order



def _ready_word(index, op_owner, cores, cross_delay):
    """Fixed-owner list schedule, O((V+E) log V + kV), without stale-key scans.

    Each resource has a release heap and an available-priority heap. Every ready
    op enters each heap at most once. The best head across 2k resources is the
    exact minimum (feasible start, negative bottom level, ID) ready operation.
    """
    pipes = ("PIPE_M", "PIPE_V")
    resources = [(c, p) for c in range(cores) for p in pipes]
    future = {r: [] for r in resources}
    available = {r: [] for r in resources}
    free = dict.fromkeys(resources, 0)
    degree = {u: len(index.pred[u]) for u in index.ops}
    release = dict.fromkeys(index.ops, 0)
    bottom = {}
    for u in reversed(index.order):
        bottom[u] = index.duration(u) + max((bottom[v] for v in index.succ[u]), default=0)

    def enqueue(u):
        r = (op_owner[u], index.ops[u]["pipe"])
        if release[u] <= free[r]:
            heapq.heappush(available[r], (-bottom[u], u))
        else:
            heapq.heappush(future[r], (release[u], -bottom[u], u))

    for u in index.order:
        if not degree[u]:
            enqueue(u)
    schedules = [[] for _ in range(cores)]
    finish, starts, global_word = {}, {}, []
    while len(global_word) < len(index.ops):
        candidates = []
        for r in resources:
            while future[r] and future[r][0][0] <= free[r]:
                _, priority, u = heapq.heappop(future[r])
                heapq.heappush(available[r], (priority, u))
            if available[r]:
                priority, u = available[r][0]
                candidates.append((free[r], priority, u, r, True))
            elif future[r]:
                start, priority, u = future[r][0]
                candidates.append((start, priority, u, r, False))
        if not candidates:
            raise AssertionError("original operation ready list became incomplete")
        start, _, u, r, is_available = min(candidates, key=lambda t: t[:3])
        if is_available:
            heapq.heappop(available[r])
        else:
            heapq.heappop(future[r])
        starts[u] = start
        finish[u] = start + index.duration(u)
        free[r] = finish[u]
        schedules[op_owner[u]].append(u)
        global_word.append(u)
        for v in sorted(index.succ[u]):
            release[v] = max(release[v], finish[u] + (cross_delay if op_owner[u] != op_owner[v] else 0))
            degree[v] -= 1
            if not degree[v]:
                enqueue(v)
    return schedules, finish, starts, global_word


def _ffn_motifs(index, ports):
    """Recognize original four-op, raw-port-closed diamonds without ownership."""
    result = []
    for a in index.order:
        if index.ops[a]["op"] != "MATMUL" or len(index.succ[a]) != 2:
            continue
        sig = [u for u in index.succ[a] if index.ops[u]["op"] == "SIGMOID"]
        mul = [u for u in index.succ[a] if index.ops[u]["op"] == "MUL"]
        if len(sig) != 1 or len(mul) != 1:
            continue
        b, c = sig[0], mul[0]
        if (index.pred[b] != {a} or index.succ[b] != {c}
                or index.pred[c] != {a, b} or len(index.succ[c]) != 1):
            continue
        d = next(iter(index.succ[c]))
        if index.ops[d]["op"] != "MATMUL" or index.pred[d] != {c}:
            continue
        nodes = {a, b, c, d}
        if any(ports.consumers[t] - nodes for u in (a, b, c) for t in ports.outputs[u]):
            continue
        result.append((a, b, c, d))
    return result


def _packed_ffn_motifs(index, ports, rows):
    """Pick disjoint M/V/V/M diamonds outside rows, in original topological order."""
    occupied = {u for row in rows for u in row["nodes"]}
    result = []
    for nodes in _ffn_motifs(index, ports):
        if len(set(nodes)) != 4 or occupied.intersection(nodes):
            continue
        if tuple(index.ops[u]["pipe"] for u in nodes) != ("PIPE_M", "PIPE_V", "PIPE_V", "PIPE_M"):
            continue
        result.append(nodes)
        occupied.update(nodes)
    return result


def _ffn_diagnostics(index, ports, op_owner):
    """Report closed original M -> (SIGMOID, MUL) -> M diamonds, not new ops."""
    result = []
    for a, b, c, d in _ffn_motifs(index, ports):
        nodes = {a, b, c, d}
        remote = []
        for u in (a, b, c):
            for t in sorted(ports.outputs[u]):
                dest = sorted({op_owner[v] for v in ports.consumers[t] & nodes
                               if op_owner[v] != op_owner[u]})
                if dest:
                    remote.append({"tensor": t, "bytes": ports.tensors[t]["size"],
                                   "producer_core": op_owner[u], "destination_cores": dest})
        result.append({"nodes": [a, b, c, d], "cores": [op_owner[u] for u in (a, b, c, d)],
                       "split": len({op_owner[u] for u in nodes}) > 1,
                       "work": {p: sum(index.duration(u) for u in nodes if index.ops[u]["pipe"] == p)
                                for p in ("PIPE_M", "PIPE_V")},
                       "remote_internal_tensors": remote,
                       "remote_internal_tensor_bytes_proxy": sum(t["bytes"] * len(t["destination_cores"]) for t in remote)})
    return result


def construct(index, cores, cross_delay=500, *, pack_ffn=False):
    """One construction, at most k core trials/unit; optional closed FFN packing."""
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if type(cross_delay) is not int or cross_delay < 0:
        raise ValueError("cross_delay must be a nonnegative integer")
    if type(pack_ffn) is not bool:
        raise ValueError("pack_ffn must be a boolean")
    ports = _ports(index)
    rows = _recognize(index, ports)
    ffn_diamonds = _packed_ffn_motifs(index, ports, rows) if pack_ffn else ()
    blocks, block_of, predecessors, successors, border_order = _capsules(index, rows, ffn_diamonds)
    weights = {u: index.duration(u) for u in index.ops}
    block_work = [{p: sum(weights[u] for u in b["nodes"] if index.ops[u]["pipe"] == p)
                   for p in ("PIPE_M", "PIPE_V")} for b in blocks]
    bottom = {}
    for j in reversed(border_order):
        # A priority coordinate only: summed compute work is not a two-pipe CP.
        bottom[j] = sum(block_work[j].values()) + max((bottom[v] for v in successors[j]), default=0)
    incoming = [{t for u in b["nodes"] for t in ports.inputs[u]
                 if block_of.get(ports.producer.get(t)) != j}
                for j, b in enumerate(blocks)]
    pipe_free = [{"PIPE_M": 0, "PIPE_V": 0} for _ in range(cores)]
    finish, op_owner = {}, {}
    degree = {j: len(predecessors[j]) for j in successors}
    ready = [(-bottom[j], blocks[j]["nodes"][0], j) for j in successors if not degree[j]]
    heapq.heapify(ready)
    schedules = [[] for _ in range(cores)]
    global_word, dispatch = [], []
    while ready:
        _, _, j = heapq.heappop(ready)
        trials = []
        for c in range(cores):
            free = dict(pipe_free[c])
            local = {}
            starts = {}
            for u in blocks[j]["nodes"]:
                release = 0
                for p in index.pred[u]:
                    if block_of[p] == j:
                        at = local[p]
                    else:
                        at = finish[p] + (cross_delay if op_owner[p] != c else 0)
                    release = max(release, at)
                pipe = index.ops[u]["pipe"]
                starts[u] = max(release, free[pipe])
                local[u] = starts[u] + weights[u]
                free[pipe] = local[u]
            # Distinct original remote tensor demand, not official COPY bytes.
            remote_bytes = sum(ports.tensors[t]["size"] for t in incoming[j]
                               if ports.producer.get(t) in op_owner
                               and op_owner[ports.producer[t]] != c)
            trials.append((max(local.values()), remote_bytes, c, local, free, starts))
        end, remote_bytes, c, local, free, starts = min(trials, key=lambda trial: trial[:3])
        pipe_free[c] = free
        finish.update(local)
        op_owner.update((u, c) for u in blocks[j]["nodes"])
        schedules[c].extend(blocks[j]["nodes"])
        global_word.extend(blocks[j]["nodes"])
        dispatch.append({"capsule": j, "kind": blocks[j]["kind"], "core": c,
                         "nodes": list(blocks[j]["nodes"]), "work": block_work[j],
                         "proxy_first_start": min(starts.values()), "proxy_finish": end,
                         "remote_boundary_bytes_proxy": remote_bytes})
        for v in sorted(successors[j]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, (-bottom[v], blocks[v]["nodes"][0], v))
    if len(finish) != len(index.ops):
        raise AssertionError("ready construction missed original compute operations")
    rank = {u: i for i, u in enumerate(global_word)}
    if any(rank[u] >= rank[v] for u in index.ops for v in index.succ[u]):
        raise AssertionError("global capsule selection order is not original-DAG topological")
    placement_proxy = max(finish.values())
    # Placement trials commit capsule words only to choose ownership. The final
    # singleton word is built afresh, so different rows may overlap/interleave.
    schedules, finish, starts, global_word = _ready_word(index, op_owner, cores, cross_delay)
    rank = {u: i for i, u in enumerate(global_word)}
    if any(rank[u] >= rank[v] for u in index.ops for v in index.succ[u]):
        raise AssertionError("final global word is not original-DAG topological")
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in word] for word in schedules]}
    derive_multicore_plan(index.graph, plan)
    row_nodes = {u for row in rows for u in row["nodes"]}
    total_work = {p: sum(weights[u] for u in index.ops if index.ops[u]["pipe"] == p)
                  for p in ("PIPE_M", "PIPE_V")}
    row_work = {p: sum(weights[u] for u in row_nodes if index.ops[u]["pipe"] == p)
                for p in ("PIPE_M", "PIPE_V")}
    metadata = {"strategy": "attention_rows", "cores": cores,
                  "row_count": len(rows), "row_compute_ops": len(row_nodes),
                  "eligible_ops": len(index.ops), "capsule_count": len(blocks),
                  "chain_capsule_count": sum(b["kind"] == "exclusive_chain" for b in blocks),
                  "total_compute_work_cycles": total_work, "row_compute_work_cycles": row_work,
                  "capsule_dispatch": dispatch,
                  "placement_proxy_makespan_cycles": placement_proxy,
                  "proxy_makespan_cycles": max(finish.values()),
                  "ffn_diamonds": _ffn_diagnostics(index, ports, op_owner),
                  "cross_delay_proxy": cross_delay,
                  "core_compute_work_cycles": [{p: sum(weights[u] for u in index.ops
                      if op_owner[u] == c and index.ops[u]["pipe"] == p)
                      for p in ("PIPE_M", "PIPE_V")} for c in range(cores)],
                  "order": "placement: quotient bottom-level ready; final fixed-owner order: minimum feasible op start, negative op bottom-level, ID; one global word projected per core",
                  "placement": "minimum per-operation compute/pipe finish, distinct remote boundary bytes, core ID",
                  "complexity": "recognition worst-case O(C*(V+E)) for C final-DIV candidates; quotient/placement O(k*(V+E)+(V+E) log V); final ready pass O((V+E) log V+kV)",
                  "guards": ["positive M/V compute cycles", "unique tensor producers and no direct op edges",
                             "raw tensor dependencies equal COPY-contracted compute dependencies",
                             "closed nonoverlapping attention rows and acyclic row/chain quotient",
                             "one raw output and shared Q/K/V plus scalar frontier"],
                  "submission": "Original ops remain singleton subgraphs; per-core Tasks are rederived by official P3.",
                  "limitations": ["No COPY service, DDR contention, cache, capacity or spill model; not an official score or claimed official bound.",
                                  "Only row placement is shared; each op uses its own original predecessor release, no all-frontier barrier.",
                                  "Placement is chosen using contiguous capsule trial words; the final op-level ready pass may improve or worsen that proxy and does not revisit ownership.",
                                  "Bottom-level and remote tensor bytes are proxies, not optimality guarantees or actual traffic.",
                                  "A fixed row/chain placement family can miss useful splits; peripheral FFN diamonds are not separately packed."]}
    if pack_ffn:
        metadata["strategy"] = "attention_rows_ffn"
        metadata["packed_ffn_count"] = len(ffn_diamonds)
        metadata["guards"][3] = "closed nonoverlapping attention/FFN capsules and acyclic quotient"
        metadata["guards"].append("four original M/V/V/M FFN ops outside rows; no raw nonterminal tensor consumer outside the diamond")
        metadata["limitations"][1] = "Only row/FFN placement is shared; each op uses its own original predecessor release, no all-frontier barrier."
        metadata["limitations"][-1] = "A fixed row/FFN/chain placement family can miss useful splits; packing does not fuse, clone or remove original ops."
    return plan, metadata
