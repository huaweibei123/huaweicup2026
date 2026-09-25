"""Read fixed Git objects and prepare a Pro input packet; no algorithm runs."""
import argparse, csv, hashlib, io, json, math, subprocess, zipfile
from pathlib import Path
from datetime import datetime, timezone

p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
a=p.parse_args(); a.output_dir.mkdir(parents=True,exist_ok=True)
base='a0537aeb72dc702af86d67d3194587d581ac207c'
paper='67c0f603960fddf86416d23ca3e85e53561c3c3a'
recent='8e63305f86a3692b9552295c61c4f234a006c105'
archive='9c5f87548cc7588465a638e032993969b5cac891'
auditrev='ad670c2f2414007cad80589b1f02621cea4037e8'
entries={}; origins=[]
def blob(rev,path):
    return subprocess.check_output(['git','show',rev+':'+path],cwd=a.repo)
def add(rev,path,dest=None):
    dest=dest or path
    if dest in entries: return entries[dest]
    data=blob(rev,path); entries[dest]=data
    origins.append({'path':dest,'source_commit':rev,'source_path':path,
      'source_url':f'https://github.com/huaweibei123/huaweicup2026/blob/{rev}/{path}',
      'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return data
for name in ['contest_io.py','evaluation_validation.py','multicore_cut_evaluate_problem_1.py',
             'schedule_step1.py','schedule_step2.py','schedule_step3.py',
             'singlecore_evaluate.py','stub_multicore_cut_and_schedule.py']:
    add(base,'data/raw/a/official/code/'+name)
add(base,'data/raw/a/official/data/config.txt')
add(base,'data/raw/a/official-cases.zip')
add(base,'docs/a/source-manifest.json')
add(base,'docs/a/Q1_LOWER_BOUNDS.md')
bounds=json.loads(add(base,'results/a/q1-lower-bounds-20260924/static_bounds.json'))
names=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'--','src/q1'],cwd=a.repo,text=True).splitlines()
for path in names:
    if path.endswith('.py'): add(base,path)
for path in ['paper/sections/P1-问题一论文初稿.md','paper/notes/P1-证据与更新清单.md',
             'paper/support/p1-draft/snapshot-v4-20260925.json',
             'paper/support/p1-draft/core-pairs-v4-20260925.json',
             'paper/support/p1-draft/followup-evidence-20260925.json']:
    add(paper,path)
feedpath='results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json'
feedraw=add(archive,feedpath)
assert hashlib.sha256(feedraw).hexdigest()=='4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764'
feed=json.loads(feedraw)
audit=json.loads(add(auditrev,'results/a/q1-yuanzhifang/v4-reuse-audit-20260925/reusable-index.json'))
for path in ['docs/a/P1_RETURN_CUT_RESOURCE_BOUND.md',
 'results/a/p1-core-budget-diagnostic-20260925/README.md',
 'results/a/p1-signature-path-diagnostic-20260925/README.md',
 'results/a/p1-period7-colab-20260925/run-0534Z/ZERO_CUT_MODEL_BOUND.md',
 'results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json',
 'results/a/p1-r5-local-audit-20260925/README.md',
 'results/a/p1-r5-local-audit-20260925/bounds/result.json',
 'src/q1/response_oracle.py','src/q1/compiled_memory_response.py',
 'src/review/p1_saved_signature_window_audit.py']:
    add(recent,path,'recent/'+path)
add('0b47d802cdd0bfe7011017c8098c1c0917b2c959','docs/a/q1-yuanzhifang/DDR_BARRIER_BOUND.md')
add('0b47d802cdd0bfe7011017c8098c1c0917b2c959','results/a/q1-yuanzhifang/ddr-proof-20260925/REVIEW.md')
add('6036015bedb7a1fc076583782f1420973aa708cb','docs/a/q1-yuanzhifang/WINDOW_BOUND.md')
idx={x['case_id']:x for x in audit['k4']}
lb={Path(x['input_member']).stem.split('_')[-1]:x for x in bounds['cases']}
assert len(idx)==len(lb)==100 and len(feed['records'])==500
rows=[]
for row in sorted(feed['records'],key=lambda r:(r['case_id'],r['cores'])):
    case,k=row['case_id'],row['cores']; d=lb[case]; b=idx[case]
    assert row['status']=='ok'
    assert d['input_sha256']==b['graph_sha256']==row['identity']['graph_sha256']
    assert bounds['code_identity']['config_sha256']==row['identity']['config_sha256']
    v=next(x for x in d['bounds'] if x['cores']==k)
    L,U,B=v['lower_bound_cycles'],row['metrics']['makespan_cycles'],b['baseline_makespan_cycles']
    assert 0<L<=U and B>0
    rows.append(dict(case_id=case,cores=k,graph_sha256=d['input_sha256'],
      baseline_makespan_cycles=B,current_E0_makespan_cycles=U,
      candidate_static_lower_bound_cycles=L,current_speedup=B/U,
      conditional_speedup_upper_bound=B/L,conditional_max_fractional_makespan_reduction=1-L/U,
      conditional_max_relative_speedup_gain=U/L-1,extra_ddr_bytes=row['metrics']['extra_ddr_bytes']))
