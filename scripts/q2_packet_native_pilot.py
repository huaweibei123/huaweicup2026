"""Single-window 069/K5 online E2 diagnostic and bounded packet selection.

Upload this runner and a SHA-pinned capsule; run ``python -B
q2_packet_native_pilot.py run`` on Linux x86_64. No install/build/retry.
The capsule includes the unchanged q2_rcx_fixed_e0_probe.py safety helper.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path('/content/q2-packet-native-capsule')
E2ROOT = ROOT / 'e2-src'
OUT = Path('/content/q2-packet-native-output')
RESULT_ZIP = Path('/content/q2-packet-native-results.zip')
SCHEMA = 'q2-packet-native-069-k5-v1'
LIMITS = {'workers': 1, 'wall_seconds': 120, 'rss_bytes': 536870912,
          'propose': 1, 'native_E2': 17, 'E0': 1, 'E1': 0,
          'separate_prepare': 0, 'retries': 0}
INPUT_SHA = {
    'graph': '9632392d98cfc04291ba0546accf1f4c3ede8ff71befd3cd0ae67caf27659e52',
    'config': 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
    'plan': 'ad12cf6ce766358f8b31b994707f7c8fa0e2c7b12d4497c6159ca2a1319ccadf',
    'reference_result': '3dc8f94e3806d5baf13655e477f9df1c9202f438df93a37c530335402b918b51',
    'contract': 'b52dfe8015d468dd402e1cdae38466e5af14e8d44056f80a343d652b42b73914',
}
GZIP_SHA = {
    'plan': '80d570c1ba0dbe14f75fc467dd32ecd5c1cf134d66313cbf7d6817bb56ae8553',
    'reference_result': '5e62bb6d5100745916f49a4bbb81e0a35275f2e8c1b37a42b723fda3c21f4339',
    'contract': '4ccaca8aeccdff6b4d9e37cb684c0c0db74f3ee3fcc6387b01e4064cbbd9a83d',
}
HELPER_SHA = 'c002ee5e1a18fb71a77eaa1caae94bedd8fdf2b20c4198afde4ad9f4b405f156'
BUILD_RECEIPT_SHA = '6be18cdf50290a9fd478a468cd421a10fbd25bd10a94e502170dd14fb6a906ef'
BINARY_SHA = '77ece8929ddcc04e6087dd1c8fc02ee61e79f03b79499182b9f069122092ab3a'
SOURCE_MANIFEST_SHA = '9ee379269c0c4f25b64f9d0aeaf1e397e85e48c2103b08637db356d3c9595387'
PINNED = {'scripts/q2_rcx_fixed_e0_probe.py': HELPER_SHA,
          'scripts/e2_linux_native.py': '60456182ce739ae26f899959a4dea951f17d38a5a386332c3941f2b791983f62',
          'src/q2_nikolastarx/native_trace_diagnostic.py': 'bb2170fdfdb0360140e41c342a592a1f7a1624d7610be7fbdced39d1bb200413',
          'src/q2_nikolastarx/critical_packet_exchange.py': 'eabcff53168538d3d8f9b417d8cdaaf94dd2dacbcae40c56bc7ff0e477fc581c',
          'attestation/e2-linux-build.json': BUILD_RECEIPT_SHA,
          'fixed-p2-manifest.json': SOURCE_MANIFEST_SHA,
          'e2-src/research/a/e2_search/native/libreplay_bc.so': BINARY_SHA}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def read_input(manifest, key):
    path = ROOT / manifest['inputs'][key]
    data = path.read_bytes()
    if path.suffix != '.gz':
        return data
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        expanded = stream.read((64 << 20) + 1)
    if len(expanded) > 64 << 20:
        raise ValueError('input expansion exceeds 64 MiB')
    return expanded


def verify(manifest, names, helper):
    if (manifest.get('schema') != SCHEMA or manifest.get('limits') != LIMITS or
            any(not isinstance(manifest.get(k), str) or len(manifest[k]) != 40
                for k in ('source_commit', 'runner_commit'))):
        raise ValueError('schema, limits, or provenance mismatch')
    files, inputs = manifest['files'], manifest['inputs']
    if (set(files) | {'manifest.json'} != names or set(inputs) != set(INPUT_SHA)
            or any(inputs[k] not in files for k in inputs)):
        raise ValueError('file set or input map mismatch')
    for key, suffix in {'graph': '.json', 'config': '.txt', 'plan': '.json.gz',
                        'reference_result': '.json.gz', 'contract': '.json.gz'}.items():
        if not inputs[key].endswith(suffix):
            raise ValueError('input suffix mismatch: ' + key)
    for name, digest in files.items():
        if len(digest) != 64 or sha((ROOT / helper.safe(name)).read_bytes()) != digest:
            raise ValueError('capsule member mismatch: ' + name)
    if files.get('scripts/q2_packet_native_pilot.py') != sha(Path(__file__).read_bytes()):
        raise ValueError('uploaded runner differs from capsule')
    for name, digest in PINNED.items():
        if files.get(name) != digest:
            raise ValueError('pinned member mismatch: ' + name)
    for name, digest in helper.OFFICIAL.items():
        if files.get('data/raw/a/official/code/' + name) != digest:
            raise ValueError('official source drift: ' + name)
    for key, digest in INPUT_SHA.items():
        if sha(read_input(manifest, key)) != digest:
            raise ValueError('fixed input drift: ' + key)
    for key, digest in GZIP_SHA.items():
        if sha((ROOT / inputs[key]).read_bytes()) != digest:
            raise ValueError('archived gzip bytes drift: ' + key)
    old = json.loads(read_input(manifest, 'reference_result'))
    if old.get('scene') != 'B' or old.get('num_cores') != 5 or old.get('makespan') != 11962:
        raise ValueError('old E0 coordinate or score mismatch')
    return old


def verify_runtime():
    """Native/NumPy checks run only inside the parent's monitored child."""
    from importlib.util import module_from_spec, spec_from_file_location
    source = ROOT / 'scripts/e2_linux_native.py'
    if sha(source.read_bytes()) != PINNED['scripts/e2_linux_native.py']:
        raise ValueError('Linux verifier source mismatch before import')
    spec = spec_from_file_location('e2_linux_native', source)
    e2tool = module_from_spec(spec)
    spec.loader.exec_module(e2tool)
    e2tool.require_linux()
    entries = e2tool.checked_sources(E2ROOT, ROOT / 'fixed-p2-manifest.json')
    actual = {p.relative_to(E2ROOT).as_posix() for p in E2ROOT.rglob('*') if p.is_file()}
    if len(entries) != 50 or actual != set(entries) | {e2tool.LIBRARY.as_posix()}:
        raise ValueError('E2 source exact file set mismatch')
    binary = E2ROOT / e2tool.LIBRARY
    if sha(binary.read_bytes()) != BINARY_SHA:
        raise ValueError('E2 binary differs from external expected SHA')
    receipt = json.loads((ROOT / 'attestation/e2-linux-build.json').read_bytes())
    if (receipt.get('e2_commit') != e2tool.E2_COMMIT or
            receipt.get('source_manifest_sha256') != SOURCE_MANIFEST_SHA or
            receipt.get('source_sha256') != entries or
            receipt.get('binary') != e2tool.checked_binary(binary)):
        raise ValueError('prior Linux build provenance mismatch')
    bindings = e2tool.binding_info(E2ROOT)
    for key in ('input_bytes', 'output_bytes', 'input_offsets', 'output_offsets'):
        if bindings[key] != receipt['bindings'][key]:
            raise ValueError('current Python native layout differs from old build')
    if bindings['input_bytes'] != 160 or bindings['output_bytes'] != 64:
        raise ValueError('native struct size mismatch')
    official_step = ROOT / 'data/raw/a/official/code/schedule_step3.py'
    e2_step = E2ROOT / 'data/raw/a/official/code/schedule_step3.py'
    if sha(official_step.read_bytes()) != sha(e2_step.read_bytes()):
        raise ValueError('official/E2 Step3 source differs')
    return {'build_receipt_sha256': BUILD_RECEIPT_SHA, 'binary_sha256': BINARY_SHA,
            'old_runtime': receipt['runtime'], 'current_runtime': e2tool.machine_info(),
            'old_bindings': receipt['bindings'], 'current_bindings': bindings,
            'e2_source_count': len(entries)}


