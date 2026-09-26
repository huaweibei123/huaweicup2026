"""Compress identical input-column supports, then detect exact two-bundle products."""
from collections import defaultdict,deque,Counter

def bundle_products(a):
    comps=a['components']; co={v:i for i,c in enumerate(comps) for v in c}
    twins=defaultdict(list)
    for t,vs in a['ext'].items():
        support=tuple(sorted({co[v] for v in vs}))
        twins[support].append(t)
    bundles=[]; job_bundles=[[] for _ in comps]
    for support,tids in sorted(twins.items()):
        b=len(bundles)
        bundles.append({'support':list(support),'tensors':sorted(tids),'bytes':sum(a['ts'][t]['size'] for t in tids)})
        for j in support:job_bundles[j].append(b)
    adj=defaultdict(list)
    for j,bs in enumerate(job_bundles):
        if len(bs)==2:
            u,v=bs;adj[u].append((v,j));adj[v].append((u,j))
    colors={};products=[]
    for x in sorted(adj):
        if x in colors:continue
        colors[x]=0;stack=[x];nodes=[];jobs=set();bip=True
        while stack:
            u=stack.pop();nodes.append(u)
            for v,j in adj[u]:
                jobs.add(j)
                if v in colors:
                    if colors[v]==colors[u]:bip=False
                else:colors[v]=1-colors[u];stack.append(v)
        aa=sorted(u for u in nodes if colors[u]==0);bb=sorted(u for u in nodes if colors[u]==1)
        cells={}
        for j in sorted(jobs):
            u,v=job_bundles[j]
            if colors[u]:u,v=v,u
            cells.setdefault((u,v),[]).append(j)
        complete=bip and len(cells)==len(jobs)==len(aa)*len(bb)
        # Require supports consist solely of these jobs. A shared column touching other jobs breaks closed rectangle interpretation.
        closed=all(set(bundles[b]['support'])<=jobs for b in nodes)
        if complete and closed:
            coords={j:(aa.index(u),bb.index(v)) for (u,v),[j] in cells.items()}
            products.append({'rows':aa,'cols':bb,'jobs':sorted(jobs),'coords':coords,'shape':[len(aa),len(bb)]})
    return {'bundles':bundles,'job_bundles':job_bundles,'products':products}

if __name__=='__main__':
    import json,time
    from pathlib import Path
    from scan import ROOT,index_graph
    start=time.perf_counter();rows=[]
    for path in sorted((ROOT/'data').glob('case_*.json')):
        a=index_graph(json.loads(path.read_text()));r=bundle_products(a)
        summary={'case':path.stem,'components':len(a['components']),'bundles':len(r['bundles']),'job_bundle_counts':dict(Counter(map(len,r['job_bundles']))),'products':[{'shape':p['shape'],'jobs':len(p['jobs']),'row_bytes':sorted(set(r['bundles'][b]['bytes'] for b in p['rows'])),'col_bytes':sorted(set(r['bundles'][b]['bytes'] for b in p['cols']))} for p in r['products']]}
        rows.append(summary)
        if summary['products']:print(summary,flush=True)
    Path('/mnt/data/r2_research/analysis/bundle_product_scan_100.json').write_text(json.dumps({'elapsed_seconds':time.perf_counter()-start,'cases':rows},indent=2))
