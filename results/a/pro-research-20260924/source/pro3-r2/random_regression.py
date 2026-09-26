"""Independent small bipartite graphs; legal and deliberately malformed plans."""
from runtime import *
from plans import *
import random,contextlib,io

def graph(seed):
 r=random.Random(seed);n=r.randint(2,12);ts=[];ops=[];es=[];nextid=1;outs=[];succ=[0]*n
 def tensor(pos,size):
  nonlocal nextid
  i=nextid;nextid+=1;ts.append(dict(id=i,pos=pos,size=size));return i
 def op(ty,pipe,cycles,ins,outs):
  nonlocal nextid
  i=nextid;nextid+=1;ops.append(dict(id=i,op=ty,pipe=pipe,cycles=cycles));es.extend(dict(source=t,target=i)for t in ins);es.extend(dict(source=i,target=t)for t in outs);return i
 for j in range(n):
  preds=[i for i in range(j) if r.random()<.25]
  if preds:
   ins=[outs[i] for i in preds]
   for i in preds:succ[i]+=1
  else:
   sz=r.choice([0,1,59,60,61,128]);a=tensor('DDR',sz);b=tensor('UB',sz);op('COPY_IN','PIPE_MTE2',1,[a],[b]);ins=[b]
  out=tensor('UB',r.choice([0,1,60,64,128]));op('ADD','PIPE_V',r.choice([0,1,2,17,101]),ins,[out]);outs.append(out)
 for i,t in enumerate(outs):
  if not succ[i]:a=tensor('DDR',next(x['size']for x in ts if x['id']==t));op('COPY_OUT','PIPE_MTE3',1,[t],[a])
 ids=[x['id']for x in ops+ts];shuffled=ids[:];r.shuffle(shuffled);rename=dict(zip(ids,shuffled))
 for x in ts+ops:x['id']=rename[x['id']]
 for x in es:x.update(source=rename[x['source']],target=rename[x['target']])
 r.shuffle(ts);r.shuffle(ops);r.shuffle(es);return dict(tensors=ts,ops=ops,edges=es)
if __name__=='__main__':
 e=load();f=load(ROOT/'fast_code');out=ROOT/'results/random_regression';out.mkdir(exist_ok=True);rows=[]
 for i in range(20):
  g=graph(2026092300+i);save_json(out/f'g{i:02d}.json',g);cores=2+i%4
  ps=[component_plan(g,cores=cores),intervals(g,cores=cores,chunks=3)]
  bad=json.loads(json.dumps(ps[0]));bad['node_to_subgraph'].pop(next(iter(bad['node_to_subgraph'])));ps.append(bad)
  for j,p in enumerate(ps):
   save_json(out/f'g{i:02d}_p{j}.json',p)
   for q in [1,2,3]:
    outputs=[];row={'graph':i,'plan':j,'q':q,'deliberately_missing_mapping':j==2}
    for name,mods in [('E0',e),('R2',f)]:
     err=io.StringIO()
     try:
      with contextlib.redirect_stderr(err):rr=evaluate(mods,q,g,p)
      outputs.append(('ok',rr));save_json(out/f'g{i:02d}_p{j}_q{q}.{name}.json.gz',rr)
     except Exception as ex:outputs.append(('error',{'type':type(ex).__name__,'message':str(ex),'stderr':err.getvalue()}))
    strict_equal(*outputs);row.update(equal=True,status=outputs[0][0]);
    if outputs[0][0]=='error':row['error']=outputs[0][1]
    rows.append(row)
  save_json(out/'summary.json',{'seed_start':2026092300,'rows':rows})
 print(len(rows),'comparisons',sum(x['status']=='ok'for x in rows),'success',sum(x['status']=='error'for x in rows),'errors, all matched')
