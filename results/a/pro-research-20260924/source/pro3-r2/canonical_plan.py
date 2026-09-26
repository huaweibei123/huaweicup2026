"""Q2/Q3 score-equivalent coarsening, guarded by public legality and literal word equality.
Adjacent buckets are merged only across an ascent in the raw augmented Step1 rank.
Entire candidate is rejected (original returned) if simultaneous coarsening cycles.
"""
from word_quotient import WordEvaluator

def coarsen(context:WordEvaluator,plan):
 view,labels,words,key=context.view_and_words(plan);new_sg={};schedules=[];next_id=0
 for c,order in view['core_orders'].items():
  rawpos={o:i for i,o in enumerate(context.raw_seq[c])};bounds={sg:[] for sg in order}
  for o in words[c]:bounds[labels[c][o]].append(rawpos[o])
  new_order=[];previous_last=None;current=None
  for sg in order:
   ranks=bounds[sg]
   if not ranks:raise ValueError('empty subgraph operational bucket')
   if current is None or previous_last>=ranks[0]:
    current=next_id;next_id+=1;new_order.append(current)
   new_sg[sg]=current;previous_last=ranks[-1]
  schedules.append(new_order)
 candidate={'node_to_subgraph':{k:new_sg[v]for k,v in plan['node_to_subgraph'].items()},'core_schedules':schedules}
 try:
  newkey=context.view_and_words(candidate)[-1]
 except (ValueError,RuntimeError) as ex:
  return plan,{'accepted':False,'reason':str(ex),'subgraphs_before':len(view['subgraph_ids'])}
 if key!=newkey:raise AssertionError('ascent guard failed literal augmented-word check')
 return candidate,{'accepted':True,'subgraphs_before':len(view['subgraph_ids']),'subgraphs_after':next_id,'same_augmented_word':True}

if __name__=='__main__':
 from runtime import *
 from plans import component_plan,from_blocks
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--case',default='097');ap.add_argument('--q',type=int,default=3);a=ap.parse_args()
 out=ROOT/f'results/canonical/{a.case}_q{a.q}';out.mkdir(parents=True,exist_ok=True)
 e=load();f=load(ROOT/'fast_code');g=json.loads((OFF/f'data/case_{a.case}.json').read_bytes());seed=component_plan(g,cores=4)
 ctx=WordEvaluator(f,a.q,g,seed);eligible=set(ctx.seed_core);blocks=[];assign=[]
 for c,seq in ctx.raw_seq.items():
  for o in seq:
   if o in eligible:blocks.append([o]);assign.append(c)
 p=from_blocks(blocks,assign,4);candidate,certificate=coarsen(ctx,p);save_json(out/'input.plan.json',p);save_json(out/'canonical.plan.json',candidate)
 results=[]
 for name,plan in [('input',p),('canonical',candidate)]:
  t=time.perf_counter();r=evaluate(e,a.q,g,plan);e0secs=time.perf_counter()-t;save_json(out/(name+'.E0.json.gz'),r)
  t=time.perf_counter();rr=ctx.evaluate(plan);wsecs=time.perf_counter()-t;strict_equal(r,rr);save_json(out/(name+'.WORD.json.gz'),rr)
  results.append({'name':name,'makespan':r['makespan'],'full_equal':True,'traffic':r['data_movement_bytes'],'E0_seconds':e0secs,'word_seconds':wsecs})
 save_json(out/'summary.json',{'certificate':certificate,'prepare_seconds':ctx.prepare_seconds,'hits':ctx.hits,'misses':ctx.misses,'rows':results});print(certificate,results,ctx.hits,ctx.misses)
