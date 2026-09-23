"""Fixed synthetic P2 matrix; every evaluation admitted before invocation."""
from __future__ import annotations
import argparse, copy, ctypes as ct, hashlib, json, os, runpy, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
LIMITS={'A':(9,3,7),'B':(5,0,5),'C':(4,0,0),'D':(8,0,0),'E':(3,0,4)}

def save(path,value):
    with Path(path).open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def elapsed(private):
    t=json.loads((private/'T0.json').read_text(encoding='utf-8-sig'))
    k=ct.WinDLL('kernel32');k.GetTickCount64.restype=ct.c_uint64
    return max((datetime.now(timezone.utc)-datetime.fromisoformat(t['t0_utc'])).total_seconds(),
               (k.GetTickCount64()-t['t0_tick64'])/1000)

def eq(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(eq(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    return a==b

def prepare(private):
    assert elapsed(private)<300
    graph=dict(ops=[dict(id=i,op='CONV',pipe='PIPE_M',cycles=i) for i in (1,2,3)],tensors=[],edges=[dict(source=1,target=3,data_size=17)])
    mapping={str(i):i-1 for i in (1,2,3)}
    plans={k:dict(node_to_subgraph=mapping,core_schedules=v) for k,v in dict(R=[[0],[1,2]],S=[[0],[2,1]],T=[[0,2],[1]]).items()}
    spill,spillplan=runpy.run_path(str(ROOT/'tests/eval_exact/fixtures.py'))['tensor_graph']()
    config=dict(bandwidth=60,capacity={'L1':524288,'UB':131072},cross_core_copy_delay=500,max_iter=1000000)
    data=dict(graph=graph,plans=plans,spill=spill,spillplan=spillplan,config=config)
    save(private/'inputs.json',data)
    destination=Path(__file__).parent/'inputs.json';save(destination,data)
    save(private/'limits.json',dict(matrix=LIMITS,record=29,debug=3,fixed_e0=16,potential_e0=45,formal_e0=0,total_wall=900,evaluation_cutoff=600,preparation_cutoff=300))

def child(stage,private):
    gate=private/(stage+'.gate');until=time.perf_counter()+15
    while not gate.exists():
        if time.perf_counter()>until:raise TimeoutError('Job gate not opened')
        time.sleep(.01)
    assert elapsed(private)<(300 if stage=='build' else 600)
    if stage=='build':
        from research.a.e2_search.build_native import build
        compiler=Path(os.environ['LOCALAPPDATA'])/'CodexToolchains/llvm-mingw-20260922/llvm-mingw-20260922-ucrt-x86_64/bin/x86_64-w64-mingw32-clang++.exe'
        save(private/'build.json',build(compiler=str(compiler),problem=2))
        from research.a.e2_search import _native_b
        lib=_native_b.get_lib();assert lib.replay_bc_abi()==1
        save(private/'abi.json',dict(abi=lib.replay_bc_abi(),loaded_path=lib._name))
        return 0
    from research.a.e2_search import SceneBEvaluator,E2BatchEvaluator,read_config,_native_b
    from research.a.e2_search._official_b import load_bundle
    data=json.loads((private/'inputs.json').read_text());g=data['graph'];p=data['plans'];cfg=data['config']
    actual=read_config(ROOT/'data/raw/a/official/data/config.txt',problem=2);actual.setdefault('max_iter',1000000);assert eq(cfg,actual)
    oracle,_=load_bundle(2)
    receipt=dict(stage=stage,admitted=dict(record=0,debug=0,fixed_e0=0),events=[],pools=[])
    def flush():save(private/(stage+'.child.json'),receipt)
    def admit(kind,label,n=1):
        assert elapsed(private)<590,'evaluation cleanup reserve reached'
        index={'record':0,'debug':1,'fixed_e0':2}[kind]
        assert receipt['admitted'][kind]+n<=LIMITS[stage][index],(stage,kind)
        receipt['admitted'][kind]+=n
        event=dict(kind=kind,label=label,count=n,status='reserved',wall_since_t0=elapsed(private));receipt['events'].append(event);flush();return event
    def truth(label,graph,plan,config):
        e=admit('fixed_e0',label)
        try:v=oracle.evaluate_scene_b(graph,plan,**config);e.update(status='ok');save(private/(label+'.truth.json'),v);return v
        except Exception as error:e.update(status='exception',error_type=type(error).__name__,message=str(error));return {'_exception':[type(error).__name__,str(error)]}
        finally:flush()
    def rec(label,engine,plan,config,full=False):
        e=admit('record',label)
        v=engine.evaluate_record(plan,full=full,**config);e.update(status='returned',record=v);flush();return v
    def compare(v,t,route='native'):
        assert v['problem']==2 and v['route']==route,v
        if '_exception' in t:
            assert v['status'] in ('invalid','error') and [v['error_type'],v['message']]==t['_exception'],(v,t)
        else:
            assert v['status']=='ok',v
            for k in ('makespan','data_movement_bytes','cross_task_traffic'):assert eq(v[k],t[k]),(k,v,t)
    def batch(label,pool,plans,config,full=False):
        e=admit('record',label,len(plans));rows=[];e['records']=rows
        for row in pool.evaluate_batch(plans,full=full,**config):rows.append(row);flush()
        e.update(status='returned',returned=len(rows));flush();assert len(rows)==len(plans);return rows
    def closed(pool):
        pool.close();pool.close();assert all(x is None for x in pool._slots)
        receipt['pools'].append(dict(closed=True,slots_empty=True));flush()
    def newpool(graph=None,**kw):return E2BatchEvaluator(g if graph is None else graph,problem=2,workers=kw.pop('workers',1),timeout_seconds=kw.pop('timeout_seconds',30),startup_timeout_seconds=15,**kw)
    code=0
    try:
        if stage=='A':
            configurations={'R':cfg,'S':cfg,'T':cfg,'bandwidth':dict(cfg,bandwidth=30),'capacity':dict(cfg,capacity={'L1':1048576,'UB':262144}),'delay':dict(cfg,cross_core_copy_delay=0),'spill':cfg}
            expected={}
            for name,c in configurations.items():
                expected[name]=truth('A-'+name,data['spill'] if name=='spill' else g,data['spillplan'] if name=='spill' else p.get(name,p['R']),c)
                assert '_exception' not in expected[name],expected[name]
            external=copy.deepcopy(g);engine=SceneBEvaluator(external,problem=2)
            for name,key in [('cold','R'),('repeat','R'),('order','S'),('assignment','T'),('bandwidth','bandwidth'),('capacity','capacity'),('delay','delay'),('snapshot','R'),('spill','spill')]:
                if name=='snapshot':external['ops'][0]['cycles']+=1000
                e=SceneBEvaluator(data['spill'],problem=2) if name=='spill' else engine
                plan=data['spillplan'] if name=='spill' else p.get(key,p['R'])
                row=rec('A-'+name,e,plan,configurations[key]);compare(row,expected[key])
                assert row['compilation_cache_hit']==(name in ('repeat','delay','snapshot')),(name,row)
                if name=='spill':assert row['data_movement_bytes']['spill_added_copy_bytes']>0
            for name in ('R','S','spill'):
                e=admit('debug','A-debug-'+name)
                eng=SceneBEvaluator(data['spill'],problem=2) if name=='spill' else engine
                plan=data['spillplan'] if name=='spill' else p[name]
                result=eng._native_score(plan,dict(configurations[name]),debug=True);d=result['debug']
                got={(int(core),int(oid)):(int(d['op_start'][i]),int(d['op_end'][i])) for i,(core,oid) in enumerate(d['op_keys'])}
                want={(c['core_id'],o['op_id']):(o['start'],o['end']) for c in expected[name]['per_core_timeline'] for o in c['ops']}
                save(private/('A-debug-'+name+'.json'),dict(op_keys=list(d['op_keys']),op_start=[int(x) for x in d['op_start']],op_end=[int(x) for x in d['op_end']]))
                e.update(status='returned',operations=len(got));flush();assert eq(got,want)
        elif stage=='B':
            cases=[('empty',{},cfg),('order',dict(p['T'],core_schedules=[[2,0],[1]]),cfg),('bandwidth',p['R'],dict(cfg,bandwidth=0)),('extra',p['R'],dict(cfg,same_core_wait=100)),('iteration',p['R'],dict(cfg,max_iter=1))]
            engine=SceneBEvaluator(g,problem=2)
            for name,plan,c in cases:
                t=truth('B-'+name,g,plan,c);assert '_exception' in t
                compare(rec('B-'+name,engine,plan,c),t,'e0_fallback')
        elif stage=='C':
            t=json.loads((private/'A-R.truth.json').read_text());engine=SceneBEvaluator(g,problem=2)
            with patch.object(_native_b,'_LIB',None),patch.object(_native_b.ct,'CDLL',side_effect=OSError('injected missing BC DLL')):
                row=rec('C-missing',engine,p['R'],cfg);compare(row,t,'e0_fallback');assert 'injected missing' in row['fallback_reason']['message']
            fake=Mock();fake.replay_bc_abi.return_value=999
            with patch.object(_native_b,'_LIB',None),patch.object(_native_b.ct,'CDLL',return_value=fake):
                row=rec('C-ABI',engine,p['R'],cfg);compare(row,t,'e0_fallback');assert 'ABI' in row['fallback_reason']['message']
            with newpool(native_enabled=False) as pool:compare(batch('C-disabled',pool,[p['R']],cfg)[0],t,'e0_fallback')
            closed(pool)
            with newpool() as pool:
                row=batch('C-full',pool,[p['R']],cfg,full=True)[0];compare(row,t,'e0_full');assert eq(row['result'],t)
            closed(pool)
        elif stage=='D':
            t=json.loads((private/'A-R.truth.json').read_text())
            with newpool(workers=2,max_tasks_per_worker=1) as pool:rows=batch('D-order',pool,[p['R'],{},p['R'],p['R']],cfg)
            closed(pool);assert [r['index'] for r in rows]==list(range(4));assert [r['status'] for r in rows]==['ok','invalid','ok','ok'];assert rows[0]['worker_pid']!=rows[2]['worker_pid']
            for i in (0,2,3):compare(rows[i],t)
            with newpool(timeout_seconds=1e-12) as pool:
                row=batch('D-timeout',pool,[p['R']],cfg)[0];assert row['status']=='timeout';pool._timeout=30
                compare(batch('D-recovery',pool,[p['R']],cfg)[0],t)
            closed(pool)
            with newpool(recycle_peak_rss_bytes=1) as pool:rows=batch('D-rss',pool,[p['R'],p['R']],cfg)
            closed(pool)
            for row in rows:compare(row,t);assert row['worker_peak_rss_bytes']>0 and row['recycle_reason']=='peak_rss_threshold'
            assert rows[0]['worker_pid']!=rows[1]['worker_pid']
        elif stage=='E':
            save(private/'cli-graph.json',g);save(private/'cli-plan.json',p['R']);save(private/'cli-bad.json',{})
            (private/'cli-plans.jsonl').write_text('\n'.join(json.dumps(x) for x in [p['R'],{},p['R']]),encoding='utf-8')
            def command(label,args):
                with (private/(label+'.stdout')).open('wb') as out,(private/(label+'.stderr')).open('wb') as err:
                    value=subprocess.run([sys.executable]+args,cwd=ROOT,stdout=out,stderr=err,timeout=min(30,590-elapsed(private)))
                return value.returncode
            e=admit('record','E-search-cli',3)
            rc=command('E-search',['-m','research.a.e2_search.cli',str(private/'cli-graph.json'),str(private/'cli-plans.jsonl'),'--problem','2','--config',str(ROOT/'data/raw/a/official/data/config.txt'),'--output',str(private/'cli-out.jsonl')])
            rows=[json.loads(s) for s in (private/'cli-out.jsonl').read_text().splitlines()];e.update(status='returned',returncode=rc,records=rows);flush()
            assert rc==1 and [x['status'] for x in rows]==['ok','invalid','ok'] and all(x['problem']==2 for x in rows)
            t=json.loads((private/'A-R.truth.json').read_text())
            for i in (0,2):compare(rows[i],t)
            for name in ('plan','bad'):
                for mode in ('official','adapter'):
                    e=admit('fixed_e0','E-full-'+name+'-'+mode)
                    args=[str(ROOT/'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py')] if mode=='official' else ['-m','research.a.e2_search.multicore_cut_evaluate_problem_2']
                    prefix=private/('full-'+name+'-'+mode)
                    rc=command('E-full-'+name+'-'+mode,args+[str(private/'cli-graph.json'),str(private/('cli-'+name+'.json')),'--config',str(ROOT/'data/raw/a/official/data/config.txt'),'--output',str(prefix)+'.json','--trace-output',str(prefix)+'.trace.json','--log-output',str(prefix)+'.log'])
                    e.update(status='returned',returncode=rc);flush();assert rc==(0 if name=='plan' else 1)
                if name=='plan':
                    for suffix in ('.json','.trace.json','.log'):assert (private/('full-plan-official'+suffix)).read_bytes()==(private/('full-plan-adapter'+suffix)).read_bytes()
        assert tuple(receipt['admitted'][k] for k in ('record','debug','fixed_e0'))==LIMITS[stage]
    except BaseException as error:
        code=1;receipt.update(error_type=type(error).__name__,message=str(error));raise
    finally:receipt.update(exit_code=code,wall_since_t0=elapsed(private));flush()
    return code
class BasicLimit(ct.Structure):
    _fields_ = [("p_time",ct.c_int64),("j_time",ct.c_int64),("flags",ct.c_uint32),
                ("min_ws",ct.c_size_t),("max_ws",ct.c_size_t),("active_limit",ct.c_uint32),
                ("affinity",ct.c_size_t),("priority",ct.c_uint32),("scheduling",ct.c_uint32)]
class IO(ct.Structure):
    _fields_ = [(name,ct.c_uint64) for name in ("r_op","w_op","o_op","r_byte","w_byte","o_byte")]
class Extended(ct.Structure):
    _fields_ = [("basic",BasicLimit),("io",IO)]+[(name,ct.c_size_t) for name in ("p_limit","j_limit","p_peak","j_peak")]
class Accounting(ct.Structure):
    _fields_ = [(name,ct.c_int64) for name in ("u","k","period_u","period_k")]+[(name,ct.c_uint32) for name in ("faults","total","active","terminated")]


def controlled(stage, private, deadline):
    k = ct.WinDLL("kernel32",use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ct.c_void_p,ct.c_wchar_p],ct.c_void_p),
        "SetInformationJobObject": ([ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_uint32],ct.c_int),
        "AssignProcessToJobObject": ([ct.c_void_p,ct.c_void_p],ct.c_int),
        "QueryInformationJobObject": ([ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_uint32,ct.c_void_p],ct.c_int),
        "TerminateJobObject": ([ct.c_void_p,ct.c_uint32],ct.c_int),
        "CloseHandle": ([ct.c_void_p],ct.c_int),
    }
    for name,(args,restype) in signatures.items():
        fn=getattr(k,name);fn.argtypes=args;fn.restype=restype
    job=k.CreateJobObjectW(None,None)
    if not job: raise ct.WinError(ct.get_last_error())
    limits=Extended();limits.basic.flags=0x2000
    process=None
    start=time.perf_counter()
    record=dict(stage=stage, job_kill_on_close=True, wall_scope="spawn, imports, IPC, tests, worker cleanup; preparation charged to global deadline")
    try:
        if not k.SetInformationJobObject(job,9,ct.byref(limits),ct.sizeof(limits)):
            raise ct.WinError(ct.get_last_error())
        with (private/(stage+".stdout")).open("wb") as stdout, (private/(stage+".stderr")).open("wb") as stderr:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--child",stage,"--private",str(private)],
                cwd=ROOT,stdout=stdout,stderr=stderr,env=dict(os.environ,PYTHONIOENCODING="utf-8"))
            record["pid"]=process.pid
            if not k.AssignProcessToJobObject(job,int(process._handle)):
                process.kill();process.wait(timeout=5)
                raise ct.WinError(ct.get_last_error())
            save(private/(stage+".gate"),dict(job_assigned=True,pid=process.pid))
            remaining=min((deadline-datetime.now(timezone.utc)).total_seconds(),600-elapsed(private))-10
            if remaining<=0: raise TimeoutError("no remaining cleanup-safe budget")
            try:
                record["returncode"]=process.wait(timeout=min(120,remaining))
            except subprocess.TimeoutExpired:
                record["status"]="outer_timeout"
                k.TerminateJobObject(job,137)
                process.wait(timeout=5)
        accounting=Accounting()
        if not k.QueryInformationJobObject(job,1,ct.byref(accounting),ct.sizeof(accounting),None):
            raise ct.WinError(ct.get_last_error())
        record["active_before_cleanup"]=accounting.active
        record["total_job_processes"]=accounting.total
        if accounting.active:
            record["forced_descendant_cleanup"]=True
            k.TerminateJobObject(job,137)
        for _ in range(100):
            if not k.QueryInformationJobObject(job,1,ct.byref(accounting),ct.sizeof(accounting),None):
                raise ct.WinError(ct.get_last_error())
            if not accounting.active: break
            time.sleep(.05)
        record["active_after_cleanup"]=accounting.active
        if accounting.active: record["status"]="cleanup_failed"
    except Exception as error:
        record.update(status="controller_error",error_type=type(error).__name__,message=str(error))
        if process is not None and process.poll() is None:
            k.TerminateJobObject(job,137)
            process.wait(timeout=5)
    finally:
        k.CloseHandle(job)
        record["wall_seconds"]=time.perf_counter()-start
        save(private/(stage+".controller.json"),record)
    return record



