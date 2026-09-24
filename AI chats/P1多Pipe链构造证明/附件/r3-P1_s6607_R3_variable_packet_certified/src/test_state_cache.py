#!/usr/bin/env python3
"""Small counterexamples/certificate checks only; no candidate or global E0 run."""
import hashlib,json,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'frozen_repo'))
sys.path.insert(0,str(R/'frozen_repo/data/raw/a/official/code'))
import variable_packet as vp
import archived_recognizer as author
from src.q1.response_compile import compile_plan
from src.q1.response_oracle import simulate

capacity={'L1':524288,'UB':131072};calls=0

def chain_graph(count=6):
 ops=[];ts=[];edges=[]
 for i in range(count):
  opids=[100*i+j+1 for j in range(3)]
  tids=[10000+100*i+j for j in range(3)]
  for u,p,w in zip(opids,['PIPE_M','PIPE_V','PIPE_M'],[10,20,10]):ops.append(dict(id=u,op='X',pipe=p,cycles=w))
  for t in tids:ts.append(dict(id=t,pos='UB',size=60))
  for j in range(3):
   edges.append(dict(source=opids[j],target=tids[j]))
   if j<2:edges.append(dict(source=tids[j],target=opids[j+1]))
 return dict(ops=ops,tensors=ts,edges=edges)

def generic_local(graph):
 """Only for testing a prekey on inputs outside the optimized block guard."""
 f=object.__new__(vp.Family);f.graph=graph;f.view=author.views(graph)
 f.eligible={u for u,o in f.view.ops.items() if o['op'] not in author.COPY}
 f.has_out={t:any(f.view.ops[u]['op']=='COPY_OUT' for u in f.view.consumers[t]) for t in f.view.tensors}
 f.direct={u:[] for u in f.eligible}
 for e in graph['edges']:
  if e['source'] in f.eligible and e['target'] in f.eligible:f.direct[e['source']].append(e)
 f.next_id=max(set(f.view.ops)|set(f.view.tensors))+1
 return f

def compiled(f,nodes):
 global calls
 calls+=1
 lines,_=compile_plan(f.projection(nodes),dict(node_to_subgraph={str(u):0 for u in nodes},core_schedules=[[0]]),capacity,60)
 return lines[0][0]

def main():
 began=time.perf_counter();out=R/'results/state_cache_tests.json'
 if out.exists():raise FileExistsError('do not overwrite test receipt')
 reports=[]
 g=chain_graph();f=vp.Family(g,2,capacity,60)
 ns0=f.members(0,1,1,1,1);ns1=f.members(1,1,1,1,1)
 assert f.prekey(ns0)==f.prekey(ns1)
 t0,t1=compiled(f,ns0),compiled(f,ns1)
 assert t0.signature()==t1.signature()
 reports.append(dict(test='ordered-block prekey equality implies observed compiler equality',status='pass'))
 # Same graph, n=2 and r=1, but allowing different pending identities.
 # Give the first old chain a late output-tensor ID, the second an early one.
 g2=chain_graph(3)
 replace={10002:50000,10102:9999}
 for t in g2['tensors']:t['id']=replace.get(t['id'],t['id'])
 for e in g2['edges']:
  e['source']=replace.get(e['source'],e['source']);e['target']=replace.get(e['target'],e['target'])
 fg=generic_local(g2)
 nodesA=[3,201,202];nodesB=[103,201,202]
 a,b=compiled(fg,nodesA),compiled(fg,nodesB)
 assert fg.prekey(nodesA)!=fg.prekey(nodesB)
 assert a.signature()!=b.signature()
 ca,cb=simulate([[a]],100),simulate([[b]],100)
 reports.append(dict(test='count-only pending state without canonical suffix is insufficient',status='pass',
     n=2,r=1,M_FIFO_A=[x.original_id for x in a.ports[0]],M_FIFO_B=[x.original_id for x in b.ports[0]],
     model_cycles_A=ca['makespan'],model_cycles_B=cb['makespan']))
 try:vp.Family(g2,1,capacity,60)
 except vp.Unsupported:reports.append(dict(test='interleaved tensor blocks fail closed',status='pass'))
 else:raise AssertionError('unsafe block fast path accepted')
 # Isolated postcompile scalar agreement is NOT signature equivalence.
 # Both have work 10+20+10; dependency/FIFO responses above differ.
 assert ca['makespan']!=cb['makespan']
 reports.append(dict(test='identical aggregate compute work does not determine local response',status='pass'))
 # Reject a perturbed transition under an already-issued potential certificate.
 d=json.loads((R/'results/variable_q/diagnostics.json').read_bytes())
 cert=json.loads((R/'results/cycle_certificate.json').read_bytes())['variable']
 from fractions import Fraction as F
 lam=F(cert['lambda_fraction']);h=list(map(F,cert['potentials']))
 edge=next(e for e in d['edges'] if (e['r'],e['q'],e['s'])==(6,5,4))
 assert F(edge['cost'][0])-lam*edge['q']-h[edge['s']]+h[edge['r']]==0
 assert F(edge['cost'][0]-1)-lam*edge['q']-h[edge['s']]+h[edge['r']]<0
 reports.append(dict(test='cycle certificate rejects one-cycle cost tampering',status='pass'))
 result=dict(tests=reports,wall_seconds=time.perf_counter()-began,calls=dict(unit_suite_processes=1,static_task_compiles=calls,candidate_constructors=0,E0=0,E1=0,E2=0))
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
