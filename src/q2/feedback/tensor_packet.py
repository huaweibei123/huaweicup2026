"""P2 direct construction from shared-input chains and serial packets.

No score/evaluator is called. All clock estimates omit spill and memory reuse;
the global DDR term is service demand, not a prediction of completion time.
Shared-chain active-core arithmetic follows yuanzhifang P3 bb7a7e8. The generic
placement is informed by NikolaStarx's tensor DAG at 7f064bb, with serial-chain
packets and an explicit global DDR service term instead of node-only EFT.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq
import math

from .construct import Index, PIPES, UnsupportedStructure, derive_multicore_plan


class TensorIndex(Index):
    def __init__(self, graph):
        super().__init__(graph)
        self.tensors = {t['id']: t for t in graph['tensors']}
        self.inputs = {u: set() for u in self.ops}
        self.outputs = {u: set() for u in self.ops}
        self.producer = {}
        self.consumers = defaultdict(set)
        self.direct = defaultdict(list)
        self.final = set()
        original = {o['id']: o for o in graph['ops']}
        all_producers = defaultdict(set)
        for edge_id, edge in enumerate(graph['edges']):
            u, v = edge['source'], edge['target']
            if u in original and v in self.tensors:
                all_producers[v].add(u)
            if u in self.ops and v in self.tensors:
                self.outputs[u].add(v)
                self.producer[v] = u
            if u in self.tensors and v in self.ops:
                self.inputs[v].add(u)
                self.consumers[u].add(v)
            if u in self.ops and v in self.ops and u != v:
                self.direct[v].append((edge_id, u, max(0, int(edge.get('data_size', 0)))))
            if u in self.tensors and v in original and original[v]['op'] == 'COPY_OUT':
                self.final.add(u)
        if any(len(ps) > 1 for ps in all_producers.values()):
            raise UnsupportedStructure('tensor_packet requires at most one original producer per tensor')
        self.final.update(t for t in self.producer if not self.consumers[t])
        self.external_by_job = [set() for _ in self.components]
        for u, tids in self.inputs.items():
            self.external_by_job[self.owner[u]].update(t for t in tids if t not in self.producer)
        for u in self.ops:
            self.inputs[u] = tuple(sorted(self.inputs[u]))
            self.outputs[u] = tuple(sorted(self.outputs[u]))

    def shared_signature(self):
        if not self.components:
            return None
        common = set.intersection(*self.external_by_job)
        if not common:
            return None
        signatures = []
        for job in self.components:
            if any(v not in self.succ[u] for u, v in zip(job, job[1:])):
                return None
            signatures.append(tuple((self.ops[u]['pipe'], self.duration(u),
                                     tuple(t for t in self.inputs[u] if t in common)) for u in job))
        return common if len(set(signatures)) == 1 else None

    def shared_stages(self, cores, bandwidth, common):
        def cost(t):
            return max(1, math.ceil(self.tensors[t]['size'] / bandwidth))

        choices = []
        for active in range(1, min(cores, len(self.components)) + 1):
            groups = self.assignment(active)
            input_sets = [set().union(*(self.external_by_job[j] for j in group)) for group in groups]
            incoming = sum(cost(t) for ts in input_sets for t in ts)
            # Unique original producer guarantees exactly one producing core.
            outgoing = sum(cost(t) for t in self.final if t in self.producer)
            compute = max(sum(self.work[j][p] for j in group) for group in groups for p in PIPES)
            byte_count = sum(self.tensors[t]['size'] for ts in input_sets for t in ts)
            choices.append({'active_cores': active, 'pipe_work': compute,
                            'copy_service': incoming + outgoing,
                            'ingress_bytes': byte_count,
                            'model_cycles': max(compute, incoming + outgoing)})
        choice = min(choices, key=lambda r: (r['model_cycles'], r['ingress_bytes'], r['active_cores']))
        active = choice['active_cores']
        groups = self.assignment(active)
        sequences = [[self.components[j][position] for position in range(len(self.components[0])) for j in group]
                     for group in groups]
        sequences.extend([] for _ in range(cores - active))
        return sequences, {'selected': 'shared_stages', 'active_cores': active,
                           'common_input_bytes': sum(self.tensors[t]['size'] for t in common),
                           'resource_choices': choices,
                           'scope': 'Exact no-spill COPY service for this placement; model choice is heuristic'}

    def shared_cohorts(self, cores, bandwidth):
        """Group ordered isomorphic DAGs sharing inputs at the same positions.

        Different input cohorts need not share a tensor globally. A cohort is
        placed once using at most k arithmetic load/copy-demand comparisons.
        The method never creates or scores k complete schedules.
        """
        counts = Counter(t for ts in self.external_by_job for t in ts)
        shared = {t for t, count in counts.items() if count > 1}
        groups = defaultdict(list)
        for j, job in enumerate(self.components):
            position = {u: i for i, u in enumerate(job)}
            signature = tuple((self.ops[u]['pipe'], self.duration(u),
                               tuple(sorted(position[p] for p in self.pred[u])),
                               tuple(t for t in self.inputs[u] if t in shared)) for u in job)
            # A component with no repeated input is an individual cohort.
            key = signature if any(t in shared for t in self.external_by_job[j]) else ('private', j)
            groups[key].append(j)
        if not any(len(group) > 1 for group in groups.values()):
            return None
        cohorts = sorted(groups.values(), key=lambda js: (
            -max(sum(self.work[j][p] for j in js) for p in PIPES), self.components[js[0]][0]))
        loads = [dict.fromkeys(PIPES, 0) for _ in range(cores)]
        inputs = [set() for _ in range(cores)]
        service = sum(max(1, math.ceil(self.tensors[t]['size'] / bandwidth)) for t in self.final if t in self.producer)
        sequences = [[] for _ in range(cores)]
        details = []
        arithmetic_choices = 0

        for cohort in cohorts:
            order = sorted(range(cores), key=lambda c: (max(loads[c].values()), sum(loads[c].values()), c))
            choices = []
            for active in range(1, min(cores, len(cohort)) + 1):
                trial = [dict(load) for load in loads]
                delta_inputs = [set() for _ in range(cores)]
                assigned = [[] for _ in range(cores)]
                for j in cohort:
                    c = min(order[:active], key=lambda c: (
                        max(trial[c][p] + self.work[j][p] for p in PIPES), sum(trial[c].values()), c))
                    assigned[c].append(j)
                    for p in PIPES:
                        trial[c][p] += self.work[j][p]
                    delta_inputs[c].update(self.external_by_job[j] - inputs[c])
                extra = sum(max(1, math.ceil(self.tensors[t]['size'] / bandwidth)) for ts in delta_inputs for t in ts)
                byte_count = sum(self.tensors[t]['size'] for ts in delta_inputs for t in ts)
                peak = max(max(load.values()) for load in trial)
                score = (max(peak, service + extra), byte_count, peak, active)
                choices.append((score, assigned, trial, delta_inputs, extra))
            arithmetic_choices += len(choices)
            score, assigned, loads, delta_inputs, extra = min(choices, key=lambda item: item[0])
            service += extra
            for c, jobs in enumerate(assigned):
                inputs[c].update(delta_inputs[c])
                if jobs:
                    sequences[c].extend(self.components[j][pos] for pos in range(len(self.components[jobs[0]])) for j in jobs)
            details.append({'jobs': len(cohort), 'active_cores': score[-1],
                            'model_cycles_after_placement': score[0]})
        return sequences, {'selected': 'shared_cohorts', 'cohorts': details,
                           'arithmetic_resource_choices': arithmetic_choices,
                           'no_spill_ddr_service': service,
                           'active_cores': sum(bool(s) for s in sequences),
                           'scope': 'Direct cohort load/COPY arithmetic and stage order; spill and timing unpredicted'}

    def packets(self, cores):
        """Keep small components intact; split heavier ones into maximal chains.

        A component is heavy iff its work on some pipe exceeds the whole-graph
        ceil(work/cores) budget. Inside it contract u->v only for outdeg(u)=1 and
        indeg(v)=1. This cannot introduce a contracted cycle.
        """
        target = {p: math.ceil(sum(w[p] for w in self.work) / cores) for p in PIPES}
        heavy = {j for j, w in enumerate(self.work) if any(w[p] > target[p] for p in PIPES)}
        packets, owner = [], {}
        for job_id, job in enumerate(self.components):
            if job_id not in heavy:
                packet = len(packets)
                packets.append(list(job))
                owner.update((u, packet) for u in job)
                continue
            for u in job:
                if u in owner:
                    continue
                packet = len(packets)
                chain = [u]
                owner[u] = packet
                while len(self.succ[chain[-1]]) == 1:
                    v = next(iter(self.succ[chain[-1]]))
                    if len(self.pred[v]) != 1:
                        break
                    owner[v] = packet
                    chain.append(v)
                packets.append(chain)
        pred = [set() for _ in packets]
        succ = [set() for _ in packets]
        for u in self.order:
            for v in self.succ[u]:
                a, b = owner[u], owner[v]
                if a != b:
                    pred[b].add(a)
                    succ[a].add(b)
        # Packet numbering need not be topological across contractions.
        degree = [len(x) for x in pred]
        ready = [i for i, d in enumerate(degree) if d == 0]
        heapq.heapify(ready)
        order = []
        while ready:
            u = heapq.heappop(ready)
            order.append(u)
            for v in sorted(succ[u]):
                degree[v] -= 1
                if not degree[v]:
                    heapq.heappush(ready, v)
        if len(order) != len(packets):
            raise AssertionError('serial contraction produced a cycle')
        work = [sum(self.duration(u) for u in packet) for packet in packets]
        tail = {}
        for u in reversed(order):
            tail[u] = work[u] + max((tail[v] for v in succ[u]), default=0)
        return packets, pred, succ, tail, len(heavy)

    def packet_eft(self, cores, bandwidth, delay):
        packets, pred, succ, tail, heavy_count = self.packets(cores)
        pipe_at = [{p: 0 for p in PIPES} for _ in range(cores)]
        owner, finish, arrivals = {}, {}, {}
        per_core = [[] for _ in range(cores)]
        packets_by_core = [[] for _ in range(cores)]
        load = [0] * cores
        ddr_work = 0
        ddr_bytes = 0
        degree = [len(p) for p in pred]
        ready = [(-tail[j], packets[j][0], j) for j, d in enumerate(degree) if not d]
        heapq.heapify(ready)

        def propose(packet, core):
            clocks, incoming, local_finish = {}, {}, {}
            extra_work, extra_bytes = 0, 0

            def clock(c, p):
                return clocks.get((c, p), pipe_at[c][p])

            def transfer(key, source, release, size):
                nonlocal extra_work, extra_bytes
                if key in arrivals:
                    return arrivals[key]
                if key in incoming:
                    return incoming[key]
                cost = max(1, math.ceil(size / bandwidth))
                if source is not None:
                    release = max(release, clock(source, 'PIPE_MTE3')) + cost
                    clocks[source, 'PIPE_MTE3'] = release
                    release += delay
                    extra_work += cost
                    extra_bytes += size
                end = max(release, clock(core, 'PIPE_MTE2')) + cost
                clocks[core, 'PIPE_MTE2'] = end
                incoming[key] = end
                extra_work += cost
                extra_bytes += size
                return end

            end = 0
            score_end = 0
            for u in packet:
                release = max((local_finish[v] if v in local_finish else finish[v] for v in self.pred[u]), default=0)
                for tid in self.inputs[u]:
                    producer = self.producer.get(tid)
                    if producer is None:
                        release = max(release, transfer(('input', tid, core), None, 0, self.tensors[tid]['size']))
                    elif producer not in local_finish and owner[producer] != core:
                        source = owner[producer]
                        release = max(release, transfer(('tensor', tid, source, core), source, finish[producer], self.tensors[tid]['size']))
                for edge_id, v, size in self.direct[u]:
                    if v not in local_finish and owner[v] != core:
                        release = max(release, transfer(('direct', edge_id), owner[v], finish[v], size))
                pipe = self.ops[u]['pipe']
                end = max(release, clock(core, pipe)) + self.duration(u)
                clocks[core, pipe] = end
                local_finish[u] = end
                score_end = max(score_end, end)
                for tid in self.outputs[u]:
                    if tid in self.final:
                        cost = max(1, math.ceil(self.tensors[tid]['size'] / bandwidth))
                        out_end = max(end, clock(core, 'PIPE_MTE3')) + cost
                        clocks[core, 'PIPE_MTE3'] = out_end
                        score_end = max(score_end, out_end)
                        extra_work += cost
                        extra_bytes += self.tensors[tid]['size']
            score = (max(score_end, ddr_work + extra_work), score_end, extra_bytes, load[core], core)
            return score, clocks, incoming, local_finish, extra_work, extra_bytes

        while ready:
            _, _, packet_id = heapq.heappop(ready)
            packet = packets[packet_id]
            score, clocks, incoming, local_finish, work, byte_count = min(
                (propose(packet, c) for c in range(cores)), key=lambda c: c[0])
            core = score[-1]
            owner.update((u, core) for u in packet)
            finish.update(local_finish)
            arrivals.update(incoming)
            for (c, p), end in clocks.items():
                pipe_at[c][p] = end
            load[core] += sum(self.duration(u) for u in packet)
            ddr_work += work
            ddr_bytes += byte_count
            per_core[core].extend(packet)
            packets_by_core[core].append(packet_id)
            for child in sorted(succ[packet_id]):
                degree[child] -= 1
                if degree[child] == 0:
                    heapq.heappush(ready, (-tail[child], packets[child][0], child))
        if len(owner) != len(self.ops):
            raise AssertionError('packet dispatch did not cover graph')
        per_core, pipeline = self.pipeline_packets(packets, packets_by_core)
        return per_core, {'selected': 'packet_eft', 'packets': len(packets),
                          'split_components': heavy_count,
                          'predicted_pipe_horizon': max(max(x.values()) for x in pipe_at),
                          'no_spill_ddr_service': ddr_work, 'no_spill_ddr_bytes': ddr_bytes,
                          'compute_load_by_core': load,
                          'priority': pipeline,
                          'scope': 'Construction heuristic: local COPY clocks plus global work; memory/spill/FIFO omitted'}

    def pipeline_packets(self, packets, groups):
        """Bound admitted packets, retain all true predecessors, pipeline pipes.

        Placement dispatch order is a topological packet order. Limiting each
        core to a prefix of that order cannot deadlock: the earliest unfinished
        packet in the global dispatch has no unfinished predecessor packet.
        Times here are compute-only priority coordinates, not execution times.
        """
        cores = len(groups)
        positions, remaining, released = {}, {}, {}
        active = [[] for _ in groups]
        next_packet = [0] * cores
        pipe_at = [dict.fromkeys(PIPES, 0) for _ in groups]
        finish = {}
        unresolved = {u: len(self.pred[u]) for u in self.ops}
        predecessor_release = dict.fromkeys(self.ops, 0)
        sequences = [[] for _ in groups]
        windows = []

        def admit(core, at):
            packet = groups[core][next_packet[core]]
            next_packet[core] += 1
            active[core].append(packet)
            positions[packet] = 0
            remaining[packet] = sum(self.duration(u) for u in packets[packet])
            released[packet] = at

        for c, group in enumerate(groups):
            work = {p: sum(self.duration(u) for j in group for u in packets[j] if self.ops[u]['pipe'] == p) for p in PIPES}
            window = min(len(group), 8, 1 + math.ceil(sum(work.values()) / max(work.values()))) if group else 0
            windows.append(window)
            for _ in range(window):
                admit(c, 0)
        while any(active):
            candidates = []
            for c, admitted in enumerate(active):
                for j in admitted:
                    u = packets[j][positions[j]]
                    if unresolved[u]:
                        continue
                    at = max(released[j], pipe_at[c][self.ops[u]['pipe']],
                             predecessor_release[u])
                    candidates.append((at, remaining[j], u, c, j))
            if not candidates:
                raise AssertionError('bounded packet admission blocked despite topological dispatch')
            at, _, u, c, j = min(candidates)
            end = at + self.duration(u)
            finish[u] = end
            for child in self.succ[u]:
                unresolved[child] -= 1
                predecessor_release[child] = max(predecessor_release[child], end)
            released[j] = end
            pipe_at[c][self.ops[u]['pipe']] = end
            remaining[j] -= self.duration(u)
            sequences[c].append(u)
            positions[j] += 1
            if positions[j] == len(packets[j]):
                active[c].remove(j)
                if next_packet[c] < len(groups[c]):
                    admit(c, end)
        return sequences, {'method': 'bounded_packet_pipeline', 'windows': windows,
                           'ideal_compute_coordinate_end': max(finish.values(), default=0)}

    def build_tensor_plan(self, cores, bandwidth, delay):
        if type(cores) is not int or not 1 <= cores <= 5:
            raise ValueError('cores must be 1..5')
        if isinstance(bandwidth, bool) or not isinstance(bandwidth, (int, float)) or not math.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError('positive finite bandwidth required')
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
            raise ValueError('nonnegative finite cross-core delay required')
        try:
            self.word_descriptor()
        except UnsupportedStructure:
            pass
        else:
            plan, meta = super().build(cores, 'resource_word')
            return plan, {**meta, 'selected': 'guarded_resource_word', 'online_E0_calls': 0}
        common = self.shared_signature()
        if common is not None:
            sequences, meta = self.shared_stages(cores, bandwidth, common)
        else:
            cohort_plan = self.shared_cohorts(cores, bandwidth)
            if cohort_plan is not None:
                sequences, meta = cohort_plan
            else:
                sequences, meta = self.packet_eft(cores, bandwidth, delay)
        mapping = {str(u): j for j, u in enumerate(self.order)}
        plan = {'node_to_subgraph': mapping,
                'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
        derive_multicore_plan(self.graph, plan)
        return plan, {**meta, 'strategy': 'tensor_packet', 'cores': cores,
                      'eligible_ops': len(self.ops), 'components': len(self.components),
                      'online_E0_calls': 0}
