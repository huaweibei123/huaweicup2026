"""Three fixed C01 shifted-packet mechanism probes in one bounded Linux window.

005/069/071 K5 saved c665 plans are starting points, not benchmark results.
Upload a SHA-pinned capsule and this runner, then run ``python -B
q2_shifted_packet_pilot.py run``. No build, install, retry, or extra prepare.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path('/content/q2-shifted-packet-capsule')
E2ROOT = ROOT / 'e2-src'
OUT = Path('/content/q2-shifted-packet-output')
RESULT_ZIP = Path('/content/q2-shifted-packet-results.zip')
SCHEMA = 'q2-shifted-cone-three-v1'
LIMITS = {'workers': 1, 'wall_seconds': 120, 'rss_bytes': 536870912,
          'propose': 3, 'native_E2': 27, 'E0': 3, 'E1': 0,
          'separate_prepare': 0, 'retries': 0}
CONFIG_SHA = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
PINNED = {
    'scripts/q2_rcx_fixed_e0_probe.py': 'c002ee5e1a18fb71a77eaa1caae94bedd8fdf2b20c4198afde4ad9f4b405f156',
    'scripts/q2_packet_native_pilot.py': '328d272dc4410c6e17bfa9125f7dfe82688c20c364db6c3e5ced302385a4dfbc',
    'src/q2_nikolastarx/native_trace_diagnostic.py': 'bb2170fdfdb0360140e41c342a592a1f7a1624d7610be7fbdced39d1bb200413',
    'src/q2_nikolastarx/critical_packet_exchange.py': '6f358bf9993fd4afec834d836ae21fc14fd0abaee5bd69ecafdfbd076cb0ebdb',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def load_raw(path):
    data = path.read_bytes()
    if path.suffix != '.gz':
        return data
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read((64 << 20) + 1)
    if len(raw) > 64 << 20:
        raise ValueError('expanded input exceeds 64 MiB')
    return raw


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(manifest, names, helper):
    if (manifest.get('schema') != SCHEMA or manifest.get('limits') != LIMITS or
            any(not isinstance(manifest.get(k), str) or len(manifest[k]) != 40
                for k in ('source_commit', 'runner_commit')) or
            manifest.get('config') != 'data/raw/a/official/data/config.txt'):
        raise ValueError('schema, limits, provenance, or config path mismatch')
    files = manifest['files']
    if 'manifest.json' in files or set(files) | {'manifest.json'} != names:
        raise ValueError('capsule member set mismatch')
    for name, digest in files.items():
        if len(digest) != 64 or sha((ROOT / helper.safe(name)).read_bytes()) != digest:
            raise ValueError('capsule member hash mismatch: ' + name)
    if files.get('scripts/q2_shifted_packet_pilot.py') != sha(Path(__file__).read_bytes()):
        raise ValueError('uploaded runner differs from capsule')
    for name, digest in PINNED.items():
        if files.get(name) != digest:
            raise ValueError('pinned source mismatch: ' + name)
    for name, digest in helper.OFFICIAL.items():
        if files.get('data/raw/a/official/code/' + name) != digest:
            raise ValueError('official source mismatch: ' + name)
    if sha(load_raw(ROOT / manifest['config'])) != CONFIG_SHA:
        raise ValueError('fixed config drift')
    rows = manifest['rows']
    if (type(rows) is not list or [r.get('case') for r in rows] != ['005', '069', '071']
            or any(r.get('cores') != 5 for r in rows)):
        raise ValueError('fixed three-row coordinates mismatch')
    for row in rows:
        case = row['case']
        expected = {'graph': f'inputs/{case}/graph.json', 'plan': f'inputs/{case}/plan.json.gz',
                    'reference_result': f'inputs/{case}/result.json.gz'}
        if ({k: row.get(k) for k in expected} != expected or
                set(row.get('sha256', {})) != set(expected)):
            raise ValueError('fixed row path/hash fields mismatch')
        for key, name in expected.items():
            digest = row['sha256'][key]
            if (name not in files or type(digest) is not str or len(digest) != 64 or
                    sha(load_raw(ROOT / name)) != digest):
                raise ValueError('row raw input hash mismatch: ' + case + '/' + key)
        result = json.loads(load_raw(ROOT / row['reference_result']))
        plan = json.loads(load_raw(ROOT / row['plan']))
        if (result.get('scene') != 'B' or result.get('num_cores') != 5 or
                set(plan) != {'node_to_subgraph', 'core_schedules'} or
                len(plan['core_schedules']) != 5):
            raise ValueError('row old E0 or plan domain mismatch: ' + case)


def original_starts(graph, plan, trace, derive):
    view = derive(graph, plan)
    eligible = {op['id'] for op in graph['ops'] if op['op'] not in ('COPY_IN', 'COPY_OUT')}
    owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    if set(owner) != eligible:
        raise ValueError('eligible plan coverage mismatch')
    starts = {}
    for row in trace['per_core_timeline']:
        core = row['core_id']
        for op in row['ops']:
            u = op['op_id']
            if u in eligible:
                if u in starts or owner[u] != core or type(op['start']) is not int or op['start'] < 0:
                    raise ValueError('native original start owner/domain mismatch')
                starts[u] = op['start']
    if set(starts) != eligible:
        raise ValueError('native trace original start coverage mismatch')
    return starts


def child(manifest_path, deadline):
    manifest = json.loads(Path(manifest_path).read_bytes())
    ledger = {'status': 'running', 'request_in_flight': False,
              'calls': {'propose_started': 0, 'E2_reserved': 0, 'E2_native_returned': 0,
                        'E0_fallback': 0, 'E0_started': 0, 'separate_prepare': 0}, 'rows': []}
    ledger_path = OUT / 'ledger.json'
    save(ledger_path, ledger)
    def reserve(label):
        if ledger['request_in_flight'] or ledger['calls']['E2_reserved'] >= 27 or time.perf_counter() >= deadline:
            raise RuntimeError('uncertain native request, total E2 cap, or deadline')
        ledger['request_in_flight'] = True
        ledger['calls']['E2_reserved'] += 1
        ledger['active_label'] = label
        save(ledger_path, ledger)
    def returned():
        ledger['calls']['E2_native_returned'] += 1
        ledger['request_in_flight'] = False
        ledger.pop('active_label', None)
        save(ledger_path, ledger)
    try:
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before runtime verification')
        pilot = import_file('q2_packet_native_pilot', ROOT / 'scripts/q2_packet_native_pilot.py')
        pilot.ROOT, pilot.E2ROOT, pilot.OUT = ROOT, E2ROOT, OUT
        save(OUT / 'runtime-compatibility.json', pilot.verify_runtime())
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline after runtime verification')
        sys.path.insert(0, str(E2ROOT))
        from research.a.e2_search import SceneBEvaluator, read_config
        import research.a.e2_search.scene_b as scene_b
        import src.eval_exact._official as e2_official
        if any(not Path(m.__file__).resolve().is_relative_to(E2ROOT) for m in (scene_b, e2_official)):
            raise ValueError('E2 imported outside fixed source root')
        sys.path.insert(1, str(ROOT))
        from src.q2_nikolastarx import critical_packet_exchange, native_trace_diagnostic
        from src.q2_nikolastarx.direct import derive_multicore_plan
        if any(not Path(m.__file__).resolve().is_relative_to(ROOT)
               for m in (critical_packet_exchange, native_trace_diagnostic)):
            raise ValueError('solver imported outside fixed source root')
        cfg = pilot.normalize_p2_config(read_config(str(ROOT / manifest['config']), problem=2))
        if set(cfg) != native_trace_diagnostic.REQUIRED_CONFIG:
            raise ValueError('private P2 config domain drift')
        for row in manifest['rows']:
            case = row['case']
            folder = OUT / case
            folder.mkdir()
            graph = json.loads(load_raw(ROOT / row['graph']))
            base = json.loads(load_raw(ROOT / row['plan']))
            old = json.loads(load_raw(ROOT / row['reference_result']))
            old_key = (old['makespan'], old['data_movement_bytes']['added_copy_bytes'])
            state = {'case': case, 'cores': 5, 'old_E0_key': list(old_key),
                     'old_plan_sha256': row['sha256']['plan'], 'candidate_scores': []}
            ledger['rows'].append(state)
            save(ledger_path, ledger)
            reserve(case + ':baseline')
            start = time.perf_counter()
            diag = native_trace_diagnostic.diagnose(scene_b, graph, base, cfg,
                {'case': case, 'graph_sha256': row['sha256']['graph'],
                 'plan_sha256': row['sha256']['plan'],
                 'old_E0_sha256': row['sha256']['reference_result']}, include_trace=True)
            save(folder / 'native-diagnostic.json', diag)
            if (diag.get('counts', {}).get('native_attempted') != 1 or
                    diag.get('counts', {}).get('native_returned') != 1):
                raise ValueError('baseline native request did not return once')
            returned()
            if (diag.get('diagnostic_status') != 'consistent' or
                    diag['counts']['prepare_observed'] != 1 or
                    pilot.key(diag['score']) != old_key or
                    diag['score']['data_movement_bytes'] != old['data_movement_bytes'] or
                    diag['score']['cross_task_traffic'] != old['cross_task_traffic'] or
                    pilot.timeline(diag['trace_result']) != pilot.timeline(old)):
                raise ValueError('online baseline differs from saved official E0: ' + case)
            starts = original_starts(graph, base, diag['trace_result'], derive_multicore_plan)
            state.update(baseline_score=diag['score'], full_timeline_equal=True,
                         baseline_wall_seconds=time.perf_counter()-start,
                         critical_link_count=len(diag['critical_links']))
            save(ledger_path, ledger)
            if ledger['calls']['propose_started'] >= 3 or time.perf_counter() >= deadline:
                raise TimeoutError('proposal cap or deadline')
            ledger['calls']['propose_started'] += 1
            save(ledger_path, ledger)
            proposals, meta = critical_packet_exchange.propose(
                graph, base, cfg, diag['critical_links'], diag['critical_original_ids']['op_ids'],
                incumbent_makespan=old['makespan'], max_seeds=8, merge_policy='shifted', closure_scope='critical_cone',
                original_start_times=starts)
            save(folder / 'proposal-meta.json', meta)
            if len(proposals) > 8:
                raise ValueError('shifted proposal count exceeds eight')
            evaluator = SceneBEvaluator(graph, problem=2, cache_bytes=0, max_cache_entries=1)
            if evaluator.problem != 2:
                raise ValueError('candidate evaluator problem mismatch')
            best, winner, winning_record = old_key, None, None
            seen = set()
            for i, item in enumerate(proposals):
                plan = item['plan']
                if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5:
                    raise ValueError('proposal plan shape mismatch')
                derive_multicore_plan(graph, plan)
                canonical = sha(json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
                if canonical in seen or plan == base:
                    raise ValueError('duplicate or baseline proposal')
                seen.add(canonical)
                path = folder / ('candidate-%02d.json' % i)
                save(path, plan)
                plan_sha = sha(path.read_bytes())
                reserve(case + ':candidate_%02d' % i)
                t = time.perf_counter()
                record = evaluator._native_score(plan, cfg, debug=False)
                score = pilot.key(record)
                if record.get('compilation_cache_hit') is not False:
                    raise ValueError('candidate compilation cache was not disabled')
                returned()
                state['candidate_scores'].append({'ordinal': i, 'plan_sha256': plan_sha,
                    'score': record, 'key': list(score), 'wall_seconds': time.perf_counter()-t,
                    'detail': item['detail']})
                save(ledger_path, ledger)
                if score < best:
                    best, winner, winning_record = score, path, record
            state['best_native_key'] = list(best)
            state['winner_plan_sha256'] = sha(winner.read_bytes()) if winner else None
            save(ledger_path, ledger)
            if winner is None:
                state['status'] = 'no_strict_native_improvement'
            else:
                if ledger['calls']['E0_started'] >= 3 or time.perf_counter() >= deadline:
                    raise TimeoutError('E0 cap or deadline')
                from src.q2_nikolastarx.evaluate_feedback import monitored
                e0 = folder / 'e0'
                e0.mkdir()
                args = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                        str(ROOT / row['graph']), str(winner), '--config', str(ROOT / manifest['config']),
                        '--output', str(e0 / 'result.json'), '--trace-output', str(e0 / 'trace.json'),
                        '--log-output', str(e0 / 'official.log')]
                ledger['calls']['E0_started'] += 1
                state['E0_winner_plan_sha256_before_dispatch'] = sha(winner.read_bytes())
                save(ledger_path, ledger)
                process = monitored(args, e0 / 'process', deadline, 536870912, cleanup_timeout=5.0)
                state['E0_process'] = process
                save(ledger_path, ledger)
                if process['status'] != 'ok' or process.get('surviving_pids'):
                    raise RuntimeError('independent E0 failed or survived cleanup')
                final = json.loads((e0 / 'result.json').read_bytes())
                if (final.get('scene') != 'B' or final.get('num_cores') != 5 or
                        (final['makespan'], final['data_movement_bytes']['added_copy_bytes']) != best or
                        final['data_movement_bytes'] != winning_record['data_movement_bytes'] or
                        final['cross_task_traffic'] != winning_record['cross_task_traffic'] or
                        sha(winner.read_bytes()) != state['winner_plan_sha256']):
                    raise ValueError('independent E0 differs from winning native score')
                state.update(status='confirmed_by_E0', E0_result_sha256=sha((e0 / 'result.json').read_bytes()))
            save(ledger_path, ledger)
        ledger['status'] = 'completed_three_rows'
        save(ledger_path, ledger)
    except BaseException as error:
        ledger.update(status='stopped', error=repr(error))
        save(ledger_path, ledger)
        raise


def run():
    start = time.perf_counter()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    filename, expected = (os.environ[k] for k in
        ('P2_SHIFTED_PACKET_CAPSULE_FILENAME', 'P2_SHIFTED_PACKET_CAPSULE_SHA256'))
    if Path(filename).name != filename or not filename.endswith('.zip') or len(expected) != 64:
        raise ValueError('plain capsule filename and expected SHA required')
    archive = Path('/content') / filename
    if ROOT.exists() or OUT.exists() or RESULT_ZIP.exists():
        raise FileExistsError('single attempt already reserved')
    OUT.mkdir(exist_ok=False)
    receipt = {'status': 'reserved', 'capsule_sha256': expected,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'cloud_git_verified': False,
               'timing_scope': 'remote wall through monitored child completion; ZIP packaging follows'}
    save(OUT / 'attempt.json', receipt)
    try:
        if archive.stat().st_size > 128 << 20:
            raise ValueError('uploaded capsule exceeds 128 MiB')
        if sha(archive.read_bytes()) != expected:
            raise ValueError('uploaded capsule SHA mismatch')
        ROOT.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as z:
            info = z.getinfo('scripts/q2_rcx_fixed_e0_probe.py')
            if info.file_size > 64 << 10:
                raise ValueError('safety helper too large')
            helper_bytes = z.read(info)
        if sha(helper_bytes) != PINNED['scripts/q2_rcx_fixed_e0_probe.py']:
            raise ValueError('safety helper hash mismatch before import')
        helper_path = ROOT / 'scripts/q2_rcx_fixed_e0_probe.py'
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_bytes(helper_bytes)
        helper = import_file('q2_rcx_fixed_e0_probe', helper_path)
        helper.ROOT = ROOT
        helper_path.unlink()
        names = helper.extract(archive)
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        verify(manifest, names, helper)
        receipt.update(manifest_sha256=sha((ROOT / 'manifest.json').read_bytes()),
                       source_commit_provenance=manifest['source_commit'],
                       runner_commit_provenance=manifest['runner_commit'])
        save(OUT / 'receipt.json', receipt)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        deadline = start + 120
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before child dispatch')
        receipt['child_started'] = True
        save(OUT / 'receipt.json', receipt)
        process = monitored([sys.executable, '-B', str(ROOT / 'scripts/q2_shifted_packet_pilot.py'),
                             'child', str(ROOT / 'manifest.json'), str(deadline)],
                            OUT / 'child-process', deadline, 536870912, cleanup_timeout=5.0)
        receipt['child_process'] = process
        if process['status'] != 'ok' or process.get('surviving_pids'):
            raise RuntimeError('three-row child failed or survived cleanup')
        ledger = json.loads((OUT / 'ledger.json').read_bytes())
        if ledger['request_in_flight'] or ledger['status'] != 'completed_three_rows':
            raise ValueError('child did not reach known terminal result')
        receipt.update(status=ledger['status'], calls=ledger['calls'])
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
                          'zip_bytes': RESULT_ZIP.stat().st_size, 'calls': receipt.get('calls')}))


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'run':
        run()
    elif len(sys.argv) == 4 and sys.argv[1] == 'child':
        child(sys.argv[2], float(sys.argv[3]))
    else:
        raise SystemExit('usage: q2_shifted_packet_pilot.py run')
