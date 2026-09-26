"""Isolated publish guard tests; no real git mutation or network."""
import json
import subprocess
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import q2_publish_completed_batch as pub


class PublishGuards(unittest.TestCase):
    def test_publish_orders_audit_commit_push_and_records_ambiguous_push(self):
        for fail_push in (False, True):
            with self.subTest(fail_push=fail_push), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'repo'
                batch = root / 'results/a/q2-yuanzhifang/feedback-20260924/roundx'
                batch.mkdir(parents=True)
                feed = batch / 'board-feed-saved.json'
                feed.write_text('{}', encoding='utf-8')
                (batch / 'board-feed-saved-preflight.json').write_text('{}', encoding='utf-8')
                (batch / 'summary.json').write_text('{}', encoding='utf-8')
                (batch / 'summary.csv').write_text('x\n', encoding='utf-8')
                source = batch.parent / 'roundx-spec.json'
                spec = {'methods': [{'variant': 'frontier_gap'}], 'cases': ['001']}
                source.write_text(json.dumps(spec), encoding='utf-8')
                receipt = Path(temp) / 'receipt.json'
                calls = []
                added = False
                rel = batch.relative_to(root).as_posix()

                def fake(argv, **_):
                    nonlocal added
                    calls.append(argv)
                    if argv[:2] == ['git', 'show']:
                        return SimpleNamespace(stdout=source.read_bytes())
                    if argv[:4] == ['git', 'diff', '--cached', '--name-only']:
                        return SimpleNamespace(stdout=(rel + '/ledger.json\0').encode() if added else b'')
                    if argv[:2] == ['git', 'add']:
                        added = True
                    if argv[:3] == ['git', 'branch', '--show-current']:
                        return SimpleNamespace(stdout=b'codex/test\n')
                    if argv[:3] == ['git', 'rev-parse', 'HEAD']:
                        return SimpleNamespace(stdout=b'deadbeef\n')
                    if 'push' in argv and fail_push:
                        raise subprocess.TimeoutExpired(argv, 180)
                    return SimpleNamespace(stdout=b'')

                def audit(_, __, ___, ____):
                    calls.append(['audit'])
                    (batch / 'measurement-audit.json').write_text('{}', encoding='utf-8')

                with (patch.object(pub, 'ROOT', root), patch.object(pub, 'SCOPE', batch.parent),
                      patch.object(pub, 'validate', return_value=(spec, {'spec_sha256': 'fixed'},
                                                                 '2026-09-25T00:00:00+00:00')),
                      patch.object(pub, 'batch_files_only'),
                      patch.object(pub, 'verify_audit', side_effect=audit)):
                    if fail_push:
                        with self.assertRaises(subprocess.TimeoutExpired):
                            pub.process(batch, 'fixed', receipt, publish=True, command=fake)
                    else:
                        pub.process(batch, 'fixed', receipt, publish=True, command=fake)
                saved = json.loads(receipt.read_text())
                self.assertEqual(saved['commit'], 'deadbeef')
                self.assertIn('push_started_at_utc', saved)
                self.assertEqual(saved['status'], 'push_unknown' if fail_push else 'pushed')
                self.assertIn('existing_feed_observed_at_utc', saved)
                self.assertNotIn('post_successful_export_return_observed_at_utc', saved)
                self.assertEqual(len(saved['feed_sha256']), 64)
                self.assertLess(calls.index(['audit']), next(i for i, a in enumerate(calls)
                                                         if a[:2] == ['git', 'commit']))
                self.assertEqual([a for a in calls if a[:2] == ['git', 'add']],
                                 [['git', 'add', '-A', '--', rel]])
                pushes = [a for a in calls if 'push' in a]
                self.assertEqual(len(pushes), 1)
                self.assertLess(next(i for i, a in enumerate(calls) if a[:2] == ['git', 'commit']),
                                calls.index(pushes[0]))

    def test_unrelated_staged_file_stops_before_add_or_commit(self):
        calls = []

        def fake(argv, **_):
            calls.append(argv)
            return SimpleNamespace(stdout=b'other-task.txt\0')

        with self.assertRaisesRegex(ValueError, 'unrelated staged'):
            pub.clean_index(fake)
        self.assertEqual(calls, [['git', 'diff', '--cached', '--name-only', '-z']])

    def test_failed_audit_never_reaches_git_stage_or_push(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            batch = root / 'results/a/q2-yuanzhifang/feedback-20260924/roundx'
            batch.mkdir(parents=True)
            (batch / 'board-feed-saved.json').write_text('{}', encoding='utf-8')
            (batch / 'board-feed-saved-preflight.json').write_text('{}', encoding='utf-8')
            (batch / 'summary.json').write_text('{}', encoding='utf-8')
            (batch / 'summary.csv').write_text('x\n', encoding='utf-8')
            source = root / 'results/a/q2-yuanzhifang/feedback-20260924/roundx-spec.json'
            fixed_spec = {'methods': [{'variant': 'frontier_gap'}], 'cases': ['001']}
            source.write_text(json.dumps(fixed_spec), encoding='utf-8')
            receipt = Path(temp) / 'receipt.json'
            calls = []

            def fake(argv, **_):
                calls.append(argv)
                if argv[:2] == ['git', 'show']:
                    return SimpleNamespace(stdout=source.read_bytes())
                return SimpleNamespace(stdout=b'')

            with (patch.object(pub, 'ROOT', root),
                  patch.object(pub, 'SCOPE', batch.parent),
                  patch.object(pub, 'validate', return_value=(
                      fixed_spec, {'spec_sha256': 'fixed'}, '2026-09-25T00:00:00+00:00')),
                  patch.object(pub, 'batch_files_only'),
                  patch.object(pub, 'verify_audit', side_effect=ValueError('audit hash mismatch'))):
                with self.assertRaisesRegex(ValueError, 'audit hash mismatch'):
                    pub.process(batch, 'fixed', receipt, publish=True, command=fake)
            self.assertEqual(json.loads(receipt.read_text())['status'], 'failed')
            self.assertFalse(any(argv[:2] in (['git', 'add'], ['git', 'commit'], ['git', 'push'])
                                 for argv in calls))


if __name__ == '__main__':
    unittest.main()