groups=[]
for k in range(1,6):
    rs=[r for r in rows if r['cores']==k]
    A=math.fsum(r['current_speedup'] for r in rs)/100
    C=math.fsum(r['conditional_speedup_upper_bound'] for r in rs)/100
    groups.append(dict(cores=k,n=100,current_candidate_mean_speedup=A,
      official_curve_mean_speedup=1.0 if k==1 else A,
      conditional_mean_speedup_upper_bound=C,
      conditional_absolute_mean_speedup_gap=C-A,
      conditional_max_relative_mean_speedup_gain=C/A-1,
      zero_gap_cases=sum(r['candidate_static_lower_bound_cycles']==r['current_E0_makespan_cycles'] for r in rs)))
out={'kind':'conditional_static_bound_pairing_for_review_not_new_benchmark',
     'created_utc':datetime.now(timezone.utc).isoformat(),
     'scope':'All 500 graph/config identities matched. Archived bound proof and binary64/EPS applicability require Pro audit. A loose upper gap is not promised attainable gain. No solver, Task compiler, simulator, E0/E1/E2 calls.',
     'bounds_code_identity':bounds['code_identity'],'bounds_input_identity':bounds['input_identity'],
     'groups':groups,'rows':rows}
entries['derived/paired-bounds-v4.json']=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
s=io.StringIO(newline=''); w=csv.DictWriter(s,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
entries['derived/paired-bounds-v4.csv']=s.getvalue().encode()
for path in ['derived/paired-bounds-v4.json','derived/paired-bounds-v4.csv']:
    origins.append(dict(path=path,derived_from=['static_bounds.json',feedpath,'reusable-index.json'],size_bytes=len(entries[path]),sha256=hashlib.sha256(entries[path]).hexdigest()))
entries['README.md']='''# P1 R4: global bounds and remaining room, fixed evidence\n\nRead the question, official code/config, bound proof and paired rows first. Existing papers/research are claims to audit. All raw graph bytes are in the original official-cases.zip. The v4 feed is all 500 rows; no raw 500-result audit is claimed here. A reported static bound is a candidate certificate pending numerical-semantics audit, not a new score or guaranteed attainable gain. K1 official reporting is fixed to one; candidate K1 repartitioning is kept separate. The recent/ directory is research-only, not an update to the official v4 benchmark.\n\nEvery copied repository file is frozen in MANIFEST.json. Building this packet only read files and recomputed ratios. No solver, Task compiler, response oracle, E0/E1/E2 or paid compute was invoked. Please return a real read-manifest, precise domains of all theorems and reproducible scalar arithmetic. Do not run evaluator batches.\n'''.encode()
entries['MANIFEST.json']=(json.dumps(origins,ensure_ascii=False,indent=2)+'\n').encode()
zpath=a.output_dir/'p1-pro-r4-fixed-evidence.zip'
with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path,data in entries.items():z.writestr(path,data)
receipt={'filename':zpath.name,'files':len(entries),'bytes':zpath.stat().st_size,
         'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'sources':origins}
for name,data in [('r4-upload-sources.json',receipt),('r4-paired-bounds-v4.json',out)]:
    with (a.output_dir/name).open('x',encoding='utf8',newline='\n') as f:json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
print(json.dumps({'packet':str(zpath),'files':receipt['files'],'bytes':receipt['bytes'],
                 'sha256':receipt['sha256'],'groups':groups},ensure_ascii=False))
