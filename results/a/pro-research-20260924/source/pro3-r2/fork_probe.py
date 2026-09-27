from runtime import *
from word_quotient import WordEvaluator

def graph():
 ts=[(100,'DDR',64),(101,'UB',64),(102,'UB',40000),(103,'UB',64),(104,'UB',64),(105,'DDR',64),(106,'DDR',64)]
 ops=[(1,'COPY_IN','PIPE_MTE2',1),(2,'ADD','PIPE_V',100),(3,'ADD','PIPE_V',1000),(4,'ADD','PIPE_V',2000),(5,'COPY_OUT','PIPE_MTE3',1),(6,'COPY_OUT','PIPE_MTE3',1)]
 es=[(100,1),(1,101),(101,2),(2,102),(102,3),(3,103),(102,4),(4,104),(103,5),(5,105),(104,6),(6,106)]
 return {'tensors':[dict(id=i,pos=p,size=s)for i,p,s in ts],'ops':[dict(id=i,op=o,pipe=p,cycles=c)for i,o,p,c in ops],'edges':[dict(source=a,target=b)for a,b in es]}
if __name__=='__main__':
 out=ROOT/'results/counterexamples/fork';out.mkdir(parents=True,exist_ok=True);g=graph();e=load();save_json(out/'graph.json',g)
 ps=[{'node_to_subgraph':{'2':0,'3':0,'4':1},'core_schedules':[[0],[1]]},{'node_to_subgraph':{'2':0,'3':1,'4':2},'core_schedules':[[0,1],[2]]}];rows=[]
 for q in [1,2,3]:
  w=WordEvaluator(e,q,g,ps[0]) if q>1 else None
  for i,p in enumerate(ps):
   save_json(out/f'plan{i}.json',p);r=evaluate(e,q,g,p);save_json(out/f'q{q}_plan{i}.E0.json.gz',r);row={'q':q,'plan':i,'makespan':r['makespan'],'traffic':r['data_movement_bytes']}
   if w:
    rr=w.evaluate(p);strict_equal(r,rr);save_json(out/f'q{q}_plan{i}.WORD.json.gz',rr);row.update(word=w.view_and_words(p)[-1],full_equal=True)
   rows.append(row)
 save_json(out/'summary.json',rows);print([(x['q'],x['plan'],x['makespan'],x.get('word'))for x in rows])
