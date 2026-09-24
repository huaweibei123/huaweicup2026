"""Deterministic synthetic P1 fork/chain/reduction inputs; no solver or score."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FAMILIES = (
    ("family-a", ((8, 4, 200, 7),) * 3, ("balanced",) * 3, 5),
    ("family-b", ((7, 3, 60, 7),) * 3, ("comb",) * 3, 3),
    ("family-c", ((5, 2, 400, 5), (9, 3, 80, 9), (6, 5, 150, 4)),
     ("balanced", "comb", "balanced"), 4),
)
SIZES = (128, 4096, 32768)
DISCLAIMER = "Synthetic input only; no official graph, solver, E0/E1/E2, or quality result."


def _graph(specs, shapes, size):
    ops, tensors, edges = [], [], []
    next_op, next_tensor = 1, 1_000_000

    def tensor(pos):
        nonlocal next_tensor
        ident = next_tensor
        next_tensor += 1
        tensors.append({"id": ident, "pos": pos, "size": size})
        return ident

    def operation(kind, pipe, cycles, inputs, output_pos="UB"):
        nonlocal next_op
        ident = next_op
        next_op += 1
        ops.append({"id": ident, "op": kind, "pipe": pipe, "cycles": cycles})
        edges.extend({"source": source, "target": ident} for source in inputs)
        output = tensor(output_pos)
        edges.append({"source": ident, "target": output})
        return output

    copy_cycles = max(1, (size + 59) // 60)
    ddr_input = tensor("DDR")
    previous = operation("COPY_IN", "PIPE_MTE2", copy_cycles, [ddr_input])
    for (width, depth, chain_cycles, reduce_cycles), shape in zip(specs, shapes):
        leaves = []
        for _ in range(width):
            current = previous
            for _ in range(depth):
                current = operation("COMPUTE", "PIPE_V", chain_cycles, [current])
            leaves.append(current)
        if shape == "comb":
            previous = leaves[0]
            for leaf in leaves[1:]:
                previous = operation("COMPUTE", "PIPE_V", reduce_cycles,
                                     [previous, leaf])
        elif shape == "balanced":
            while len(leaves) > 1:
                following = []
                for index in range(0, len(leaves) - 1, 2):
                    following.append(operation("COMPUTE", "PIPE_V", reduce_cycles,
                                               leaves[index:index + 2]))
                if len(leaves) % 2:
                    following.append(leaves[-1])
                leaves = following
            previous = leaves[0]
        else:
            raise ValueError(f"unknown reduction shape: {shape}")
    operation("COPY_OUT", "PIPE_MTE3", copy_cycles, [previous], "DDR")
    return {"ops": ops, "tensors": tensors, "edges": edges}


def fixtures():
    """Yield exactly nine (name, graph, cores, metadata) synthetic fixtures."""
    for family, specs, shapes, cores in FAMILIES:
        for size in SIZES:
            name = f"{family}-tensor-{size}"
            yield name, _graph(specs, shapes, size), cores, {
                "family": family, "rounds": [list(s) for s in specs],
                "reduction_shapes": list(shapes), "tensor_size_bytes": size,
                "copy_cycles": max(1, (size + 59) // 60),
                "synthetic_only": True,
            }


def _bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_all(directory):
    """Write graph files and a hash manifest once; refuse any existing output."""
    directory = Path(directory)
    rows, files = [], []
    for name, graph, cores, metadata in fixtures():
        filename = f"{name}.json"
        payload = _bytes(graph)
        files.append((directory / filename, payload))
        rows.append({"name": name, "file": filename, "sha256": hashlib.sha256(payload).hexdigest(),
                     "cores": cores, "metadata": metadata})
    manifest = directory / "manifest.json"
    if any(path.exists() for path, _ in files) or manifest.exists():
        raise FileExistsError("synthetic output already exists")
    directory.mkdir(parents=True, exist_ok=True)
    for path, payload in files:
        with path.open("xb") as stream:
            stream.write(payload)
    with manifest.open("xb") as stream:
        stream.write(_bytes({"disclaimer": DISCLAIMER, "fixtures": rows}))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    print(write_all(parser.parse_args().output_dir))
