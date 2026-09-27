"""Test coalescing ordinary-compute settlement epochs, NOT an exact engine."""
from runtime import *
from plans import from_blocks
import types,ast,signal

def make_graph(n,size=480000):
 ops=[];ts=[];edges=[];nextid=1;blocks=[]
 def tensor(pos,size):
  nonlocal nextid
  i=nextid;nextid+=1;ts.append(dict(id=i,pos=pos,size=size));return i
 def op(ty,pipe,cycles,ins=(),outs=()):
  nonlocal nextid
  i=nextid;nextid+=1;ops.append(dict(id=i,op=ty,pipe=pipe,cycles=cycles));edges.extend(dict(source=t,target=i) for t in ins);edges.extend(dict(source=i,target=t) for t in outs);return i
 for c in range(3):
  a=tensor('DDR',size);b=tensor('L1',size);d=tensor('L1',1);e=tensor('DDR',1)
  op('COPY_IN','PIPE_MTE2',1,[a],[b]);v=op('ADD','PIPE_M',1,[b],[d]);op('COPY_OUT','PIPE_MTE3',1,[d],[e]);blocks.append([v])
 vs=[];prev=None
 for k in range(n):
  t=tensor('UB',1);v=op('ADD','PIPE_V',1,[] if prev is None else [prev],[t]);vs.append(v);prev=t
 out=tensor('DDR',1);op('COPY_OUT','PIPE_MTE3',1,[prev],[out]);blocks.append(vs)
 return {'ops':ops,'tensors':ts,'edges':edges},from_blocks(blocks,list(range(4)),4)

def run():
 e=load();m=e['multicore_cut_evaluate_problem_2'];cfg=settings(e);source=Path(m.__file__).read_text();tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='evaluate_scene_b');src='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])
 a='''        advance_ddr_work(now)
        retired_ddr = False'''
 b='''        # Incorrect "real-equivalent" optimization under test:
        # only settle when a bandwidth operation retires (new issues still settle).
        if any(item in ddr_remaining_work and end <= now
               for running in executors.values() for item, end in running):
            advance_ddr_work(now)
        retired_ddr = False'''
 assert src.count(a)==1
 ns=dict(m.__dict__);exec(compile(src.replace(a,b),'<coalesced-compute-epochs>','exec'),ns);wrong=ns['evaluate_scene_b'];out=ROOT/'results/counterexamples/float_epochs';out.mkdir(parents=True,exist_ok=True);rows=[]
 (out/'mutation.diff.txt').write_text(a+'\n--REPLACED-WITH--\n'+b)
 for n in [1,64,512,1024,2048,3072,4096,6144]:
  g,p=make_graph(n);t=time.perf_counter();r=evaluate(e,2,g,p,cfg);rr=wrong(g,p,bandwidth=cfg['bandwidth'],capacity=cfg['capacity'],cross_core_copy_delay=cfg['cross_core_copy_delay_cycles']);diff=None
  try:strict_equal(r,rr)
  except AssertionError as ex:diff=str(ex)
  row={'n':n,'E0':r['makespan'],'coalesced':rr['makespan'],'difference':diff,'seconds':time.perf_counter()-t};rows.append(row);print(row,flush=True)
  if diff:
   save_json(out/'graph.json',g);save_json(out/'plan.json',p);save_json(out/'E0.result.json.gz',r);save_json(out/'coalesced.result.json.gz',rr);break
 save_json(out/'summary.json',rows)
if __name__=='__main__':run()
