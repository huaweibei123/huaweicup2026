#!/usr/bin/env python3
"""Frozen finite budget: 8 prototype CLI processes, 0 official solver/E0/E1/E2.
Retains every attempt and measures complete child-process wall time.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,platform,subprocess,sys,time
from p1_phase_cut import recognize, encode, boundary_counts, cut_table, model_plan, atomic_json
from lower_bounds_extensions import general_certificate, verify_general, strict_family_cut_certificate
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'experiments'/'attempts'
CAP={'L1':524288,'UB':131072}
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    if (ROOT/'experiments'/'ledger.json').exists():raise FileExistsError('Do not overwrite ledger')
    specs=[('A-small-interface',m) for m in ['whole','return-cut','entry-cut','whole-tasks','auto']]
    specs += [('B-large-interface',m) for m in ['whole','return-cut','auto']]
    receipts=[]
    for i,(case,mode) in enumerate(specs):
        d=OUT/f'{i+1:02d}-{case}-{mode}';d.mkdir()
        inp=ROOT/'experiments'/'inputs'/(case+'.json');plan=d/'plan.json';diag=d/'model.json'
        argv=[sys.executable,'-B',str(ROOT/'p1_phase_cut.py'),str(inp),'--cores','1','--config',str(ROOT/'original'/'config.txt'),
              '--output',str(plan),'--diagnostics',str(diag),'--mode',mode,'--packet','1']
        start=stamp();t0=time.perf_counter()
        timed_out=False
        try:
            child=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=10)
            returncode=child.returncode;stdout=child.stdout;stderr=child.stderr
        except subprocess.TimeoutExpired as e:
            timed_out=True;returncode=None;stdout=e.stdout or b'';stderr=e.stderr or b''
        wall=time.perf_counter()-t0;finish=stamp()
        (d/'stdout.txt').write_bytes(stdout);(d/'stderr.txt').write_bytes(stderr)
        rec={'attempt':i+1,'case':case,'mode':mode,'kind':'prototype_middle_model_NOT_E0',
             'started_utc':start,'finished_utc':finish,'argv':argv,'timeout_seconds':10,
             'complete_process_wall_seconds':wall,'exit_code':returncode,'timed_out':timed_out,
             'input_sha256':digest(inp),'source_sha256':digest(ROOT/'p1_phase_cut.py'),
             'config_sha256':digest(ROOT/'original'/'config.txt'),
             'calls':{'prototype_solver_process':1,'official_solver':0,'E0':0,'E1':0,'E2':0}}
        if returncode==0:
            info=json.loads(diag.read_text());m=info['model']
            rec.update({'plan_sha256':digest(plan),'model_sha256':digest(diag),
                'model_cycles':m['cycles'],'model_upper_envelope_cycles':m['upper_envelope_cycles'],
                'model_partition_extra_bytes':m['boundary']['partition_added_copy_bytes'],
                'model_MV_overlap':m['M_V_overlap_cycles_sum_over_cores'],
                'virgin_certificate':m['virgin_capacity_certificate'],'conditional_exact_model':m['conditional_exact_model'],
                'task_count':len(set(json.loads(plan.read_text())['node_to_subgraph'].values()))})
        atomic_json(d/'receipt.json',rec);receipts.append(rec)
        if returncode!=0:break
    # C: one in-process static interface check; deliberately NO E0/CLI process.
    g=json.loads((ROOT/'experiments'/'inputs'/'C-skip-interface.json').read_text())
    _,chains,_,_,_=recognize(g)
    p=encode(chains,g['ops'],1,1,1,1,cut_position=2)
    b=boundary_counts(g,p,60);table=cut_table(g,chains[0],60)
    c={'kind':'static_boundary_count_NOT_E0','cut_after_compute_index':1,
       'interface':table[1],'boundary':b,'plan':p}
    atomic_json(ROOT/'experiments'/'C-interface.json',c)
    certs={}
    for name in ['A-small-interface','B-large-interface','C-skip-interface']:
        g=json.loads((ROOT/'experiments'/'inputs'/(name+'.json')).read_text())
        cert=general_certificate(g,1,60);assert verify_general(g,cert)
        certs[name]={'general':cert,'cut_or_serialize':strict_family_cut_certificate(g,1,60)}
    atomic_json(ROOT/'experiments'/'micro_lower_bounds.json',certs)
    ledger={'kind':'research_microtests_NOT_OFFICIAL_PERFORMANCE',
        'fixed_budget':{'prototype_solver_processes':8,'timeout_seconds_each':10,'official_E0':0},
        'actual_calls':{'prototype_solver_processes':len(receipts),'official_solver':0,'E0':0,'E1':0,'E2':0,
                        'static_interface_checks':1,'static_graph_lower_bound_certificates':len(certs)},
        'environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),
                       'concurrency':1,'cache':'not cleared','host_exclusivity':'unknown'},
        'receipts':receipts}
    atomic_json(ROOT/'experiments'/'ledger.json',ledger)
    print(json.dumps([{k:r.get(k) for k in ['attempt','case','mode','exit_code','model_cycles','model_partition_extra_bytes','model_MV_overlap',
                       'conditional_exact_model','complete_process_wall_seconds','model_upper_envelope_cycles','task_count']} for r in receipts],indent=2))
    print('C interface:',table[1],'; partition extra:',b['partition_added_copy_bytes'])
if __name__=='__main__':main()
