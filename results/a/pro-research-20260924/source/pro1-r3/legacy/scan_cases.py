#!/usr/bin/env python3
"""Read-only static audit of the supplied NPU graphs. Standard library only."""
import argparse, collections, hashlib, json, math, pathlib, statistics, sys, time

def views(g):
    ops={o['id']:o for o in g['ops']}; ts={t['id']:t for t in g['tensors']}
    prod=collections.defaultdict(list); cons=collections.defaultdict(list)
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a in ops and b in ts:prod[b].append(a)
        elif a in ts and b in ops:cons[a].append(b)
        else:raise ValueError(f'non-bipartite edge {a} -> {b}')
    eligible={k for k,o in ops.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    preds={o:set() for o in eligible};succs={o:set() for o in eligible}
    edge_tensors=collections.defaultdict(list)
    for t in ts:
        for a in prod[t]:
            if a not in eligible:continue
            for b in cons[t]:
                if b in eligible:preds[b].add(a);succs[a].add(b);edge_tensors[a,b].append(t)
    return ops,ts,prod,cons,eligible,preds,succs,edge_tensors

def components(nodes,edges):
    parent={i:i for i in nodes};sz=dict.fromkeys(parent,1)
    def root(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b in edges:
        a,b=root(a),root(b)
        if a!=b:
            if sz[a]<sz[b]:a,b=b,a
            parent[b]=a;sz[a]+=sz[b]
    groups=collections.defaultdict(list)
    for i in parent:groups[root(i)].append(i)
    return list(groups.values())

def audit(path):
    start=time.perf_counter(); raw=path.read_bytes();g=json.loads(raw)
    ops,ts,prod,cons,eligible,preds,succs,ets=views(g)
    comp=components(eligible,ets)
    w={p:sum(o['cycles'] for o in ops.values() if o['pipe']==p) for p in ['PIPE_M','PIPE_V']}
    indeg={i:len(preds[i]) for i in eligible};q=collections.deque(i for i in sorted(eligible) if indeg[i]==0)
    cp={i:ops[i]['cycles'] for i in q};levels={i:0 for i in q};topo=[]
    while q:
        i=q.popleft();topo.append(i)
        for j in succs[i]:
            cp[j]=max(cp.get(j,0),cp[i]+ops[j]['cycles']);levels[j]=max(levels.get(j,0),levels[i]+1)
            indeg[j]-=1
            if not indeg[j]:q.append(j)
    if len(topo)!=len(eligible):raise ValueError('cyclic compute graph')
    input_t=[t for t in ts if any(c in eligible for c in cons[t]) and not any(p in eligible for p in prod[t])]
    out_t=[t for t in ts if any(p in eligible for p in prod[t]) and any(ops[c]['op']=='COPY_OUT' for c in cons[t])]
    input_bytes=sum(ts[t]['size'] for t in input_t)
    cm=[]
    for c in comp:
        ws={p:sum(ops[o]['cycles'] for o in c if ops[o]['pipe']==p) for p in w}
        cm.append({'n':len(c),'M':ws['PIPE_M'],'V':ws['PIPE_V'],'min_op':min(c)})
    by_total=sorted(cm,key=lambda x:x['M']+x['V'],reverse=True)
    pure_v=[c for c in cm if c['M']==0]
    sizes=collections.Counter(t['size'] for t in ts.values())
    result={'case':path.stem,'sha256':hashlib.sha256(raw).hexdigest(),'file_bytes':len(raw),'ops':len(ops),'compute_ops':len(eligible),
        'tensors':len(ts),'bipartite_edges':len(g['edges']),'compute_edges':len(ets),'dag':True,'M_cycles':w['PIPE_M'],'V_cycles':w['PIPE_V'],
        'compute_critical_path':max(cp.values(),default=0),'max_level':max(levels.values(),default=0),
        'compute_components':len(comp),'full_components':len(components(set(ops)|set(ts),((e['source'],e['target']) for e in g['edges']))),
        'input_tensor_count':len(input_t),'input_bytes':input_bytes,'output_bytes':sum(ts[t]['size'] for t in out_t),
        'max_tensor_bytes':max(sizes,default=0),'multi_producer_tensors':sum(len(prod[t])>1 for t in ts),
        'max_input_fanout':max((sum(c in eligible for c in cons[t]) for t in input_t),default=0),
        'reused_input_count':sum(sum(c in eligible for c in cons[t])>1 for t in input_t),
        'shared_input_weighted_excess_bytes':sum(ts[t]['size']*max(0,sum(c in eligible for c in cons[t])-1) for t in input_t),
        'largest_component':by_total[0] if by_total else {},
        'largest_pureV_component_cycles':max((c['V'] for c in pure_v),default=0),
        'components':by_total,'op_counts':dict(collections.Counter(o['op'] for o in ops.values())),
        'tensor_size_counts':dict(sorted(sizes.items())),
        'compute_cut_tensor_sizes':dict(collections.Counter(ts[t]['size'] for t in ts if any(p in eligible for p in prod[t]) and any(c in eligible for c in cons[t]))),
        'scan_seconds':time.perf_counter()-start}
    result['LB_noL2_5']=math.ceil(max(result['compute_critical_path'],w['PIPE_M']/5,w['PIPE_V']/5,(input_bytes+result['output_bytes'])/60))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('data',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    paths=sorted(a.data.glob('case_*.json'));rows=[audit(path) for path in paths]
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    for f in ['ops','compute_ops','tensors','compute_edges','M_cycles','V_cycles','compute_components','full_components','input_bytes','max_tensor_bytes','max_input_fanout','largest_pureV_component_cycles']:
        v=[r[f] for r in rows];print(f,'min',min(v),'median',statistics.median(v),'max',max(v))
    print('cases',len(rows),'total_compute_ops',sum(r['compute_ops'] for r in rows),'input_over_L2',sum(r['input_bytes']>1048576 for r in rows),'total_s',sum(r['scan_seconds'] for r in rows))
    print('largest',[(r['case'],r['ops']) for r in sorted(rows,key=lambda r:-r['ops'])[:5]])
if __name__=='__main__':main()
