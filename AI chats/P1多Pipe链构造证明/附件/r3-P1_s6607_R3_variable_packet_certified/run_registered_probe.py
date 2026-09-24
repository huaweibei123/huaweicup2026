import datetime, hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path
R=Path(__file__).resolve().parent
out=R/'results/variable_q';out.mkdir(parents=True,exist_ok=True)
ledger=R/'results/ledger.json'
if ledger.exists():raise FileExistsError('single registered run; ledger already exists')
cmd=[sys.executable,'-B',str(R/'src/variable_packet.py'),str(R/'source_inputs/data/case_084.json'),'--cores','5','--output',str(out/'plan.json'),'--diagnostics',str(out/'diagnostics.json')]
record=dict(utc_start=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=cmd,
 source_sha256={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'src/variable_packet.py',R/'frozen_repo/src/q1/response_compile.py',R/'frozen_repo/src/q1/response_oracle.py',R/'PREREGISTRATION.json']},
 environment=dict(python=sys.version,platform=platform.platform(),cpus=os.cpu_count()),
 timeout_seconds=180,workers=1,retries=0,candidate_constructors=1,E0=0,E1=0,E2=0)
t=time.perf_counter()
with (out/'stdout.txt').open('wb') as so,(out/'stderr.txt').open('wb') as se:
 try:
  r=subprocess.run(cmd,stdout=so,stderr=se,timeout=180);record.update(exit_code=r.returncode,status='ok' if r.returncode==0 else 'failed')
 except subprocess.TimeoutExpired:record.update(exit_code=None,status='timeout')
record.update(process_wall_seconds=time.perf_counter()-t,utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat())
if (out/'diagnostics.json').exists():
 d=json.loads((out/'diagnostics.json').read_bytes());record.update({k:d[k] for k in ['representative_compiles','final_task_compiles','total_static_task_compiles','model_makespan','read_to_plan_fsync_seconds','plan_sha256']})
ledger.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2));print((out/'stdout.txt').read_text());print((out/'stderr.txt').read_text())
