from runtime import *
from plans import *
from word_quotient import WordEvaluator
import random,statistics,gc,traceback

def refinements(w,p,random_count=0):
 candidates=[('seed',p)];cores=len(p['core_schedules']);eligible=w.eligible
 for width in [1,2,4,8,16,32,64]:
  blocks=[];ass=[]
  for c,raw in w.raw_seq.items():
   vs=[v for v in raw if v in eligible]
   for i in range(0,len(vs),width):blocks.append(vs[i:i+width]);ass.append(c)
  candidates.append((f'raw_word_width{width}',from_blocks(blocks,ass,cores)))
 for seed in range(random_count):
  rng=random.Random(93000+seed);blocks=[];ass=[];rate=[.04,.12,.3,.7][seed%4]
  for c,raw in w.raw_seq.items():
   block=[]
   for v in raw:
    if v not in eligible:continue
    block.append(v)
    if rng.random()<rate:blocks.append(block);ass.append(c);block=[]
   if block:blocks.append(block);ass.append(c)
  candidates.append((f'random_cuts_{seed}',from_blocks(blocks,ass,cores)))
 seen=set();out=[]
 for name,pp in candidates:
  k=json.dumps(pp,separators=(',',':'))
  if k not in seen:seen.add(k);out.append((name,pp))
 return out

def run(case,q,random_count=0):
 out=ROOT/f'results/word/case_{case}_q{q}';out.mkdir(parents=True,exist_ok=True)
 e=load();f=load(ROOT/'fast_code');g=json.loads((OFF/f'data/case_{case}.json').read_bytes());t=time.perf_counter();p=component_plan(g,granularity='bins');seedsecs=time.perf_counter()-t
 w=WordEvaluator(f,q,g,p);candidates=refinements(w,p,random_count);rows=[]
 for i,(name,p) in enumerate(candidates):
  row={'i':i,'name':name,'subgraphs':len(set(p['node_to_subgraph'].values()))};save_json(out/f'{i:03d}.plan.json',p)
  h,m=w.hits,w.misses
  try:
   t=time.perf_counter();r0=evaluate(e,q,g,p);row['e0_seconds']=time.perf_counter()-t;save_json(out/f'{i:03d}.E0.json.gz',r0)
   t=time.perf_counter();r=w.evaluate(p,full=True);row['word_seconds']=time.perf_counter()-t;save_json(out/f'{i:03d}.WORD.json.gz',r)
   strict_equal(r0,r);row.update(full_equal=True,makespan=r['makespan'],added_bytes=r['data_movement_bytes']['added_copy_bytes'],cache_hits=r.get('cache_stats',{}).get('hits'),word_hash=hashlib.sha256(repr(w.view_and_words(p)[-1]).encode()).hexdigest())
  except Exception as ex:row.update(error_type=type(ex).__name__,error=str(ex));print('ERROR',row,flush=True)
  row['cache_hit']=w.hits>h;row['cache_miss']=w.misses>m;rows.append(row)
  save_json(out/'summary.json',{'case':case,'q':q,'seed_seconds':seedsecs,'prepare_seconds':w.prepare_seconds,'cache_hits':w.hits,'cache_misses':w.misses,'rows':rows})
  print(case,q,name,row.get('makespan'),row.get('e0_seconds'),row.get('word_seconds'),row['cache_hit'],flush=True)
 return rows
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',default=['001','004','008','019','080','003','025']);ap.add_argument('--questions',nargs='+',type=int,default=[2,3]);ap.add_argument('--random-count',type=int,default=0);a=ap.parse_args()
 for case in a.cases:
  for q in a.questions:run(case,q,a.random_count)
