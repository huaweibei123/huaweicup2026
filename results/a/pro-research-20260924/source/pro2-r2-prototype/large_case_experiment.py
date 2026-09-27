"""Largest eligible-op-count case, same 300s/8-E0 caps; engineering stress only."""
import json,subprocess,sys,time,os,hashlib
from pathlib import Path
from scan import ROOT
OUT=Path('/mnt/data/r2_research/runs/large');OUT.mkdir(exist_ok=False)
protocol={'case':14,'problem':2,'cores':4,'budget_seconds':300,'evaluation_cap':8,'per_evaluation_seconds':60,'order':['baseline','structured'],'purpose':'largest-size engineering stress, one trial, not a sealed performance benchmark','source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}}
(OUT/'PROTOCOL.json').write_text(json.dumps(protocol,indent=2));rows=[]
for policy in protocol['order']:
 dest=OUT/policy;cmd=[sys.executable,str(Path(__file__).parent/'solve.py'),str(ROOT/'data/case_014.json'),'-n','4','-q','2','--official',str(ROOT),'--output',str(dest),'--time-limit','300','--max-evaluations','8','--per-evaluation-timeout','60','--policy',policy]
 t=time.perf_counter();r=subprocess.run(cmd,capture_output=True,timeout=320,env={**os.environ,'PYTHONHASHSEED':'0','PYTHONDONTWRITEBYTECODE':'1'})
 (OUT/f'{policy}.stdout').write_bytes(r.stdout);(OUT/f'{policy}.stderr').write_bytes(r.stderr)
 row=json.loads((dest/'solve.json').read_text());row.update(process_wall_seconds=time.perf_counter()-t,returncode=r.returncode)
 rows.append(row);(OUT/'summary.json').write_text(json.dumps(rows,indent=2));print(policy,row,flush=True)
