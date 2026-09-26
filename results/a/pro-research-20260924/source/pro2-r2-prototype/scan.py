"""Read every official JSON; exact graph/incidence statistics, no timing proxy."""
import json, hashlib, time, sys, collections, heapq
from pathlib import Path
ROOT=Path('/mnt/data/r2_bundle/data/raw/a/official')

def index_graph(g):
    ops={o['id']:o for o in g['ops']}; ts={t['id']:t for t in g['tensors']}
    eligible={v:o for v,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    prod=collections.defaultdict(list); cons=collections.defaultdict(list)
    ins=collections.defaultdict(list); outs=collections.defaultdict(list); direct=[]
    for e in g['edges']:
        u,v=e['source'],e['target']
        if u in ops and v in ts: prod[v].append(u);outs[u].append(v)
        elif u in ts and v in ops: cons[u].append(v);ins[v].append(u)
        else: direct.append((u,v))
    pred={v:set() for v in eligible};succ={v:set() for v in eligible}
    for t in ts:
        for u in prod[t]:
            if u not in eligible: continue
            for v in cons[t]:
                if v in eligible:pred[v].add(u);succ[u].add(v)
    for u,v in direct:
        if u in eligible and v in eligible:pred[v].add(u);succ[u].add(v)
    deg={v:len(p) for v,p in pred.items()}; h=[v for v,d in deg.items() if d==0];heapq.heapify(h)
    top=[]; depth={v:0 for v in eligible}
    while h:
        u=heapq.heappop(h);top.append(u)
        for v in sorted(succ[u]):
            depth[v]=max(depth[v],depth[u]+1);deg[v]-=1
            if not deg[v]:heapq.heappush(h,v)
    parent={v:v for v in eligible}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    for u in eligible:
        for v in succ[u]:parent[find(v)]=find(u)
    comps=collections.defaultdict(list)
    for u in top: comps[find(u)].append(u)
    cs=sorted(comps.values(),key=lambda c:(min(c),len(c)))
    ext={t:[v for v in cons[t] if v in eligible] for t in ts if not any(v in eligible for v in prod[t]) and any(v in eligible for v in cons[t])}
    return dict(ops=ops,ts=ts,eligible=eligible,prod=prod,cons=cons,ins=ins,outs=outs,pred=pred,succ=succ,top=top,depth=depth,components=cs,ext=ext,direct=direct)

def stats(g):
    a=index_graph(g); cs=a['components'];e=a['eligible']; ext=a['ext'];
    comp_of={u:i for i,c in enumerate(cs) for u in c}
    sig=collections.Counter(tuple(sorted(collections.Counter((e[v]['op'],e[v]['pipe'],e[v]['cycles']) for v in c).items())) for c in cs)
    comp_ext=[set() for _ in cs]
    for t,vs in ext.items():
        for u in vs: comp_ext[comp_of[u]].add(t)
    two=[(i,sorted(tids)) for i,tids in enumerate(comp_ext) if len(tids)==2]
    inp_adj=collections.defaultdict(list)
    for i,(u,v) in two:inp_adj[u].append((v,i));inp_adj[v].append((u,i))
    colors={};products=[]
    for x in sorted(inp_adj):
        if x in colors:continue
        colors[x]=0;stack=[x];nodes=[];ed=set();bip=True
        while stack:
            u=stack.pop();nodes.append(u)
            for v,i in inp_adj[u]:
                ed.add(i)
                if v in colors:
                    if colors[v]==colors[u]:bip=False
                else:colors[v]=1-colors[u];stack.append(v)
        aa=[u for u in nodes if colors[u]==0];bb=[u for u in nodes if colors[u]==1]
        unique_pairs={tuple(sorted(comp_ext[i])) for i in ed}
        products.append({'a':len(aa),'b':len(bb),'jobs':len(ed),'bipartite':bip,'complete_simple':bip and len(unique_pairs)==len(ed)==len(aa)*len(bb)})
    levels=collections.Counter(a['depth'].values())
    return {'eligible':len(e),'ops':len(g['ops']),'tensors':len(g['tensors']),'edges':len(g['edges']),
      'non_bipartite_edges':len(a['direct']),'eligible_dag':len(a['top'])==len(e),'eligible_edges':sum(map(len,a['succ'].values())),
      'types':dict(collections.Counter(o['op'] for o in e.values())),
      'pipe_work':dict((p,sum(o['cycles'] for o in e.values() if o['pipe']==p)) for p in sorted({o['pipe'] for o in e.values()})),
      'components':len(cs),'component_sizes':dict(collections.Counter(map(len,cs))),
      'component_signature_count':len(sig),'max_identical_component_signatures':max(sig.values(),default=0),
      'depth':max(a['depth'].values(),default=-1)+1,'max_level_width':max(levels.values(),default=0),
      'ext_inputs':len(ext),'ext_bytes':sum(a['ts'][t]['size'] for t in ext),'ext_fanout_max':max(map(len,ext.values()),default=0),
      'component_ext_counts':dict(collections.Counter(map(len,comp_ext))), 'two_input_products':products,
      'tensor_sizes':dict(collections.Counter(t['size'] for t in a['ts'].values())),
      'multiple_eligible_producers':sum(sum(v in e for v in a['prod'][t])>1 for t in a['ts'])}

if __name__=='__main__':
    start=time.perf_counter(); res=[]
    for p in sorted((ROOT/'data').glob('case_*.json')):
        raw=p.read_bytes(); g=json.loads(raw); t=time.perf_counter();r=stats(g)
        r.update(case=p.stem,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),scan_seconds=time.perf_counter()-t);res.append(r)
        print(p.stem,r['eligible'],r['components'],r['depth'],r['component_sizes'],r['component_ext_counts'],r['two_input_products'][:3],flush=True)
    Path('/mnt/data/r2_research/analysis/structural_scan_100.json').write_text(json.dumps({'elapsed_seconds':time.perf_counter()-start,'cases':res},ensure_ascii=False,indent=2))
