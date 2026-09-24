"""Read-only scoring audit plus derived exports for the three-cell ordering pilot.

No solver, evaluator, Git or network command is executed. All writes are new
batch-level reports; original nested cell/driver evidence remains immutable.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import gzip
import hashlib
import json
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / 'docs/a/source-manifest.json').is_file())
SOURCE = 'e5c3a923eafa570dba1cc8f415cd58014df1aa3b'
RUNNER = '1beadbbc70971d262f570499d5e2d1cd867d7195'
OLD_DATA = 'd15f27fe3ad41be63c9e837af0a7afae440eca66'
EXPECTED = ('062-k2', '062-k4', '062-k5')
METRICS = ('makespan_cycles', 'ddr_bytes', 'extra_ddr_bytes', 'spill_bytes', 'solver_wall_seconds', 'evaluation_wall_seconds')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def reference(entry):
    path = ROOT / entry['path']
    assert sha(path.read_bytes()) == entry['sha256'], entry['path']
    return path


def inspect_ordering(graph, old_plan, new_plan, old_detail, new_detail):
    """Reconstruct compute ancestry directly from graph, without solver imports."""
    assert old_plan['node_to_subgraph'] == new_plan['node_to_subgraph']
    assert list(old_plan['node_to_subgraph'].items()) == list(new_plan['node_to_subgraph'].items())
    reverse = {sg: int(u) for u, sg in old_plan['node_to_subgraph'].items()}
    assert len(reverse) == len(old_plan['node_to_subgraph'])
    eligible = set(reverse.values())
    before = [[reverse[sg] for sg in seq] for seq in old_plan['core_schedules']]
    after = [[reverse[sg] for sg in seq] for seq in new_plan['core_schedules']]
    old_owner = {u: c for c, seq in enumerate(before) for u in seq}
    new_owner = {u: c for c, seq in enumerate(after) for u in seq}
    assert old_owner == new_owner and set(old_owner) == eligible
    assert len(old_owner) == sum(map(len, before)) == sum(map(len, after))
    shared = ('cores', 'eligible_ops', 'components', 'sink', 'sources', 'capacity_bytes',
              'packet_threshold_rational_cycles', 'packet_count', 'skeleton_ops', 'packets',
              'compute_load_by_core', 'active_cores', 'cut_edges', 'tensor_copy_bytes_without_spill')
    assert all(old_detail[k] == new_detail[k] for k in shared)
    predecessors = defaultdict(set)
    for edge in graph['edges']:
        predecessors[edge['target']].add(edge['source'])
    compute_pred = {}
    for u in eligible:
        found, seen, stack = set(), set(), list(predecessors[u])
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            if v in eligible:
                found.add(v)
            else:
                stack.extend(predecessors[v])
        compute_pred[u] = found
    ops = {op['id']: op for op in graph['ops']}
    packet_members, membership = {}, {}
    for packet in old_detail['packets']:
        members, stack = set(), [packet['root']]
        while stack:
            u = stack.pop()
            if u in members:
                continue
            members.add(u)
            stack.extend(compute_pred[u])
        assert len(members) == packet['ops']
        assert sum(max(1, int(ops[u]['cycles'])) for u in members) == packet['work_cycles']
        assert all(old_owner[u] == packet['core'] and u not in membership for u in members)
        membership.update({u: packet['root'] for u in members})
        packet_members[packet['root']] = members
        assert [u for u in before[packet['core']] if u in members] == [u for u in after[packet['core']] if u in members]
    skeleton = eligible - set(membership)
    assert len(skeleton) == old_detail['skeleton_ops']
    stable_partition = [[u for u in seq if u in membership] + [u for u in seq if u in skeleton] for seq in before]
    assert after == stable_partition
    # Reconstruct all compute producer -> tensor -> consumer cross-core edges.
    tensors = {t['id']: t for t in graph['tensors']}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        if a in eligible and b in tensors:
            producers[b].add(a)
        if a in tensors and b in eligible:
            consumers[a].add(b)
    cuts = []
    for tensor, ps in producers.items():
        for u in ps:
            for v in consumers[tensor]:
                if old_owner[u] != old_owner[v]:
                    cuts.append({'source_op': u, 'target_op': v, 'tensor': tensor, 'bytes': tensors[tensor]['size'],
                                 'source_core': old_owner[u], 'target_core': old_owner[v]})
    canonical = lambda entries: sorted(json.dumps(x, sort_keys=True) for x in entries)
    assert canonical(cuts) == canonical(old_detail['cut_edges']) == canonical(new_detail['cut_edges'])
    changed = [c for c, (a,b) in enumerate(zip(before,after)) if a != b]
    assert len(changed) == new_detail['changed_core_orders']
    assert new_detail['unchanged_ownership'] is True
    return {'node_to_subgraph_unchanged': True, 'all_op_owners_unchanged': True,
            'packet_metadata_unchanged': True, 'packet_membership_reconstructed': True,
            'packet_internal_words_unchanged': True, 'skeleton_subsequence_unchanged': True,
            'exact_stable_partition_packets_then_skeleton': True,
            'raw_cross_core_edges_and_bytes_reconstructed': True,
            'changed_core_ids': changed, 'packet_count': len(packet_members),
            'packet_member_ops': len(membership), 'skeleton_ops': len(skeleton),
            'raw_cross_core_edge_count': len(cuts), 'raw_cross_core_tensor_bytes': sum(x['bytes'] for x in cuts),
            'unchanged_metadata_fields': shared,
            'owner_map_sha256': sha(json.dumps(old_owner, sort_keys=True).encode())}


def main():
    started = time.monotonic()
    assert not (OUT / 'board-feed.json').exists(), 'Exports already exist; preserve them.'
    originals = {rel(p): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                 for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'postprocess.py'}
    batch, frozen = read(OUT / 'batch.json'), read(OUT.parent / 'manifest.json')
    assert batch['source_commit'] == frozen['source_commit'] == SOURCE and batch['runner_commit'] == RUNNER
    assert batch['status'] == 'completed' and batch['finished_at']
    assert tuple(x['cell'] for x in batch['cells']) == EXPECTED == tuple(f'{c}-k{k}' for c,k in frozen['cells'])
    assert frozen['max_solver'] == frozen['max_E0'] == 3
    assert frozen['max_online_E0'] == frozen['max_E1'] == frozen['max_E2'] == frozen['retries'] == 0
    assert frozen['workers'] == 1 and batch['aggregate_wall_seconds'] <= frozen['aggregate_wall_seconds']
    official_manifest = read(ROOT / 'docs/a/source-manifest.json')
    official_files = {x['path']: x for x in official_manifest['files']}
    graph = read(ROOT / 'data/raw/a/official/data/case_062.json')
    records, rows, comparisons, indexes, processes, runtime_hashes = [], [], [], [], [], []
    calls = Counter()
    manifests = compressed = 0
    for item in batch['cells']:
        key = item['cell']
        matrix, cell = OUT / key, OUT / key / key
        context, journal = read(matrix / 'context.json'), read(matrix / 'journal.json')
        run, ledger = read(cell / 'run.json'), read(cell / 'online/solver.json')
        protocol_path = context['argv'][context['argv'].index('--protocol') + 1]
        protocol_raw = (ROOT / protocol_path).read_bytes()
        protocol = json.loads(protocol_raw)
        assert protocol_path in frozen['protocols'] and sha(protocol_raw) == context['protocol_sha256']
        assert context['source_commit'] == SOURCE and context['runner_commit'] == RUNNER
        assert journal['identity'] == {k:context[k] for k in ('source_commit','runner_commit','protocol_sha256')}
        assert list(journal['cells']) == [key] and journal['stop_reason'] == 'all_fixed_cells_dispatched'
        assert journal['cells'][key]['state'] == 'ok' and journal['cells'][key]['charged_E0'] == 1
        assert journal['budget_E0'] == protocol['max_E0'] == 1
        assert protocol['max_internal_per_cell'] == protocol['retries'] == 0 and protocol['solver_mode'] == 'direct'
        assert protocol['solver_module'] == 'src.q2_nikolastarx.tree_packets_first'
        assert protocol['cases'] == [run['case']] and protocol['cores'] == [run['cores']]
        for category in ('source','runner','official','inputs'):
            for path,digest in context['hashes'][category].items():
                actual = ROOT / path if category in ('source','runner') else ROOT / 'data/raw/a/official' / path
                assert sha(actual.read_bytes()) == digest, (category,path)
                if category in ('official','inputs'):
                    assert official_files[path]['sha256'] == digest
                runtime_hashes.append({'cell':key,'category':category,'path':path,'sha256':digest})
        feed_path = matrix / f'board-feed-{key}.json'
        record = read(feed_path)['records'][0]
        result = read(cell / 'final/result.json.gz')
        assert run == item['attempt'] and item['accepted'] is True and run['online'] == ledger
        assert run['status'] == ledger['status'] == record['status'] == 'ok'
        assert run['phase'] == 'complete' and run['solver_mode'] == 'direct' and run['full_online_result_equal'] is None
        assert ledger['calls'] == {'E0':0,'E1':0,'E2':0} and len(ledger['attempts']) == 1
        assert run['calls'] == journal['cells'][key]['calls'] == record['provenance']['measurement']['calls'] == {'solver':1,'E0':1,'E1':0,'E2':0}
        calls.update(run['calls'])
        assert record['problem'] == 'P2' and result['scene'] == 'B' and result.get('problem') != 3
        assert record['case_id'] == run['case'] and record['cores'] == result['num_cores'] == run['cores']
        assert record['solver_commit'] == record['provenance']['solver']['source']['commit'] == SOURCE
        assert record['provenance']['runner']['source']['commit'] == RUNNER and record['parameters']['protocol'] == protocol
        assert record['identity']['graph_sha256'] == context['hashes']['inputs']['data/case_062.json']
        assert record['identity']['config_sha256'] == protocol['config_sha256'] == context['hashes']['inputs']['data/config.txt']
        assert record['identity']['official_sha256'] == protocol['official_sha256'] == official_manifest['official_code_hash']
        assert type(result['makespan']) is type(record['metrics']['makespan_cycles']) is int
        assert result['makespan'] == run['makespan_cycles'] == record['metrics']['makespan_cycles'] > 0
        plan_raw = (cell / 'plan.json').read_bytes()
        plan = json.loads(plan_raw)
        assert set(plan) == {'node_to_subgraph','core_schedules'}
        assert plan_raw == (cell / 'online/tree_packets_first/plan.json').read_bytes()
        assert sha(plan_raw) == ledger['plan_sha256'] == ledger['attempts'][0]['plan_sha256'] == record['identity']['plan_sha256']
        for metric,field in (('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','added_copy_bytes'),('spill_bytes','spill_added_copy_bytes')):
            assert record['metrics'][metric] == result['data_movement_bytes'][field]
        for stage,receipt,path in (('driver',item['driver'],OUT/f'{key}-driver/process.json'),('solver',run['solver'],cell/'solver-process/process.json'),('final',run['final'],cell/'final/process.json')):
            assert read(path) == receipt and receipt['status'] == 'ok' and receipt['exit_code'] == 0 and receipt['finished_at']
            assert not receipt['surviving_pids'] and not receipt['cleanup_killed_pids']
            assert receipt['observer_inclusive_peak_rss_bytes'] <= frozen['rss_observation_stop_bytes']
            processes.append({'cell':key,'stage':stage,'pid':receipt['pid'],'path':rel(path),'sha256':sha(path.read_bytes())})
        assert record['metrics']['solver_wall_seconds'] == run['solver']['wall_seconds']
        assert record['metrics']['evaluation_wall_seconds'] == run['final']['wall_seconds']
        assert 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py' in run['final']['argv']
        for name,entry in read(cell/'manifest.json').items():
            raw=(cell/name).read_bytes()
            assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],(key,name)
            manifests += 1
        for entry in read(cell/'archive.json')['compression'].values():
            packed=(cell/entry['stored']).read_bytes(); raw=gzip.decompress(packed)
            assert sha(packed)==entry['stored_sha256'] and len(packed)==entry['stored_bytes']
            assert sha(raw)==entry['raw_sha256'] and len(raw)==entry['raw_bytes']
            compressed += 1
        for entry in record['artifacts'].values(): reference(entry)
        reference(record['baseline']['result'])
        for field in ('graph_sha256','config_sha256','official_sha256'):
            assert record['baseline'][field]==record['identity'][field]
        p=read(matrix/f'precheck-{key}.json'); eligible=json.loads(p['stdout'])
        assert p['exit_code']==0 and eligible['valid'] and eligible['eligible']==1
        detail=ledger['attempts'][0]['detail']
        assert record['parameters']['selected_strategy']==detail['selected_strategy']=='tree_packets_first'
        assert detail['index_constructions']==detail['base_construct_calls']==1
        old_dir=ROOT/'results/a/q2-nikolastarx/tree-pilot-20260924/run'
        old_feed_path=old_dir/f'board-feed-{key}.json'; old=read(old_feed_path)['records'][0]
        assert old['status']=='ok' and old['case_id']==record['case_id'] and old['cores']==record['cores']
        for field in ('graph_sha256','config_sha256','official_sha256'):
            assert old['identity'][field]==record['identity'][field]
        old_plan=read(reference(old['artifacts']['plan']))
        old_result=read(reference(old['artifacts']['result']))
        old_run=read(reference(old['artifacts']['run']))
        old_manifest=read(reference(old['artifacts']['manifest']))
        old_ledger_path=old_dir/key/'online/solver.json'; old_ledger=read(old_ledger_path)
        assert sha(old_ledger_path.read_bytes())==old_manifest['online/solver.json']['sha256']
        assert old_run['online']==old_ledger
        assert old_run['status']=='ok' and old_result['makespan']==old['metrics']['makespan_cycles']
        assert old_run['solver']['wall_seconds']==old['metrics']['solver_wall_seconds']
        assert old_run['final']['wall_seconds']==old['metrics']['evaluation_wall_seconds']
        assert old_result['data_movement_bytes']==result['data_movement_bytes']
        for metric,field in (('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','added_copy_bytes'),('spill_bytes','spill_added_copy_bytes')):
            assert old['metrics'][metric]==old_result['data_movement_bytes'][field]
        ordering=inspect_ordering(graph,old_plan,plan,old_ledger['attempts'][0]['detail'],detail)
        row={'case':run['case'],'cores':run['cores'],'status':run['status'],'route':'tree_packets_first'}
        for metric in METRICS:
            row['old_'+metric]=old['metrics'][metric]; row['new_'+metric]=record['metrics'][metric]
            row['delta_'+metric]=record['metrics'][metric]-old['metrics'][metric]
        row['makespan_reduction_percent']=100*(1-record['metrics']['makespan_cycles']/old['metrics']['makespan_cycles'])
        row['quality']='win' if row['delta_makespan_cycles']<0 else 'loss' if row['delta_makespan_cycles']>0 else 'tie'
        row['changed_core_orders']=len(ordering['changed_core_ids'])
        row['all_movement_fields_identical']=True
        row['fixed_fifo_bound_before']=detail['fixed_compute_fifo_bound_before']
        row['fixed_fifo_bound_after']=detail['fixed_compute_fifo_bound_after']
        rows.append(row);records.append(record)
        comparisons.append({'cell':key,'old_data_commit_reported_by_protocol':OLD_DATA,'old_solver_commit':old['solver_commit'],
                            'old_feed':rel(old_feed_path),'old_feed_sha256':sha(old_feed_path.read_bytes()),
                            'old_artifacts':old['artifacts'],'old_ledger_sha256':sha(old_ledger_path.read_bytes()),
                            'ordering_checks':ordering,'all_official_movement_fields_identical':result['data_movement_bytes'],
                            'metrics':row})
        indexes.append({'cell':key,'feed':rel(feed_path),'sha256':sha(feed_path.read_bytes()),'precheck':eligible})
    assert dict(calls)=={'solver':3,'E0':3,'E1':0,'E2':0}
    live={int(x) for x in subprocess.check_output(['ps','-axo','pid='],text=True).splitlines()}
    survivors=sorted({x['pid'] for x in processes}&live);assert not survivors,survivors
    save('board-feed.json',{'schema_version':1,'submission_version':1,'records':records})
    argv=[sys.executable,'-B','src/benchmark_board/protocol.py',rel(OUT/'board-feed.json'),'--submission']
    checked=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,timeout=30)
    save('precheck.json',{'argv':['.venv/bin/python',*argv[1:]],'exit_code':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr})
    eligible=json.loads(checked.stdout)
    assert checked.returncode==0 and eligible['valid'] and eligible['eligible']==3
    feed_hash=sha((OUT/'board-feed.json').read_bytes())
    indexes.append({'cell':'aggregate-three','feed':rel(OUT/'board-feed.json'),'sha256':feed_hash,'precheck':eligible})
    save('feed-index.json',indexes);save('original-artifacts.json',originals);save('comparisons.json',comparisons)
    with (OUT/'metrics.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    assert b'\r' not in (OUT/'metrics.csv').read_bytes()
    save('summary.json',{'source_commit':SOURCE,'runner_commit':RUNNER,'old_tree_data_commit':OLD_DATA,'cells':rows,
                         'quality_counts':dict(Counter(r['quality'] for r in rows)),'calls':dict(calls),'online_E0':0,
                         'aggregate_wall_seconds':batch['aggregate_wall_seconds'],'scope':'Three paired case062 development cells; no full-100/500 or global optimality claim.'})
    assert all(sha((ROOT/p).read_bytes())==e['sha256'] and (ROOT/p).stat().st_size==e['bytes'] for p,e in originals.items())
    save('verification.json',{'status':'pass','verified_at_utc':datetime.now(timezone.utc).isoformat(),'source_commit':SOURCE,'runner_commit':RUNNER,
                             'original_files_unchanged':len(originals),'cell_manifest_entries_verified':manifests,
                             'compressed_json_roundtrips':compressed,'process_receipts':processes,'surviving_pids':survivors,
                             'runtime_files_match_recorded_hashes':runtime_hashes,'calls':dict(calls),'online_E0':0,
                             'new_scoring_calls_during_postprocess':0,'scoring_failures':0,'scoring_retries':0,
                             'source_attribution_limit':'Pinned IDs match receipts, batch, journals and feeds; current code bytes match captured runtime hashes. No Git object reads in this task.',
                             'comparison_limit':'Previous tree feed/plan/result/run/ledger bytes match recorded hashes; parent identifies fixed data commit d15f27fe. No Git reads or old E0 reruns.',
                             'protocol_text_note':'failure_policy contains inherited words six-cell driver; manifest, single-cell protocols, batch coverage and counts are exactly three. Original frozen text is unchanged.',
                             'resource_window_note':'Root reports actually receiving and replying to the P1 window-release handoff. This audit did not independently read the external handoff record.',
                             'timing_limit':'End-to-end solver wall includes observation/cleanup; final E0 separate. Before/after wall is descriptive and not causal speedup.',
                             'aggregate_feed_sha256':feed_hash,'producer_precheck_eligible':3,
                             'precheck_code_sha256':sha((ROOT/'src/benchmark_board/protocol.py').read_bytes()),
                             'verification_wall_seconds':time.monotonic()-started})
    lines=['# Tree packet-first ordering: three paired official results','',f'Source `{SOURCE}`; runner `{RUNNER}`. Prior tree data `{OLD_DATA}`.','',
           f'Execution UTC {batch["started_at"]} to {batch["finished_at"]}; aggregate driver wall {batch["aggregate_wall_seconds"]:.9f} s.','',
           'Three fresh solver calls and three final official E0 calls succeeded; zero online E0/E1/E2, scoring failures or retries. Postprocessing adds zero scoring calls and does not rerun the old tree solver.','',
           '| Case | k | Old Makespan | New Makespan | Delta | Reduction | DDR B | Extra DDR B | Spill B | Solver s | Final E0 s |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["case"]} | {r["cores"]} | {r["old_makespan_cycles"]} | {r["new_makespan_cycles"]} | {r["delta_makespan_cycles"]:+} | {r["makespan_reduction_percent"]:.6f}% | {r["new_ddr_bytes"]} | {r["new_extra_ddr_bytes"]} | {r["new_spill_bytes"]} | {r["new_solver_wall_seconds"]:.6f} | {r["new_evaluation_wall_seconds"]:.6f} |')
    lines+=['','Two wins and one loss are retained: k2 worsens by 36 cycles; k4 improves by 163495 cycles; k5 improves by 1176 cycles.','',
            'Independent byte/data checks confirm node_to_subgraph entries and all op owners are unchanged. Packet metadata, reconstructed complete packet membership, each internal packet word, skeleton subsequences, core compute loads, raw cut edges and transfer bytes are unchanged. New core schedules exactly equal the stable partition of each old schedule into packet ops first, skeleton ops second; 1/2/3 core orders change for k2/k4/k5 respectively.','',
            'Every official data_movement_bytes field is identical old/new, including original_graph_copy_bytes, scheduled_copy_bytes, added_copy_bytes, partition_added_copy_bytes and spill_added_copy_bytes. All three have zero observed spill. The sole plan-level intervention is order, so DDR volume does not explain these quality changes; this does not prove a general ordering improvement or zero-spill theorem.','',
            'The reported fixed-FIFO bounds remain candidate-specific metadata. They are preserved for diagnosis and are not treated as predicted Makespan or independently reproved by this export. The k5 bound is unchanged while its official Makespan improves.','',
            f'Checked {manifests} per-cell manifest entries, {compressed} raw/stored gzip hash-and-size roundtrips, {len(originals)} unchanged original files, and nine completed driver/solver/final receipts. All nine PIDs are absent. All per-cell and aggregate producer prechecks are eligible; this is not central admission or scientific acceptance.','',
            'This is case062 at three fixed core counts, a selected paired development experiment, not full100/500. No whole-suite mean is reported. Wall times include launch/input/output/observation/cleanup; separate final E0 wall is retained. Machine timing differences do not establish causal solver speedup.','',
            'The frozen failure_policy retains the copied phrase six-cell driver; manifest, three single-cell protocols, journals and batch cover exactly three cells with max3 final E0. This wording issue does not change the observed allocation. Original evidence is not altered.','',
            'Root reports actually receiving and replying to the P1 resource-window release. This export does not independently validate the external handoff messages.','',
            'Publication remains with the parent: explicitly include three nested final/official.log files. Original driver receipts retain actual interpreter paths. No Git operations, external messages, network requests, central ledger writes or mirror synchronization were performed.','']
    with (OUT/'SUMMARY.md').open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines))
    with (OUT/'.gitattributes').open('x',encoding='utf-8',newline='\n') as stream:stream.write('# Preserve evidence bytes and LF exports.\n* -text\n')
    manifest={p.relative_to(OUT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'manifest.json'}
    save('manifest.json',manifest)
    print(json.dumps({'rows':rows,'feed_sha256':feed_hash,'manifest_sha256':sha((OUT/'manifest.json').read_bytes()),'manifest_files':len(manifest),
                      'original_files':len(originals),'cell_manifest_entries':manifests,'compressed_roundtrips':compressed,'process_receipts':len(processes),
                      'eligible':3,'calls':dict(calls),'verification_wall_seconds':time.monotonic()-started},indent=2))


if __name__=='__main__':main()
