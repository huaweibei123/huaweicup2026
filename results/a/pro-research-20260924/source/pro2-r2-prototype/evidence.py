"""Unmodified official CLI runner; each evaluation retains full native artifacts."""
import os,sys,json,time,hashlib,subprocess,platform,gzip,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEFAULT_OFFICIAL=Path(os.environ.get('HUAWEI_OFFICIAL','/mnt/data/r2_bundle/data/raw/a/official'))
CODE_HASH='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run_e0(graph,plan,problem,out,timeout=40,official=DEFAULT_OFFICIAL,compress=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);pp=out/'plan.json'
    pp.write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n')
    paths=[out/'result.json',out/'trace.json',out/'log.txt']
    script='singlecore_evaluate.py' if problem==0 else f'multicore_cut_evaluate_problem_{problem}.py'
    cmd=[sys.executable,str(official/'code'/script),str(Path(graph).resolve())]
    if problem!=0:cmd.append(str(pp.resolve()))
    cmd+=['--config',str(official/'data/config.txt'),'-o',str(paths[0]),'--trace-output',str(paths[1]),'--log-output',str(paths[2])]
    meta={'graph':str(graph),'graph_hash':sha(graph),'plan_hash':sha(pp),'config_hash':sha(official/'data/config.txt'),'official_code_hash':CODE_HASH,'problem':problem,'cores':len(plan['core_schedules']),
        'python':sys.version,'platform':platform.platform(),'command':cmd,'timeout_seconds':timeout,'environment':{'PYTHONHASHSEED':'0','PYTHONDONTWRITEBYTECODE':'1'},'processes':1,'mode':'unmodified_official_full_cli'}
    env=os.environ.copy();env.update(meta['environment']);t=time.perf_counter()
    try:
        r=subprocess.run(cmd,capture_output=True,timeout=timeout,env=env)
        meta.update(returncode=r.returncode,status='ok' if r.returncode==0 else 'official_error')
        (out/'stdout.txt').write_bytes(r.stdout);(out/'stderr.txt').write_bytes(r.stderr)
    except subprocess.TimeoutExpired as exc:
        meta.update(status='timeout',returncode=None)
        (out/'stdout.txt').write_bytes(exc.stdout or b'');(out/'stderr.txt').write_bytes(exc.stderr or b'')
    meta['official_cli_seconds']=time.perf_counter()-t
    if meta['status']=='ok':
        data=json.loads(paths[0].read_text());meta['makespan']=data['makespan'];meta['movement']=data['data_movement_bytes']
        if 'cache_stats' in data:meta['cache_stats']=data['cache_stats']
    else:
        meta['error']=(out/'stderr.txt').read_text(errors='replace')[-8000:]
    meta['artifacts']={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths if p.exists()}
    if compress:
        zstart=time.perf_counter()
        for p in paths[:2]:
            if p.exists():
                with p.open('rb') as src,gzip.open(str(p)+'.gz','wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
                p.unlink()
        meta['archive_seconds']=time.perf_counter()-zstart
    (out/'run.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    return meta
