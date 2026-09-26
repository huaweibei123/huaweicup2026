from __future__ import annotations
import gzip, hashlib, json, math, statistics, subprocess, sys, time
from collections import Counter, defaultdict
from pathlib import Path
T0 = time.perf_counter()
ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
ANALYSIS_COMMIT = '4a501d7f4a8b780263e097a963e12dcb66178e69'
TENSOR_COMMIT = 'e64723bdf99669c44f76d8e90ab0379a8578522e'
GAP_COMMIT = '384b6c2a7ff937ca44180dee09a9d4bcaea0c50d'
OFFICIAL_COMMIT = '45f647b395b84e9569f418fd33d62c2b8eb4d190'
sys.path.insert(0, str(ROOT))
from src.q2.feedback.construct import derive_multicore_plan
from src.q2.feedback.tensor_packet import TensorIndex
from src.q2.feedback.physical_frontier import certificate
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
from schedule_step3 import _op_duration

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def readj(path: Path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
def check_code(path):
    local=(ROOT/path).read_bytes()
    frozen=subprocess.check_output(['git','show',f'{ANALYSIS_COMMIT}:{path.as_posix()}'],cwd=ROOT)
    if local != frozen: raise RuntimeError(f'analysis source differs from frozen commit: {path}')
    return sha(local)
def parse_config(path):
    section=None; values=defaultdict(dict)
    for raw in path.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('[') and line.endswith(']'): section=line[1:-1]; continue
        k,v=line.split()[:2]; values[section][k]=int(v)
    return {'bandwidth':values['bandwidth']['bandwidth'], 'capacity':values['capacity']}
def core_map(graph,plan):
    view=derive_multicore_plan(graph,plan)
    mapping=view['mapping']; bysg=view['core_by_subgraph']
    eligible={op['id'] for op in graph['ops'] if op.get('op') not in ('COPY_IN','COPY_OUT')}
    cm={}
    for u in eligible:
        sg=mapping.get(str(u),mapping.get(u))
        if sg is None: raise RuntimeError(f'eligible op missing from derived mapping: {u}')
        cm[u]=int(bysg.get(sg,bysg.get(str(sg))))
    return view,cm,eligible
def build_multiset(graph,cm,eligible,bandwidth):
    tensors={t['id']:t for t in graph['tensors']}
    ops={o['id']:o for o in graph['ops']}
    producers=defaultdict(set); consumers=defaultdict(set); copy_out=set()
    for e in graph['edges']:
        u,v=e['source'],e['target']
        if u in eligible and v in tensors: producers[v].add(u)
        if u in tensors and v in eligible: consumers[u].add(v)
        if u in tensors and v in ops and ops[v].get('op')=='COPY_OUT': copy_out.add(u)
    items=[]; links=[]
    def add(kind, ident, size, src=None, dst=None, edge_index=None, link_src=None, link_dst=None):
        size=max(0,int(size)); items.append({'kind':kind,'identity':ident,'source_core':src,'target_core':dst,
            'link_source_core':link_src,'link_target_core':link_dst,'edge_index':edge_index,
            'bytes':size,'service_cycles':max(1,math.ceil(size/bandwidth))})
    for tid,t in tensors.items():
        prod=sorted({cm[u] for u in producers[tid]}); cons=sorted({cm[u] for u in consumers[tid]}); size=t['size']
        if cons and not prod:
            for c in cons: add('graph_input_copy_in',tid,size,dst=c)
        if prod and (tid in copy_out or not cons):
            for c in prod: add('graph_output_copy_out',tid,size,src=c)
        for src in prod:
            for dst in cons:
                if src==dst: continue
                links.append({'kind':'tensor_core_pair','identity':tid,'source_core':src,'target_core':dst,'bytes':size})
                add('tensor_pair_copy_out',tid,size,src=src,link_src=src,link_dst=dst)
                add('tensor_pair_copy_in',tid,size,dst=dst,link_src=src,link_dst=dst)
    for edge_id,e in enumerate(graph['edges']):
        src,dst=e['source'],e['target']
        if src not in eligible or dst not in eligible: continue
        sc,dc=cm[src],cm[dst]
        if sc==dc: continue
        size=max(0,int(e.get('data_size',0)))
        links.append({'kind':'direct_eligible_edge','identity':f'{src}->{dst}','edge_index':edge_id,
                      'source_core':sc,'target_core':dc,'bytes':size})
        add('direct_edge_copy_out',f'{src}->{dst}',size,src= sc,edge_index=edge_id,link_src=sc,link_dst=dc)
        add('direct_edge_copy_in',f'{src}->{dst}',size,dst=dc,edge_index=edge_id,link_src=sc,link_dst=dc)
    return items,links

def duration_by_core(graph,cm,eligible,bandwidth,core_count):
    tensors={t['id']:t for t in graph['tensors']}; ops={o['id']:o for o in graph['ops']}
    work={c:0 for c in range(core_count)}; counts={c:0 for c in range(core_count)}
    for u in eligible:
        d=_op_duration(ops[u],{}, {},tensors,bandwidth)
        work[cm[u]]+=d; counts[cm[u]]+=1
    return {str(c):{'eligible_ops':counts[c],'C_c_official_op_duration_cycles':work[c]} for c in range(core_count)}
def analyze(case, old_batch, gap_batch, old_variant, gap_variant, config):
    raw=ROOT/f'data/raw/a/official/data/case_{case}.json'; graph=readj(raw)
    config_path=ROOT/'data/raw/a/official/data/config.txt'; config_hash=sha(config_path.read_bytes())
    records={}
    for batch,variant,solver in ((old_batch,old_variant,TENSOR_COMMIT),(gap_batch,gap_variant,GAP_COMMIT)):
        d=ROOT/f'results/a/q2-yuanzhifang/feedback-20260924/{batch}/{case}-{variant}'
        runp=d/'run.json'; run=readj(runp)
        if run['status']!='ok' or run['solver_commit']!=solver or run['evaluator_commit']!=OFFICIAL_COMMIT:
            raise RuntimeError(f'unexpected saved run identity/status for {case} {batch}')
        planp=d/f'case_{case}_multicore_res.json'; plan=readj(planp)
        if set(plan)!={'node_to_subgraph','core_schedules'}: raise RuntimeError('saved plan output schema mismatch')
        if sha(planp.read_bytes())!=run['identity']['plan_sha256']: raise RuntimeError('saved plan hash mismatch')
        if sha(raw.read_bytes())!=run['identity']['graph_sha256'] or config_hash!=run['identity']['config_sha256']:
            raise RuntimeError('input/config identity mismatch')
        result_art=run['artifacts']['result']; resultp=ROOT/result_art['path']
        if sha(resultp.read_bytes())!=result_art['sha256']: raise RuntimeError('saved result hash mismatch')
        result=readj(resultp)
        if result['makespan']!=run['metrics']['makespan_cycles']: raise RuntimeError('saved M mismatch')
        view,cm,eligible=core_map(graph,plan)
        if view['num_cores']!=5: raise RuntimeError('expected k5 plan')
        multiset,links=build_multiset(graph,cm,eligible,config['bandwidth'])
        work=duration_by_core(graph,cm,eligible,config['bandwidth'],5)
        total_bytes=sum(x['bytes'] for x in multiset); total_count=len(multiset)
        service=sum(x['service_cycles'] for x in multiset)
        movement=result['data_movement_bytes']; saved_base=movement['scheduled_copy_bytes']-movement['spill_added_copy_bytes']
        manual={'base_copy_count':total_count,'base_copy_bytes':total_bytes,'base_copy_service_cycles_W':service}
        checks={'manual_bytes_equals_scheduled_minus_spill':total_bytes==saved_base,
                'scheduled_minus_spill_bytes':saved_base}
        cert=None
        if variant=='tensor_packet':
            try:
                cert=certificate(TensorIndex(graph),plan,config['capacity'])
                checks['manual_count_equals_physical_certificate']=total_count==cert['base_copy_count']
                checks['manual_bytes_equals_physical_certificate']=total_bytes==cert['base_copy_bytes']
            except Exception as exc:
                cert={'status':'not_applicable_or_error','error_type':type(exc).__name__,'error':str(exc)}
                checks['manual_count_equals_physical_certificate']=None
                checks['manual_bytes_equals_physical_certificate']=None
        cmax=max(v['C_c_official_op_duration_cycles'] for v in work.values())
        records[variant]={'batch':batch,'plan_path':planp.relative_to(ROOT).as_posix(),'plan_sha256':sha(planp.read_bytes()),
            'run_path':runp.relative_to(ROOT).as_posix(),'run_sha256':sha(runp.read_bytes()),
            'solver_commit':run['solver_commit'],'runner_commit':run['runner_commit'],'evaluator_commit':run['evaluator_commit'],
            'graph_sha256':run['identity']['graph_sha256'],'config_sha256':run['identity']['config_sha256'],
            'official_code_sha256':run['identity']['official_sha256'],'result_path':result_art['path'],'result_sha256':result_art['sha256'],
            'existing_saved_measurement_only':True,'saved_makespan_cycles':result['makespan'],
            'saved_data_movement_bytes':movement,'core_map':{str(k):v for k,v in cm.items()},
            'eligible_op_count':len(eligible),'per_core_compute_work':work,'max_core_compute_work_cycles':cmax,
            **manual,'normalized_base_copy_multiset':multiset,'normalized_multiset_kind_counts':dict(Counter(x['kind'] for x in multiset)),
            'cross_core_link_count':len(links),'cross_core_links':links,'no_cross_links_guard':len(links)==0,
            'cross_link_guard_definition':'No cross-core tensor producer-consumer core pair and no direct eligible op-op edge crossing cores.',
            'base_copy_cross_checks':checks,'physical_frontier_certificate_A_only':cert}
    A=records[old_variant]; B=records[gap_variant]
    U_A=A['max_core_compute_work_cycles']+A['base_copy_service_cycles_W']; L_B=B['base_copy_service_cycles_W']
    trigger=bool(A['no_cross_links_guard'] and isinstance(A['physical_frontier_certificate_A_only'],dict)
                 and A['physical_frontier_certificate_A_only'].get('certified') is True and U_A < L_B)
    records['_comparison']={'U_A_cycles':U_A,'L_B_cycles':L_B,
        'heuristic_trigger':trigger,
        'heuristic_trigger_definition':'Diagnostic-only strict preference for A if A has no cross-core links, physical_frontier certificate A passes, and U_A < L_B. False means the sufficient diagnostic condition is not met; it does not prefer B.',
        'U_A_definition':'max over A per-core sums of official schedule_step3._op_duration for eligible ops + A normalized base-copy service W_A; W_A excludes spill and cross-core fixed delay.',
        'L_B_definition':'B normalized base-copy service W_B=sum(max(1,ceil(copy_bytes/config_bandwidth))) per mandatory copy; a service-demand lower bound, not an E0 prediction.',
        'raw_saved_M_A_cycles':A['saved_makespan_cycles'],'raw_saved_M_B_cycles':B['saved_makespan_cycles'],
        'raw_saved_M_role':'Existing official E0 measurements only; not recomputed and not used by the trigger.'}
    return records

def main():
    for p in ('src/q2/feedback/construct.py','src/q2/feedback/tensor_packet.py','src/q2/feedback/physical_frontier.py'):
        check_code(Path(p))
    cfg=parse_config(ROOT/'data/raw/a/official/data/config.txt')
    cfg.update({'config_path':'data/raw/a/official/data/config.txt','config_sha256':sha((ROOT/'data/raw/a/official/data/config.txt').read_bytes()),
                'official_step3_path':'data/raw/a/official/code/schedule_step3.py','official_step3_sha256':sha((ROOT/'data/raw/a/official/code/schedule_step3.py').read_bytes())})
    rows=[]
    # Only two hand-selected existing graph/plan pairs; no dataset scan.
    rows.append(analyze('020','round9a','round15m','tensor_packet','gap_packet',cfg))
    rows.append(analyze('045','round9b','round15n','tensor_packet','gap_packet',cfg))
    report={'kind':'bounded_static_component_ddr_diagnostic','created_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'analysis_code_commit':ANALYSIS_COMMIT,'source_commits':{'old_tensor':TENSOR_COMMIT,'fixed_gap':GAP_COMMIT,'official_E0':OFFICIAL_COMMIT},
        'source_hashes':{p:check_code(Path(p)) for p in ('src/q2/feedback/construct.py','src/q2/feedback/tensor_packet.py','src/q2/feedback/physical_frontier.py')},
        'config':cfg,'cases':{row['_comparison']['raw_saved_M_A_cycles'] and row['tensor_packet']['plan_path'].split('/')[-1].split('_')[1].split('.')[0] or '':row for row in rows},
        'limits':{'solver_calls':0,'step2_calls':0,'step3_calls':0,'E0_calls':0,'dataset_scan':False,
          'uses_official_build_scene_b_tasks':False,'uses_official_step2_or_step3_simulation':False,
          'scope':'two saved k5 graph/plan pairs (020,045), static derivation and saved-output cross-checks only'},
        'elapsed_static_script_seconds':time.perf_counter()-T0}
    # Stable explicit keys independent of path formatting.
    report['cases']={'020':rows[0],'045':rows[1]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(OUT),'elapsed_static_script_seconds':report['elapsed_static_script_seconds'],
      'cases':{case:{'U_A_cycles':r['_comparison']['U_A_cycles'],'L_B_cycles':r['_comparison']['L_B_cycles'],
        'no_cross_links_A':r['tensor_packet']['no_cross_links_guard'],'certificate_A':r['tensor_packet']['physical_frontier_certificate_A_only'].get('certified') if isinstance(r['tensor_packet']['physical_frontier_certificate_A_only'],dict) else None,
        'trigger':r['_comparison']['heuristic_trigger'],'M_A_existing':r['_comparison']['raw_saved_M_A_cycles'],'M_B_existing':r['_comparison']['raw_saved_M_B_cycles'],
        'crosschecks_A':r['tensor_packet']['base_copy_cross_checks'],'crosschecks_B':r['gap_packet']['base_copy_cross_checks']}
        for case,r in report['cases'].items()}},ensure_ascii=False))
if __name__=='__main__': main()
