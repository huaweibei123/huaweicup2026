"""Independent Index adapter for the archived sealed-subtree time template.

Adapted mathematically from ChatGPT Pro answer 5418ca5e-924f-4e80-8205-92d4c5388f6d,
AI chats/20260924-Pro-P3-归约森林切分/完整问答-20260924T153228Z.md, sections 3-4.
The source attachment was read as text, not executed. No original op is changed.
No E0, COPY-service, memory, bandwidth or Cache model is used by this module.

This /tmp draft imports the worktree through the caller's PYTHONPATH. Production
integration may change the absolute package imports to relative package imports.
"""
from collections import Counter, deque

from src.q3.construct import UnsupportedStructure, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views


SOURCE = {
    "answer_id": "5418ca5e-924f-4e80-8205-92d4c5388f6d",
    "archive": "AI chats/20260924-Pro-P3-归约森林切分/完整问答-20260924T153228Z.md",
    "attachment_sha256": "87ef7f94b0792048498408b14c7f9f4c8c57b7f174bf3a6342921575369ba350",
}


def _guard(index):
    """Accept one binary in-tree and prove its edges need no COPY contraction."""
    if not index.ops or len(index.components) != 1:
        raise UnsupportedStructure("requires one nonempty reduction tree")
    if any(len(index.succ[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("forks are outside the sealed-subtree family")
    if any(len(index.pred[u]) > 2 for u in index.ops):
        raise UnsupportedStructure("original compute indegree exceeds two; no reassociation allowed")
    if any(o["pipe"] not in {"PIPE_M", "PIPE_V"} for o in index.ops.values()):
        raise UnsupportedStructure("requires original non-COPY M/V operations")
    if any(type(o.get("cycles")) is not int or o["cycles"] < 0
           for o in index.ops.values()):
        raise UnsupportedStructure("requires nonnegative integer original cycles")
    roots = [u for u in index.ops if not index.succ[u]]
    if len(roots) != 1:
        raise UnsupportedStructure("requires exactly one computation root")
    producers, consumers, direct = _original_tensor_views(index.graph)
    if any(len(set(values)) > 1 for values in producers.values()):
        raise UnsupportedStructure("ambiguous tensor with multiple original producers")
    supported = set()
    for tid, values in producers.items():
        for u in values:
            if u in index.ops:
                supported.update((u, v) for v in consumers.get(tid, ())
                                 if v in index.ops and u != v)
    supported.update((e["source"], e["target"]) for e in direct
                     if e["source"] in index.ops and e["target"] in index.ops)
    contracted = {(u, v) for u, targets in index.succ.items() for v in targets}
    if supported != contracted:
        raise UnsupportedStructure("COPY-contracted edge lacks the exact original P3 dependency witness")
    children = {u: tuple(sorted(index.pred[u])) for u in index.ops}
    # Frozen compute duration is max(1, cycles); a raw zero does not take zero time.
    weights = {u: index.duration(u) for u in index.ops}
    return roots[0], children, weights


def _identity(dim):
    return [[0 if i == j else None for j in range(dim)] for i in range(dim)]


def _row_compose(row, matrix):
    """r times M over max-plus; None denotes exact negative infinity."""
    dim = len(row)
    result = [None] * dim
    for i, value in enumerate(row):
        if value is None:
            continue
        for j, other in enumerate(matrix[i]):
            if other is not None:
                candidate = value + other
                if result[j] is None or candidate > result[j]:
                    result[j] = candidate
    return result


def _matrix_compose(left, right):
    return [_row_compose(row, right) for row in left]


def _signatures(index, children, weights):
    """Return exact all-subtree fixed DFS signatures R, g and zero-input D.

    Coordinate 0 is the constant zero; the rest are incoming pipe availability.
    A child root row is saved before its resource matrix is composed. This
    retains first-child completion even when it lies on a different pipe.
    """
    pipes = sorted({o["pipe"] for o in index.ops.values()})
    pipe_column = {p: i + 1 for i, p in enumerate(pipes)}
    dim = len(pipes) + 1
    matrices, root_rows, local = {}, {}, {}
    for v in index.order:
        resource = _identity(dim)
        input_rows = []
        for child in children[v]:
            input_rows.append(_row_compose(root_rows[child], resource))
            resource = _matrix_compose(matrices[child], resource)
        target = pipe_column[index.ops[v]["pipe"]]
        constraints = [resource[0], resource[target], *input_rows]
        finish_row = []
        for j in range(dim):
            finite = [r[j] for r in constraints if r[j] is not None]
            finish_row.append(max(finite) + weights[v] if finite else None)
        resource[target] = finish_row
        matrices[v], root_rows[v] = resource, finish_row
        local[v] = max(x for x in finish_row if x is not None)
    return pipes, matrices, root_rows, local


def _abstract_fifo(index, words, delay):
    """Exact fixed-plan compute DAG timing, never an official evaluation."""
    owner = {u: c for c, word in enumerate(words) for u in word}
    flat = [u for word in words for u in word]
    if len(flat) != len(index.ops) or set(owner) != set(index.ops):
        raise AssertionError("compiled words do not cover original computation exactly once")
    successors = {u: {} for u in index.ops}
    for u in index.order:
        for v in index.succ[u]:
            successors[u][v] = delay if owner[u] != owner[v] else 0
    for word in words:
        previous = {}
        for v in word:
            pipe = index.ops[v]["pipe"]
            if pipe in previous:
                u = previous[pipe]
                successors[u][v] = max(successors[u].get(v, 0), 0)
            previous[pipe] = v
    degree = dict.fromkeys(index.ops, 0)
    for targets in successors.values():
        for v in targets:
            degree[v] += 1
    ready = deque(u for u in index.order if not degree[u])
    start = dict.fromkeys(index.ops, 0)
    processed = 0
    completion = 0
    while ready:
        u = ready.popleft()
        processed += 1
        end = start[u] + index.duration(u)
        completion = max(completion, end)
        for v, lag in successors[u].items():
            start[v] = max(start[v], end + lag)
            degree[v] -= 1
            if not degree[v]:
                ready.append(v)
    if processed != len(index.ops):
        raise AssertionError("compiled enhanced compute DAG is cyclic")
    return completion


def construct(index, cores, delay):
    """One deterministic LOCAL/SEQ/PAR plan and metadata; no parameter search.

    DP/signature core: O(n*k^2 + n*P^3) time, O(n*k + n*P^2) memory.
    End-to-end construction additionally scans the raw graph and invokes the
    official static plan validator, whose internal sorting may cost more.
    H is the selected barrier-template witness, NOT an official upper/lower bound.
    Static dependency checks do not prove Step2/Step3 or full E0 executability.
    """
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if type(delay) is not int or delay < 0:
        raise ValueError("delay must be a nonnegative integer")
    root, children, weights = _guard(index)
    pipes, _, _, local = _signatures(index, children, weights)
    costs, selected = {}, {}
    for v in index.order:
        costs[v], selected[v] = [None] * (cores + 1), [None] * (cores + 1)
        for q in range(1, cores + 1):
            candidates = [(local[v], ("LOCAL",))]
            if q > 1:
                candidates.append((costs[v][q - 1], ("LESS",)))
            ch = children[v]
            if len(ch) == 1:
                candidates.append((costs[ch[0]][q] + weights[v], ("UNARY",)))
            elif len(ch) == 2:
                a, b = ch
                candidates.append((costs[a][q] + costs[b][q] + weights[v], ("SEQ",)))
                for split in range(1, q):
                    ca, cb = costs[a][split], costs[b][q - split]
                    candidates.append((max(ca, cb + delay) + weights[v], ("PAR", split, 0)))
                    candidates.append((max(ca + delay, cb) + weights[v], ("PAR", split, 1)))
            # Stable preference: LOCAL, LESS, SEQ, then increasing split/A-root/B-root.
            costs[v][q], selected[v][q] = min(candidates, key=lambda x: x[0])

    words = [[] for _ in range(cores)]
    counts = Counter()
    stack = [(False, root, tuple(range(cores)))]
    while stack:
        append, v, team = stack.pop()
        if append:
            words[team[0]].append(v)
            continue
        q = len(team)
        mode, *args = selected[v][q]
        counts[mode] += 1
        if mode == "LESS":
            stack.append((False, v, team[:-1]))
        elif mode == "LOCAL":
            dfs = [(v, False)]
            while dfs:
                u, visited = dfs.pop()
                if visited:
                    words[team[0]].append(u)
                else:
                    dfs.append((u, True))
                    dfs.extend((a, False) for a in reversed(children[u]))
        else:
            stack.append((True, v, team))
            if mode == "UNARY":
                stack.append((False, children[v][0], team))
            elif mode == "SEQ":
                a, b = children[v]
                stack.extend(((False, b, team), (False, a, team)))
            else:
                a, b = children[v]
                split, return_side = args
                if return_side == 0:
                    ta, tb = team[:split], team[split:]
                else:
                    tb, ta = team[:q - split], team[q - split:]
                stack.extend(((False, b, tb), (False, a, ta)))
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in word] for word in words]}
    derive_multicore_plan(index.graph, plan)
    exact = _abstract_fifo(index, words, delay)
    witness = costs[root][cores]
    if exact > witness:
        raise AssertionError("compiled FIFO timing exceeds its sealed-team witness")
    owner = {u: c for c, word in enumerate(words) for u in word}
    cross_edges = sum(owner[u] != owner[v] for u in index.order for v in index.succ[u])
    per_core_pipe = [{p: sum(weights[u] for u in word if index.ops[u]["pipe"] == p)
                      for p in pipes} for word in words]
    return plan, {
        "strategy": "sealed_subtree_team_dp", "cores": cores,
        "eligible_ops": len(index.ops), "root": root, "pipes": pipes,
        "delay_model_cycles": delay, "local_dfs_cycles": local[root],
        "root_witness_by_budget": costs[root][1:],
        "abstract_witness_upper_cycles": witness, "abstract_fifo_cycles": exact,
        "zero_delay_fifo_cycles": _abstract_fifo(index, words, 0),
        "fifo_le_witness": True, "emitted_template_counts": dict(counts),
        "used_cores": sum(bool(w) for w in words), "per_core_pipe_work": per_core_pipe,
        "cross_core_compute_edges": cross_edges,
        "official_evaluations": 0, "execution_legality_proved": False,
        "source": SOURCE,
        "limitations": "Time-only binary single-tree template; no COPY service, memory, bandwidth or Cache. H is not an E0 bound. No global schedule optimality claim.",
    }
