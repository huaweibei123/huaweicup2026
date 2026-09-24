from pathlib import Path
import subprocess,sys,json,time,datetime,hashlib,platform
root=Path(__file__).resolve().parents[1]
ledger={'kind':'own_port_model_NOT_E0','python':sys.version,'platform':platform.platform(),
        'official_calls':{'E0':0,'E1':0,'E2':0},'attempts':[]}
ledger['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src').glob('*.py')}
for name,extra in [('allcut', ['--reference']),('one_intact_lane', [])]:
 argv=[sys.executable,'-B',str(root/'src/one_intact_lane.py'),str(root/'inputs/case_084.json'),
       '--cores','5','--output-dir',str(root/'results'/name)]+extra
 began=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.perf_counter()
 try:
  r=subprocess.run(argv,capture_output=True,text=True,timeout=40)
  row={'name':name,'argv':argv,'started_utc':began,'wall_seconds':time.perf_counter()-t,'exit_code':r.returncode,
       'stdout':r.stdout,'stderr':r.stderr,'timeout':False}
 except subprocess.TimeoutExpired as e:
  row={'name':name,'argv':argv,'started_utc':began,'wall_seconds':time.perf_counter()-t,'exit_code':None,
       'stdout':str(e.stdout),'stderr':str(e.stderr),'timeout':True}
 ledger['attempts'].append(row)
 (root/'results/ledger.json').write_text(json.dumps(ledger,indent=2))
 print(json.dumps(row,indent=2),flush=True)
 if row['exit_code']!=0:break
