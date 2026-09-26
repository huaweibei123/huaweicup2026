#!/usr/bin/env python3
"""Small integer certificate / analytic counterexample checks only; no plans or official code."""
from __future__ import annotations
import argparse, io, json, time, zipfile
from pathlib import Path
from audit_readonly import static_graph, compute_window_certificate, ceildiv

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();t0=time.perf_counter()
    # These tiny DAGs are mathematics examples, not candidate plans for any input.
    examples=[([(1,'PIPE_M'),(2,'PIPE_V'),(3,'PIPE_M')],[(0,1),(1,2)]),
              ([(5,'PIPE_M'),(2,'PIPE_M'),(4,'PIPE_V'),(3,'PIPE_M')],[(0,2),(1,2),(2,3)]),
              ([(3,'PIPE_V'),(3,'PIPE_V'),(3,'PIPE_V'),(1,'PIPE_M')],[(0,3),(1,3),(2,3)]),
              ([(2,'PIPE_M'),(4,'PIPE_V'),(1,'PIPE_M'),(6,'PIPE_V'),(5,'PIPE_M')],[(0,1),(0,2),(2,3),(1,4),(3,4)])]
    checks=[]
    for eid,(vs,es) in enumerate(examples):
        g={'ops':[{'id':i,'op':'COMPUTE','pipe':pipe,'cycles':d} for i,(d,pipe) in enumerate(vs)],'tensors':[],
           'edges':[{'source':u,'target':v} for u,v in es]}
        s=static_graph(g)
        for k in range(1,6):
            cert=compute_window_certificate(s,k);brute=0
            for pipe in s['work']:
                uu=[u for u,o in s['compute'].items() if o['pipe']==pipe]
                for h in {s['h'][u] for u in uu}:
                    for t in {s['t'][u] for u in uu}:
                        chosen=[u for u in uu if s['h'][u]>=h and s['t'][u]>=t]
                        if chosen:brute=max(brute,h+t+ceildiv(sum(s['d'][u] for u in chosen),k))
            assert brute==cert['value'];checks.append({'example':eid,'k':k,'value':brute})
    exchange=0
    for hi,ri,hj,rj in [(10,8,8,1),(5,2,5,2),(9,0,8,3),(0,0,3,1)]:
        if hi-ri<hj-rj:hi,ri,hj,rj=hj,rj,hi,ri
        assert max(hi,ri+hj)<=max(hj,rj+hi);exchange+=1
    def preload(R,q):
        U=[0,1,9];first=[0,2]
        return max(R,U[q])+1+3+max([0]+[U[r]-U[q]-first[r-1] for r in range(q+1,3)])
    preloads={str(R):[preload(R,q) for q in (1,2)] for R in (1,10)};assert preloads=={'1':[11,13],'10':[20,14]}
    z=zipfile.ZipFile(a.archive);cz=zipfile.ZipFile(io.BytesIO(z.read('data/raw/a/official-cases.zip')))
    s=static_graph(json.loads(cz.read('data/case_067.json')))
    ww=[sum(s['d'][u] for u in comp if s['compute'][u]['pipe']=='PIPE_M') for comp in s['components']]
    assert len(ww)==71 and set(ww)=={829792}
    # Analytic same-input counterexample: M-pipe A(1000)->B(1000), independent C(2000),
    # A->B tensor =500000 bytes, external ports 1 byte. Empty second core permitted.
    # P co-locates A,B,C: compute-FIFO+500 bound=4000, total serial work <=4004.
    # Q separates B: compute-FIFO+500 bound=max(A+C,A+500+B)=3000;
    # even optimistic cache read is 2000, output alone requires 8334, giving >=12834.
    counter={'old_compute_fifo_plus_500':4000,'new_compute_fifo_plus_500':3000,
             'old_serial_work_upper':4004,'new_optimistic_chain_lower':1000+ceildiv(500000,60)+500+ceildiv(500000,250)+1000,
             'scope':'analytic tiny example, no submitted plan, Task, Step or E0 was generated or run'}
    assert counter['new_compute_fifo_plus_500']<counter['old_compute_fifo_plus_500'] and counter['new_optimistic_chain_lower']>counter['old_serial_work_upper']
    out={'integer_window_crosschecks':checks,'exchange_examples':exchange,'partial_preload_examples':preloads,
         'whole_job_067':{'components':71,'M_per_component':829792,'k5_restricted_family_lower':15*829792},
         'lower_decrease_is_not_M_decrease':counter,'official_calls':0,'static_audit_wall_seconds':time.perf_counter()-t0}
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'small_proofs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
