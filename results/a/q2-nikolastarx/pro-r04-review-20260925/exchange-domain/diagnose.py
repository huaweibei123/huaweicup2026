"""Read-only fixed-calendar exchange-domain diagnosis for frozen case 003/k2.

No plan construction, search, flow, or evaluator calls. Binary labels are the
two original cores. Overlapping opposite-core Pipe intervals force equal flip
bits, so their low-lag groups join one exchange block.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import gzip
import json
import argparse
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PROBE = HERE.parent / 'static-003-k2'
CASE_SHA = '2c80acfd37edcf811ce76b7e7b1f7194c706bd4d4aa6449e6a19e9eac1028ced'
WITNESS_SHA = '01846e479bda5974554e01858b00b534c43ad6f029ae09c111df21d5c30e1f52'


class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        x, y = self.find(x), self.find(y)
        if x == y:
            return False
        if self.size[x] < self.size[y]:
            x, y = y, x
        self.parent[y] = x
        self.size[x] += self.size[y]
        return True


def verified_bytes(path, digest):
    data = path.read_bytes()
    actual = sha256(data).hexdigest()
    if actual != digest:
        raise ValueError(f'{path}: SHA-256 mismatch {actual}')
    return data


def summary(values):
    values = sorted(values)
    if not values:
        return {'count': 0}
    return {'count': len(values), 'min': values[0], 'median': values[len(values)//2],
            'p90': values[(9*(len(values)-1))//10],
            'p99': values[(99*(len(values)-1))//100], 'max': values[-1],
            'histogram': {str(k): v for k, v in sorted(Counter(values).items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, default=ROOT/'data/raw/a/official/data/case_003.json')
    args = parser.parse_args()
    graph = json.loads(verified_bytes(args.graph, CASE_SHA))
    raw = verified_bytes(PROBE / 'seed-witness.json.gz', WITNESS_SHA)
    witness = json.loads(gzip.decompress(raw))
    result = json.loads((PROBE / 'result.json').read_text())
    if result['source_commit'] != '56962a8946c5ae6976d231fe4b471730b9a171de':
        raise ValueError('unexpected probe source commit')
    chains = witness['chains']
    n = len(chains)
    placement = {int(k): v for k, v in witness['placement'].items()}
    starts = {int(k): v for k, v in witness['starts'].items()}
    delays = [(u, v, lag) for u, v, lag in witness['delays']]
    ops = {op['id']: op for op in graph['ops'] if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
    if n != 9903 or set(placement) != set(range(n)) or set(starts) != set(ops):
        raise ValueError('frozen witness dimensions changed')
    if {u for chain in chains for u in chain} != set(ops) or sum(map(len, chains)) != len(ops):
        raise ValueError('chains do not partition eligible ops')
    if set(placement.values()) != {0, 1}:
        raise ValueError('expected exactly two original cores')
    unit_start = [starts[chain[0]] for chain in chains]
    unit_end = [starts[chain[-1]] + max(1, ops[chain[-1]]['cycles']) for chain in chains]
    lowlag = DSU(n)
    lowlag_edges = 0
    for u, v, lag in delays:
        slack = unit_start[v] - unit_end[u]
        if slack < 0 or (placement[u] != placement[v] and slack < lag):
            raise ValueError('frozen static lag witness infeasible')
        if slack < lag:
            lowlag_edges += 1
            lowlag.union(u, v)
    roots = sorted({lowlag.find(j) for j in range(n)})
    if len(roots) != result['repair']['tight_group_count']:
        raise ValueError('low-lag group count differs from frozen probe')
    group_id = {root: i for i, root in enumerate(roots)}
    unit_group = [group_id[lowlag.find(j)] for j in range(n)]
    group_cores = defaultdict(set)
    group_chains = Counter()
    group_ops = Counter()
    for j, chain in enumerate(chains):
        group = unit_group[j]
        group_cores[group].add(placement[j])
        group_chains[group] += 1
        group_ops[group] += len(chain)
    if any(len(colors) != 1 for colors in group_cores.values()):
        raise ValueError('low-lag group spans original cores')

    # Each original (core, Pipe) calendar is disjoint. Two sorted lists can
    # therefore enumerate all opposite-core overlaps in linear time.
    calendars = defaultdict(list)
    for j, chain in enumerate(chains):
        for u in chain:
            op = ops[u]
            begin = starts[u]
            end = begin + max(1, op['cycles'])
            calendars[op['pipe'], placement[j]].append((begin, end, unit_group[j], u))
    for row in calendars.values():
        row.sort()
        if any(left[1] > right[0] for left, right in zip(row, row[1:])):
            raise ValueError('original same-core Pipe calendar overlaps')
    exchange = DSU(len(roots))
    overlap_count = 0
    merging_overlaps = 0
    overlap_by_pipe = Counter()
    for pipe in sorted({key[0] for key in calendars}):
        left = calendars[pipe, 0]
        right = calendars[pipe, 1]
        i = j = 0
        while i < len(left) and j < len(right):
            x, y = left[i], right[j]
            if x[0] < y[1] and y[0] < x[1]:
                overlap_count += 1
                overlap_by_pipe[pipe] += 1
                merging_overlaps += exchange.union(x[2], y[2])
            if x[1] <= y[1]:
                i += 1
            else:
                j += 1

    blocks = defaultdict(list)
    for group in range(len(roots)):
        blocks[exchange.find(group)].append(group)
    rows = []
    for members in blocks.values():
        color_counts = Counter(next(iter(group_cores[g])) for g in members)
        rows.append({'groups': len(members), 'chains': sum(group_chains[g] for g in members),
                     'ops': sum(group_ops[g] for g in members),
                     'original_core_group_counts': {str(c): color_counts[c] for c in (0, 1)},
                     'has_both_original_cores': len(color_counts) == 2})
    rows.sort(key=lambda row: (-row['groups'], -row['chains'], -row['ops']))
    mixed = sum(row['has_both_original_cores'] for row in rows)
    # With two identical cores, complementing all flip bits is a global core
    # rename and leaves COPY connectivity unchanged. Fix the largest block's
    # bit to zero; only nets incident to the remaining blocks can change.
    sys.path.insert(0, str(ROOT))
    from src.q2_nikolastarx.gap_corridor import physical_nets
    constant, nets = physical_nets(graph, {u: u for u in ops})
    op_block = {u: exchange.find(unit_group[j]) for j, chain in enumerate(chains) for u in chain}
    op_core = {u: placement[j] for j, chain in enumerate(chains) for u in chain}
    biggest = max(blocks, key=lambda b: sum(group_ops[g] for g in blocks[b]))
    original_bytes = constant
    possible_saved_bytes = 0
    mutable_cross_nets = 0
    invariant_cross_bytes = 0
    for net in nets:
        colors = {op_core[u] for u in net.pins}
        original_bytes += net.weight * (len(colors)-1)
        if len(colors) < 2:
            continue
        by_block = defaultdict(set)
        for u in net.pins:
            by_block[op_block[u]].add(op_core[u])
        invariant = any(len(c) == 2 for c in by_block.values())
        if invariant:
            invariant_cross_bytes += net.weight
        elif any(b != biggest for b in by_block):
            possible_saved_bytes += net.weight
            mutable_cross_nets += 1
    assert original_bytes == result['before_bytes']
    report = {
        'scope': 'Read-only fixed-timestamp binary exchange domain; no plan, scoring, flow, or official validation.',
        'source_commit': result['source_commit'],
        'case_sha256': CASE_SHA, 'witness_gzip_sha256': WITNESS_SHA,
        'case': '003', 'cores': 2,
        'chain_count': n, 'eligible_op_count': len(ops), 'delay_count': len(delays),
        'low_lag_edges': lowlag_edges, 'low_lag_group_count': len(roots),
        'opposite_core_overlap_count': overlap_count,
        'opposite_core_overlap_by_pipe': dict(sorted(overlap_by_pipe.items())),
        'overlaps_that_merge_components': merging_overlaps,
        'exchange_block_count': len(rows),
        'exchange_block_group_sizes': summary(row['groups'] for row in rows),
        'exchange_block_chain_sizes': summary(row['chains'] for row in rows),
        'exchange_block_op_sizes': summary(row['ops'] for row in rows),
        'mixed_core_blocks': mixed, 'single_core_blocks': len(rows) - mixed,
        'all_blocks_have_both_original_cores': mixed == len(rows),
        'largest_block_group_share': rows[0]['groups'] / len(roots),
        'largest_block_chain_share': rows[0]['chains'] / n,
        'whole_graph_one_block': len(rows) == 1,
        'blocks': rows,
        'fixed_calendar_copy_byte_saving_upper_bound': possible_saved_bytes,
        'current_pre_step2_copy_bytes': original_bytes,
        'fixed_calendar_copy_byte_lower_bound': original_bytes-possible_saved_bytes,
        'mutable_current_cross_nets': mutable_cross_nets,
        'provably_invariant_cross_bytes': invariant_cross_bytes,
        'bound_scope': 'All two-core fixed-time assignments preserving the original chains and chosen unit lag model; not an official Makespan or retimed-plan bound.',
    }
    out = HERE / 'diagnosis.json'
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
    print(json.dumps({k: report[k] for k in (
        'low_lag_group_count', 'opposite_core_overlap_count', 'exchange_block_count',
        'mixed_core_blocks', 'largest_block_group_share', 'whole_graph_one_block')},
        ensure_ascii=False))


if __name__ == '__main__':
    main()
