#!/usr/bin/env python3
"""P1: reduced fair-sharing pipeline and cut-or-blocking certificates.

NOT official E0, NOT a contest solver, NOT an E0 benchmark.
D0 omits every small COPY, memory constraints, and non-chain-contiguous FIFOs.
Its individual schedule values are approximations, NOT E0 lower bounds.
The analytical certificate instead allows arbitrary Task partitions, including
cross-round Tasks. See ASSUMPTIONS below before applying it to official E0.

The PS calculation uses exact rational continuous service. Every COPY completion
in the reported default examples is integral, so the stated ceil projection
has no effect on these examples. This does NOT emulate floating-point E0 or its
unspecified simultaneous-event tie handling on other inputs.
"""
from __future__ import annotations
from fractions import Fraction
from dataclasses import dataclass, asdict
from math import ceil
import argparse
import json
from pathlib import Path

N, ROUNDS, P, CHAIN, SMALL_ADD = 12, 24, 524, 2096, 13
W, G, CROSS = 547, 100, 1000
ROUND_V_WORK = 25295
FIRST_LB = N * W + CHAIN + SMALL_ADD
EPOCH_LB = G + FIRST_LB
FULL_LB = FIRST_LB + (ROUNDS - 1) * EPOCH_LB

ASSUMPTIONS = [
    'All stated compute dependencies are preserved, including root-to-next-round.',
    'All compute nodes use one PIPE_V per core; a core has at most one active Task.',
    'Task activation waits for predecessor Task completion and the stated 100/1000 gates.',
    'A COPY can run only while its owning Task is active.',
    'Every nonresident 32768-byte input of a new Task requires its own COPY_IN of work 547.',
    'Every 32768-byte produced tensor crossing a Task boundary requires COPY_OUT plus COPY_IN, even on the same core; no inter-Task forwarding/cache exception.',
    'The 12 distinct original inputs are used once per branch per round, as stated.',
    'All three internal tensors of each four-node heavy chain are 32768 bytes.',
    'DDR is work-conserving or slower, with total normalized capacity at most one; rounding cannot create extra capacity.',
    'Spills and small COPYs may add work and dependencies; they are not subtracted from the analytical certificates.',
]


def as_number(x: Fraction):
    return x.numerator if x.denominator == 1 else f'{x.numerator}/{x.denominator}'


def ps_inputs(counts: tuple[int, ...], releases: tuple[int, ...], work: int = W):
    """One eager, sequential input-COPY stream per core; exact fluid PS."""
    if len(counts) != len(releases) or not counts or work <= 0:
        raise ValueError('Invalid stream dimensions or work')
    if any(not isinstance(n, int) or n < 0 for n in counts):
        raise ValueError('Counts must be nonnegative integers')
    if any(not isinstance(t, int) or t < 0 for t in releases):
        raise ValueError('Release times must be nonnegative integers')
    copied = [0] * len(counts)
    out = [[] for _ in counts]
    pending = {c: Fraction(releases[c]) for c, n in enumerate(counts) if n}
    active: dict[int, Fraction] = {}
    t = Fraction(0)
    while pending or active:
        arrival = min(pending.values()) if pending else None
        done_time = t + len(active) * min(active.values()) if active else None
        nxt = min(v for v in (arrival, done_time) if v is not None)
        if active:
            service = (nxt - t) / len(active)
            active = {c: value - service for c, value in active.items()}
            if any(value < 0 for value in active.values()):
                raise AssertionError('Negative exact remaining work')
        t = nxt
        done = [c for c, value in active.items() if value == 0]
        for c in done:
            del active[c]
            out[c].append(t)
            copied[c] += 1
        # Simultaneous completions retire as a batch; continuous fluid results
        # are independent of zero-time ordering in this stripped model.
        for c in done:
            if copied[c] < counts[c]:
                active[c] = Fraction(work)
        for c in list(pending):
            if pending[c] == t:
                active[c] = Fraction(work)
                del pending[c]
    return out


