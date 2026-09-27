"""Real CLI probes, same graph/plan/config, all three output paths explicit."""
from runtime import *
import subprocess
if __name__=='__main__':
 out=ROOT/'results/cli';out.mkdir(exist_ok=True);rows=[]
 for case,q,pfile in [('003',1,ROOT/'results/benchmark/003_q1_intervals/plan.json'),('080',3,ROOT/'results/solver080_q3.plan.json')]:
  row={'case':case,'q':q,'warmup':0,'repeats':1,'timing':'complete subprocess CLI including interpreter, parsing, compilation, simulation, all JSON/trace/log writes','outputs':{}}
  for name,path in [('E0',OFF/'code'),('R2',ROOT/'fast_code')]:
   folder=out/f'{case}_q{q}_{name}';folder.mkdir(exist_ok=True)
   cmd=[sys.executable,'-B',str(path/f'multicore_cut_evaluate_problem_{q}.py'),str(OFF/f'data/case_{case}.json'),str(pfile),'--config',str(OFF/'data/config.txt'),'-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'log.txt')]
   t=time.perf_counter();proc=subprocess.run(cmd,capture_output=True,text=True,timeout=90);elapsed=time.perf_counter()-t
   (folder/'stdout.txt').write_text(proc.stdout);(folder/'stderr.txt').write_text(proc.stderr);row[name+'_seconds']=elapsed;row[name+'_returncode']=proc.returncode
   if proc.returncode:raise RuntimeError(proc.stderr)
   row['outputs'][name]={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [folder/'result.json',folder/'trace.json',folder/'log.txt']}
  da=out/f'{case}_q{q}_E0';db=out/f'{case}_q{q}_R2'
  for fn in ['result.json','trace.json']:strict_equal(json.loads((da/fn).read_bytes()),json.loads((db/fn).read_bytes()))
  assert (da/'log.txt').read_bytes()==(db/'log.txt').read_bytes();row['three_outputs_equal']=True;rows.append(row);save_json(out/'summary.json',rows);print(row,flush=True)
