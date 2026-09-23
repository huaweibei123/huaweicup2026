"""Run the preregistered two-call prospective trace-priority comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

from search import ROOT, OFFICIAL, dump, sha, plan_key, confirm
from profile_refine import atomic_plan, journal, objective, run_guarded
from trace_priority import reorder_pool


def read_protocol(root):
    return json.loads((root/'protocol.json').read_text())


def verify_frozen(protocol, evaluator_root):
    for name, expected in protocol['frozen_source_hashes'].items():
        assert sha(Path(__file__).with_name(name)) == expected, name
    assert sha(OFFICIAL/'data/config.txt') == protocol['config_sha256']
    for case, expected in protocol['graph_hashes'].items():
        assert sha(OFFICIAL/f'data/case_{case}.json') == expected
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=evaluator_root,text=True).strip()
    assert actual == protocol['evaluator_commit']
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=evaluator_root)


def arm(args, protocol):
    case_dir=args.root/('case'+args.case)
    folder=case_dir/args.method
    began=time.monotonic()
    summary={'method':args.method,'status':'started','records':[],'evaluations':0}
    try:
        sys.path.insert(0,str(args.evaluator_root))
        from src.eval_exact import P1BatchEvaluator, read_config
        graph_path=OFFICIAL/f'data/case_{args.case}.json'
        graph=json.loads(graph_path.read_text())
        seed_path=case_dir/'parent.json'
        parent=json.loads(seed_path.read_text())
        reference=json.loads((case_dir/'e0_parent/result.json').read_text())
        checkpoint=folder/'confirmed_plan.json'
        provisional=folder/'provisional_plan.json'
        atomic_plan(checkpoint,seed_path.read_bytes())
        atomic_plan(provisional,seed_path.read_bytes())
        best={key:reference[key] for key in ['makespan','data_movement_bytes']}
        summary['confirmed_result']=best
        search_start=time.monotonic();deadline=search_start+protocol['arm_search_budget_seconds']
        seen=folder/'seen.json';dump(seen,[plan_key(parent)])
        generated=folder/'generated.json'
        command=[sys.executable,'-B',str(Path(__file__).with_name('profile_candidates.py')),
                 str(graph_path),str(seed_path),str(seen),str(generated)]
        journal(folder,{'event':'profile_started','parent_sha256':sha(seed_path)})
        generation_started=time.monotonic()
        run=subprocess.run(command,capture_output=True,text=True,timeout=protocol['profile_generation_timeout_seconds'])
        (folder/'proposal.stdout.txt').write_text(run.stdout)
        (folder/'proposal.stderr.txt').write_text(run.stderr)
        if run.returncode:
            raise RuntimeError('profile generation failed')
        summary['generation_wall_seconds']=time.monotonic()-generation_started
        pool=json.loads(generated.read_text())
        summary['pool_keys']=[item['key'] for item in pool['candidates']]
        ranking_started=time.monotonic()
        if args.method=='entry_relief':
            order,features=reorder_pool(graph,parent,pool,reference)
        else:
            order,features=list(range(len(pool['candidates']))),{}
        summary.update(order=order,features=features,ranking_seconds=time.monotonic()-ranking_started)
        dump(folder/'ranking_before_evaluation.json',{'pool_keys':summary['pool_keys'],'order':order,'features':features})
        config=read_config(str(OFFICIAL/'data/config.txt'))
        with P1BatchEvaluator(graph,workers=protocol['workers'],cache_bytes=protocol['cache_bytes'],
                              timeout_seconds=protocol['e1_timeout_seconds'],
                              startup_timeout_seconds=protocol['e1_startup_timeout_seconds'],max_tasks_per_worker=8) as evaluator:
            for position,index in enumerate(order[:protocol['evaluation_budget_per_arm']]):
                reserve=protocol['e1_timeout_seconds']+(protocol['e1_startup_timeout_seconds'] if position==0 else 0)
                if deadline-time.monotonic()<reserve:
                    raise TimeoutError('search budget insufficient for the next planned call')
                item=pool['candidates'][index]
                candidate_dir=folder/f'candidate{position}';candidate_dir.mkdir()
                path=candidate_dir/'plan.json';dump(path,item['plan'])
                request={'pool_index':index,'position':position,'choice':item['choice'],'plan_sha256':sha(path)}
                journal(folder,dict(event='e1_dispatched',**request))
                result=list(evaluator.evaluate_batch([item['plan']],full=False,**config))[0]
                summary['evaluations']+=1
                accepted=result['status']=='ok' and objective(result)<objective(best)
                row=dict(request,result=result,accepted=accepted)
                summary['records'].append(row)
                journal(folder,dict(event='e1_returned',**row))
                if result['status']!='ok':
                    raise RuntimeError('evaluator_'+result['status'])
                if accepted:
                    best={key:result[key] for key in ['makespan','data_movement_bytes']}
                    atomic_plan(provisional,path.read_bytes())
                dump(folder/'progress.json',{'provisional':best,'evaluations':summary['evaluations'],'confirmed_parent_retained':True})
        summary['search_seconds']=time.monotonic()-search_start
        journal(folder,{'event':'final_e0_started','plan_sha256':sha(provisional)})
        final=confirm(graph_path,provisional,folder/'e0_final',protocol['arm_final_e0_timeout_seconds'])
        summary['e0_final']=final
        if final['status']!='ok':
            raise RuntimeError('final E0 failed')
        result=json.loads((folder/'e0_final/result.json').read_text())
        if objective(result)!=objective(best) or result['data_movement_bytes']!=best['data_movement_bytes']:
            raise RuntimeError('final E0 disagrees with E1')
        atomic_plan(checkpoint,provisional.read_bytes())
        summary.update(status='ok',confirmed_result=best,final_e0_matches=True,confirmed_plan_sha256=sha(checkpoint))
    except Exception as error:
        summary.update(status='error',error_type=type(error).__name__,message=str(error))
        (folder/'failure.txt').write_text(traceback.format_exc())
        journal(folder,{'event':'arm_failed','error_type':type(error).__name__,'message':str(error)})
    finally:
        summary['inside_arm_seconds']=time.monotonic()-began
        dump(folder/'summary.json',summary)
    return summary['status']=='ok'


def case(args,protocol):
    folder=args.root/('case'+args.case)
    began=time.monotonic()
    summary={'case':args.case,'status':'started','arms':{}}
    try:
        seed=folder/'parent.json'
        spec=protocol['parents'][args.case]
        if 'path' in spec:
            source=ROOT/spec['path']
            assert sha(source)==spec['sha256']
            atomic_plan(seed,source.read_bytes())
        else:
            command=[sys.executable,'-B',str(Path(__file__).with_name('search.py')),'propose',
                     str(OFFICIAL/f'data/case_{args.case}.json'),str(seed),'--kind','fixed64','--cores','4','--seed','0']
            journal(folder,{'event':'parent_constructor_started'})
            run=subprocess.run(command,text=True,capture_output=True,timeout=protocol['parent_construction_timeout_seconds'])
            (folder/'parent_constructor.stdout.txt').write_text(run.stdout)
            (folder/'parent_constructor.stderr.txt').write_text(run.stderr)
            if run.returncode:
                raise RuntimeError('parent constructor failed')
        journal(folder,{'event':'parent_e0_started','plan_sha256':sha(seed)})
        result=confirm(OFFICIAL/f'data/case_{args.case}.json',seed,folder/'e0_parent',protocol['parent_e0_timeout_seconds'])
        summary['parent_e0']=result
        if result['status']!='ok':
            raise RuntimeError('parent E0 failed')
        summary['parent_preparation_seconds']=time.monotonic()-began
        summary['parent_sha256']=sha(seed)
        for method in protocol['arm_order_by_case'][args.case]:
            arm_folder=folder/method;arm_folder.mkdir()
            command=[sys.executable,'-B',str(Path(__file__).resolve()),'arm','--root',str(args.root),
                     '--case',args.case,'--method',method,'--evaluator-root',str(args.evaluator_root)]
            start=time.monotonic()
            with (arm_folder/'runner.stdout.txt').open('w') as out,(arm_folder/'runner.stderr.txt').open('w') as err:
                run=subprocess.run(command,stdout=out,stderr=err,timeout=45)
            wall=time.monotonic()-start
            summary_path=arm_folder/'summary.json'
            if not summary_path.exists():
                raise RuntimeError('arm missing summary')
            report=json.loads(summary_path.read_text())
            report['arm_subprocess_wall_seconds']=wall
            report['charged_parent_plus_arm_seconds']=summary['parent_preparation_seconds']+wall
            summary['arms'][method]=report
            if run.returncode or report['status']!='ok':
                raise RuntimeError('arm failed; stop this case')
        original=summary['arms']['original'];guided=summary['arms']['entry_relief']
        assert original['pool_keys']==guided['pool_keys'],'Methods did not use the same candidate pool'
        summary['same_candidate_pool']=True
        summary['status']='ok'
    except Exception as error:
        summary.update(status='error',error_type=type(error).__name__,message=str(error))
        (folder/'failure.txt').write_text(traceback.format_exc())
        journal(folder,{'event':'case_failed','error_type':type(error).__name__,'message':str(error)})
    finally:
        summary['inside_case_seconds']=time.monotonic()-began
        dump(folder/'summary.json',summary)
    return summary['status']=='ok'


def recover_ledger(folder):
    counts={'e1_dispatched':0,'e1_returned':0,'parent_e0_started':0,'final_e0_started':0}
    errors=[]
    for path in sorted(folder.rglob('journal.jsonl')):
        for number,line in enumerate(path.read_text().splitlines(),1):
            if line.strip():
                try:
                    row=json.loads(line)
                    if row['event'] in counts:
                        counts[row['event']]+=1
                except (json.JSONDecodeError,KeyError) as error:
                    errors.append({'path':str(path.relative_to(folder)),'line':number,'error':str(error)})
    return {'counts':counts,'parse_errors':errors}


def experiment(args,protocol):
    verify_frozen(protocol,args.evaluator_root)
    source=args.root/'source';source.mkdir()
    for name in list(protocol['frozen_source_hashes'])+[Path(__file__).name]:
        (source/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    dump(args.root/'run_identity.json',{'protocol_sha256':sha(args.root/'protocol.json'),
                                      'source_hashes':{p.name:sha(p) for p in source.iterdir()},
                                      'evaluator_commit':protocol['evaluator_commit'],'python':sys.version})
    started=time.monotonic();reports=[]
    for name in protocol['cases']:
        folder=args.root/('case'+name);folder.mkdir()
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'case','--case',name,
                 '--root',str(args.root),'--evaluator-root',str(args.evaluator_root)]
        supervisor=run_guarded(command,folder,wall_seconds=protocol['case_outer_wall_seconds'],
                               rss_bytes=protocol['sampled_group_rss_stop_bytes'])
        dump(folder/'supervisor.json',supervisor)
        ledger=recover_ledger(folder);dump(folder/'recovered_ledger.json',ledger)
        try:
            summary=json.loads((folder/'summary.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError) as error:
            summary={'status':'missing_or_malformed_summary','message':str(error)}
        status=summary['status'] if supervisor['status']=='ok' and not ledger['parse_errors'] else 'supervised_failure'
        report={'case':name,'status':status,'supervisor':supervisor,'ledger':ledger,
                'parent_makespan':summary.get('parent_e0',{}).get('makespan'),
                'parent_preparation_seconds':summary.get('parent_preparation_seconds'),
                'arms':{method:{key:data.get(key) for key in ['status','evaluations','confirmed_result','order','ranking_seconds',
                        'generation_wall_seconds','search_seconds','arm_subprocess_wall_seconds','charged_parent_plus_arm_seconds']}
                        for method,data in summary.get('arms',{}).items()},
                'same_candidate_pool':summary.get('same_candidate_pool',False)}
        reports.append(report)
        dump(args.root/'summary.json',{'cases':reports,'experiment_wall_seconds':time.monotonic()-started})
        print(json.dumps(report),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['experiment','case','arm'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--evaluator-root',type=Path,required=True)
    p.add_argument('--case',choices=['008','003','044'])
    p.add_argument('--method',choices=['original','entry_relief'])
    args=p.parse_args();args.root=args.root.resolve();args.evaluator_root=args.evaluator_root.resolve()
    protocol=read_protocol(args.root)
    if args.mode=='experiment':
        experiment(args,protocol)
    elif args.mode=='case':
        sys.exit(0 if case(args,protocol) else 1)
    else:
        sys.exit(0 if arm(args,protocol) else 1)


if __name__=='__main__':
    main()
