"""One 069/K5 saved-contract audit, packet construction, and optional official E0.

Upload this runner separately from a SHA-pinned capsule, then run ``python -B
q2_critical_packet_colab_probe.py run``. No pickle or separate preparation
before E0 occurs; official E0 includes its own preparation.
The capsule must include the unchanged q2_rcx_fixed_e0_probe.py helper.
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

ROOT = Path('/content/q2-critical-packet-capsule')
OUT = Path('/content/q2-critical-packet-output')
RESULT_ZIP = Path('/content/q2-critical-packet-results.zip')
SCHEMA = 'q2-critical-packet-069-k5-v1'
LIMITS = {'workers': 1, 'wall_seconds': 120, 'rss_bytes': 536870912,
          'constructor': 1, 'E0': 1, 'E1': 0, 'E2': 0, 'scene_b_prepare': 0,
          'retries': 0}
INPUT_SHA = {
    'graph': '9632392d98cfc04291ba0546accf1f4c3ede8ff71befd3cd0ae67caf27659e52',
    'config': 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
    'plan': 'ad12cf6ce766358f8b31b994707f7c8fa0e2c7b12d4497c6159ca2a1319ccadf',
    'reference_result': '3dc8f94e3806d5baf13655e477f9df1c9202f438df93a37c530335402b918b51',
    'contract': 'b52dfe8015d468dd402e1cdae38466e5af14e8d44056f80a343d652b42b73914',
}
PINNED = {
    'scripts/q2_rcx_fixed_e0_probe.py': 'c002ee5e1a18fb71a77eaa1caae94bedd8fdf2b20c4198afde4ad9f4b405f156',
    'src/q2_nikolastarx/critical_packet_exchange.py': 'd7915ea2152f3c30af93dc055e3cc4fb36099bdff5701237d871b03f4b6bb241',
    'src/q2_nikolastarx/prepared_trace_contract.py': '6377b90c4dc22b70b47ee0b0ade32c8de925026576e367e7bc09f8cf31a5f36d',
    'src/q2_nikolastarx/evaluate_feedback.py': '9b9dbbf1b43423cafb1492285af3d9e7ec55d7201539a65c56c12f5f0edc4849',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def raw_input(manifest, key):
    path = ROOT / manifest['inputs'][key]
    data = path.read_bytes()
    if path.suffix != '.gz':
        return data
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read((64 << 20) + 1)
    if len(raw) > 64 << 20:
        raise ValueError('expanded input exceeds 64 MiB')
    return raw


def verify(manifest, names, base):
    if (manifest.get('schema') != SCHEMA or manifest.get('limits') != LIMITS or
            any(not isinstance(manifest.get(k), str) or len(manifest[k]) != 40
                for k in ('source_commit', 'runner_commit'))):
        raise ValueError('schema, limits, or provenance mismatch')
    files, inputs = manifest['files'], manifest['inputs']
    if (set(files) | {'manifest.json'} != names or set(inputs) != set(INPUT_SHA)
            or any(inputs[k] not in files for k in INPUT_SHA)):
        raise ValueError('capsule file set or input map mismatch')
    if (not inputs['graph'].endswith('.json') or not inputs['config'].endswith('.txt')
            or not inputs['plan'].endswith('.json.gz')
            or not inputs['reference_result'].endswith('.json.gz')
            or not inputs['contract'].endswith('.json.gz')):
        raise ValueError('input type mismatch')
    for name, expected in files.items():
        if len(expected) != 64 or sha((ROOT / base.safe(name)).read_bytes()) != expected:
            raise ValueError('capsule member hash mismatch: ' + name)
    runner = 'scripts/q2_critical_packet_colab_probe.py'
    if files.get(runner) != sha(Path(__file__).read_bytes()):
        raise ValueError('uploaded runner differs from capsule')
    for name, expected in {**{'data/raw/a/official/code/' + n: v
                               for n, v in base.OFFICIAL.items()}, **PINNED}.items():
        if files.get(name) != expected:
            raise ValueError('fixed source mismatch: ' + name)
    for key, expected in INPUT_SHA.items():
        if sha(raw_input(manifest, key)) != expected:
            raise ValueError('fixed input identity mismatch: ' + key)
    for key, expected in {'plan': '80d570c1ba0dbe14f75fc467dd32ecd5c1cf134d66313cbf7d6817bb56ae8553',
                          'reference_result': '5e62bb6d5100745916f49a4bbb81e0a35275f2e8c1b37a42b723fda3c21f4339',
                          'contract': '4ccaca8aeccdff6b4d9e37cb684c0c0db74f3ee3fcc6387b01e4064cbbd9a83d'}.items():
        if sha((ROOT / inputs[key]).read_bytes()) != expected:
            raise ValueError('saved gzip member drift: ' + key)
    old = json.loads(raw_input(manifest, 'reference_result'))
    if old.get('scene') != 'B' or old.get('num_cores') != 5 or old.get('makespan') != 11962:
        raise ValueError('wrong old result coordinate or score')
    return old


def child(manifest_path):
    """Supervised process: retrospective audit then exactly one static construct."""
    manifest = json.loads(Path(manifest_path).read_bytes())
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.direct import derive_multicore_plan
    from src.q2_nikolastarx.prepared_trace_contract import audit
    from src.q2_nikolastarx.critical_packet_exchange import construct

    graph = json.loads(raw_input(manifest, 'graph'))
    plan = json.loads(raw_input(manifest, 'plan'))
    old = json.loads(raw_input(manifest, 'reference_result'))
    contract = json.loads(raw_input(manifest, 'contract'))
    if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5:
        raise ValueError('old plan shape mismatch')
    finding = audit(contract, old)
    save(OUT / 'audit.json', finding)
    if not finding['consistent']:
        raise ValueError('saved contract and old trace are inconsistent')
    view = derive_multicore_plan(graph, plan)
    eligible = {op['id']: op['op'] for op in graph['ops']
                if op['op'] not in ('COPY_IN', 'COPY_OUT')}
    if len(eligible) != sum(op['op'] not in ('COPY_IN', 'COPY_OUT') for op in graph['ops']):
        raise ValueError('duplicate eligible original ID')
    owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    if set(owner) != set(eligible):
        raise ValueError('old plan eligible coverage mismatch')
    seen = set()
    for op in contract['operations']:
        u = op['id']
        if u in eligible:
            if u in seen or op['core'] != owner[u] or op['kind'] != eligible[u]:
                raise ValueError('contract original operation identity/owner mismatch')
            seen.add(u)
    if seen != set(eligible):
        raise ValueError('contract omitted original eligible IDs')
    critical = []
    for pair in finding['critical_operations']:
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(type(x) is not int for x in pair)):
            raise ValueError('invalid critical operation coordinate')
        core, u = pair
        if u in eligible:
            if owner[u] != core:
                raise ValueError('critical original owner mismatch')
            critical.append(u)
    if len(critical) != len(set(critical)):
        raise ValueError('duplicate critical original ID')
    save(OUT / 'critical-input.json', {'original_ids': critical,
                                      'original_coverage': len(seen),
                                      'critical_links': finding['critical_cross_links']})
    config_path = str(ROOT / manifest['inputs']['config'])
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    candidate, meta = construct(graph, plan, config, finding['critical_cross_links'], critical,
                                incumbent_makespan=old['makespan'])
    save(OUT / 'candidate-meta.json', meta)
    state = {'constructor_calls': 1, 'candidate': False, 'old_plan_sha256': INPUT_SHA['plan']}
    if candidate is not None:
        if set(candidate) != {'node_to_subgraph', 'core_schedules'} or len(candidate['core_schedules']) != 5:
            raise ValueError('constructor candidate has wrong plan shape')
        derive_multicore_plan(graph, candidate)
        if candidate != plan:
            candidate_path = OUT / 'candidate-plan.json'
            save(candidate_path, candidate)
            state.update(candidate=True, candidate_plan_sha256=sha(candidate_path.read_bytes()))
    save(OUT / 'constructor-result.json', state)


def run():
    start = time.perf_counter()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    filename = os.environ['P2_PACKET_CAPSULE_FILENAME']
    expected = os.environ['P2_PACKET_CAPSULE_SHA256']
    if Path(filename).name != filename or not filename.endswith('.zip') or len(expected) != 64:
        raise ValueError('plain capsule ZIP filename and SHA-256 required')
    archive = Path('/content') / filename
    if ROOT.exists() or OUT.exists() or RESULT_ZIP.exists():
        raise FileExistsError('single attempt already reserved')
    OUT.mkdir(exist_ok=False)
    receipt = {'status': 'reserved', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'capsule_sha256': expected, 'cloud_git_verified': False,
               'calls': {'audit_constructor_process_started': 0, 'E0_started': 0, 'E1': 0, 'E2': 0,
                         'scene_b_prepare': 0},
               'timing_scope': 'remote wall through scoring includes capsule verification, audit, construction, and optional E0; packaging follows'}
    save(OUT / 'attempt.json', receipt)
    try:
        if sha(archive.read_bytes()) != expected:
            raise ValueError('uploaded capsule SHA-256 mismatch')
        ROOT.mkdir(exist_ok=False)
        # Reuse the unchanged prior runner's extraction and official-source checks.
        from importlib.util import module_from_spec, spec_from_file_location
        with zipfile.ZipFile(archive) as z:
            helper_info = z.getinfo('scripts/q2_rcx_fixed_e0_probe.py')
            if helper_info.file_size > 64 << 10:
                raise ValueError('helper source exceeds fixed size bound')
            helper_bytes = z.read('scripts/q2_rcx_fixed_e0_probe.py')
        if sha(helper_bytes) != PINNED['scripts/q2_rcx_fixed_e0_probe.py']:
            raise ValueError('pre-import helper source mismatch')
        helper_path = ROOT / 'scripts/q2_rcx_fixed_e0_probe.py'
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_bytes(helper_bytes)
        spec = spec_from_file_location('q2_rcx_fixed_e0_probe', helper_path)
        base = module_from_spec(spec)
        spec.loader.exec_module(base)
        base.ROOT = ROOT
        # Remove provisional helper so extract's exclusive creation still checks every member.
        helper_path.unlink()
        names = base.extract(archive)
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        old = verify(manifest, names, base)
        receipt.update(manifest_sha256=sha((ROOT / 'manifest.json').read_bytes()),
                       source_commit_provenance=manifest['source_commit'],
                       runner_commit_provenance=manifest['runner_commit'],
                       old_makespan=old['makespan'])
        save(OUT / 'receipt.json', receipt)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        deadline = start + 120
        if time.perf_counter() >= deadline:
            raise TimeoutError('deadline before construction')
        receipt['calls']['audit_constructor_process_started'] = 1
        save(OUT / 'receipt.json', receipt)
        proc = monitored([sys.executable, '-B', str(ROOT / 'scripts/q2_critical_packet_colab_probe.py'),
                          'child', str(ROOT / 'manifest.json')], OUT / 'construct-process',
                         deadline, 536870912, cleanup_timeout=5.0)
        receipt['construct_process'] = proc
        if proc['status'] != 'ok' or proc.get('surviving_pids'):
            raise RuntimeError('audit/constructor failed, timed out, or survived cleanup')
        state = json.loads((OUT / 'constructor-result.json').read_bytes())
        if state.get('constructor_calls') != 1:
            raise ValueError('constructor count mismatch')
        receipt['constructor_result'] = state
        if not state['candidate']:
            receipt['status'] = 'no_candidate'
        else:
            candidate_path = OUT / 'candidate-plan.json'
            candidate_sha = sha(candidate_path.read_bytes())
            if candidate_sha != state['candidate_plan_sha256']:
                raise ValueError('candidate changed after construction')
            receipt['candidate_plan_sha256'] = candidate_sha
            save(OUT / 'receipt.json', receipt)
            if time.perf_counter() >= deadline:
                raise TimeoutError('deadline before E0')
            e0 = OUT / 'e0'
            e0.mkdir()
            args = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                    str(ROOT / manifest['inputs']['graph']), str(candidate_path), '--config',
                    str(ROOT / manifest['inputs']['config']), '--output', str(e0 / 'result.json'),
                    '--trace-output', str(e0 / 'trace.json'), '--log-output', str(e0 / 'official.log')]
            receipt['calls']['E0_started'] = 1
            receipt['e0_dispatch_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            save(OUT / 'receipt.json', receipt)
            proc = monitored(args, e0 / 'process', deadline, 536870912, cleanup_timeout=5.0)
            receipt['e0_process'] = proc
            if proc['status'] != 'ok' or proc.get('surviving_pids'):
                raise RuntimeError('official E0 failed, timed out, or survived cleanup')
            result = json.loads((e0 / 'result.json').read_bytes())
            if result.get('scene') != 'B' or result.get('num_cores') != 5:
                raise ValueError('official E0 coordinate mismatch')
            receipt.update(status='completed', candidate_makespan=result['makespan'],
                           candidate_movement=result['data_movement_bytes'],
                           old_movement=old['data_movement_bytes'])
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['wall_seconds'] = time.perf_counter() - start
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
        print(json.dumps({'status': receipt['status'], 'result_zip_sha256': sha(RESULT_ZIP.read_bytes()),
                          'result_zip_bytes': RESULT_ZIP.stat().st_size,
                          'calls': receipt['calls']}))


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'run':
        run()
    elif len(sys.argv) == 3 and sys.argv[1] == 'child':
        child(sys.argv[2])
    else:
        raise SystemExit('usage: q2_critical_packet_colab_probe.py run')
