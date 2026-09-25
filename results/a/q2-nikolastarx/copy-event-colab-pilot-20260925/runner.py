"""Fixed-owner three-cell Colab CPU ablation; E0 only, not a complete cold solver."""
from pathlib import Path
import argparse, hashlib, json, os, platform, sys, time
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
CASES = ('005', '009', '015')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def construct(case, out):
    from src.q2_nikolastarx.direct import derive_multicore_plan
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.copy_event_retime import retime
    raw = ROOT / 'data/raw/a/official/data'
    graph = json.loads((raw / f'case_{case}.json').read_bytes())
    cfg = {**read_evaluation_config(raw/'config.txt'), **read_scene_b_config(raw/'config.txt')}
    seed = json.loads((ROOT/'seeds'/f'{case}-k5.json').read_bytes())
    start = time.perf_counter()
    plan, detail = retime(graph, seed, cfg)
    old_view = derive_multicore_plan(graph, seed)
    new_view = derive_multicore_plan(graph, plan)
    assert old_view['mapping']==new_view['mapping'] and old_view['core_by_subgraph']==new_view['core_by_subgraph']
    save(out/'plan.json', plan)
    save(out/'candidate.json', {'case':case, 'cores':5,
         'scope':'Fixed selected-plan ablation, not cold complete solver',
         'detail':detail, 'construct_seconds':time.perf_counter()-start,
         'seed_plan_sha256':sha(ROOT/'seeds'/f'{case}-k5.json'),
         'plan_sha256':sha(out/'plan.json')})

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--construct', choices=CASES)
    args = ap.parse_args()
    if args.construct:
        construct(args.construct, args.output); return
    start = time.perf_counter(); deadline = start + 360
    manifest_path = ROOT/'capsule-manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    for rel, expected in manifest['files'].items():
        p=(ROOT/rel).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=expected:
            raise ValueError('capsule identity mismatch: '+rel)
    from src.q2_nikolastarx.evaluate_feedback import monitored
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {'status':'running', 'capsule_sha256':sha(manifest_path),
        'solver_source_commit':manifest['solver_source_commit'],
        'runner_source_commit':manifest['runner_source_commit'],
        'platform':platform.platform(),'python':sys.version,'cpu_count':os.cpu_count(),
        'limits':{'cases':3,'workers':1,'E0':3,'E2':0,'retries':0,
                  'stage_seconds':60,'batch_seconds':360,'rss_bytes':4<<30},
        'calls':{'construct':0,'E0':0,'E2':0},'rows':[]}
    save(args.output/'batch.json',receipt)
    try:
        for case in CASES:
            if time.perf_counter()>=deadline: raise TimeoutError('batch deadline')
            folder=args.output/(case+'-k5'); folder.mkdir()
            row={'case':case,'cores':5,'old_M':manifest['comparison'][case]['old_M']}
            receipt['rows'].append(row); receipt['calls']['construct']+=1
            save(args.output/'batch.json',receipt)
            process=monitored([sys.executable,'-B',str(Path(__file__).resolve()),
                '--construct',case,'--output',str(folder)],folder/'construct-process',
                min(deadline,time.perf_counter()+60),4<<30)
            row['construct_process']=process
            if process['status']!='ok' or process['surviving_pids']:
                raise RuntimeError('construct failed; no retry')
            raw=ROOT/'data/raw/a/official/data'
            e0=[sys.executable,'-B',str(ROOT/'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                str(raw/f'case_{case}.json'),str(folder/'plan.json'),
                '--config',str(raw/'config.txt'),'--output',str(folder/'result.json'),
                '--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'official.log')]
            receipt['calls']['E0']+=1; save(args.output/'batch.json',receipt)
            process=monitored(e0,folder/'e0-process',min(deadline,time.perf_counter()+60),4<<30)
            row['e0_process']=process
            if process['status']!='ok' or process['surviving_pids']:
                raise RuntimeError('E0 failed; no retry')
            result=json.loads((folder/'result.json').read_bytes())
            if result['scene']!='B' or result['num_cores']!=5 or type(result['makespan']) is not int:
                raise ValueError('unexpected official result')
            row.update(M=result['makespan'],movement=result['data_movement_bytes'],
                       result_sha256=sha(folder/'result.json'),plan_sha256=sha(folder/'plan.json'),
                       M_reduction_fraction=1-result['makespan']/row['old_M'])
            save(args.output/'batch.json',receipt)
            print(json.dumps({k:row[k] for k in ('case','old_M','M','M_reduction_fraction')}),flush=True)
        receipt['status']='completed'
    except BaseException as error:
        receipt.update(status='stopped',error=repr(error)); raise
    finally:
        receipt['batch_seconds']=time.perf_counter()-start
        save(args.output/'batch.json',receipt)

if __name__=='__main__': main()
