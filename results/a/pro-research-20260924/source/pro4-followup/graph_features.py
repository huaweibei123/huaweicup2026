"""Independent structural view of official bipartite NPU graphs (not a timing oracle)."""
from __future__ import annotations
import json, heapq, hashlib, sys, time
from pathlib import Path
from collections import defaultdict, Counter

COPY = {'COPY_IN','COPY_OUT'}
class Graph:
    def __init__(self, obj):
        self.obj = obj
        self.ops = {o['id']: o for o in obj['ops']}
        self.ts = {t['id']: t for t in obj['tensors']}
        self.ids = sorted(o for o in self.ops if self.ops[o]['op'] not in COPY)
        self.eligible=set(self.ids)
        self.prod=defaultdict(set); self.cons=defaultdict(set)
        self.inputs=defaultdict(set); self.outputs=defaultdict(set)
        direct=[]
        for e in obj['edges']:
            u,v=e['source'],e['target']
            if u in self.ops and v in self.ts:
                self.prod[v].add(u); self.outputs[u].add(v)
            elif u in self.ts and v in self.ops:
                self.cons[u].add(v); self.inputs[v].add(u)
            else:
                raise ValueError('This constructor supports the problem bipartite input domain only')
        opnext={o:set() for o in self.ops}
        for t in self.ts:
            for p in self.prod[t]: opnext[p].update(self.cons[t])
        self.succ={o:set() for o in self.ids}; self.pred={o:set() for o in self.ids}
        for o in self.ids:
            stack=list(opnext[o]); seen=set()
            while stack:
                v=stack.pop()
                if v in seen: continue
                seen.add(v)
                if v in self.eligible:
                    self.succ[o].add(v); self.pred[v].add(o)
                else: stack.extend(opnext[v])
        self.topo=self.toposort()
        self.bottom={}
        for o in reversed(self.topo):
            self.bottom[o]=self.duration(o)+max((self.bottom[v] for v in self.succ[o]),default=0)
        self.depth={}
        for o in self.topo:
            self.depth[o]=1+max((self.depth[v] for v in self.pred[o]),default=-1)
        seen=set(); self.components=[]
        for o in self.ids:
            if o in seen: continue
            seen.add(o); comp=[]; stack=[o]
            while stack:
                u=stack.pop(); comp.append(u)
                for v in self.pred[u] | self.succ[u]:
                    if v not in seen: seen.add(v); stack.append(v)
            self.components.append(sorted(comp))
        self.components.sort(key=lambda c:c[0])
        self.comp_by_op={o:i for i,c in enumerate(self.components) for o in c}
    def duration(self,o): return max(1,self.ops[o]['cycles'])
    def toposort(self,priority=None):
        if priority is None: priority=lambda o:(o,)
        deg={o:len(self.pred[o]) for o in self.ids}
        heap=[(priority(o),o) for o in self.ids if deg[o]==0]; heapq.heapify(heap)
        order=[]
        while heap:
            _,o=heapq.heappop(heap); order.append(o)
            for v in sorted(self.succ[o]):
                deg[v]-=1
                if deg[v]==0: heapq.heappush(heap,(priority(v),v))
        if len(order)!=len(self.ids): raise ValueError('compute cycle')
        return order
    def statistics(self):
        load=Counter()
        for o in self.ids: load[self.ops[o]['pipe']]+=self.duration(o)
        boundary=[t for t in self.ts if self.cons[t]&self.eligible and not self.prod[t]&self.eligible]
        supports=[frozenset(self.comp_by_op[o] for o in self.cons[t]&self.eligible) for t in boundary]
        chain_comps=sum(all(len(self.pred[o])<=1 and len(self.succ[o])<=1 for o in c) for c in self.components)
        chains=Counter()
        for c in self.components:
            oc=sorted(c,key=lambda o:(self.depth[o],o))
            if all(len(self.pred[o])<=1 and len(self.succ[o])<=1 for o in c):
                stages=[]
                for o in oc:
                    p=self.ops[o]['pipe'];d=self.duration(o)
                    if stages and stages[-1][0]==p: stages[-1][1]+=d
                    else:stages.append([p,d])
                chains[tuple(tuple(x) for x in stages)]+=1
        return {'eligible':len(self.ids),'tensors':len(self.ts),'edges':len(self.obj['edges']),
            'compute_edges':sum(map(len,self.succ.values())), 'components':len(self.components),
            'largest_component':max(map(len,self.components),default=0), 'chain_components':chain_comps,
            'chain_word_types':len(chains),'top_chain_words':[[list(k),v] for k,v in chains.most_common(4)],
            'work':dict(load),'critical_path':max(self.bottom.values(),default=0),
            'input_tensors':len(boundary),'input_bundles':len(set(supports)),
            'input_shared_fraction':sum(len(s)>1 for s in supports)/max(1,len(supports)),
            'max_tensor_size':max(t['size'] for t in self.ts.values())}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('official',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    sys.path.insert(0,str(args.official/'code'))
    from stub_multicore_cut_and_schedule import _build_op_adjacency,_contract_excluded_copy_nodes
    data=[]
    for path in sorted((args.official/'data').glob('case_*.json')):
        t0=time.perf_counter();obj=json.loads(path.read_text());g=Graph(obj)
        _,succ=_build_op_adjacency(obj)
        pred2,succ2=_contract_excluded_copy_nodes(g.ids,succ)
        assert g.pred==pred2 and g.succ==succ2,path.name
        row={'case':path.stem,'graph_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**g.statistics(),
             'scan_wall_s':time.perf_counter()-t0,'official_compute_adjacency_equal':True}
        data.append(row)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    for r in data:
        print(r['case'],r['eligible'],r['components'],r['largest_component'],r['chain_word_types'],r['work'],r['top_chain_words'][:1])
