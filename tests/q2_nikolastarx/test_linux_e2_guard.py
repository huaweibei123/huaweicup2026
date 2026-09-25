"""Synthetic Linux E2 capsule and receipt checks; never load or score native code."""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_guarded as guard
from src.q2_nikolastarx import adaptive_semantic
from tests.q2_nikolastarx.test_component_envelope import config, jobs


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class LinuxE2GuardTests(unittest.TestCase):
    def fixture(self, tmp):
        root = tmp / 'capsule'
        root.mkdir()
        sources = {}
        for i in range(50):
            name = f'research/a/e2_search/file_{i:02d}.py'
            raw = f'file {i}\n'.encode()
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            sources[name] = digest(raw)
        binary_name = 'research/a/e2_search/native/libreplay_bc.so'
        binary = root / binary_name
        binary.parent.mkdir(parents=True, exist_ok=True)
        raw_binary = bytearray(64)
        raw_binary[:6] = b'\x7fELF\x02\x01'
        raw_binary[18:20] = (62).to_bytes(2, 'little')
        binary.write_bytes(raw_binary)
        binary_sha = digest(raw_binary)
        manifest = tmp / 'manifest.json'
        manifest_raw = json.dumps({'e2_commit': guard.E2_COMMIT,
                                   'e2_sources': sources,
                                   'binary': {'path': binary_name}}).encode()
        manifest.write_bytes(manifest_raw)
        bindings = {'numpy': 'synthetic', 'input_bytes': 160, 'output_bytes': 64,
                    'input_offsets': {}, 'output_offsets': {}}
        runtime = {'platform': 'synthetic-linux', 'machine': 'x86_64',
                   'libc': ['glibc', '2.40'], 'python': sys.version,
                   'python_abi': sysconfig.get_config_var('SOABI'),
                   'pointer_bytes': ctypes.sizeof(ctypes.c_void_p),
                   'byteorder': sys.byteorder}
        receipt = {'schema': 'e2-linux-native-v1', 'e2_commit': guard.E2_COMMIT,
                   'source_manifest_sha256': digest(manifest_raw),
                   'source_sha256': sources,
                   'binary': {'path': binary_name, 'sha256': binary_sha,
                              'bytes': len(raw_binary),
                              'format': 'ELF64 little-endian x86_64',
                              'replay_bc_abi': 1},
                   'runtime': runtime, 'bindings': bindings}
        receipt_path = tmp / 'receipt.json'
        receipt_path.write_text(json.dumps(receipt))
        return root, manifest, binary, receipt_path, bindings

    def check(self, root, manifest, receipt, bindings, *, expected_receipt=None,
              expected_binary=None):
        with patch.object(guard, 'MANIFEST', manifest), \
             patch.object(guard, 'E2_SOURCE_MANIFEST_SHA256', digest(manifest.read_bytes())), \
             patch.object(guard.platform, 'system', return_value='Linux'), \
             patch.object(guard.platform, 'machine', return_value='x86_64'), \
             patch.object(guard.platform, 'platform', return_value='synthetic-linux'), \
             patch.object(guard.platform, 'libc_ver', return_value=('glibc', '2.40')), \
             patch.object(guard, '_linux_binding_info', return_value=bindings), \
             patch.object(guard.ctypes, 'CDLL', side_effect=AssertionError('must not load native library')):
            return guard.check_e2_source(
                root, linux_build_receipt=receipt,
                linux_build_receipt_sha256=expected_receipt or digest(receipt.read_bytes()),
                linux_binary_sha256=expected_binary or digest(
                    (root / 'research/a/e2_search/native/libreplay_bc.so').read_bytes()))

    def test_valid_fixed_receipt_and_no_cdll(self):
        with tempfile.TemporaryDirectory() as folder:
            root, manifest, _, receipt, bindings = self.fixture(Path(folder))
            result = self.check(root, manifest, receipt, bindings)
            self.assertEqual(result['platform'], 'Linux x86_64')
            self.assertEqual(result['linux_build_receipt_sha256'], digest(receipt.read_bytes()))
            self.assertEqual(result['manifest_sha256'], digest(manifest.read_bytes()))

    def test_external_sha_source_set_binary_header_and_runtime_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root, manifest, binary, receipt, bindings = self.fixture(Path(folder))
            with self.assertRaisesRegex(ValueError, 'receipt differs'):
                self.check(root, manifest, receipt, bindings, expected_receipt='0' * 64)
            with self.assertRaisesRegex(ValueError, 'binary SHA'):
                self.check(root, manifest, receipt, bindings, expected_binary='0' * 64)
            extra = root / 'unexpected.py'
            extra.write_text('x')
            with self.assertRaisesRegex(ValueError, 'unexpected or missing'):
                self.check(root, manifest, receipt, bindings)
            extra.unlink()
            source = root / 'research/a/e2_search/file_00.py'
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source drift'):
                self.check(root, manifest, receipt, bindings)
            source.write_text('file 0\n')
            original_binary = binary.read_bytes()
            wrong_machine = bytearray(original_binary)
            wrong_machine[18:20] = (183).to_bytes(2, 'little')
            binary.write_bytes(wrong_machine)
            with self.assertRaisesRegex(ValueError, 'ELF64'):
                self.check(root, manifest, receipt, bindings,
                           expected_binary=digest(wrong_machine))
            binary.write_bytes(original_binary)
            bad_bindings = dict(bindings, input_bytes=152)
            with self.assertRaisesRegex(ValueError, 'binding ABI'):
                self.check(root, manifest, receipt, bad_bindings)
            original_receipt = receipt.read_bytes()
            altered = json.loads(original_receipt)
            altered['runtime']['python_abi'] = 'different-abi'
            receipt.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'runtime mismatch'):
                self.check(root, manifest, receipt, bindings)
            receipt.write_bytes(original_receipt)

    def test_all_linux_options_required_and_mac_default_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root, manifest, _, receipt, bindings = self.fixture(Path(folder))
            with patch.object(guard, 'MANIFEST', manifest):
                with self.assertRaisesRegex(ValueError, 'supplied together'):
                    guard.check_e2_source(root, linux_build_receipt=receipt)
            with patch.object(guard, 'MANIFEST', manifest), \
                 patch.object(guard.platform, 'system', return_value='Linux'), \
                 patch.object(guard.platform, 'machine', return_value='x86_64'):
                with self.assertRaisesRegex(ValueError, 'macOS arm64 only'):
                    guard.check_e2_source(root)
            self.assertEqual(bindings['output_bytes'], 64)

    def test_main_rejects_unknown_before_writing_plan_but_allows_unscored_route(self):
        graph = jobs(6)
        plan, _ = adaptive_semantic.build(graph, 2, config())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph_path = root / 'graph.json'
            graph_path.write_text(json.dumps(graph))
            for label, evidence in [('unknown', 'unknown'), ('not_requested', 'not_requested')]:
                out = root / f'{label}.json'
                ledger_dir = root / f'{label}-evidence'
                def constructor(_, __, ___, oracle):
                    return plan, {'score_evidence': evidence}
                with patch.object(guard, 'native_e2', side_effect=AssertionError('no E2 expected')):
                    if evidence == 'unknown':
                        with self.assertRaises(SystemExit):
                            guard.main([str(graph_path), '--cores', '2', '--e2-root',
                                        str(root / 'absent'), '--output', str(out),
                                        '--evidence', str(ledger_dir)], constructor=constructor)
                    else:
                        guard.main([str(graph_path), '--cores', '2', '--e2-root',
                                    str(root / 'absent'), '--output', str(out),
                                    '--evidence', str(ledger_dir)], constructor=constructor)
                ledger = json.loads((ledger_dir / 'solver.json').read_text())
                self.assertEqual(ledger['calls']['E2_api_attempted'], 0)
                self.assertEqual(out.exists(), evidence != 'unknown')
                self.assertEqual(ledger['status'], 'failed' if evidence == 'unknown' else 'ok')
                if evidence == 'unknown':
                    self.assertEqual(ledger['detail']['score_evidence'], 'unknown')
            in_flight = root / 'in-flight.json'
            def fake_adapter(_, ledger, __, **___):
                def mark(_):
                    ledger['request_in_flight'] = True
                return mark
            def constructor(_, __, ___, oracle):
                oracle(plan)
                return plan, {'score_evidence': 'not_requested'}
            with patch.object(guard, 'score_adapter', side_effect=fake_adapter):
                with self.assertRaises(SystemExit):
                    guard.main([str(graph_path), '--cores', '2', '--e2-root',
                                str(root / 'absent'), '--output', str(in_flight),
                                '--evidence', str(root / 'in-flight-evidence')],
                               constructor=constructor)
            self.assertFalse(in_flight.exists())
            in_flight_ledger = json.loads((root / 'in-flight-evidence/solver.json').read_text())
            self.assertTrue(in_flight_ledger['request_in_flight'])
            self.assertEqual(in_flight_ledger['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
