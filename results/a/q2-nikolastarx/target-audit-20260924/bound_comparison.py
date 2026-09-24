#!/usr/bin/env python3
"""Read-only comparison of frozen static P2 bounds with the earlier board snapshot.
No solver or evaluator imports. Only BOUND_COMPARISON.json is generated here.
"""
from pathlib import Path
from fractions import Fraction
import gzip, hashlib, json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
INPUT=HERE/'BOUND_INPUT.json'
TARGET={2:Fraction('2.26'),3:Fraction('3.18'),4:Fraction('3.96'),5:Fraction('4.53')}
def read(name):
    path=HERE/name
    raw=path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix(path.suffix+'.gz').read_bytes())
    return json.loads(raw)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
bounds=read('BOUND_INPUT.json'); capture=read('capture-manifest.json')
for response in capture['responses']:
    stored=(HERE/response.get('stored_name',response['name'])).read_bytes()
    if 'stored_sha256' in response: assert hashlib.sha256(stored).hexdigest()==response['stored_sha256']
    raw=gzip.decompress(stored) if response.get('stored_name','').endswith('.gz') else stored
    assert hashlib.sha256(raw).hexdigest()==response['sha256']
record_history=[r for x in capture['responses'] if x['name'].startswith('p2-records-') for r in read(x['name'])['records']]
latest={}
for r in record_history:
    if r['attempt_id'] not in latest or r['revision']>latest[r['attempt_id']]['revision']:latest[r['attempt_id']]=r
fang={(r['case_id'],r['cores']):r for r in latest.values() if r['run_id'] in {'20260924T131640Z-s59ee','20260924T1325Z-s59ee'}}
winners={(c['case_id'],c['cores']):c['best'] for c in read('p2-cells.json')['cells']}
certificates={(r['graph_file'][5:8],c['cores']):(r,c) for r in bounds['records'] for c in r['by_core_count']}
expected={(f'{c:03d}',k) for c in range(1,101) for k in range(1,6)}
assert set(fang)==set(winners)==set(certificates)==expected
base={}; baseline_hash_count=0
for b in read('baseline-verification.json'):
    path=ROOT/b['path']; path=path if path.exists() else HERE/'baseline-blobs'/b['sha256']
    assert sha(path)==b['sha256']; raw=path.read_bytes(); result=json.loads(gzip.decompress(raw))
    assert result['makespan']==b['makespan_cycles'] and result['scene']=='A'
    c=b['case_id']; assert c not in base or base[c]['makespan_cycles']==b['makespan_cycles'];base[c]=b
    baseline_hash_count+=1
for name,digest in bounds['official_source_sha256'].items(): assert sha(ROOT/'data/raw/a/official/code'/name)==digest
for g in bounds['records']:
    c=g['graph_file'][5:8]
    assert g['supported'] and g['precedence_supported']
    assert sha(ROOT/'data/raw/a/official/data'/g['graph_file'])==g['graph_sha256']==base[c]['graph_sha256']

rows=[];anomalies=[]
for case,k in sorted(expected,key=lambda x:(x[1],x[0])):
    g,q=certificates[(case,k)]; L=q['makespan_lower_bound_cycles']; B=base[case]['makespan_cycles']
    assert type(L) is int and L>0 and type(B) is int and B>0
    r={'case_id':case,'cores':k,'graph_sha256':g['graph_sha256'],'singlecore_baseline_cycles':B,'makespan_lower_bound_cycles':L,'speedup_upper_bound':float(Fraction(B,L)),'proof_domain_supported':True}
    for name,source in [('history',winners[(case,k)]),('fang',fang[(case,k)])]:
        assert source['eligible'] and source['status']=='ok' and source['baseline_verified']
        assert source['identity']['graph_sha256']==g['graph_sha256']
        assert source['baseline']['official_sha256']==base[case]['official_sha256']
        assert source['baseline']['config_sha256']==base[case]['config_sha256']
        U=source['metrics']['makespan_cycles'];assert type(U) is int
        r[name+'_makespan_cycles']=U;r[name+'_minus_lower_bound_cycles']=U-L
        r[name+'_record_id']=source['id'];r[name+'_baseline_speedup']=float(Fraction(B,U))
        r[name+'_relative_suboptimality_certified_upper_bound']=float(Fraction(U,L)-1)
        if U<L:anomalies.append({'case_id':case,'cores':k,'source':name,'U':U,'L':L,'record_id':source['id'],'scope_reason':'UNRESOLVED: a successful admitted witness conflicts with the stated global lower bound; inspect domain/source before using the certificate.','bound_witness':q})
    rows.append(r)