def stage_d0(counts: tuple[int, ...], *, source: int | None, tail: int):
    """One frontier Task per occupied core, then a separate 143-cycle tail."""
    k = len(counts)
    if sum(counts) != N or not 0 <= tail < k:
        raise ValueError('Expected 12 chains and a valid tail core')
    if source is not None and not 0 <= source < k:
        raise ValueError('Invalid source core')
    releases = tuple(0 if source is None else G if c == source else CROSS
                     for c in range(k))
    inp = ps_inputs(counts, releases)
    vends = []
    ends = []
    for c, xs in enumerate(inp):
        v = Fraction(releases[c]); seq = []
        for x in xs:
            v = max(v, x) + CHAIN
            seq.append(v)
        vends.append(seq)
        ends.append(v if seq else None)
    tail_start = max(end + (G if c == tail else CROSS)
                     for c, end in enumerate(ends) if end is not None)
    return {
        'model': 'D0; not E0 and not an E0 lower bound',
        'counts': counts, 'source': source, 'tail': tail, 'releases': releases,
        'input_completions': [[as_number(x) for x in xs] for xs in inp],
        'V_chain_completions': [[as_number(x) for x in xs] for xs in vends],
        'tail_start': as_number(tail_start),
        'root_completion': as_number(tail_start + 11 * SMALL_ADD),
        'all_COPY_completions_integral': all(x.denominator == 1 for xs in inp for x in xs),
        'tasks': sum(n > 0 for n in counts) + 1,
    }


def prefix_certificate(full: int, cut_lengths: tuple[int, ...]):
    """A necessary epoch bound, not a realizable schedule.

    full: branches whose entire current-round chain is in the previous-root Task.
    cut_lengths: prefix lengths 1..3 of partially carried current-round branches.
    All other branches start outside the previous-root Task.
    """
    if full < 0 or full + len(cut_lengths) > N:
        raise ValueError('Invalid carried-branch count')
    if any(x not in (1, 2, 3) for x in cut_lengths):
        raise ValueError('Prefix lengths must lie in 1..3')
    cuts = len(cut_lengths)
    carried = full + cuts
    if full == N:
        bound = N * CHAIN  # deliberately ignores all ADDs and copies
        return {'full': full, 'partial': cuts, 'carried': carried,
                'cut_lengths': cut_lengths, 'lower_bound': bound}
    prefix_work = full * CHAIN + sum(cut_lengths) * P
    largest_prefix = max(cut_lengths, default=0) * P
    end_of_previous_root_task = prefix_work
    if cuts:
        end_of_previous_root_task = max(end_of_previous_root_task,
                                      min(cut_lengths) * P + cuts * W)
        # Without a complete current-round chain, no current-round ADD can
        # be in this Task. Its last current-round V op produces a boundary
        # tensor, whose COPY_OUT must finish before the Task finishes.
        if full == 0:
            end_of_previous_root_task = max(end_of_previous_root_task,
                                          prefix_work + W)
    first_outside_inputs = N - full
    bound = (end_of_previous_root_task + G + first_outside_inputs * W
             + CHAIN - largest_prefix + SMALL_ADD)
    return {
        'full': full, 'partial': cuts, 'carried': carried,
        'cut_lengths': cut_lengths, 'prefix_V_work': prefix_work,
        'previous_root_Task_end_offset_LB': end_of_previous_root_task,
        'first_outside_big_inputs': first_outside_inputs,
        'remaining_compute_tail_LB': CHAIN - largest_prefix + SMALL_ADD,
        'lower_bound': bound,
    }


def verify_prefix_inequalities():
    """Check all 1,820 count-tuples; this is NOT a Task-plan search."""
    checked = 0; minimum = None; minimum_carried = None
    for full in range(N + 1):
        for c1 in range(N - full + 1):
            for c2 in range(N - full - c1 + 1):
                for c3 in range(N - full - c1 - c2 + 1):
                    lengths = (1,) * c1 + (2,) * c2 + (3,) * c3
                    cert = prefix_certificate(full, lengths)
                    b, lb = cert['carried'], cert['lower_bound']
                    assert lb >= EPOCH_LB
                    assert lb >= EPOCH_LB + P * b
                    if b:
                        assert lb >= EPOCH_LB + W
                        minimum_carried = lb if minimum_carried is None else min(minimum_carried, lb)
                    minimum = lb if minimum is None else min(minimum, lb)
                    checked += 1
    return {'count_tuples_checked': checked, 'minimum_epoch_bound': minimum,
            'minimum_bound_with_any_carried_first_op': minimum_carried,
            'checked_inequality': 'epoch >= 8773 + 524 * carried_first_ops'}


