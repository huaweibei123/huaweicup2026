"""Spill witness from Q1 semantic review d7fc440, function tensor_graph.
Exercises original DDR backing + two L1 incarnations under official config.
"""
def tensor_graph():
    size = 262144
    graph = {
        "ops": [{"id": i, "op": "COPY_IN" if i == 1 else "CONV",
                 "pipe": "PIPE_MTE2" if i == 1 else "PIPE_M",
                 "cycles": 0 if i == 1 else 4} for i in range(1, 9)],
        "tensors": [{"id": 10001+i, "pos": "DDR" if i == 0 else "L1",
                     "size": size} for i in range(9)],
    }
    edges = [(10001,1),(1,10002),(10002,2),(2,10003),(10003,3),
             (3,10004),(3,4),(10002,4),(4,10005),(10005,5),
             (5,10006),(10006,6),(6,10007),(10007,7),(7,10008),
             (7,8),(10002,8),(8,10009)]
    graph["edges"] = [{"source": a, "target": b} for a,b in edges]
    plan = {"node_to_subgraph": {str(i): 0 for i in range(2,9)},
            "core_schedules": [[0], []]}
    return graph, plan
