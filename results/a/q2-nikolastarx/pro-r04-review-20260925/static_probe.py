"""One frozen 003/k2 construction pair, zero official evaluator calls.

Run only once into a fresh directory. The graph selects the experiment, never
an algorithm branch. This is not a complete solver or leaderboard submission.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def worker(args):
    started = time.perf_counter()
    from src.q2_nikolastarx.gap_candidate import build_with_witness
    from src.q2_nikolastarx.gap_corridor import repair_gap_witness
    from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
    from src.q2_nikolastarx.direct import derive_multicore_plan
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config

    manifest = json.loads((ROOT/'results/a/q2-nikolastarx/gap-full500-20260925/manifest.json').read_bytes())
    row = next(r for r in manifest['rows'] if r['case']=='003' and r['cores']==2)
    raw = (args.raw_root/'case_003.json').read_bytes()
    config_path = args.raw_root/'config.txt'
    assert sha(raw) == row['graph']['sha256']
    assert sha(config_path.read_bytes()) == manifest['config']['sha256']
    graph = json.loads(raw)
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    at = time.perf_counter()
    seed, seed_meta, witness = build_with_witness(graph, 2, config)
    seed_seconds = time.perf_counter()-at
    at = time.perf_counter()
    repaired, detail = repair_gap_witness(graph, cores=2, **witness)
    repair_seconds = time.perf_counter()-at
    derive_multicore_plan(graph, repaired)
    before = mandatory_copy_work(graph, seed, config['bandwidth'])['transfer_bytes']
    after = mandatory_copy_work(graph, repaired, config['bandwidth'])['transfer_bytes']
    assert (before,after)==(detail['pre_step2_bytes_before'],detail['pre_step2_bytes_after'])
    assert after <= before
    if after == before:
        repaired = seed
    # This known seed is used only after construction to audit unchanged behavior.
    oldpath = 'results/a/q2-nikolastarx/gap-solver-pilot-20260925/run/003-k2/plan.json.gz'
    oldbytes = subprocess.check_output(['git','show','a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075:'+oldpath],cwd=ROOT)
    assert seed == json.loads(gzip.decompress(oldbytes)), 'seed construction changed'
    artifacts = {}
    witness_json = {**witness, 'delays': [[a,b,v] for (a,b),v in witness['delays'].items()]}
    for name,value in (('seed-plan',seed),('repaired-plan',repaired),('seed-witness',witness_json)):
        data=encode(value)
        packed=gzip.compress(data,mtime=0)
        (args.output/(name+'.json.gz')).write_bytes(packed)
        artifacts[name]={'raw_sha256':sha(data),'gzip_sha256':sha(packed),'raw_bytes':len(data)}
    result = {'source_commit':args.source_commit,'case':'003','cores':2,
              'graph_sha256':sha(raw),'config_sha256':sha(config_path.read_bytes()),
              'seed_matches_prior_pilot_plan':True,'seed_metadata':seed_meta,
              'repair':detail,'before_bytes':before,'after_bytes':after,
              'seed_seconds':seed_seconds,'repair_seconds':repair_seconds,
              'child_read_import_construct_verify_write_seconds':time.perf_counter()-started,
              'calls':{'E0':0,'E1':0,'E2':0},'artifacts':artifacts,
              'scope':'One candidate construction pair only; no baseline construction, online scoring or final E0; not a solver runtime or official performance.'}
    (args.output/'result.json').write_bytes(encode(result))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--raw-root',type=Path,required=True)
    p.add_argument('--output',type=Path,default=HERE/'static-003-k2')
    p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    args.output=args.output.resolve()
    if args.worker:
        worker(args)
        return
    started=time.perf_counter()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source_commit
    paths=subprocess.check_output(['git','ls-files','src/q2_nikolastarx','src/q1_nikolastarx','data/raw/a/official/code'],cwd=ROOT,text=True).splitlines()
    paths+=[Path(__file__).relative_to(ROOT).as_posix()]
    sources={}
    for path in paths:
        if path.endswith('.py'):
            raw=(ROOT/path).read_bytes()
            assert raw==subprocess.check_output(['git','show',args.source_commit+':'+path],cwd=ROOT),path
            sources[path]=sha(raw)
    args.output.mkdir(parents=True,exist_ok=False)
    receipt={'started_at':datetime.now(timezone.utc).isoformat(),'source_commit':args.source_commit,
             'source_sha256':sources,'budget':{'seed_builds':1,'repairs':1,'workers':1,'child_wall_seconds':30,'retries':0,'E0':0,'E2':0},
             'status':'started','resource_context':'Shared macOS ARM64; independent P2 full500 single worker and possible P3 E0 single worker; not exclusive timing.'}
    (args.output/'process.json').write_bytes(encode(receipt))
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--source-commit',args.source_commit,
             '--raw-root',str(args.raw_root),'--output',str(args.output)]
    try:
        run=subprocess.run(command,cwd=ROOT,timeout=30,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        receipt.update(status='completed' if run.returncode==0 else 'failed',returncode=run.returncode)
        (args.output/'stdout.txt').write_text(run.stdout)
        (args.output/'stderr.txt').write_text(run.stderr)
    except subprocess.TimeoutExpired:
        receipt.update(status='timeout')
    receipt.update(finished_at=datetime.now(timezone.utc).isoformat(),
                   total_harness_seconds=time.perf_counter()-started)
    (args.output/'process.json').write_bytes(encode(receipt))
    print(json.dumps({k:receipt[k] for k in ('status','source_commit','total_harness_seconds')}))
    if receipt['status']!='completed':
        raise SystemExit(1)


if __name__=='__main__':
    main()