def target_certificate(target: int, known_M: int | None = None):
    """M is distinct original-input/Task pairs, not necessarily actual COPY count."""
    if target < FULL_LB:
        return {'target': target, 'excluded_by_universal_bound': True}
    M_min = max(N, N * ROUNDS - (target - FULL_LB) // P)
    available_big_copy_work_units = target // W
    M = known_M if known_M is not None else M_min
    if not N <= M <= N * ROUNDS:
        raise ValueError('M must be between 12 and 288')
    B_max = (available_big_copy_work_units - M) // 2
    return {
        'target': target, 'M_min_from_blocking': M_min,
        'M_used_for_capacity': M, 'big_internal_boundary_count_max': B_max,
        'small_COPYs_ignored_in_capacity': True,
    }


def create_report():
    stages = {
        'C_first5': stage_d0((3, 3, 2, 2, 2), source=None, tail=0),
        'first4': stage_d0((3, 3, 3, 3, 0), source=None, tail=0),
        'C_steady_rotating': stage_d0((3, 3, 2, 2, 2), source=0, tail=1),
        'candidate_steady_fixed': stage_d0((4, 2, 2, 2, 2), source=0, tail=0),
        'four_core_steady': stage_d0((3, 3, 3, 3), source=0, tail=1),
    }
    assert stages['C_first5']['root_completion'] == 10805
    assert stages['first4']['root_completion'] == 9803
    assert stages['C_steady_rotating']['root_completion'] == 10552
    assert stages['candidate_steady_fixed']['root_completion'] == 9709
    assert stages['four_core_steady']['root_completion'] == 10619
    assert all(s['all_COPY_completions_integral'] for s in stages.values())
    totals = {
        'C5_D0': {'makespan': 10805 + 23 * 10552, 'tasks': 144},
        'user_candidate_D0': {'makespan': 10805 + 23 * 9709, 'tasks': 144},
        'first4_then_candidate_D0': {'makespan': 9803 + 23 * 9709, 'tasks': 143},
        'C4_D0': {'makespan': 9803 + 23 * 10619, 'tasks': 120},
    }
    return {
        'notice': 'Analytical/reduced-model results only. No official E0 was read or run.',
        'analytical_assumptions': ASSUMPTIONS,
        'D0_stages': stages, 'D0_24round_totals': totals,
        'universal_bound': {'first': FIRST_LB, 'later': EPOCH_LB, 'total': FULL_LB},
        'prefix_inequality_checks': verify_prefix_inequalities(),
        'target_certificates': [target_certificate(253855), target_certificate(253855, 288),
                                target_certificate(233110)],
        'COPY_accounting_under_the_stated_boundary_rule': {
            'uncut_big_input_COPYs': 288, 'uncut_small_COPYs': 715,
            'uncut_bytes': 288 * 32768 + 715 * 2,
            'uncut_normalized_work': 288 * W + 715,
            'star_big_internal_cuts': 94,
            'star_big_COPYs': 288 + 2 * 94,
            'star_small_COPYs': 715 + 46,
            'star_bytes': (288 + 2 * 94) * 32768 + (715 + 46) * 2,
            'star_normalized_work': (288 + 2 * 94) * W + 715 + 46,
        },
        'small_COPY_counterexample': {
            'one_core_two_chains': True,
            'MTE2_FIFO': ['A_32768B', 'B_32768B', 'shared_root_2B'],
            'each_chain_first_op_needs_shared_root': True,
            'full_time': 2 * W + 1 + 2 * CHAIN,
            'without_small_COPY_and_its_dependency': W + 2 * CHAIN,
            'difference': W + 1,
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    report = create_report()
    data = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(data + '\n', encoding='utf-8')
        print(f'Wrote {args.output}')
    else:
        print(data)


if __name__ == '__main__':
    main()
