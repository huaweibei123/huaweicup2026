from __future__ import annotations
import json,sys,hashlib,subprocess,time,gzip,platform,os
from pathlib import Path
from graph_features import Graph
from construct import make
ROOT=Path(__file__).resolve().parents[1]
OFF=Path(os.environ.get('NPU_OFFICIAL',str(ROOT.parent/'route4_base/data/raw/a/official')))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(case,problem,k,assignment,method,gamma=1.0,lookahead=8,tag='pilot',timeout=60,graph_path=None):
    graph=Path(graph_path) if graph_path else OFF/'data'/f'case_{case:03d}.json'
    label=f'{tag}_c{case:03d}_q{problem}_k{k}_{assignment}_{method}_g{gamma}_h{lookahead}'
    target=ROOT/'runs'/label
    if target.exists():raise RuntimeError(f'run already exists {label}')
    target.mkdir(); meta={'label':label,'case':case,'problem':problem,'cores':k,'assignment':assignment,'method':method,'gamma':gamma,'lookahead':lookahead,'environment':platform.platform(),'python':sys.version,'graph_sha256':sha(graph),'config_sha256':sha(OFF/'data/config.txt')}
    start=time.perf_counter()
    try:
        g=Graph(json.loads(graph.read_text()));plan,cm=make(g,k,assignment,method,gamma,lookahead)
        planpath=target/'plan.json';planpath.write_text(json.dumps(plan,separators=(',',':')))
        meta['construct_wall_s']=time.perf_counter()-start;meta['constructor']=cm;meta['plan_sha256']=sha(planpath)
    except Exception as e:
        meta.update(status='constructor_error',error=repr(e),total_wall_s=time.perf_counter()-start)
        (target/'run.json').write_text(json.dumps(meta,indent=2));return meta
    cmd=[sys.executable,str(OFF/'code'/f'multicore_cut_evaluate_problem_{problem}.py'),str(graph),str(planpath),'--config',str(OFF/'data/config.txt'),'-o',str(target/'result.json'),'--trace-output',str(target/'trace.json'),'--log-output',str(target/'log.txt')]
    meta['command']=cmd;t=time.perf_counter()
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=timeout)
        (target/'stdout.txt').write_bytes(p.stdout);(target/'stderr.txt').write_bytes(p.stderr)
        meta['returncode']=p.returncode
        if p.returncode==0:
            r=json.loads((target/'result.json').read_text());meta['status']='ok';meta['makespan']=r['makespan'];meta['data_movement_bytes']=r['data_movement_bytes']
            if 'cache' in r:meta['cache']=r['cache']
            meta['result_sha256']=sha(target/'result.json')
        else:meta.update(status='e0_nonzero',stderr=p.stderr.decode(errors='replace'))
    except subprocess.TimeoutExpired as e:
        meta['status']='timeout';(target/'stdout.txt').write_bytes(e.stdout or b'');(target/'stderr.txt').write_bytes(e.stderr or b'')
    meta['e0_cli_wall_s']=time.perf_counter()-t;meta['total_wall_s']=time.perf_counter()-start
    (target/'run.json').write_text(json.dumps(meta,indent=2))
    for name in ['result.json','trace.json']:
        p=target/name
        if p.exists():
            raw=p.read_bytes()
            with gzip.GzipFile(str(p)+'.gz','wb',mtime=0) as f:f.write(raw)
            p.unlink()
    print(label,meta['status'],meta.get('makespan'),round(meta['total_wall_s'],3),meta.get('data_movement_bytes',{}).get('spill_added_copy_bytes'),flush=True)
    return meta

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('protocol',type=Path);args=p.parse_args()
    protocol=json.loads(args.protocol.read_text())
    results=[]
    for request in protocol['requests']:results.append(run(**request))
    out=ROOT/'analysis'/(protocol['name']+'.json');out.write_text(json.dumps(results,indent=2))
