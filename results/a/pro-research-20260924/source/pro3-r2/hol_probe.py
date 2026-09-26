from runtime import *

def make():
 ts=[(100,'DDR',64),(101,'UB',64),(102,'UB',64),(103,'UB',64),(104,'DDR',64),(105,'DDR',64),(106,'UB',64),(107,'UB',64),(108,'DDR',64)]
 ops=[(1,'COPY_IN','PIPE_MTE2',1),(2,'ADD','PIPE_V',10000),(3,'ADD','PIPE_V',1),(4,'COPY_OUT','PIPE_MTE3',1),(5,'COPY_IN','PIPE_MTE2',1),(6,'ADD','PIPE_V',5000),(7,'COPY_OUT','PIPE_MTE3',1)]
 edges=[(100,1),(1,101),(101,2),(2,102),(102,3),(3,103),(103,4),(4,104),(105,5),(5,106),(106,6),(6,107),(107,7),(7,108)]
 g={'tensors':[dict(id=i,pos=p,size=s) for i,p,s in ts],'ops':[dict(id=i,op=o,pipe=p,cycles=c) for i,o,p,c in ops],'edges':[dict(source=a,target=b) for a,b in edges]}
 p0={'node_to_subgraph':{'2':0,'3':1,'6':2},'core_schedules':[[0],[1,2]]};p1={'node_to_subgraph':dict(p0['node_to_subgraph']),'core_schedules':[[0],[2,1]]};return g,[p0,p1]

def run():
 g,ps=make();e=load();out=ROOT/'results/counterexamples/head_blocking';out.mkdir(parents=True,exist_ok=True);save_json(out/'graph.json',g);rows=[]
 for k,p in enumerate(ps):
  save_json(out/f'plan_{k}.json',p)
  for q in [1,2,3]:
   r=evaluate(e,q,g,p);save_json(out/f'q{q}_p{k}.result.json',r);rows.append({'q':q,'plan':k,'makespan':r['makespan'],'traffic':r['data_movement_bytes'],'core1_ops':r['per_core_timeline'][1]['ops']})
 save_json(out/'summary.json',rows);print([(v['q'],v['plan'],v['makespan']) for v in rows])
if __name__=='__main__':run()
