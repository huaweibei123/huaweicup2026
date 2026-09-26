"""Sethi-Ullman-style ordering for guarded forests of reduction trees.

The scalar frontier is a scheduling proxy over internal output tensors. It is
not an official L1/UB, spill, or Cache capacity certificate.
"""
from __future__ import annotations

from .construct import UnsupportedStructure, derive_multicore_plan


def _original_tree(index):
    graph = index.graph
    ops = {op.get("id"): op for op in graph.get("ops", [])}
    compute = set(index.ops)
    copies = {u: op.get("op") for u, op in ops.items()
              if op.get("op") in {"COPY_IN", "COPY_OUT"}}
    if not compute or set(ops) != compute | set(copies):
        raise UnsupportedStructure("only compute and boundary COPY_IN/COPY_OUT ops are supported")

    tensors, tensor_pos = {}, {}
    for tensor in graph.get("tensors", []):
        tid = tensor.get("id")
        size = tensor.get("size")
        if tid in tensors or type(size) is not int or size < 0:
            raise UnsupportedStructure("requires unique tensors with known nonnegative sizes")
        tensors[tid] = size
        tensor_pos[tid] = tensor.get("pos")

    producers = {tid: set() for tid in tensors}
    consumers = {tid: set() for tid in tensors}
    copy_producers = {tid: set() for tid in tensors}
    copy_consumers = {tid: set() for tid in tensors}
    copy_inputs = {u: set() for u in copies}
    copy_outputs = {u: set() for u in copies}
    direct = set()
    for edge in graph.get("edges", []):
        source, target = edge.get("source"), edge.get("target")
        if source in compute and target in tensors:
            producers[target].add(source)
        elif source in tensors and target in compute:
            consumers[source].add(target)
        elif source in copies and target in tensors:
            copy_producers[target].add(source)
            copy_outputs[source].add(target)
        elif source in tensors and target in copies:
            copy_consumers[source].add(target)
            copy_inputs[target].add(source)
        elif source in compute and target in compute:
            direct.add((source, target))
        else:
            raise UnsupportedStructure("edge has unknown or unsupported endpoint")
    if direct:
        raise UnsupportedStructure("direct compute edges have no output-tensor size")

    for op_id, kind in copies.items():
        incoming = copy_inputs[op_id]
        outgoing = copy_outputs[op_id]
        if len(incoming) != 1 or len(outgoing) != 1:
            raise UnsupportedStructure("boundary COPY must have one input and one output tensor")
        source, target = next(iter(incoming)), next(iter(outgoing))
        if kind == "COPY_IN":
            if (producers[source] or copy_producers[source] or producers[target]
                    or copy_producers[target] != {op_id}):
                raise UnsupportedStructure("COPY_IN must map an external input to a non-produced tensor")
            if tensor_pos[source] != "DDR" or tensor_pos[target] != "L1":
                raise UnsupportedStructure("COPY_IN tensor positions are unsupported")
            if tensors[source] != tensors[target]:
                raise UnsupportedStructure("COPY_IN input/output sizes differ")
        else:
            if (len(producers[source]) != 1 or consumers[source]
                    or copy_consumers[source] != {op_id}):
                raise UnsupportedStructure("COPY_OUT must consume a root compute output")
            if (producers[target] or consumers[target]
                    or copy_producers[target] != {op_id} or copy_consumers[target]):
                raise UnsupportedStructure("COPY_OUT target must be an external output")
            if tensor_pos[source] != "L1" or tensor_pos[target] != "DDR":
                raise UnsupportedStructure("COPY_OUT tensor positions are unsupported")
            if tensors[source] != tensors[target]:
                raise UnsupportedStructure("COPY_OUT input/output sizes differ")

    successors = {u: set() for u in compute}
    predecessor = {u: set() for u in compute}
    output_tensors = {u: [] for u in compute}
    for tid in tensors:
        ps, cs = producers[tid], consumers[tid]
        if len(ps) > 1:
            raise UnsupportedStructure("tensor has multiple compute producers")
        if not ps:
            continue  # External graph input; not part of the internal frontier.
        producer = next(iter(ps))
        output_tensors[producer].append(tid)
        if len(cs) > 1:
            raise UnsupportedStructure("produced tensor has extra consumers")
        if cs:
            child_parent = next(iter(cs))
            if child_parent == producer:
                raise UnsupportedStructure("self-consumed tensor")
            successors[producer].add(child_parent)
            predecessor[child_parent].add(producer)

    if any(len(children) > 1 for children in successors.values()):
        raise UnsupportedStructure("compute outdegree exceeds one")
    if any(successors[u] != set(index.succ[u]) for u in compute):
        raise UnsupportedStructure("original tensor edges disagree with indexed dependencies")
    if len(index.components) < 2:
        raise UnsupportedStructure("requires a multi-tree forest")

    records = []
    joined_nodes = 0
    for component in index.components:
        members = set(component)
        roots = sorted(u for u in members if not successors[u])
        if len(roots) != 1:
            raise UnsupportedStructure("each component must have exactly one reduction root")
        root = roots[0]
        if any((predecessor[u] - members) or (successors[u] - members) for u in members):
            raise UnsupportedStructure("tree edge crosses component boundary")
        if sum(len(predecessor[u]) for u in members) != len(members) - 1:
            raise UnsupportedStructure("component is not a tree")

        for u in members:
            expected_outputs = 1
            if len(output_tensors[u]) != expected_outputs:
                raise UnsupportedStructure("each op must have one sized internal result or root output")
            tid = output_tensors[u][0]
            if u == root:
                if consumers[tid]:
                    raise UnsupportedStructure("root result must be an external output")
            elif consumers[tid] != successors[u] or copy_consumers[tid]:
                raise UnsupportedStructure("non-root result must feed only its tree parent")

        joined_nodes += sum(len(predecessor[u]) >= 2 for u in members)
        records.append({"members": members, "root": root,
                        "children": {u: sorted(predecessor[u]) for u in members}})
    if not joined_nodes:
        raise UnsupportedStructure("requires at least one reduction join")
    return tensors, output_tensors, records, joined_nodes


