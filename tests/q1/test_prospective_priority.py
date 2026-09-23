"""Incomplete journals retain dispatched calls and mark corrupted records."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/q1'))
from prospective_priority import recover_ledger


class ProspectiveLedger(unittest.TestCase):
    def test_unreturned_call_and_truncated_record_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'journal.jsonl').write_text('{"event":"parent_e0_started"}\n')
            arm=root/'entry_relief';arm.mkdir()
            (arm/'journal.jsonl').write_text('{"event":"e1_dispatched"}\n{"event":')
            result=recover_ledger(root)
            self.assertEqual(result['counts']['parent_e0_started'],1)
            self.assertEqual(result['counts']['e1_dispatched'],1)
            self.assertEqual(result['counts']['e1_returned'],0)
            self.assertEqual(len(result['parse_errors']),1)
            self.assertEqual(result['parse_errors'][0]['path'],'entry_relief/journal.jsonl')


if __name__=='__main__':
    unittest.main()
