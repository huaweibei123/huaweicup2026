"""Four-way cold-cache batch ablation; each batch has eight distinct preprovided plans.
The selected pool intentionally refines the same augmented operation word.
Includes module load, parsing, fixed-context preparation, full output construction.
Excludes interpreter startup, comparison and file output. No cross-repeat memoization.
"""
from runtime import *
from word_quotient import WordEvaluator
import argparse,gc,statistics

def once(case,q,mode):
 t=time.perf_counter();mods=load(ROOT/'fast_code' if mode in ('S','W_S') else None)
 cfg=settings(mods);g=json.loads((OFF/f'data/case_{case}.json').read_bytes())
 ps=[json.loads(p.read_bytes()) for p in sorted((ROOT/f'results/word/case_{case}_q{q}').glob('*.plan.json'))]
 ctx=WordEvaluator(mods,q,g,ps[0],cfg) if mode.startswith('W_') else None
 rs=[ctx.evaluate(p) if ctx else evaluate(mods,q,g,p,cfg) for p in ps]
 return time.perf_counter()-t,rs,{'hits':ctx.hits if ctx else 0,'misses':ctx.misses if ctx else len(ps),'plans':len(ps),'prepare_seconds':ctx.prepare_seconds if ctx else 0}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--case',default='080');ap.add_argument('--q',type=int,default=3);ap.add_argument('--repeats',type=int,default=5);a=ap.parse_args()
 folder=ROOT/f'results/word_ablation/{a.case}_q{a.q}';folder.mkdir(parents=True,exist_ok=False)
 report={'case':a.case,'q':a.q,'repeats_requested':a.repeats,'scope':__doc__,'rows':[]};modes=['E0','S','W_E0','W_S']
 for i in range(a.repeats):
  order=modes[i%4:]+modes[:i%4];row={'rep':i,'order':order};ref=None
  for mode in order:
   gc.collect();secs,rs,info=once(a.case,a.q,mode);row[mode]={'seconds':secs,**info}
   if ref is None:ref=rs
   else:strict_equal(ref,rs)
   if i==0:save_json(folder/(mode+'.full_batch.json.gz'),rs)
  row['four_way_full_equal']=True;report['rows'].append(row);save_json(folder/'summary.json',report);print(i,{m:round(row[m]['seconds'],4) for m in modes},flush=True)
 report['medians']={m:statistics.median(r[m]['seconds']for r in report['rows']) for m in modes}
 report['speedup_vs_E0']={m:report['medians']['E0']/report['medians'][m]for m in modes}
 report['completed']=True;save_json(folder/'summary.json',report);print(report['medians'],report['speedup_vs_E0'],flush=True)
