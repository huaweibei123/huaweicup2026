#!/usr/bin/env python3
"""Propose potentials by LP; ACCEPT only exact Fraction inequalities.
No compiler, plan generator, E0/E1/E2 calls. Input is the recorded transition table.
"""
import argparse, hashlib, json, math, time
from fractions import Fraction as F
from pathlib import Path

def certify(d, fixed_q=None):
    from scipy.optimize import linprog
    R=d['Rmax'] if fixed_q is None else min(d['Rmax'],fixed_q)
    edges=[e for e in d['edges']+d['drains'] if e['r']<=R and e['s']<=R and (fixed_q is None or e['q'] in (0,fixed_q))]
    # lambda*q + h(s) - h(r) <= edge_cost; h(0)=0.
    A=[];b=[]
    for e in edges:
        row=[0.]*(R+2);row[0]=e['q'];row[1+e['s']]+=1;row[1+e['r']]-=1
        A.append(row);b.append(e['cost'][0])
    obj=[-1.]+[0.]*(R+1)
    lp=linprog(obj,A_ub=A,b_ub=b,bounds=[(0,None),(0,0)]+[(None,None)]*R,method='highs')
    if not lp.success:raise RuntimeError(lp.message)
    val=[F(float(x)).limit_denominator(1000000) for x in lp.x]
    lam,h=val[0],val[1:]
    slacks=[F(e['cost'][0])-lam*e['q']-h[e['s']]+h[e['r']] for e in edges]
    if min(slacks)<0:raise AssertionError('LP floating proposal failed exact certificate; NOT accepted')
    terminals=[t for t in d['terminals'] if t['r']<=R]
    # Stored terminal costs include the initial gate; remove exactly one initial gate globally.
    end=min(h[t['r']]+t['cost'][0] for t in terminals)
    lb=lam*d['B']+end-d['gate']
    return dict(kind='rational cycle-potential certificate, RESTRICTED SYNCHRONOUS MODEL ONLY',
        fixed_q=fixed_q,lambda_fraction=str(lam),potentials=[str(x) for x in h],
        constraints_checked=len(edges),min_exact_slack=str(min(slacks)),
        terminal_min_potential_plus_cost=str(end),B=d['B'],finite_lower_bound_fraction=str(lb),
        finite_lower_bound_ceil=math.ceil(lb),
        tight_edges=[dict(r=e['r'],q=e['q'],s=e['s'],cost=e['cost'][0]) for e,s in zip(edges,slacks) if s==0],
        scope='Costs include frozen static compiler/ordered-prekey certificates plus Fraction response; no binary64 or whole-P1 optimum claim')

def main():
    p=argparse.ArgumentParser();p.add_argument('diagnostics',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError('refuse overwrite')
    t=time.perf_counter();raw=a.diagnostics.read_bytes();d=json.loads(raw)
    # The comparison packet is derived by the frozen mixed footprint rule, not by case ID.
    q=min([d['B']]+[d['capacity'][p]//(d['footprints']['prefix'][p]+d['footprints']['returning'][p]) for p in d['capacity'] if d['footprints']['prefix'][p]+d['footprints']['returning'][p]])
    result=dict(input_sha256=hashlib.sha256(raw).hexdigest(),variable=certify(d),fixed_capacity_packet=certify(d,q),calls=dict(candidate_constructors=0,static_compiles=0,E0=0,E1=0,E2=0),wall_seconds=time.perf_counter()-t)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
