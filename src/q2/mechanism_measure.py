"""Two fixed P2 CLI measurements; no construction, search, E1 or E2.

Authorization: Issue33#5804640018. Prepare is zero-evaluation. Run never retries.
Original JSON bytes remain untouched, including mapping insertion order.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

from .job_control import run_job

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / 'data/raw/a/official'
AUTH = 'https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5804640018'
EXPECTED = {'parent': 'ed987c6abf0764f9f64d0f99fd9eec52fbd3729f13d82f2404a9fad8a4e3dbd7',
            'child': 'a5fd82ce49f2e6bc96b4bbefe2cc1c9f219412997c831decb04c6cd968c04a08'}

def utc(): return datetime.now(timezone.utc).isoformat()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def rel(path): return path.relative_to(ROOT).as_posix()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
def copy_checked(source, target, expected):
    raw = source.read_bytes()
    if digest(raw) != expected: raise ValueError('fixed input hash mismatch: ' + target.name)
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
def fixed_code():
    manifest = read(ROOT/'docs/a/source-manifest.json')
    entries = sorted((x for x in manifest['files'] if x['path'].startswith('code/')), key=lambda x:x['path'])
    for entry in entries:
        if sha(OFFICIAL/entry['path']) != entry['sha256']: raise ValueError('official source changed')
    combined = ''.join(x['path']+'\t'+x['sha256']+'\n' for x in entries).encode()
    if digest(combined) != manifest['official_code_hash']: raise ValueError('aggregate mismatch')
    return manifest['official_code_hash']

def timeline_summary(result):
    """Observed occupied/idle interval totals, not a causal waiting attribution."""
    answer={}
    for core in result['per_core_timeline']:
        pipes={}
        for op in core['ops']:pipes.setdefault(op['pipe'],[]).append((op['start'],op['end']))
        stats={}
        for pipe, intervals in pipes.items():
            merged=[]
            for lo,hi in sorted(intervals):
                if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
                else:merged.append([lo,hi])
            busy=sum(hi-lo for lo,hi in merged)
            stats[pipe]={'op_count':len(intervals),'occupied_union_cycles':busy,
                         'unoccupied_in_global_horizon_cycles':result['makespan']-busy}
        answer[str(core['core_id'])]=stats
    return answer

def prepare(folder, audit, preparation):
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'.gitignore').write_text('raw/\n*.tmp\n', encoding='utf8')
    identity = read(audit/'audit.json')
    for filename, key in [('case_044.json','data/case_044.json'),('config.txt','data/config.txt')]:
        if sha(OFFICIAL/'data'/filename) != identity['inputs'][key]['sha256']:
            raise ValueError('graph/config changed')
    copy_checked(audit/'q1/seed.json',folder/'raw/inputs/parent.json',EXPECTED['parent'])
    copy_checked(audit/'q1candidate/round0/candidate1/plan.json',folder/'raw/inputs/child.json',EXPECTED['child'])
    reused = {}
    for kind in ['components','word']:
        for filename in ['plan.json','run.json','result.json.gz','trace.json.gz','log.txt','stdout.txt','stderr.txt']:
            key = 'pro2/runs/resource_word/case_008_p2_'+kind+'/'+filename
            target = folder/'raw/reused008'/kind/filename
            copy_checked(audit/key,target,identity['records'][key]['sha256'])
            reused[rel(target)] = sha(target)
    sources = {}
    for filename in ['mechanism_measure.py','job_control.py','monitor.py']:
        source = ROOT/'src/q2'/filename
        target = folder/'source'/filename
        copy_checked(source,target,sha(source)); sources[rel(source)] = sha(source)
    now = utc()
    prep = read(preparation)
    prep_start = datetime.fromisoformat(prep['utc'].replace('Z','+00:00'))
    protocol = {'authorization':AUTH,'prepared_at_utc':now,
      'preparation':{**prep,'recorded_through_freeze_seconds':(datetime.now(timezone.utc)-prep_start).total_seconds(),
          'excluded':'Prior interactive authorization/source review; later git freeze publication separately recorded'},
      'input_source_commit':'13d6b0298f944d3c0bfdf3172191f1ac25a50379',
      'reused_source_commit':'3a4505d4101e23d54580d15560da3820e02d05da',
      'driver_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
      'official_code_hash':fixed_code(),'source_hashes':sources,'plan_hashes':EXPECTED,
      'graph_sha256':identity['inputs']['data/case_044.json']['sha256'],
      'config_sha256':identity['inputs']['data/config.txt']['sha256'],
      'uv_lock_sha256':sha(ROOT/'uv.lock'),'python':platform.python_version(),'platform':platform.platform(),
      'new_calls_max':2,'call_seconds':30,'outer_seconds':180,'no_launch_after_seconds':120,
      'cleanup_reserve_seconds':60,'supervisor_job_deadline_seconds':170,
      'workers':1,'memory_sample_stop_bytes':4*1024**3,'retry':False,
      'failure':'First unexpected failure stops; explicit official semantic rejection retained without plan repair',
      'reused_hashes':reused,'reused008':identity['pro008']['existing_p2_evidence'],
      'existing044_p1':identity['q1044']['existing_p1_evidence'],
      'scope':'Fixed plan mechanism comparison, not construction performance; 044 only core0 active'}
    save(folder/'protocol.json',protocol)
    print(json.dumps({'prepared':rel(folder),'protocol_sha256':sha(folder/'protocol.json'),'new_calls':0}))

def worker(folder, started):
    if sys.stdin.readline().strip() != 'GO': raise RuntimeError('Job gate missing')
    protocol = read(folder/'protocol.json'); rows=[]
    def persist(): save(folder/'calls.json',{'maximum':2,'charged':len(rows),'calls':rows})
    persist()
    try:
        if fixed_code()!=protocol['official_code_hash']: raise ValueError('official identity changed')
        if sha(OFFICIAL/'data/case_044.json')!=protocol['graph_sha256']: raise ValueError('graph changed')
        if sha(OFFICIAL/'data/config.txt')!=protocol['config_sha256']: raise ValueError('config changed')
        for label in ['parent','child']:
            elapsed=time.monotonic()-started
            if elapsed>=120: break
            plan=folder/'raw/inputs'/f'{label}.json'
            if sha(plan)!=EXPECTED[label]: raise ValueError('plan changed')
            directory=folder/'raw/calls'/label; directory.mkdir(parents=True)
            command=[getattr(sys,'_base_executable',sys.executable),'-X','utf8','-B',
              rel(OFFICIAL/'code/multicore_cut_evaluate_problem_2.py'),rel(OFFICIAL/'data/case_044.json'),rel(plan),
              '--config',rel(OFFICIAL/'data/config.txt'),'-o',rel(directory/'result.json'),
              '--trace-output',rel(directory/'trace.json'),'--log-output',rel(directory/'summary.txt')]
            row={'label':label,'charged_index':len(rows)+1,'reserved_elapsed':elapsed,'status':'reserved',
                 'command':['python',*command[1:]],'plan_sha256':sha(plan),'launched':False}
            rows.append(row);persist()  # unknown/failed launches remain charged
            launch=time.monotonic();row.update(launch_attempted=True);persist()
            with (directory/'stdout.txt').open('wb') as stdout,(directory/'stderr.txt').open('wb') as stderr:
                try:
                    proc=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,
                         env=dict(os.environ,PYTHONHASHSEED='0',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1'))
                    row.update(launched=True,pid=proc.pid);persist()
                    try:
                        code=proc.wait(timeout=max(0,30-(time.monotonic()-launch)))
                    except subprocess.TimeoutExpired:
                        proc.kill();proc.wait(timeout=5);row['status']='timeout';code=proc.returncode
                    row.update(returncode=code,call_wall_seconds=time.monotonic()-launch)
                except Exception as exc:
                    row.update(status='launch_or_wait_error',error_type=type(exc).__name__,error=str(exc))
            if row['status']=='reserved':
                if row.get('returncode')==0:
                    if not all((directory/n).is_file() for n in ['result.json','trace.json','summary.txt']):
                        row['status']='missing_output'
                    else:
                        result=read(directory/'result.json')
                        row.update(status='ok',makespan=result['makespan'],movement=result['data_movement_bytes'],
                           memory_peak=result['memory_peak_by_core'],step3=result['step3_by_core'],
                           cross_core_transfers=result['cross_core_transfers'],timeline_summary=timeline_summary(result))
                else:
                    error=(directory/'stderr.txt').read_text(encoding='utf8',errors='replace')
                    tokens=('subgraph priority order violates an intra-core dependency',
                            'dependency cycle','[STEP2 ERROR] no spill victim')
                    official_trace=('multicore_cut_evaluate_problem_2.py' in error or 'evaluation_validation.py' in error)
                    row['status']='official_rejection' if official_trace and any(x in error for x in tokens) else 'unexpected_error'
            row['completed_elapsed']=time.monotonic()-started;persist()
            if row['status'] not in ['ok','official_rejection']:break
    except Exception as exc:
        save(folder/'failure.json',{'type':type(exc).__name__,'message':str(exc),'elapsed':time.monotonic()-started})
    finally:
        persist()
    return 0 if len(rows)==2 and all(x['status'] in ['ok','official_rejection'] for x in rows) else 2

def package(folder, started, control):
    ledger=read(folder/'calls.json') if (folder/'calls.json').exists() else {'charged':'unknown','calls':[]}
    rows=ledger['calls']; protocol=read(folder/'protocol.json')
    comparison={'scope':'Observed event timing only; no fixed-duration causal counterfactual',
       'memory_edge_evidence':'Official step3 reports dependency counts; full adjacency is not independently reconstructed',
       'idle_evidence':'Per-pipe union of occupied intervals; unoccupied horizon is not attributed to one cause'}
    if len(rows)==2 and all(r['status']=='ok' for r in rows):
        results=[read(folder/'raw/calls'/r['label']/'result.json') for r in rows]
        def events(result):
            return [[core['core_id'],[[op.get(k) for k in ['op_id','op','pipe','start','end','duration']]
                for op in core['ops']]] for core in result['per_core_timeline']]
        comparison.update(same_ordered_op_events_ignoring_subgraph_label=events(results[0])==events(results[1]),
                          same_step3_summary=results[0]['step3_by_core']==results[1]['step3_by_core'],
                          makespan_delta=rows[1]['makespan']-rows[0]['makespan'])
    save(folder/'comparison.json',comparison)
    archive=folder/'evidence.zip';members=[]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted((folder/'raw').rglob('*')):
            if path.is_file():
                raw=path.read_bytes(); name=path.relative_to(folder/'raw').as_posix();z.writestr(name,raw)
                members.append({'path':name,'bytes':len(raw),'sha256':digest(raw)})
    with zipfile.ZipFile(archive) as z:
        for m in members:
            raw=z.read(m['path'])
            if len(raw)!=m['bytes'] or digest(raw)!=m['sha256']:raise ValueError('archive verification failed')
    save(folder/'evidence.manifest.json',{'archive':'evidence.zip','bytes':archive.stat().st_size,'sha256':sha(archive),'members':members})
    with (folder/'metrics.csv').open('w',encoding='utf8',newline='') as f:
        fields=['label','status','makespan','call_wall_seconds','partition_added_copy_bytes','spill_added_copy_bytes','added_copy_bytes']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:row.get(k,row.get('movement',{}).get(k,'')) for k in fields})
    report=['# Q2 fixed-plan A/B mechanism check','',
       'Only original case044 parent/child plans were evaluated by unmodified P2 E0. No plan construction or search occurred.',
       '044 uses four configured cores but all 1364 operations are on core0. Original plan bytes and mapping order are preserved.',
       '', '| Plan | Status | P2 cycles | Added COPY bytes | Spill bytes | CLI wall s |', '|---|---|---:|---:|---:|---:|']
    for r in rows:report.append(f"| {r['label']} | {r['status']} | {r.get('makespan','unknown')} | {r.get('movement',{}).get('added_copy_bytes','unknown')} | {r.get('movement',{}).get('spill_added_copy_bytes','unknown')} | {r.get('call_wall_seconds','unknown')} |")
    report+=['','Original A evidence for these exact plans: 116227 -> 126094 cycles; source 13d6b0298f944d3c0bfdf3172191f1ac25a50379.',
       'Original Pro case008 B evidence is reused, not rerun: components 123060 -> word 63768, unchanged per-op cores, differing mapping insertion order; source 3a4505d4101e23d54580d15560da3820e02d05da.',
       'Cross-scene absolute values do not rank algorithms. These compound plan changes do not isolate one causal variable. No full-domain, independent Pro rerun, construction speed or optimality claim.',
       'Observed timing comparison: '+json.dumps(comparison,ensure_ascii=False)+'. Per-core occupied/idle intervals, memory peaks and Step3 dependency counts are in calls.json. Idle totals are not a causal FIFO-wait decomposition.',
       '', 'Task fields: goal=fixed-plan mechanism observation; input=protocol identities; output=full evidence/ledger/metrics; limits=2 calls, 30s each, one worker, 180s outer; acceptance=identities and complete evidence with failures retained; milestone=bounded mechanism checkpoint, not final algorithm acceptance.',
       '', 'Timing: recorded preparation and Git freeze precede T0 and are reported separately. T0 includes job startup, official CLI, output reading, archive/report and delivery. At 120s no new evaluator starts. Existing-plan evaluation is not solver construction wall time.',
       'controller.json, run.json and publication.json separate local measurement, packaging and publication endpoints. Missing publication receipt means delivery is not confirmed within the window.',
       '', 'Full original outputs are in evidence.zip; controller logs remain alongside. No E1/E2/P3, no retries. Memory supervision is a sampled 4 GiB stop threshold, not a hard allocation guarantee.',
       '', 'New measurement command: `python -X utf8 -B -m src.q2.mechanism_measure run --folder '+rel(folder)+'`.',
       'Inputs/source freeze and existing failure evidence must not be overwritten for a rerun. A fresh run requires new scheduling.']
    (folder/'REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    save(folder/'local-completion.json',{'utc':utc(),'charged':ledger['charged'],'statuses':[r['status'] for r in rows],
       'control_status':control['status'],'elapsed_through_packaging':time.monotonic()-started,
       'within_180_seconds':time.monotonic()-started<=180,'publication':'pending'})
    print(json.dumps({'charged':ledger['charged'],'rows':[{k:r.get(k) for k in ['label','status','makespan','movement','call_wall_seconds']} for r in rows],
       'elapsed':time.monotonic()-started,'control':control['status']},ensure_ascii=False),flush=True)

def run(folder):
    if (folder/'run.json').exists():raise FileExistsError('Never reset a run or its budget')
    protocol=read(folder/'protocol.json')
    for name, expected in protocol['source_hashes'].items():
        if sha(ROOT/name)!=expected:raise ValueError('driver source changed after freeze')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    started=time.monotonic()
    save(folder/'run.json',{'utc_t0':utc(),'monotonic_t0':started,'deadline_monotonic':started+180,
         'as_run_commit':head,'protocol_sha256':sha(folder/'protocol.json'),'authorization':AUTH})
    command=[sys.executable,'-X','utf8','-B','-m','src.q2.mechanism_measure','worker',
             '--folder',rel(folder),'--started',str(started)]
    control=run_job(command,cwd=ROOT,folder=folder,started=started,deadline=started+170)
    save(folder/'controller.json',control)
    package(folder,started,control)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run','worker'])
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--audit',type=Path)
    parser.add_argument('--preparation',type=Path)
    parser.add_argument('--started',type=float)
    a=parser.parse_args(); folder=a.folder.resolve()
    folder.relative_to(ROOT/'results/a/q2-yuanzhifang')
    if a.mode=='prepare':prepare(folder,a.audit,a.preparation)
    elif a.mode=='worker':return worker(folder,a.started)
    else:run(folder)
    return 0

if __name__=='__main__':raise SystemExit(main())
