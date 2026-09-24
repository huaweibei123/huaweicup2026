#!/usr/bin/env python3
"""Independent backward labels and exact inequalities for the recorded model class.
No plan is generated, no compiler/evaluator runs. Every accepted edge is checked.
"""
import argparse, hashlib, json, time
from pathlib import Path

def check_table(d):
    B,R=d['B'],d['Rmax'];byr={r:[] for r in range(R+1)}
    for e in d['edges']:byr[e['r']].append(e)
    drains={e['r']:e for e in d['drains']}
    tails={r:min(t['cost'][0] for t in d['terminals'] if t['r']==r) for r in range(R+1)}
    H=[[None]*(R+1) for _ in range(B+1)]
    for n in range(B,-1,-1):
        base={}
        for r in range(min(n,R)+1):
            values=[tails[r]] if n==B else []
            for e in byr[r]:
                if n+e['q']<=B and H[n+e['q']][e['s']] is not None:
                    values.append(e['cost'][0]+H[n+e['q']][e['s']])
            base[r]=min(values) if values else None
        H[n][0]=base[0]
        for r in range(1,min(n,R)+1):
            values=[] if base[r] is None else [base[r]]
            if r in drains and H[n][0] is not None:values.append(drains[r]['cost'][0]+H[n][0])
            H[n][r]=min(values) if values else None
    checked=0
    for n in range(B+1):
        for r in range(min(n,R)+1):
            here=H[n][r]
            if here is None:continue
            if n==B:assert here<=tails[r];checked+=1
            if r and H[n][0] is not None:
                assert here<=drains[r]['cost'][0]+H[n][0];checked+=1
            for e in byr[r]:
                if n+e['q']<=B and H[n+e['q']][e['s']] is not None:
                    assert here<=e['cost'][0]+H[n+e['q']][e['s']];checked+=1
    # The saved actual path is an upper witness, not evidence for other edges.
    lookup={(e['r'],e['q'],e['s']):e for e in d['edges']+d['drains']}
    path_cost=sum(lookup[tuple(a[1:])]['cost'][0] for a in d['actions'])
    tail=next(t for t in d['terminals'] if t['r']==d['terminal_pending'] and t['policy']==d['terminal_policy'])
    path_cost+=tail['cost'][0]
    assert path_cost==H[0][0]==d['model_makespan']+d['gate']
    return dict(kind='finite restricted Fraction-model optimum certificate',
        B=B,R=R,edge_inequalities_checked=checked,labels=H,
        source_label=H[0][0],path_cost_including_artificial_initial_gate=path_cost,
        restricted_model_optimum=H[0][0]-d['gate'],calls=dict(plan_constructors=0,static_compiles=0,E0=0,E1=0,E2=0),
        scope='Conditional on every transition ordered-prekey/compiler certificate; NOT whole P1 or official binary64 equivalence')

def main():
 p=argparse.ArgumentParser();p.add_argument('diagnostics',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 t=time.perf_counter();raw=a.diagnostics.read_bytes();r=check_table(json.loads(raw));r['input_sha256']=hashlib.sha256(raw).hexdigest();r['wall_seconds']=time.perf_counter()-t
 a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='labels'},indent=2))
if __name__=='__main__':main()
