#!/usr/bin/env python3
"""Read existing official E0 traces and summarize K5 pipe/COPY activity."""
import gzip, hashlib, json
from statistics import median
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
SUMMARY=ROOT/'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
OPPORTUNITY=ROOT/'results/a/q2-nikolastarx/template-opportunity-20260925/report.json'
OUT=ROOT/'results/a/q2-nikolastarx/k5-utilization-20260925/report.json'
def sha(b): return hashlib.sha256(b).hexdigest()
def load(p): return json.loads(p.read_text())
def union_length(intervals):
    xs=sorted((a,b) for a,b in intervals if b>a); total=0; end=None
    for a,b in xs:
        if end is None or a>end: total+=b-a
        elif b>end: total+=b-end
        end=max(end or b,b)
    return total
def main():
    summary=load(SUMMARY); opp=load(OPPORTUNITY)
    assert summary['status']=='completed' and summary['accepted_cells']==500
    rows={(r['case'],r['cores']):r for r in summary['rows']}
    assert len(rows)==500
    feeds=[]; feed_files=sorted(ARCH.glob('cases-*/board-feed.json'))
    for p in feed_files: feeds.extend(load(p)['records'])
    recs=[r for r in feeds if r['cores']==5]
    assert len(recs)==100 and len({r['case_id'] for r in recs})==100
    slack={r['case']:r['slack'] for r in opp['cells']}; assert len(slack)==100
    out=[]
    for rec in sorted(recs,key=lambda r:r['case_id']):
        case=rec['case_id']; ref=rec['artifacts']['result']; p=ROOT/ref['path']; raw=p.read_bytes()
        assert sha(raw)==ref['sha256']
        d=json.loads(gzip.decompress(raw)); M=rec['metrics']['makespan_cycles']
        assert d['scene']=='B' and d['num_cores']==5 and d['makespan']==M==rows[(case,5)]['official']['makespan']
        assert len(d['per_core_timeline'])==5 and len({c['core_id'] for c in d['per_core_timeline']})==5
        assert max(t['end'] for c in d['per_core_timeline'] for t in c['tasks'])==M
        pipe_tot={'PIPE_M':0,'PIPE_V':0}; pipe_core=[]; copy_intervals=[]; events=0
        for core in d['per_core_timeline']:
            sums={'PIPE_M':0,'PIPE_V':0}
            for op in core['ops']:
                a,b=op['start'],op['end']; assert 0<=a<=b<=M
                if op['pipe'] in sums: sums[op['pipe']]+=b-a
                if op['op'] in ('COPY_IN','COPY_OUT'):
                    copy_intervals.append((a,b)); events+=1
            for pipe,n in sums.items(): pipe_tot[pipe]+=n
            pipe_core.append({'core':core['core_id'],**sums})
        copy_union=union_length(copy_intervals)
        out.append({'case':case,'M':M,'slack':slack[case],
          'pipe_busy_cycles_per_core':pipe_core,
          'pipe_busy_cycles_across_cores':pipe_tot,
          'pipe_max_core_busy_over_M':{pipe:max(x[pipe] for x in pipe_core)/M for pipe in pipe_tot},
          'copy_active_union_cycles':copy_union,'copy_active_union_over_M':copy_union/M,
          'copy_event_count':events,'result_sha256':ref['sha256']})
    ranked=sorted(out,key=lambda x:x['slack'],reverse=True)
    def stats(xs):
        vals=sorted(xs); return {'mean':sum(vals)/len(vals),'median':median(vals),'min':vals[0],'max':vals[-1]}
    report={'scope':'existing official E0 K5 timeline diagnostics; descriptive, no causal attribution',
      'coverage':{'k5_cells':len(out),'unique_cases':len({r['case'] for r in out}),'summary_cells':len(rows)},
      'inputs':{'summary_sha256':sha(SUMMARY.read_bytes()),'opportunity_report_sha256':sha(OPPORTUNITY.read_bytes()),
                'feed_files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())} for p in feed_files]},
      'all_k5':{'M':stats([x['M'] for x in out]),'PIPE_M_max_core_busy_over_M':stats([x['pipe_max_core_busy_over_M']['PIPE_M'] for x in out]),
                'PIPE_V_max_core_busy_over_M':stats([x['pipe_max_core_busy_over_M']['PIPE_V'] for x in out]),
                'COPY_active_union_over_M':stats([x['copy_active_union_over_M'] for x in out])},
      'top12_by_template_slack':ranked[:12],'all_cells':out,
      'interpretation_limits':['COPY active is the time union of COPY_IN/COPY_OUT events, not exact DDR utilization.',
       'Per-core PIPE_M and PIPE_V are separate resources; low ratios or imbalance alone do not prove a cause of Makespan.',
       'Timeline activity cannot establish which idle intervals are critical or whether changing placement improves M.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(OUT.relative_to(ROOT)),'coverage':report['coverage'],'all_k5':report['all_k5'],'top12':[{'case':x['case'],'slack':x['slack'],'M':x['M']} for x in ranked[:12]]},indent=2))
if __name__=='__main__':main()
