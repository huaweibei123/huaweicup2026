#!/usr/bin/env python3
"""Static intact-chain-blocking versus mandatory-cut-service certificate.
No evaluator/model timeline is run. This is universal only on checked spines.
"""
import argparse,json,hashlib,time
from pathlib import Path
import archived_r1 as ar


def certificate(graph,cores,bandwidth=60):
    v,chains,ct,_,_=ar.recognize(graph)
    eligible={u for u,o in v.ops.items() if o['op'] not in ar.COPY}
    # Strong terminal-output condition makes the DFS contiguity proof explicit.
    for i,chain in enumerate(chains):
        for tid in ct[i]:
            ps=v.producers[tid]&eligible;cs=v.consumers[tid]&eligible
            h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
            if ps and (not cs or h) and ps!={chain[-1]}:
                raise ar.Unsupported('nonterminal output: no intact-chain contiguity certificate')
    n=len(chains);c=chains[0]
    ell=sum(max(1,v.ops[u]['cycles']) for u in c)
    blocking=sum(max(1,v.ops[u]['cycles']) for u in c[1:-1])
    table=ar.cut_table(graph,c,bandwidth)
    delta=min(row['universal_extra_service_min'] for row in table)
    whole=ar.encode(chains,graph['ops'],cores,packet=1,cut_count=0,whole_packet=n)
    d0=ar.boundary_counts(graph,whole,bandwidth)['boundary_service_cycles']
    def parts(s):return (ar.ceildiv(n*ell-s*blocking,cores),
                         ar.ceildiv(n-s,cores)*ell,d0+s*delta)
    lo,hi=0,n
    while lo<hi:
        mid=(lo+hi)//2;p=parts(mid)
        if max(p[:2])<=p[2]:hi=mid
        else:lo=mid+1
    probes=sorted({0,n,max(0,lo-1),lo})
    bound=min(max(parts(s)) for s in probes)
    return dict(kind='static_chain_obstruction_bound_NOT_E0',
                domain='private homogeneous retained M-V+-M spines, single producer, terminal outputs only, no COPY bridges',
                cores=cores,N=n,ell=ell,blocking=blocking,d0=d0,
                delta_min_all_cuts=delta,cut_table=table,crossing=lo,
                checked_counts=[dict(s=s,parts=parts(s)) for s in probes],lower_bound=bound,
                caveat='Resource/cycle semantic proof; not arbitrary-binary64 formal verification',
                official_calls={'E0':0,'E1':0,'E2':0})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path)
    p.add_argument('--cores',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('refuse overwrite')
    start=time.perf_counter();raw=a.graph.read_bytes();result=certificate(json.loads(raw),a.cores)
    result['graph_sha256']=hashlib.sha256(raw).hexdigest()
    result['analysis_seconds_before_write']=time.perf_counter()-start
    a.output.write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ('lower_bound','N','delta_min_all_cuts','d0','crossing')}))

if __name__=='__main__':main()