def construct(index, cores):
    """Return a legal plan preserving Index.assignment ownership and IDs."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official requested cores must be 1..5")
    if (len(index.components) < 2 or any(len(index.succ[u]) > 1 for u in index.ops)
            or not any(len(index.pred[u]) > 1 for u in index.ops)):
        raise UnsupportedStructure("requires multiple reduction trees with a join and no fanout")
    tensors, output_tensors, records, joined_nodes = _original_tree(index)
    assignment = index.assignment(cores)
    component_for = {u: cid for cid, component in enumerate(index.components) for u in component}

    # Children are processed before parents in Index.order. The Sethi-Ullman
    # ordering key is peak - retained, descending, then minimum op ID.
    peak, retained, child_order = {}, {}, {}
    for u in index.order:
        children = records[component_for[u]]["children"][u]
        children.sort(key=lambda child: (-(peak[child] - retained[child]), child))
        child_order[u] = children
        live = 0
        frontier = 0
        for child in children:
            frontier = max(frontier, live + peak[child])
            live += retained[child]
        own_output = tensors[output_tensors[u][0]]
        retained[u] = own_output
        peak[u] = max(frontier, live + own_output)

    postorders = {}
    for record in records:
        root = record["root"]
        out, stack = [], [(root, False)]
        while stack:
            u, visited = stack.pop()
            if visited:
                out.append(u)
            else:
                stack.append((u, True))
                stack.extend((child, False) for child in reversed(child_order[u]))
        if len(out) != len(record["members"]) or set(out) != record["members"]:
            raise UnsupportedStructure("DFS did not cover the indexed tree")
        postorders[min(record["members"])] = out

    sequences = []
    for component_ids in assignment:
        ordered_ids = sorted(component_ids, key=lambda cid: min(index.components[cid]))
        sequences.append([u for cid in ordered_ids
                          for u in postorders[min(index.components[cid])]])

    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(index.graph, plan)
    component_meta = []
    for record in records:
        root = record["root"]
        component_meta.append({
            "root_op": root, "min_op_id": min(record["members"]),
            "peak_frontier_bytes": peak[root],
            "retained_root_output_bytes": retained[root],
            "dfs_postorder": postorders[min(record["members"])],
        })
    return plan, {
        "strategy": "forest_memory_order",
        "components": len(records), "join_nodes": joined_nodes,
        "ownership": "Index.assignment preserved; singleton IDs follow Index.order",
        "order_rule": "DFS postorder; children sorted by descending peak-minus-retained, then op ID",
        "predicted_frontier": component_meta,
        "prediction_scope": "per-tree internal output tensors only; ordering proxy, not official memory/spill certificate",
        "complexity": "DFS ordering O(V + E + sum_v degree(v) log degree(v)); excludes Index/assignment/official validation",
    }