bycore=[]
for k in range(1,6):
    rr=[r for r in rows if r['cores']==k]
    rational=sum((Fraction(r['singlecore_baseline_cycles'],r['makespan_lower_bound_cycles']) for r in rr),Fraction())/len(rr)
    hist=sum((Fraction(r['singlecore_baseline_cycles'],r['history_makespan_cycles']) for r in rr),Fraction())/len(rr)
    fangmean=sum((Fraction(r['singlecore_baseline_cycles'],r['fang_makespan_cycles']) for r in rr),Fraction())/len(rr)
    target=TARGET.get(k)
    bycore.append({'cores':k,'n':len(rr),'mean_speedup_upper_bound':float(rational),'mean_speedup_upper_bound_exact':{'numerator':str(rational.numerator),'denominator':str(rational.denominator)},'history_mean_speedup':float(hist),'fang_mean_speedup':float(fangmean),'image_target':float(target) if target else None,'image_target_excluded_by_this_bound':target>rational if target else None,'strictly_exceeding_target_excluded':target>=rational if target else None,'upper_bound_minus_target':float(rational-target) if target else None,'target_fraction_of_upper_bound':float(target/rational) if target else None,'history_equal_lower_bound_n':sum(r['history_minus_lower_bound_cycles']==0 for r in rr),'fang_equal_lower_bound_n':sum(r['fang_minus_lower_bound_cycles']==0 for r in rr),'history_min_slack_cycles':min(r['history_minus_lower_bound_cycles'] for r in rr),'history_max_slack_cycles':max(r['history_minus_lower_bound_cycles'] for r in rr)})
summary={'schema':'p2-global-bound-crosscheck-v1','scope':'Read-only arithmetic crosscheck. No new official performance evaluations; existing board snapshot at captured_at remains fixed.','captured_at':capture['captured_at'],'bound_input_sha256':sha(INPUT),'certificate_source_sha256':bounds['certificate_source_sha256'],'proof_document':bounds['proof_document'],'proof_document_observed_sha256':sha(ROOT/bounds['proof_document']),'current_certificate_source_matches':sha(ROOT/'src/q2_nikolastarx/global_bounds.py')==bounds['certificate_source_sha256'],'official_source_hashes_verified':len(bounds['official_source_sha256']),'graph_hashes_verified':100,'baseline_reference_hashes_verified':baseline_hash_count,'bound_cells':500,'comparisons':1000,'calls':{'E0':0,'E1':0,'E2':0},'anomalies':anomalies,'any_image_target_excluded':any(x['image_target_excluded_by_this_bound'] for x in bycore if x['image_target'] is not None),'any_image_strict_surpass_excluded':any(x['strictly_exceeding_target_excluded'] for x in bycore if x['image_target'] is not None),'interpretation':'All upper bounds are necessary relaxations. Being below the bound does not prove a target attainable. Absence of U<L only rules out a counterexample among these witnesses, not a general proof audit.','by_core':bycore,'cells':rows}
(HERE/'BOUND_COMPARISON.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'comparisons':1000,'anomalies':len(anomalies),'bounds':[{k:r[k] for k in ('cores','n','mean_speedup_upper_bound','image_target','image_target_excluded_by_this_bound','history_equal_lower_bound_n','history_min_slack_cycles')} for r in bycore],'any_target_excluded':summary['any_image_target_excluded']},indent=2))
if anomalies:raise SystemExit(1)
