"""Re-read evidence, verify raw hashes, copy the frozen official input, write flat audit tables."""
from pathlib import Path
import json,gzip,hashlib,shutil,sys,platform,csv,collections,datetime
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'route4_base'
OFF=BASE/'data/raw/a/official'

def sha(b):return hashlib.sha256(b).hexdigest()
def raw(p):
    return gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()

def main():
    manifest=json.loads((BASE/'docs/a/source-manifest.json').read_text())
    checks=[]
    for x in manifest['files']:
        p=OFF/x['path'];b=p.read_bytes()
        assert len(b)==x['bytes'] and sha(b)==x['sha256'],str(p)
        checks.append(x)
    code_hash=sha(''.join(x['path']+'\t'+x['sha256']+'\n' for x in sorted(checks,key=lambda x:x['path']) if x['path'].startswith('code/')).encode())
    assert code_hash==manifest['official_code_hash']
    source_freeze=json.loads((ROOT/'audit/final_source_freeze.json').read_text())
    for name,h in source_freeze.items():assert sha((ROOT/'src'/name).read_bytes())==h,name
    # Preserve official bytes, excluding Python runtime bytecode generated while executing E0.
    shutil.copytree(OFF,ROOT/'official',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(BASE/'docs/a/source-manifest.json',ROOT/'audit/official_source_manifest.json')
    shutil.copyfile(BASE/'data/raw/a/problem.pdf',ROOT/'official_problem.pdf')
    rows=[];errors=[];total_bytes=0
    for p in sorted((ROOT/'runs').glob('*/run.json')):
        r=json.loads(p.read_text());d=p.parent
        if r['status']!='ok':errors.append(r);continue
        assert sha((d/'plan.json').read_bytes())==r['plan_sha256'],str(d)
        gr=ROOT/'official/data'/f"case_{r['case']:03d}.json" if r['case']<10000 else ROOT/'synthetic'/f"case_{r['case']:05d}.json"
        assert sha(gr.read_bytes())==r['graph_sha256'],str(gr)
        rb=raw(d/'result.json.gz');tr=raw(d/'trace.json.gz');total_bytes+=len(rb)+len(tr)
        assert sha(rb)==r['result_sha256'],str(d)
        v=json.loads(rb);json.loads(tr)
        assert v['makespan']==r['makespan'] and v['data_movement_bytes']==r['data_movement_bytes']
        rows.append({'group':'candidate','label':r['label'],'case':r['case'],'problem':r['problem'],'cores':r['cores'],
          'assignment':r['assignment'],'method':r['method'],'gamma':r['gamma'],'makespan':v['makespan'],
          **v['data_movement_bytes'],'wall_s':r['total_wall_s'],'e0_cli_wall_s':r['e0_cli_wall_s'],
          'graph_sha256':r['graph_sha256'],'plan_sha256':r['plan_sha256'],'result_sha256':sha(rb),'trace_sha256':sha(tr)})
    end_records=[]
    for outer in json.loads((ROOT/'analysis/end_to_end.json').read_text()):
        d=ROOT/'end_to_end'/outer['name'];rr=json.loads((d/'solver_report.json').read_text())
        assert rr==outer['report']
        for child in sorted(d.iterdir()):
            if not child.is_dir() or not (child/'result.json').exists():continue
            res=json.loads((child/'result.json').read_text());p=child/'plan.json'
            rb=p.read_bytes();graph=ROOT/'official/data'/f"case_{outer['case']:03d}.json"
            rec={'group':'end_to_end','label':str(child.relative_to(ROOT/'end_to_end')),'case':outer['case'],
              'problem':outer['problem'],'cores':res['num_cores'],'makespan':res['makespan'],**res['data_movement_bytes'],
              'graph_sha256':sha(graph.read_bytes()),'plan_sha256':sha(rb)}
            for name in ['result.json','trace.json']:
                pp=child/name;b=pp.read_bytes();json.loads(b);total_bytes+=len(b);rec[name.split('.')[0]+'_sha256']=sha(b)
                with gzip.GzipFile(str(pp)+'.gz','wb',mtime=0) as f:f.write(b)
                pp.unlink()
            end_records.append(rec)
    allrows=rows+end_records
    fields=list(dict.fromkeys(k for r in allrows for k in r))
    with (ROOT/'analysis/all_e0_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(allrows)
    synt=[r for r in rows if r['case']>=10000]
    summary={'official_files_verified':len(checks),'official_code_hash':code_hash,
      'candidate_full_E0_successes':len(rows),'cold_solver_full_E0_successes':len(end_records),
      'total_full_E0_successes':len(allrows),'unique_graph_plan_problem_core_keys':len({(r['graph_sha256'],r['plan_sha256'],r['problem'],r['cores']) for r in allrows}),
      'formal_cases_with_new_E0_results':sorted({r['case'] for r in allrows if r['case']<10000}),
      'formal_case_count':len({r['case'] for r in allrows if r['case']<10000}),
      'synthetic_graphs':len({r['case'] for r in synt}),'synthetic_E0_labels':len(synt),
      'synthetic_total_construct_and_CLI_s':sum(r['wall_s'] for r in synt),'synthetic_CLI_s':sum(r['e0_cli_wall_s'] for r in synt),
      'decoded_result_and_trace_bytes':total_bytes,'failed_run_json':errors,
      'external_interrupted_directories':[str(p.parent.relative_to(ROOT)) for p in (ROOT/'runs').glob('*/interrupted.json')],
      'final_frozen_source_hashes_verified':True,'note':'Successful evaluations are calls, not independent graph samples. One outer-process interruption is not official invalidity. This is artifact integrity audit, not a second execution of every test.'}
    (ROOT/'analysis/evidence_audit.json').write_text(json.dumps(summary,indent=2))
    (ROOT/'analysis/end_to_end_integrity.json').write_text(json.dumps(end_records,indent=2))
    env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'logical_cpu_count':__import__('os').cpu_count(),
         'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cpuinfo':Path('/proc/cpuinfo').read_text().split('\n\n')[0],
         'cpu_only':True,'cloud_resources_used':False,'Apple_or_CUDA_tested':False,'team_reference_Python_3_12_retest':False}
    (ROOT/'audit/environment.json').write_text(json.dumps(env,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
