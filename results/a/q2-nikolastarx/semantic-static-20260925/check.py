"""Construct only the six affected families x five core counts; no E0."""
from pathlib import Path
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,sys,time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT));HOME=Path(__file__).resolve().parent
from src.q2_nikolastarx import adaptive_semantic
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic,read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (HOME/'rows.jsonl').exists()
 started=time.perf_counter();source_names=['adaptive_semantic','baseline','direct','dag_direct','component_envelope','tree_frontier','tree_packets_first','tree_paired_leaves','vector_lanes','vector_arrival']
 source={f'src/q2_nikolastarx/{s}.py':sha(ROOT/f'src/q2_nikolastarx/{s}.py') for s in source_names}
 coverage=json.loads((ROOT/'results/a/q2-nikolastarx/specialization-coverage-20260925/coverage.json').read_text());cases=sorted(set(coverage['recognized']['tree']+coverage['recognized']['vector']));assert len(cases)==6
 old={ (r['case'],r['cores']):r for r in map(json.loads,(ROOT/'results/a/q2-nikolastarx/adaptive-static-20260924/rows.jsonl').read_text().splitlines())}
 config_path=ROOT/'data/raw/a/official/data/config.txt';config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
 reused={('062',k):f'tree-paired-leaves-pilot-20260925/run/062-k{k}/062-k{k}' for k in (2,4,5)}
 reused.update({('016',2):'vector-arrival-pilot-20260925/run/016-k2/016-k2',**{('016',k):f'direct-pilot-20260924/run/016-k{k}' for k in (4,5)}})
 rows=[]
 with ExitStack() as guard,(HOME/'rows.jsonl').open('x') as stream:
  for entry in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:guard.enter_context(patch(entry,side_effect=AssertionError('No scoring')))
  for case in cases:
   path=ROOT/f'data/raw/a/official/data/case_{case}.json';digest=sha(path);graph=json.loads(path.read_bytes())
   for k in range(1,6):
    assert digest==old[case,k]['input_sha256'];start=time.perf_counter();plan,detail=adaptive_semantic.build(graph,k,config);elapsed=time.perf_counter()-start
    view=derive_multicore_plan(graph,plan);edges=[(a,b,'original') for a,b in view['dependency_pairs']]
    for seq in plan['core_schedules']:edges.extend((a,b,'core order') for a,b in zip(seq,seq[1:]))
    check_acyclic(view['subgraph_ids'],edges,'original plus full core order')
    raw=(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode();h=hashlib.sha256(raw).hexdigest()
    row=dict(case=case,cores=k,graph_sha256=digest,plan_sha256=h,plan_bytes=len(raw),route=detail['adaptive_route'],index_constructions=detail['index_constructions'],base_construct_calls=detail['base_construct_calls'],repair_construct_calls=detail['repair_construct_calls'],trigger=detail.get('repair_trigger'),old_plan_hash_equal=h==old[case,k]['plan_sha256'],construct_seconds=elapsed,structural_validation=True)
    assert row['index_constructions']==1
    if (case,k) in reused:
     previous=ROOT/'results/a/q2-nikolastarx'/reused[case,k]/'plan.json';row['official_reference_plan']=str(previous.relative_to(ROOT));row['reference_plan_sha256']=sha(previous);row['exact_official_plan_reuse']=raw==previous.read_bytes();assert row['exact_official_plan_reuse']
    rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
   print(case,'completed five static cells',flush=True)
 assert source=={s:sha(ROOT/s) for s in source}
 report=dict(source_sha256=source,script_sha256=sha(Path(__file__)),config_sha256=sha(config_path),finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-started,cases=cases,new_static_cells=len(rows),old_hash_equal=sum(r['old_plan_hash_equal'] for r in rows),known_official_plan_equal=sum(r.get('exact_official_plan_reuse',False) for r in rows),repair_cells=[(r['case'],r['cores']) for r in rows if r['repair_construct_calls']],actual_calls=dict(top_level_constructions=30,E0=0,E1=0,E2=0),scope='30 changed-family static constructions; other94 families not reconstructed; exact reused plan scores do not imply newly measured solver timing',rows_sha256=sha(HOME/'rows.jsonl'))
 (HOME/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
