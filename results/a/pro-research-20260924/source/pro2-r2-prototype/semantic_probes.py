import json,sys,gzip
from pathlib import Path
from evidence import run_e0,DEFAULT_OFFICIAL
sys.path.insert(0,str(DEFAULT_OFFICIAL/'code'))
from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
from evaluation_validation import read_evaluation_config
class Graph:
 def __init__(self):self.g={'ops':[],'tensors':[],'edges':[]};self.n=0
 def ident(self):self.n+=1;return self.n
 def tensor(self,size,pos):
  u=self.ident();self.g['tensors'].append({'id':u,'size':size,'pos':pos});return u
 def edge(self,a,b):self.g['edges'].append({'source':a,'target':b})
 def input(self,size=64,pos='UB'):
  d=self.tensor(size,'DDR');t=self.tensor(size,pos);o=self.ident();self.g['ops'].append({'id':o,'op':'COPY_IN','pipe':'PIPE_MTE2','cycles':1});self.edge(d,o);self.edge(o,t);return t
 def op(self,ins,cycles=10,name='ADD',pipe='PIPE_V',size=64):
  o=self.ident();t=self.tensor(size,'UB');self.g['ops'].append({'id':o,'op':name,'pipe':pipe,'cycles':cycles})
  for x in ins:self.edge(x,o)
  self.edge(o,t);return o,t
 def output(self,t):
  o=self.ident();d=self.tensor(next(x['size'] for x in self.g['tensors'] if x['id']==t),'DDR');self.g['ops'].append({'id':o,'op':'COPY_OUT','pipe':'PIPE_MTE3','cycles':1});self.edge(t,o);self.edge(o,d)

out=Path('/mnt/data/r2_research/runs/semantics');fix=Path('/mnt/data/r2_research/fixtures');summary=[]
b=Graph();x=b.input();y=b.input();P,tp=b.op([x],1000,'CONV','PIPE_M');R,tr=b.op([tp],10);I,ti=b.op([y],500);b.output(tr);b.output(ti)
g=fix/'fifo_head.json';g.write_text(json.dumps(b.g,indent=2))
plans={'blocked':{'node_to_subgraph':{str(P):0,str(R):1,str(I):2},'core_schedules':[[0],[1,2]]},'independent_first':{'node_to_subgraph':{str(P):0,str(R):1,str(I):2},'core_schedules':[[0],[2,1]]}}
cfg=read_evaluation_config(str(DEFAULT_OFFICIAL/'data/config.txt'))
for name,plan in plans.items():
 tasks,links,cross_bytes,traffic,view=_build_scene_b_tasks(b.g,plan,cfg['bandwidth'],cfg['capacity'])
 snap={'pipe_orders':{c:t['pipe_ops'] for c,t in tasks.items()},'op_preds':{c:{u:sorted(ps) for u,ps in t['op_preds'].items()} for c,t in tasks.items()},'cross_links':links,'original_roles':{'P':P,'R':R,'I':I}}
 (fix/f'fifo_{name}_prepared.json').write_text(json.dumps(snap,indent=2))
 for q in [2,3]:
  r=run_e0(g,plan,q,out/f'fifo_{name}_p{q}',compress=True);summary.append(r);print(name,q,r['status'],r.get('makespan'))
# Four independent original task nodes with two forward dependencies; reversed cross-core orders create a Task cycle.
c=Graph();ia=c.input();ib=c.input();A,ta=c.op([ia],10);B,tb=c.op([ta],10);C,tc=c.op([ib],10);D,td=c.op([tc],10);c.output(tb);c.output(td)
g=fix/'task_order_cycle.json';g.write_text(json.dumps(c.g,indent=2))
mp={str(A):0,str(B):1,str(C):2,str(D):3}
for name,orders in [('cycle',[[1,2],[3,0]]),('fixed',[[2,1],[0,3]])]:
 for q in [1,2,3]:
  r=run_e0(g,{'node_to_subgraph':mp,'core_schedules':orders},q,out/f'cycle_{name}_p{q}',compress=True);summary.append(r);print(name,q,r['status'],r.get('makespan'),r.get('error','')[:140])
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
