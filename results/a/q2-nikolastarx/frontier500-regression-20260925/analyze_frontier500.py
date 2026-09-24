#!/usr/bin/env python3
"""Read-only paired comparison of semantic and frontier 500 feeds."""
import argparse, csv, gzip, hashlib, json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
NEW = OLD = None
FEEDS = {}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def load(label):
    d=json.loads(FEEDS[label].read_text()); records=d.get('records')
    if not isinstance(records,list): raise ValueError(f'{label}: missing records[]')
    ix={}
    for r in records:
        key=(str(r.get('case_id')),int(r.get('cores',0)))
        if key in ix: raise ValueError(f'{label}: duplicate cell {key}')
        ix[key]=r
    return ix

def route(root, r, label):
    p=root/'cells'/str(r['case_id'])/f"k{r['cores']}"/'online'/'solver.json'
    if not p.is_file(): raise FileNotFoundError(f'{label} route detail missing: {p}')
    d=json.loads(p.read_text()); selected=d.get('selected')
    attempt=next((a for a in d.get('attempts',[]) if a.get('name')==selected),None)
    if attempt is None: raise ValueError(f'{label}: selected attempt {selected!r} absent in {p}')
    return attempt.get('detail',{}).get('selected_strategy') or attempt.get('detail',{}).get('adaptive_route') or selected