def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private',type=Path,required=True);parser.add_argument('--child');parser.add_argument('--prepare',action='store_true');parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.child:return child(args.child,args.private)
    if args.prepare:prepare(args.private);return 0
    if args.build:
        assert elapsed(args.private)<280
        result=controlled('build',args.private,datetime.fromisoformat(json.loads((args.private/'T0.json').read_text(encoding='utf-8-sig'))['preparation_deadline_utc']))
        print(json.dumps(result));return 0 if result.get('returncode')==0 and not result.get('status') and not result.get('forced_descendant_cleanup') else 1
    assert elapsed(args.private)<300,'Preparation deadline expired; no evaluation admitted'
    assert (args.private/'abi.json').exists()
    ledger=dict(stages=[],reserved_record=0,reserved_debug=0,reserved_fixed_e0=0,potential_e0=0,formal_e0=0,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip())
    deadline=datetime.fromisoformat(json.loads((args.private/'T0.json').read_text(encoding='utf-8-sig'))['evaluation_deadline_utc'])
    for stage,(record,debug,fixed) in LIMITS.items():
        if elapsed(args.private)>570:ledger['stop']='global_cleanup_reserve';break
        ledger['reserved_record']+=record;ledger['reserved_debug']+=debug;ledger['reserved_fixed_e0']+=fixed;ledger['potential_e0']+=record+fixed
        assert ledger['reserved_record']<=29 and ledger['reserved_debug']<=3 and ledger['reserved_fixed_e0']<=16 and ledger['potential_e0']<=45
        ledger['stages'].append(dict(stage=stage,record=record,debug=debug,fixed_e0=fixed))
        save(args.private/'ledger.json',ledger)
        result=controlled(stage,args.private,deadline);ledger['stages'][-1]['controller']=result;save(args.private/'ledger.json',ledger);print(stage,json.dumps(result),flush=True)
        if result.get('returncode')!=0 or result.get('status') or result.get('forced_descendant_cleanup'):ledger['stop']='first_failure';break
    ledger['wall_since_t0']=elapsed(args.private);save(args.private/'ledger.json',ledger)
    return 1 if ledger.get('stop') else 0

if __name__=='__main__':raise SystemExit(main())