def timeline(result):
    rows = {}
    for row in result['per_core_timeline']:
        core = row['core_id']
        for op in row['ops']:
            key = (core, op['op_id'])
            if key in rows:
                raise ValueError('duplicate trace key')
            rows[key] = (op['start'], op['end'])
    return rows


def key(record):
    if (not isinstance(record, dict) or record.get('route') != 'native' or
            record.get('status') != 'ok' or type(record.get('makespan')) is not int or
            record['makespan'] < 0):
        raise ValueError('non-native or invalid P2 score')
    movement = record.get('data_movement_bytes')
    added = movement.get('added_copy_bytes') if isinstance(movement, dict) else None
    if type(added) is not int or added < 0:
        raise ValueError('invalid native added DDR')
    return (record['makespan'], added)


def normalize_p2_config(public_config):
    """Match frozen SceneBEvaluator.evaluate_record's max_iter default."""
    required_public = {'bandwidth', 'capacity', 'cross_core_copy_delay'}
    if type(public_config) is not dict or set(public_config) != required_public:
        raise ValueError('frozen P2 public config keys drifted')
    return {**public_config, 'max_iter': 1_000_000}


def child(manifest_path, deadline):
    manifest = json.loads(Path(manifest_path).read_bytes())
    ledger = {'status': 'running', 'request_in_flight': False,
              'calls': {'propose_started': 0, 'E2_reserved': 0, 'E2_native_returned': 0,
                        'E0_fallback': 0, 'E0_started': 0, 'separate_prepare': 0},
              'scores': []}
    ledger_path = OUT / 'ledger.json'
    save(ledger_path, ledger)
    def reserve(label):
        if ledger['request_in_flight'] or ledger['calls']['E2_reserved'] >= 17 or time.perf_counter() >= deadline:
            raise RuntimeError('uncertain request, E2 cap, or deadline')
        ledger['request_in_flight'] = True
        ledger['calls']['E2_reserved'] += 1
        ledger['active_label'] = label
        save(ledger_path, ledger)
    try:
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before Linux runtime check')
        runtime = verify_runtime()
        save(OUT / 'runtime-compatibility.json', runtime)
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline after Linux runtime check')
        # E2 first, then extend the src namespace with this repo's guarded modules.
        sys.path.insert(0, str(E2ROOT))
        from research.a.e2_search import SceneBEvaluator, read_config
        import research.a.e2_search.scene_b as scene_b
        import src.eval_exact._official as e2_official
        if any(not Path(m.__file__).resolve().is_relative_to(E2ROOT)
               for m in (scene_b, e2_official)):
            raise ValueError('E2 import escaped fixed root')
        sys.path.insert(1, str(ROOT))
        from src.q2_nikolastarx import critical_packet_exchange, native_trace_diagnostic
        from src.q2_nikolastarx.prepared_trace_contract import audit
        from src.q2_nikolastarx.direct import derive_multicore_plan
        if any(not Path(m.__file__).resolve().is_relative_to(ROOT)
               for m in (critical_packet_exchange, native_trace_diagnostic)):
            raise ValueError('solver import escaped fixed root')
        graph = json.loads(read_input(manifest, 'graph'))
        base = json.loads(read_input(manifest, 'plan'))
        old = json.loads(read_input(manifest, 'reference_result'))
        contract = json.loads(read_input(manifest, 'contract'))
        cfg = normalize_p2_config(read_config(str(ROOT / manifest['inputs']['config']), problem=2))
        if set(cfg) != native_trace_diagnostic.REQUIRED_CONFIG:
            raise ValueError('E2 config domain drift')
        saved = audit(contract, old)
        if not saved['consistent']:
            raise ValueError('saved contract and old E0 trace inconsistent')
        save(OUT / 'saved-audit.json', saved)
        view = derive_multicore_plan(graph, base)
        eligible = {op['id']: op for op in graph['ops'] if op['op'] not in ('COPY_IN', 'COPY_OUT')}
        owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        seen_original = set()
        for op in contract['operations']:
            u = op['id']
            if u in eligible:
                if (u in seen_original or op['core'] != owner[u] or
                        op['kind'] != eligible[u]['op'] or op['pipe'] != eligible[u]['pipe']):
                    raise ValueError('saved contract original operation identity/owner mismatch')
                seen_original.add(u)
        if seen_original != set(eligible):
            raise ValueError('saved contract omits old eligible operation')
        reserve('baseline_diagnostic')
        started = time.perf_counter()
        diag = native_trace_diagnostic.diagnose(scene_b, graph, base, cfg,
            {'graph_sha256': INPUT_SHA['graph'], 'plan_sha256': INPUT_SHA['plan'],
             'old_e0_sha256': INPUT_SHA['reference_result']}, include_trace=True)
        save(OUT / 'native-diagnostic.json', diag)
        if diag.get('counts', {}).get('native_attempted') != 1 or diag.get('counts', {}).get('native_returned') != 1:
            raise ValueError('baseline native attempt/return count mismatch')
        ledger['calls']['E2_native_returned'] += 1
        ledger['request_in_flight'] = False
        ledger.pop('active_label', None)
        save(ledger_path, ledger)
        if diag.get('diagnostic_status') != 'consistent' or diag['counts']['prepare_observed'] != 1:
            raise ValueError('online native diagnosis unavailable')
        native_base = diag['score']
        old_key = (old['makespan'], old['data_movement_bytes']['added_copy_bytes'])
        if (key(native_base) != old_key or
                native_base['data_movement_bytes'] != old['data_movement_bytes'] or
                native_base['cross_task_traffic'] != old['cross_task_traffic'] or
                timeline(diag['trace_result']) != timeline(old)):
            raise ValueError('native baseline score or full start/end differs from old E0')
        saved_ids = []
        for core, u in saved['critical_operations']:
            if u in eligible:
                if owner[u] != core:
                    raise ValueError('saved critical original owner mismatch')
                saved_ids.append(u)
        saved_ids.sort()
        original_tensors = {t['id'] for t in graph['tensors']}
        saved_tensors = sorted({l['tensor_id'] for l in saved['critical_cross_links']
                                if l['tensor_id'] in original_tensors})
        if (diag['critical_original_ids']['op_ids'] != saved_ids or
                diag['critical_original_ids']['tensor_ids'] != saved_tensors or
                diag['critical_links'] != saved['critical_cross_links']):
            raise ValueError('online critical operation/link evidence differs from saved audit')
        ledger['baseline'] = {'score': native_base, 'old_E0_key': old_key,
                              'diagnostic_wall_seconds': time.perf_counter()-started,
                              'complete_timeline_equal': True, 'critical_evidence_equal': True}
        save(ledger_path, ledger)
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before proposal')
        ledger['calls']['propose_started'] = 1
        save(ledger_path, ledger)
        proposals, meta = critical_packet_exchange.propose(
            graph, base, cfg, diag['critical_links'], diag['critical_original_ids']['op_ids'],
            incumbent_makespan=old['makespan'])
        save(OUT / 'proposal-meta.json', meta)
        if len(proposals) > 16:
            raise ValueError('proposal count exceeds fixed cap')
        evaluator = SceneBEvaluator(graph, problem=2, cache_bytes=0, max_cache_entries=1)
        if evaluator.problem != 2:
            raise ValueError('candidate evaluator problem drift')
        seen = set()
        best = old_key
        winner = None
        for i, row in enumerate(proposals):
            plan = row['plan']
            if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5:
                raise ValueError('proposal plan shape invalid')
            derive_multicore_plan(graph, plan)
            canonical = sha(json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
            if canonical in seen or plan == base:
                raise ValueError('duplicate or baseline proposal')
            seen.add(canonical)
            path = OUT / ('candidate-%02d.json' % i)
            save(path, plan)
            plan_sha = sha(path.read_bytes())
            reserve('candidate_%02d' % i)
            t = time.perf_counter()
            record = evaluator._native_score(plan, cfg, debug=False)
            score = key(record)
            if record.get('compilation_cache_hit') is not False:
                raise ValueError('candidate compilation cache was not disabled')
            ledger['calls']['E2_native_returned'] += 1
            ledger['request_in_flight'] = False
            ledger.pop('active_label', None)
            item = {'ordinal': i, 'plan_sha256': plan_sha, 'canonical_plan_sha256': canonical,
                    'score': record, 'key': list(score), 'wall_seconds': time.perf_counter()-t,
                    'detail': row['detail']}
            ledger['scores'].append(item)
            save(ledger_path, ledger)
            if score < best:
                best, winner = score, path
        ledger['best_key'] = list(best)
        ledger['winner_plan_sha256'] = sha(winner.read_bytes()) if winner else None
        save(ledger_path, ledger)
        if winner is None:
            ledger['status'] = 'no_strict_native_improvement'
        else:
            if time.perf_counter() >= deadline:
                raise TimeoutError('deadline before independent E0')
            from src.q2_nikolastarx.evaluate_feedback import monitored
            e0 = OUT / 'e0'
            e0.mkdir()
            argv = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                    str(ROOT / manifest['inputs']['graph']), str(winner), '--config',
                    str(ROOT / manifest['inputs']['config']), '--output', str(e0 / 'result.json'),
                    '--trace-output', str(e0 / 'trace.json'), '--log-output', str(e0 / 'official.log')]
            ledger['calls']['E0_started'] = 1
            ledger['E0_winner_plan_sha256_before_dispatch'] = sha(winner.read_bytes())
            save(ledger_path, ledger)
            proc = monitored(argv, e0 / 'process', deadline, 536870912, cleanup_timeout=5.0)
            ledger['E0_process'] = proc
            save(ledger_path, ledger)
            if proc['status'] != 'ok' or proc.get('surviving_pids'):
                raise RuntimeError('independent E0 failed or survived cleanup')
            final = json.loads((e0 / 'result.json').read_bytes())
            winning_record = next(item['score'] for item in ledger['scores']
                                  if item['plan_sha256'] == ledger['winner_plan_sha256'])
            if (final.get('scene') != 'B' or final.get('num_cores') != 5 or
                    (final['makespan'], final['data_movement_bytes']['added_copy_bytes']) != best or
                    final['data_movement_bytes'] != winning_record['data_movement_bytes'] or
                    final['cross_task_traffic'] != winning_record['cross_task_traffic'] or
                    sha(winner.read_bytes()) != ledger['winner_plan_sha256']):
                raise ValueError('best native score differs from independent E0')
            ledger['status'] = 'confirmed_by_E0'
            ledger['E0_result_sha256'] = sha((e0 / 'result.json').read_bytes())
        save(ledger_path, ledger)
    except BaseException as error:
        ledger.update(status='stopped', error=repr(error))
        save(ledger_path, ledger)
        raise


