"""Fixed ownership, finite windows in a REFERENCE topological sequence.
A window is NOT a physical barrier or concurrency/memory bound. Only existing
subgraph order is controlled; all actual FIFO/memory/bandwidth remains E0.
"""
from __future__ import annotations
import heapq,time,hashlib
from pathlib import Path

def construct_window(g,n,factor=2):
 from packet_construct import construct,packet_profile,initial_groups
 from scan_cases import views
 st=time.perf_counter();base,diag=construct(g,n,'chain',True)
 ops,ts,prod,cons,el,pr,su,ets=views(g);core={b:k for k,order in enumerate(base['core_schedules']) for b in order};parent={int(v):b for v,b in base['node_to_subgraph'].items()};rank={b:i for i,b in enumerate(diag['global_packet_order'])}
 groups=initial_groups(g,'phase');bid={v:b for b,ns in enumerate(groups) for v in ns};ss={b:set() for b in range(len(groups))};pp={b:set() for b in ss};piece_index={};bparent={}
 for b,ns in enumerate(groups):
  pars={parent[v] for v in ns}
  if len(pars)!=1:raise ValueError('phase packet crosses base chain')
  bparent[b]=next(iter(pars))
 for cl in initial_groups(g,'chain'):
  _,order=packet_profile(cl,ops,pr,su);seq=[]
  for v in order:
   b=bid[v]
   if not seq or seq[-1]!=b:seq.append(b)
  for j,b in enumerate(seq):piece_index[b]=j
 for v in el:
  for u in su[v]:
   a,b=bid[v],bid[u]
   if a!=b:ss[a].add(b);pp[b].add(a)
 width=max(1,factor*n)
 def key(b):return (rank[bparent[b]]//width,piece_index[b],rank[bparent[b]],b)
 degree={b:len(pp[b]) for b in ss};heap=[key(b) for b in ss if not degree[b]];heapq.heapify(heap);ordered=[]
 while heap:
  *_,b=heapq.heappop(heap);ordered.append(b)
  for u in sorted(ss[b]):
   degree[u]-=1
   if not degree[u]:heapq.heappush(heap,key(u))
 if len(ordered)!=len(groups):raise ValueError('phase quotient cycle')
 orders=[[] for _ in range(n)]
 for b in ordered:orders[core[bparent[b]]].append(b)
 plan={'node_to_subgraph':{str(v):bid[v] for v in sorted(el)},'core_schedules':orders}
 return plan,{'mode':'reference_window_phase_refinement','width_packets':width,'factor':factor,'packets':len(groups),'base_packets':diag['packets'],'fixed_assignment':True,'base_construction':diag,'physical_window_not_guaranteed':True,'construction_seconds':time.perf_counter()-st,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
