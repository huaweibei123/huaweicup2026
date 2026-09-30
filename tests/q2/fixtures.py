"""Small, explicitly labelled graphs. No evaluator is called by this module."""


def graph(tensors, ops, edges):
    return {
        "tensors": [dict(id=i, pos=p, size=s) for i, p, s in tensors],
        "ops": [dict(id=i, op=o, pipe=p, cycles=c) for i, o, p, c in ops],
        "edges": [dict(source=a, target=b) for a, b in edges],
    }


def minimal(output_size=16):
    """PDF page 11; output_size=131072 violates single-op capacity guarantee."""
    return graph(
        [(1, "DDR", 16), (2, "UB", 16), (3, "UB", output_size),
         (4, "DDR", output_size)],
        [(10, "COPY_IN", "PIPE_MTE2", 1), (11, "ADD", "PIPE_V", 4),
         (12, "COPY_OUT", "PIPE_MTE3", 1)],
        [(1, 10), (10, 2), (2, 11), (11, 3), (3, 12), (12, 4)],
    ), {"node_to_subgraph": {"11": 0}, "core_schedules": [[0], []]}


def global_cycle():
    """Two independent forward chains; opposing core FIFO orders create a wait ring."""
    return graph(
        [(1, "DDR", 16), (2, "UB", 16), (3, "UB", 16), (4, "UB", 16),
         (5, "DDR", 16), (6, "DDR", 16), (7, "UB", 16), (8, "UB", 16),
         (9, "UB", 16), (18, "DDR", 16)],
        [(10, "COPY_IN", "PIPE_MTE2", 1), (11, "ADD", "PIPE_V", 4),
         (12, "ADD", "PIPE_V", 4), (13, "COPY_OUT", "PIPE_MTE3", 1),
         (14, "COPY_IN", "PIPE_MTE2", 1), (15, "ADD", "PIPE_V", 4),
         (16, "ADD", "PIPE_V", 4), (17, "COPY_OUT", "PIPE_MTE3", 1)],
        [(1, 10), (10, 2), (2, 11), (11, 3), (3, 12), (12, 4),
         (4, 13), (13, 5), (6, 14), (14, 7), (7, 15), (15, 8),
         (8, 16), (16, 9), (9, 17), (17, 18)],
    ), {"node_to_subgraph": {"11": 0, "12": 1, "15": 2, "16": 3},
        "core_schedules": [[3, 0], [1, 2]]}


def pressure():
    """Every op fits UB, but A/B outputs coexist across priority buckets."""
    return graph(
        [(1, "DDR", 16), (2, "UB", 16), (3, "UB", 70000),
         (4, "UB", 70000), (5, "UB", 16), (6, "UB", 16),
         (7, "DDR", 16), (8, "DDR", 16)],
        [(10, "COPY_IN", "PIPE_MTE2", 1), (11, "ADD", "PIPE_V", 4),
         (12, "ADD", "PIPE_V", 4), (13, "ADD", "PIPE_V", 4),
         (14, "ADD", "PIPE_V", 4), (15, "COPY_OUT", "PIPE_MTE3", 1),
         (16, "COPY_OUT", "PIPE_MTE3", 1)],
        [(1, 10), (10, 2), (2, 11), (11, 3), (2, 12), (12, 4),
         (3, 13), (13, 5), (4, 14), (14, 6), (5, 15), (15, 7),
         (6, 16), (16, 8)],
    ), {"node_to_subgraph": {"11": 0, "12": 1, "13": 2, "14": 3},
        "core_schedules": [[0, 1, 2, 3], [], [], []]}
