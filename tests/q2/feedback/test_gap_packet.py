"""Independent calendar oracle and guarded plan checks, no official E0 calls."""
import random
import unittest

from src.q2.feedback.capacity_window import build as capacity_build
from src.q2.feedback.gap_calendar import empty, earliest, reserve
from src.q2.feedback.gap_packet import build, chain_dag
from src.q2.feedback.tensor_packet import TensorIndex
from tests.q2.feedback.test_capacity_window import chains


def diamond():
    return {'ops': [
        {'id': u, 'op': 'COMPUTE', 'pipe': pipe, 'cycles': cycles}
        for u, pipe, cycles in [(1, 'PIPE_M', 10), (2, 'PIPE_M', 30),
                                (3, 'PIPE_V', 10), (4, 'PIPE_M', 5), (5, 'PIPE_V', 5)]],
        'tensors': [], 'edges': [{'source': u, 'target': v, 'data_size': 8}
                                 for u, v in [(1, 3), (2, 3), (3, 4), (3, 5)]]}


class CalendarTests(unittest.TestCase):
    def test_persistence_and_hole_before_future_reservation(self):
        original = empty()
        booked = reserve(original, 10, 20)
        self.assertEqual(earliest(original, 0, 15), 0)
        self.assertEqual(earliest(booked, 0, 5), 0)
        self.assertEqual(earliest(booked, 6, 5), 30)
        filled = reserve(booked, 0, 5)
        self.assertEqual(earliest(filled, 0, 6), 30)
        self.assertEqual(earliest(booked, 0, 6), 0)

    def test_seeded_nonoverlap_oracle_with_past_and_future_insertions(self):
        rng = random.Random(74019)
        for _ in range(12):
            root, occupied = empty(), []
            for _ in range(80):
                release, duration = rng.randrange(300), rng.randrange(1, 21)
                candidate = release
                for left, right in sorted(occupied):
                    if candidate + duration <= left:
                        break
                    if candidate < right:
                        candidate = right
                self.assertEqual(earliest(root, release, duration), candidate)
                root = reserve(root, candidate, duration)
                occupied.append((candidate, candidate + duration))

    def test_overlapping_reservation_is_rejected(self):
        with self.assertRaises(ValueError):
            reserve(reserve(empty(), 3, 7), 4, 1)


class GapPacketTests(unittest.TestCase):
    def test_diamond_join_is_paired_and_all_nodes_appear_once(self):
        index = TensorIndex(diamond())
        for cores in (1, 2, 5):
            plan, meta = build(index, cores, 60, 500, {'L1': 524288, 'UB': 131072})
            self.assertEqual(meta['selected'], 'join_gap_packet')
            self.assertGreater(meta['paired_joins'], 0)
            self.assertEqual(meta['online_E0_calls'], 0)
            scheduled = [u for seq in plan['core_schedules'] for u in seq]
            self.assertEqual(sorted(scheduled), list(range(5)))
            self.assertEqual(len(plan['core_schedules']), cores)

    def test_chain_family_uses_existing_capacity_fallback(self):
        index = TensorIndex(chains())
        capacity = {'L1': 128, 'UB': 128}
        expected, _ = capacity_build(index, 1, 60, 500, capacity)
        actual, meta = build(index, 1, 60, 500, capacity)
        self.assertEqual(actual, expected)
        self.assertEqual(meta['selected'], 'gap_guard_capacity_fallback')

    def test_alias_and_copy_contraction_do_not_enter_physical_edge_route(self):
        graph = diamond()
        graph['tensors'] = [{'id': 100, 'pos': 'L1', 'size': 8, 'logical_tid': 100}]
        self.assertIsNone(chain_dag(TensorIndex(graph), 60, 500))
        graph = diamond()
        graph['edges'] = [e for e in graph['edges'] if (e['source'], e['target']) != (1, 3)]
        graph['ops'].append({'id': 90, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['tensors'] = [{'id': 100, 'pos': 'L1', 'size': 8}, {'id': 101, 'pos': 'DDR', 'size': 8}]
        graph['edges'] += [{'source': u, 'target': v} for u, v in [(1, 100), (100, 90), (90, 101), (101, 3)]]
        self.assertIsNone(chain_dag(TensorIndex(graph), 60, 500))

    def test_invalid_model_parameters_rejected(self):
        index = TensorIndex(diamond())
        for cores, bandwidth, delay in [(True, 60, 500), (6, 60, 500), (2, float('nan'), 500),
                                         (2, True, 500), (2, 60, -1)]:
            with self.assertRaises(ValueError):
                build(index, cores, bandwidth, delay, {'L1': 100, 'UB': 100})


if __name__ == '__main__':
    unittest.main()