def run():
    start = time.perf_counter()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    filename = os.environ['P2_PACKET_NATIVE_CAPSULE_FILENAME']
    expected = os.environ['P2_PACKET_NATIVE_CAPSULE_SHA256']
    if Path(filename).name != filename or not filename.endswith('.zip') or len(expected) != 64:
        raise ValueError('plain uploaded capsule ZIP filename and SHA required')
    archive = Path('/content') / filename
    if ROOT.exists() or OUT.exists() or RESULT_ZIP.exists():
        raise FileExistsError('attempt already reserved')
    OUT.mkdir(exist_ok=False)
    receipt = {'status': 'reserved', 'capsule_sha256': expected,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'cloud_git_verified': False,
               'timing_scope': 'remote wall through child completion; packaging follows'}
    save(OUT / 'attempt.json', receipt)
    try:
        if sha(archive.read_bytes()) != expected:
            raise ValueError('uploaded capsule bytes differ from expected SHA')
        ROOT.mkdir(exist_ok=False)
        from importlib.util import module_from_spec, spec_from_file_location
        with zipfile.ZipFile(archive) as z:
            info = z.getinfo('scripts/q2_rcx_fixed_e0_probe.py')
            if info.file_size > 64 << 10:
                raise ValueError('helper too large')
            helper_bytes = z.read(info)
        if sha(helper_bytes) != HELPER_SHA:
            raise ValueError('helper source mismatch before import')
        helper_path = ROOT / 'scripts/q2_rcx_fixed_e0_probe.py'
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_bytes(helper_bytes)
        spec = spec_from_file_location('q2_rcx_fixed_e0_probe', helper_path)
        helper = module_from_spec(spec)
        spec.loader.exec_module(helper)
        helper.ROOT = ROOT
        helper_path.unlink()
        names = helper.extract(archive)
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        old = verify(manifest, names, helper)
        receipt.update(manifest_sha256=sha((ROOT / 'manifest.json').read_bytes()),
                       source_commit_provenance=manifest['source_commit'],
                       runner_commit_provenance=manifest['runner_commit'],
                       old_makespan=old['makespan'], old_added_ddr=old['data_movement_bytes']['added_copy_bytes'])
        save(OUT / 'receipt.json', receipt)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        deadline = start + 120
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before child')
        receipt['child_started'] = True
        save(OUT / 'receipt.json', receipt)
        proc = monitored([sys.executable, '-B', str(ROOT / 'scripts/q2_packet_native_pilot.py'),
                          'child', str(ROOT / 'manifest.json'), str(deadline)],
                         OUT / 'child-process', deadline, 536870912, cleanup_timeout=5.0)
        receipt['child_process'] = proc
        if proc['status'] != 'ok' or proc.get('surviving_pids'):
            raise RuntimeError('native pilot failed, timed out, or survived cleanup')
        ledger = json.loads((OUT / 'ledger.json').read_bytes())
        if ledger['request_in_flight'] or ledger['status'] not in ('confirmed_by_E0', 'no_strict_native_improvement'):
            raise ValueError('child did not reach a known terminal result')
        receipt['status'] = ledger['status']
        receipt['calls'] = ledger['calls']
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['wall_seconds_before_packaging'] = time.perf_counter() - start
        save(OUT / 'receipt.json', receipt)
        try:
            with zipfile.ZipFile(RESULT_ZIP, 'x', compression=zipfile.ZIP_DEFLATED) as z:
                for path in sorted(OUT.rglob('*')):
                    if path.is_file():
                        z.write(path, 'output/' + path.relative_to(OUT).as_posix())
        except BaseException as error:
            receipt['zip_error'] = repr(error)
            save(OUT / 'receipt.json', receipt)
            raise
        print(json.dumps({'status': receipt['status'], 'zip_sha256': sha(RESULT_ZIP.read_bytes()),
                          'zip_bytes': RESULT_ZIP.stat().st_size,
                          'calls': receipt.get('calls')}))


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'run':
        run()
    elif len(sys.argv) == 4 and sys.argv[1] == 'child':
        child(sys.argv[2], float(sys.argv[3]))
    else:
        raise SystemExit('usage: q2_packet_native_pilot.py run')
