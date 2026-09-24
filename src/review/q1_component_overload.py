"""Static overload/sink-packet coverage across 100 graphs; zero construction/E0.

Only graph helpers and peel_packets are called. Packet/wave metrics are not a
submission plan, compilation, schedule, timing simulation or performance score.
"""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.sink_peel import peel_packets, PeelBudgetExceeded
from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes

BASE = '161cdb35de11b0d174a5a0ca149aa36657af2abd'
HEAVY = '4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f'
COMPARISON = 'results/a/q1-bounded-timeout-20260924/20260924T1524Z-timeout4/full500-filled-comparison.json'
OUT = ROOT/'results/a/q1-component-overload-20260925/analysis.json'
K, ROUNDS, SINKS = 5, 64, 64

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def checked(ref):
    raw = (ROOT/ref['path']).read_bytes()
    assert sha(raw) == ref['sha256'], ref['path']
    return json.loads(gzip.decompress(raw) if ref['path'].endswith('.gz') else raw)

def main():
    began, start = datetime.now(timezone.utc).isoformat(), time.monotonic()
    manifest = json.loads((ROOT/'docs/a/source-manifest.json').read_text())
    files = {x['path']: x['sha256'] for x in manifest['files']}
    archive = ROOT/manifest['case_archive']['path']
    assert sha(archive.read_bytes()) == manifest['case_archive']['sha256']
    protected = {p: sha((ROOT/'data/raw/a/official'/p).read_bytes()) for p in files
                 if p.startswith('code/') or p == 'data/config.txt'}
    assert all(files[p] == h for p,h in protected.items())
    sink = ROOT/'src/q1/sink_peel.py'
    assert sink.read_bytes() == subprocess.check_output(['git','show',BASE+':src/q1/sink_peel.py'],cwd=ROOT)
    records = json.loads((ROOT/COMPARISON).read_text())
    records = {r['case']:r for r in records if r['cores'] == K}
    assert len(records) == 100
    results = []
    with zipfile.ZipFile(archive) as z:
        for case, old in sorted(records.items()):
            name = f'data/case_{case}.json'
            raw = z.read(name)
            assert sha(raw) == files[name]
            g = json.loads(raw)
            run = checked(old['source_run'])
            result = checked(run['artifacts']['result'])
            assert result['makespan'] == old['makespan_cycles']
            assert result['data_movement_bytes']['spill_added_copy_bytes'] == old['spill_bytes']
            ops = {o['id']:o for o in g['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
            original_copy_out_ids={o['id'] for o in g['ops'] if o['op']=='COPY_OUT'}
            original_export_tensors={e['source'] for e in g['edges'] if e['target'] in original_copy_out_ids}
            tensors = {t['id']:t for t in g['tensors']}
            producers, consumers = defaultdict(set), defaultdict(set)
            for e in g['edges']:
                u,v=e['source'],e['target']
                if u in ops and v in tensors: producers[v].add(u)
                if u in tensors and v in ops: consumers[u].add(v)
            _, full = _build_op_adjacency(g)
            pred, succ = _contract_excluded_copy_nodes(sorted(ops),full)
            degree = {u:len(pred[u]) for u in ops}
            queue = deque(sorted(u for u in ops if not degree[u]))
            order, cp = [], {}
            while queue:
                u=queue.popleft();order.append(u)
                cp[u]=max(1,ops[u]['cycles'])+max((cp[v] for v in pred[u]),default=0)
                for v in sorted(succ[u]):
                    degree[v]-=1
                    if not degree[v]:queue.append(v)
            assert len(order)==len(ops)
            unseen, components = set(ops), []
            for root in sorted(ops):
                if root not in unseen:continue
                unseen.remove(root);stack=[root];members=[]
                while stack:
                    u=stack.pop();members.append(u)
                    for v in pred[u]|succ[u]:
                        if v in unseen:unseen.remove(v);stack.append(v)
                components.append(sorted(members))
            work=[];total=Counter()
            for ns in components:
                w=Counter()
                for u in ns:w[ops[u]['pipe']]+=max(1,ops[u]['cycles'])
                work.append(w);total.update(w)
            target={p:(w+K-1)//K for p,w in total.items()}
            dominant=min(total,key=lambda p:(-total[p],p))
            heavy=min(range(len(components)),key=lambda i:(-work[i][dominant],components[i][0]))
            old_guard=(len(components)>=K and 100*work[heavy][dominant]>=80*total[dominant])
            graph_floor=max(max(target.values()),max(cp.values()))
            comps=[]
            for ci,nodes in enumerate(components):
                w=work[ci]
                excess={p:w.get(p,0)-target[p] for p in target if w.get(p,0)>target[p]}
                if not excess:continue
                ids=set(nodes)
                component_inputs={t for t,vs in consumers.items() if not producers[t] and vs&ids}
                data={'anchor':nodes[0],'compute_ops':len(nodes),'work_by_pipe':dict(w),
                    'overload_excess_by_pipe':excess,'dominant_pipe_fraction':w.get(dominant,0)/total[dominant],
                    'selected_by_old_heavy_guard':old_guard and ci==heavy,
                    'component_input_bytes':sum(tensors[t]['size'] for t in component_inputs),
                    'component_compute_cp':max(cp[u] for u in nodes),
                    'component_max_pipe_work':max(w.values()),
                    'max_pipe_excess_over_graph_floor':max(w.values())-graph_floor,
                    'initial_sink_count':sum(not succ[u] for u in nodes)}
                try:
                    waves=peel_packets(nodes,{u:pred[u]&ids for u in nodes},{u:succ[u]&ids for u in nodes},
                                       max_rounds=ROUNDS,max_sinks=SINKS)
                except PeelBudgetExceeded as e:
                    data.update(peel_status='budget_declined',budget_failure=str(e))
                    comps.append(data);continue
                packets=[(wi,pi,ns) for wi,wave in enumerate(waves) for pi,ns in enumerate(wave)]
                label={u:(wi,pi) for wi,pi,ns in packets for u in ns}
                packet_work={}
                wave_details=[]
                for wi,wave in enumerate(waves):
                    totals=Counter();maxima=Counter();pw=[]
                    for pi,ns in enumerate(wave):
                        pwork=Counter()
                        for u in ns:pwork[ops[u]['pipe']]+=max(1,ops[u]['cycles'])
                        packet_work[(wi,pi)]=pwork;totals.update(pwork)
                        for p,x in pwork.items():maxima[p]=max(maxima[p],x)
                        pw.append(dict(pwork))
                    wave_details.append({'packets':len(wave),'packet_ops':list(map(len,wave)),
                        'total_work_by_pipe':dict(totals),'max_packet_work_by_pipe':dict(maxima),
                        'packet_work_by_pipe':pw})
                packet_pred=defaultdict(set)
                for u in nodes:
                    for v in succ[u]:
                        if label[u]!=label[v]:
                            assert label[u][0]<label[v][0]
                            packet_pred[label[v]].add(label[u])
                packet_cp={};packet_gated={}
                for label_key in sorted(packet_work):
                    weight=max(packet_work[label_key].values())
                    packet_cp[label_key]=weight+max((packet_cp[p] for p in packet_pred[label_key]),default=0)
                    packet_gated[label_key]=weight+max((packet_gated[p]+100 for p in packet_pred[label_key]),default=0)
                ext_wave_repeat=ext_packet_repeat=0
                for t in component_inputs:
                    ps={label[u] for u in consumers[t]&ids}
                    ext_packet_repeat+=(len(ps)-1)*tensors[t]['size']
                    ext_wave_repeat+=(len({x[0] for x in ps})-1)*tensors[t]['size']
                payload, packet_in, packet_out, wave_in, wave_out = 0,0,0,0,0
                for t in tensors:
                    ps={label[u] for u in producers[t]&ids};cs={label[u] for u in consumers[t]&ids}
                    if not ps or not cs or ps==cs:continue
                    if any(cs-{p} for p in ps):
                        payload+=tensors[t]['size']
                        packet_in+=len(cs-ps)*tensors[t]['size']
                        already_exported=t in original_export_tensors
                        packet_out+=(sum(already_exported or bool(cs-{p}) for p in ps)-already_exported)*tensors[t]['size']
                        pws={p[0] for p in ps};cws={p[0] for p in cs}
                        wave_in+=len(cws-pws)*tensors[t]['size']
                        wave_out+=(sum(already_exported or bool(cws-{p}) for p in pws)-already_exported)*tensors[t]['size']
                largest=max(max(w.values()) for w in packet_work.values())
                data.update(peel_status='ok',wave_count=len(waves),parallel_wave_count=sum(len(w)>1 for w in waves),
                    widths=[len(w) for w in waves],packet_count=len(packets),max_packet_ops=max(len(ns) for _,_,ns in packets),
                    max_packet_any_pipe_work=largest,max_packet_fraction=largest/max(w.values()),
                    packet_chain_work_proxy=max(packet_cp.values()),packet_chain_work_with_100_gate_proxy=max(packet_gated.values()),
                    cut_internal_payload_bytes_once=payload,packet_input_boundary_bytes=packet_in,
                    packet_output_boundary_bytes=packet_out,wave_input_boundary_bytes=wave_in,wave_output_boundary_bytes=wave_out,
                    external_wave_repeat_bytes=ext_wave_repeat,external_packet_repeat_bytes=ext_packet_repeat,
                    added_copy_proxy_by_granularity={'coalesced_wave':ext_wave_repeat+wave_in+wave_out,
                        'separate_packets':ext_packet_repeat+packet_in+packet_out},
                    static_serial_pressure_reduction_room=max(0,max(w.values())-max(graph_floor,largest,max(packet_cp.values()))),
                    waves=wave_details)
                comps.append(data)
            split_anchors={c['anchor'] for c in comps if c.get('parallel_wave_count',0)>0}
            retained_floor=max((max(work[i].values()) for i,ns in enumerate(components)
                                if ns[0] not in split_anchors),default=0)
            route_floor=max(graph_floor,retained_floor)
            for c in comps:
                if c['peel_status']=='ok':
                    c['static_room_after_retained_components']=max(0,c['component_max_pipe_work']-
                        max(route_floor,c['max_packet_any_pipe_work'],c['packet_chain_work_proxy']))
            results.append({'case':case,'cores':K,'components':len(components),'compute_ops':len(ops),
                'total_work_by_pipe':dict(total),'per_pipe_average_targets':target,'global_dominant_pipe':dominant,
                'compute_graph_lower_bound_without_task_gates':graph_floor,'old_heavy_guard_trigger':old_guard,
                'max_retained_whole_component_pipe_work':retained_floor,
                'route_compute_floor_with_retained_components':route_floor,
                'old_heavy_guard_anchor':components[heavy][0] if old_guard else None,
                'existing_makespan_cycles':old['makespan_cycles'],'existing_singlecore_baseline_cycles':old['baseline_cycles'],
                'existing_extra_ddr_bytes':old['extra_ddr_bytes'],'existing_spill_bytes':old['spill_bytes'],
                'existing_run':old['source_run'],'existing_result':run['artifacts']['result'],
                'overloaded_components':comps})
    assert all(sha((ROOT/'data/raw/a/official'/p).read_bytes())==h for p,h in protected.items())
    assert sha(archive.read_bytes())==manifest['case_archive']['sha256']
    out={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'read_base_commit':BASE,'old_heavy_source_commit':HEAVY,'sink_source_sha256':sha(sink.read_bytes()),
        'comparison':{'path':COMPARISON,'sha256':sha((ROOT/COMPARISON).read_bytes())},
        'started_utc':began,'ended_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-start,
        'python_version':platform.python_version(),'platform':platform.platform(),
        'calls':{'real_constructor':0,'synthetic_constructor':0,'Task_compiler':0,'E0':0,'E1':0,'E2':0},
        'pure_peel_calls':sum(len(r['overloaded_components']) for r in results),
        'budgets':{'cores':K,'max_rounds':ROUNDS,'max_sinks':SINKS},'official_files_verified_before_after':protected,
        'input_zip_sha256':manifest['case_archive']['sha256'],'rows':results,
        'scope':'No submitted plan, core assignment or scientific scoring. Packet-chain and stage-copy metrics are conditional static proxies; they do not include spill or prove improvement.'}
    layers={
        'any_pipe_overload':lambda r,c:True,
        'at_least_K_components':lambda r,c:r['components']>=K,
        'enough_components_and_parallel_peel':lambda r,c:r['components']>=K and c.get('parallel_wave_count',0)>0,
        'new_vs_old_guard_and_parallel_peel':lambda r,c:r['components']>=K and c.get('parallel_wave_count',0)>0 and not c['selected_by_old_heavy_guard'],
        'new_parallel_positive_static_room':lambda r,c:r['components']>=K and c.get('parallel_wave_count',0)>0 and not c['selected_by_old_heavy_guard'] and c['static_serial_pressure_reduction_room']>0,
        'new_parallel_positive_room_after_retained_components':lambda r,c:r['components']>=K and c.get('parallel_wave_count',0)>0 and not c['selected_by_old_heavy_guard'] and c['static_room_after_retained_components']>0,
    }
    out['coverage_layers']={name:{'components':len(pairs),'graphs':len({r['case'] for r,c in pairs}),
        'cases':sorted({r['case'] for r,c in pairs})} for name,test in layers.items()
        for pairs in [[(r,c)for r in results for c in r['overloaded_components']if test(r,c)]]}
    OUT.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'graphs':len(results),'overloaded_components':out['pure_peel_calls'],
        'budget_declined':sum(c['peel_status']!='ok' for r in results for c in r['overloaded_components']),
        'wall_seconds':out['wall_seconds'],'construct_compile_E0_E1_E2':0}))

if __name__=='__main__':main()
