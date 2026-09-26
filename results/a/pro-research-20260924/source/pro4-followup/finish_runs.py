import json,subprocess,time,os,sys
from pathlib import Path
from run_experiments import run
ROOT=Path(__file__).resolve().parents[1];OFF=ROOT.parent/'route4_base/data/raw/a/official'
rows=[]
# Predeclared cross-scene / core-count diagnostics, after the frozen 12-graph validation.
for case,problem,k,assignment,method,gamma in [
 (8,2,4,'component','word',1),(8,1,4,'component','coarse',1),(8,1,4,'component','stage_tail',.5),
 (2,2,2,'chain','coarse',1),(2,2,2,'chain','stage_tail',.5),
 (2,2,5,'chain','coarse',1),(2,2,5,'chain','stage_tail',.5),
 (8,2,2,'component','word',1),(8,2,5,'component','word',1)]:
 rows.append(run(case,problem,k,assignment,method,gamma,tag='transfer1',timeout=120))
(ROOT/'analysis/transfer1.json').write_text(json.dumps(rows,indent=2))
# Actual independent solver cold CLI runs. No label training or other evaluation job runs concurrently.
records=[]
for case,problem,strategy,repeat,budget in [(2,2,s,r,30) for r in range(3) for s in ['baseline','frontier']]+[(14,2,s,0,300) for s in ['baseline','frontier']]+[(8,1,'frontier',0,30)]:
 name=f'solve_c{case:03d}_q{problem}_{strategy}_r{repeat}'
 evidence=ROOT/'end_to_end'/name;evidence.parent.mkdir(exist_ok=True)
 cmd=[sys.executable,str(ROOT/'src/solve.py'),str(OFF/'data'/f'case_{case:03d}.json'),'--official',str(OFF),'--cores','4','--problem',str(problem),'--strategy',strategy,'--budget',str(budget),'--output',str(evidence.parent/(name+'_plan.json')),'--evidence',str(evidence)]
 t=time.perf_counter()
 try:
  cp=subprocess.run(cmd,capture_output=True,timeout=budget+20)
  wall=time.perf_counter()-t
  (evidence.parent/(name+'_stdout.txt')).write_bytes(cp.stdout);(evidence.parent/(name+'_stderr.txt')).write_bytes(cp.stderr)
  r=json.loads((evidence/'solver_report.json').read_text()) if (evidence/'solver_report.json').exists() else {}
  records.append(dict(name=name,case=case,problem=problem,strategy=strategy,repeat=repeat,outer_wall_s=wall,returncode=cp.returncode,report=r))
  print(name,cp.returncode,r.get('best_makespan'),round(wall,3),r.get('e0_calls'),flush=True)
 except subprocess.TimeoutExpired:
  records.append(dict(name=name,case=case,status='outer_timeout',outer_wall_s=time.perf_counter()-t))
 (ROOT/'analysis/end_to_end.json').write_text(json.dumps(records,indent=2))
