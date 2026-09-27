"""Sequential same-resource, same dual-cap comparison, frozen before new cases' E0."""
import json,time,hashlib,subprocess,sys,os
from pathlib import Path
from scan import ROOT
OUT=Path('/mnt/data/r2_research/runs/paired');OUT.mkdir(exist_ok=False)
# No E0 outcomes of these graph IDs used in constructor tuning. Families partly shared with exploration.
matrix=[(46,2,4),(89,2,4),(95,2,4),(21,2,4),(48,2,4),(63,2,4),(46,3,4),(89,3,4),(95,3,4),(21,3,4)]
freeze={'matrix':matrix,'time_limit_seconds':60,'max_evaluations':24,'per_evaluation_timeout':25,'certificate_tolerance':.01,'processes':1,'policy_order':'alternating','label':'follow-up cases; not independent cross-family sealed validation','frozen_source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}}
(OUT/'FROZEN_PROTOCOL.json').write_text(json.dumps(freeze,indent=2));rows=[]
for i,(case,q,k) in enumerate(matrix):
    for policy in (['baseline','structured'] if i%2==0 else ['structured','baseline']):
        dest=OUT/f'case_{case:03d}_p{q}_k{k}_{policy}'
        cmd=[sys.executable,str(Path(__file__).parent/'solve.py'),str(ROOT/f'data/case_{case:03d}.json'),'-q',str(q),'-n',str(k),'--output',str(dest),'--official',str(ROOT),'--policy',policy,'--time-limit','60','--max-evaluations','24']
        start=time.perf_counter();r=subprocess.run(cmd,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'},timeout=90)
        (OUT/f'{dest.name}.stdout').write_bytes(r.stdout);(OUT/f'{dest.name}.stderr').write_bytes(r.stderr)
        if not (dest/'solve.json').exists():raise RuntimeError(r.stderr.decode(errors='replace'))
        row=json.loads((dest/'solve.json').read_text());row.update(case=case,process_wall_seconds=time.perf_counter()-start,returncode=r.returncode);rows.append(row)
        print(case,q,k,policy,row['best_makespan'],row['best_name'],row['calls'],round(row['elapsed_seconds'],2),row['stop_reason'],flush=True)
        (OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
