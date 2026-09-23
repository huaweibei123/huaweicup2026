"""Compare random and legality-guided fixed-partition move neighborhoods.

This is a bounded neighborhood study, not a claimed acceleration of the entire
adaptive solver. Both arms use the same incumbent, seed, evaluator and limits.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from search import ROOT, OFFICIAL, EVALUATOR_COMMIT, confirm, dump, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--evaluator-root', required=True, type=Path)
    args = p.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.evaluator_root, text=True).strip()
    if commit != EVALUATOR_COMMIT or subprocess.check_output(['git','status','--porcelain','--untracked-files=no'], cwd=args.evaluator_root):
        raise ValueError('Require pinned clean evaluator')
    sys.path.insert(0, str(args.evaluator_root.resolve()))
    from src.eval_exact import P1BatchEvaluator, read_config
    config = read_config(str(OFFICIAL / 'data/config.txt'))
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {'cases': ['002','051','044','014'], 'incumbents': 'Previous bounded-search selected plans; 002 uses order-preserving-v2',
                'methods': ['random','guided'], 'seed': 0, 'candidate_limits': {'default':32,'014':8},
                'max_proposals':128, 'proposal_timeout_seconds':{'default':10,'014':20},
                'search_budget_seconds_per_arm':60, 'evaluation_timeout_seconds':10,
                'e0_confirmation_timeout_seconds':30, 'workers':1,'cache_bytes':16<<20,
                'evaluator_commit':commit,'scope':'Fixed-partition, fixed-incumbent neighborhood comparison; public development data',
                'planned_before_runs':True}
    dump(args.output / 'protocol.json', protocol)
    source = args.output / 'source'; source.mkdir()
    for name in ['move_experiment.py','neighborhood.py','search.py','prototype.py','structure.py']:
        (source / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    summaries = []
    for index, case in enumerate(protocol['cases']):
        graph_path = OFFICIAL / f'data/case_{case}.json'
        graph = json.loads(graph_path.read_text())
        seed_dir = 'case002-order-preserving-v2' if case == '002' else 'case' + case
        seed_path = ROOT / 'results/a/q1-search-20260924' / seed_dir / 'best_plan.json'
        seed = json.loads(seed_path.read_text())
        case_dir = args.output / ('case' + case); case_dir.mkdir()
        seed_copy = case_dir / 'seed.json'; seed_copy.write_bytes(seed_path.read_bytes())
        seed_e0 = confirm(graph_path, seed_copy, case_dir / 'e0_seed', 30)
        limit = 8 if case == '014' else 32
        methods = ['random','guided'] if index % 2 == 0 else ['guided','random']
        for method in methods:
            output = case_dir / method; output.mkdir()
            start = time.monotonic(); deadline = start + 60
            generated = output / 'generated.json'
            command = [sys.executable,'-B',str(Path(__file__).with_name('neighborhood.py')),
                       str(graph_path),str(seed_copy),str(generated),'--method',method,
                       '--seed','0','--count',str(limit-1),'--max-proposals','128']
            generation_status = 'ok'
            try:
                run = subprocess.run(command, text=True, capture_output=True, timeout=20 if case=='014' else 10)
                (output/'proposal.stderr.txt').write_text(run.stderr)
                if run.returncode:
                    generation_status = 'error'
            except subprocess.TimeoutExpired:
                generation_status = 'timeout'
            generation_wall = time.monotonic()-start
            bundle = json.loads(generated.read_text()) if generation_status=='ok' else {'plans':[]}
            plans = [seed] + bundle['plans']
            records, best = [], None
            best_path = output / 'best_plan.json'
            with P1BatchEvaluator(graph, workers=1, cache_bytes=16<<20,timeout_seconds=10,startup_timeout_seconds=5) as evaluator:
                for candidate_index, plan in enumerate(plans):
                    if deadline-time.monotonic() < 15:
                        break
                    record = list(evaluator.evaluate_batch([plan],full=False,**config))[0]
                    record['candidate_index'] = candidate_index
                    records.append(record)
                    if record['status']=='ok' and (best is None or record['makespan']<best['makespan']):
                        best = record
                        dump(best_path,plan)
            search_seconds = time.monotonic()-start
            e0 = confirm(graph_path,best_path,output/'e0_best',30) if best else {'status':'no_incumbent'}
            summary = {'case':case,'method':method,'generation_status':generation_status,
                       'generation_wall_seconds':generation_wall, 'generation':{k:v for k,v in bundle.items() if k!='plans'},
                       'records':records,'best':best,'e0_best':e0,'e0_seed':seed_e0,
                       'e0_confirms_selected_makespan':bool(best and e0['status']=='ok' and best['makespan']==e0['makespan']),
                       'search_seconds':search_seconds,'arm_total_seconds':time.monotonic()-start,
                       'graph_sha256':sha(graph_path),'seed_sha256':sha(seed_path),
                       'config_sha256':sha(OFFICIAL/'data/config.txt'),'uv_lock_sha256':sha(ROOT/'uv.lock'),
                       'python':sys.version,'source_hashes':{p.name:sha(p) for p in source.iterdir()}}
            dump(output/'summary.json',summary)
            summaries.append({k:summary[k] for k in ['case','method','generation_status','generation_wall_seconds','search_seconds','e0_best','e0_seed','e0_confirms_selected_makespan']})
            print(json.dumps(summaries[-1]),flush=True)
            dump(args.output/'summary.json',summaries)


if __name__ == '__main__':
    main()