def main():
    global NEW, OLD, FEEDS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-batch',type=Path,required=True)
    parser.add_argument('--old-batch',type=Path,required=True)
    args=parser.parse_args()
    NEW, OLD=args.new_batch.resolve(),args.old_batch.resolve()
    FEEDS={'new':NEW/'board-feed-500.json','old':OLD/'board-feed-500.json'}
    expected_feeds={'new':'15347fde245b5777edefc7d1b76bc7d49ba6c2989c278b8bdc3732b51fea3576','old':'b1652e0ef23699bd6c8139de948fff91d03ecacc64cf6b627e15e8d31fe9df3c'}
    for label,path in FEEDS.items():
        if sha(path)!=expected_feeds[label]: raise ValueError(f'{label} feed differs from recorded snapshot')
    ix={k:load(k) for k in FEEDS}
    rows=[]; summary={'cores':{},'provenance':{},'official_baselines':{}}
    for label, root in [('new',NEW),('old',OLD)]:
        summary['provenance'][label]={'feed':str(FEEDS[label]),'feed_sha256':sha(FEEDS[label]),'feed_submission_version':json.loads(FEEDS[label].read_text()).get('submission_version')}
    expected={f'{i:03d}' for i in range(1,101)}
    repo={label:root.parents[4] for label,root in [('new',NEW),('old',OLD)]}
    baselines={}
    for k in (4,5):
        core_rows=[]
        for case in sorted(expected):
            pair=[]
            for label in ('old','new'):
                r=ix[label].get((case,k))
                if r is None or r.get('status')!='ok': raise ValueError(f'{label} missing/non-ok {case}/k{k}: {None if r is None else r.get("status")}')
                base=r.get('baseline') or {}
                for field in ('graph_sha256','config_sha256','official_sha256'):
                    if base.get(field)!=r.get('identity',{}).get(field): raise ValueError(f'{label} mismatched baseline {field}: {case}')
                ident=(base.get('route'),base.get('entrypoint'))
                if ident!=('E0','singlecore_evaluate.evaluate_singlecore'): raise ValueError(f'{label} wrong E0 baseline identity {case}: {ident}')
                br=base.get('result') or {}; rel=br.get('path'); expected_sha=br.get('sha256')
                if not rel or not expected_sha: raise ValueError(f'{label} baseline path/hash missing {case}')
                bp=repo[label]/rel; actual_sha=sha(bp)
                if actual_sha!=expected_sha: raise ValueError(f'{label} baseline hash mismatch {case}: {actual_sha} != {expected_sha}')
                if label=='old': baselines[case]=(rel,actual_sha)
                elif baselines.get(case)!=(rel,actual_sha): raise ValueError(f'baseline identity differs old/new for {case}')
                if label=='new': summary['official_baselines'][case]={'path':rel,'sha256':actual_sha}
                with (gzip.open(bp,'rt') if bp.suffix=='.gz' else bp.open()) as f: bd=json.load(f)
                b=bd['makespan']
                m=(r.get('metrics') or {}).get('makespan_cycles')
                if not isinstance(m,(int,float)) or not isinstance(b,(int,float)) or not b: raise ValueError(f'{label} invalid M/B for {case}/k{k}')
                artifact=r['artifacts']['result']; rp=repo[label]/artifact['path']
                if sha(rp)!=artifact['sha256']: raise ValueError(f'{label} result hash mismatch {case}/k{k}')
                with gzip.open(rp,'rt') as f: result=json.load(f)
                if result['scene']!='B' or result['num_cores']!=k or result['makespan']!=m: raise ValueError('result identity/M mismatch')
                for field,metric in [('added_copy_bytes','extra_ddr_bytes'),('spill_added_copy_bytes','spill_bytes')]:
                    if result['data_movement_bytes'][field]!=r['metrics'][metric]: raise ValueError('movement mismatch')
                pair.append({'M':m,'B':b,'ratio':b/m,'route':route(NEW if label=='new' else OLD,r,label),'metrics':r['metrics']})
            o,n=pair; delta=n['ratio']-o['ratio']
            row={'case_id':case,'cores':k,'old_B':o['B'],'old_M':o['M'],'old_B_over_M':o['ratio'],'new_B':n['B'],'new_M':n['M'],'new_B_over_M':n['ratio'],'delta_B_over_M':delta,'old_selected_strategy':o['route'],'new_selected_strategy':n['route'],'old_extraDDR_bytes':o['metrics'].get('extra_ddr_bytes'),'new_extraDDR_bytes':n['metrics'].get('extra_ddr_bytes'),'old_spill_bytes':o['metrics'].get('spill_bytes'),'new_spill_bytes':n['metrics'].get('spill_bytes')}
            core_rows.append(row); rows.append(row)
        if len(core_rows)!=100: raise ValueError(f'k{k}: expected 100, got {len(core_rows)}')
        neg=[r for r in core_rows if r['delta_B_over_M']<0]
        pos=[r for r in core_rows if r['delta_B_over_M']>0]
        by=defaultdict(lambda:{'count':0,'sum_delta_B_over_M':0.0,'negative_contribution_sum':0.0,'negative_cases':0,'positive_contribution_sum':0.0,'improved_cases':0})
        for r in core_rows:
            x=by[r['new_selected_strategy']]; x['count']+=1; x['sum_delta_B_over_M']+=r['delta_B_over_M']
            if r['delta_B_over_M']<0: x['negative_cases']+=1; x['negative_contribution_sum']+=r['delta_B_over_M']
            elif r['delta_B_over_M']>0: x['improved_cases']+=1; x['positive_contribution_sum']+=r['delta_B_over_M']
        summary['cores'][str(k)]={'cases':len(core_rows),'negative_cases':len(neg),'improved_cases':len(pos),'ties':100-len(neg)-len(pos),'old_mean_B_over_M':sum(r['old_B_over_M'] for r in core_rows)/100,'new_mean_B_over_M':sum(r['new_B_over_M'] for r in core_rows)/100,'mean_delta_B_over_M':sum(r['delta_B_over_M'] for r in core_rows)/100,'negative_contribution_sum':sum(r['delta_B_over_M'] for r in neg),'positive_contribution_sum':sum(r['delta_B_over_M'] for r in pos),'by_new_selected_strategy':dict(by),'top10_negative':[dict(r) for r in sorted(neg,key=lambda z:z['delta_B_over_M'])[:10]]}
    summary['source_status']='new data full 500 reported exited by s59; sourceee1b8fd39efab8c8ed8140bbebe4c08e778052b9 and runner861a1f32073ba714a1bde555cea5d53f10a26b21; data commit unpublished and therefore not frozen.'
    summary['metric_definition']='Per case B is the verified official E0 result referenced by baseline.result.path and sha256; B/M = common official single-core makespan / submitted k4 or k5 makespan. Old/new baseline path and bytes must match. delta = new B/M - old B/M; negative is regression.'
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'paired-cells.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows)
    with (OUT/'negative-top10.csv').open('w',newline='') as f:
        fields=list(rows[0]); w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for k in (4,5): w.writerows(summary['cores'][str(k)]['top10_negative'])
    readme=f'''# Frontier 500 paired regression table\n\nPer-case B/M uses the feed-referenced official E0 single-core result (baseline.result.path + sha256) as B, common to old and new. The initial version incorrectly used each feed's k1 as denominator; all derived outputs here replace that version. Delta is new minus old; negative means regression. Baseline identities and hashes were verified across both feeds for all 100 cases.\n\nInputs: new `{FEEDS['new']}` SHA-256 `{summary['provenance']['new']['feed_sha256']}`; old `{FEEDS['old']}` SHA-256 `{summary['provenance']['old']['feed_sha256']}`. New dataset source commit `ee1b8fd39efab8c8ed8140bbebe4c08e778052b9`, runner `861a1f32073ba714a1bde555cea5d53f10a26b21`; new data commit is unpublished and is not frozen. Parent reported all 500 new runs exited.\n\n`paired-cells.csv` contains all 200 paired cases. `negative-top10.csv` contains the ten most negative rows for each core count. `summary.json` aggregates effects by new selected strategy and preserves input hashes. Route names come from each cell's `online/solver.json` selected attempt detail. No solver or evaluator was run.\n'''
    (OUT/'README.md').write_text(readme)
    print(json.dumps({k:{'negative_cases':v['negative_cases'],'improved_cases':v['improved_cases'],'mean_delta_B_over_M':v['mean_delta_B_over_M'],'negative_contribution_sum':v['negative_contribution_sum'],'positive_contribution_sum':v['positive_contribution_sum'],'by_new_selected_strategy':v['by_new_selected_strategy']} for k,v in summary['cores'].items()},ensure_ascii=False))
if __name__=='__main__': main()
