"""Cold-cache in-process batch; B different preprovided plans. Include decode, isolated
module load, config, WordEvaluator preparation, full result construction. Exclude
interpreter launch/output serialization. Word cache recreated for EVERY repetition.
"""
from runtime import *
from word_quotient import WordEvaluator
import argparse,statistics,gc

def once(case,q,engine):
 start=time.perf_counter();mods=load(None if engine=='E0' else ROOT/'fast_code');cfg=settings(mods);g=json.loads((OFF/f'data/case_{case}.json').read_bytes());folder=ROOT/f'results/word/case_{case}_q{q}';ps=[json.loads(p.read_bytes())for p in sorted(folder.glob('*.plan.json'))]
 w=None if engine=='E0' else WordEvaluator(mods,q,g,ps[0],cfg);rs=[evaluate(mods,q,g,p,cfg) if w is None else w.evaluate(p) for p in ps];elapsed=time.perf_counter()-start
 return elapsed,rs,{'plans':len(ps),'hits':w.hits if w else 0,'misses':w.misses if w else len(ps),'prepare_seconds':w.prepare_seconds if w else 0}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--case',default='080');ap.add_argument('--q',type=int,default=3);ap.add_argument('--repeats',type=int,default=5);a=ap.parse_args();out=ROOT/'results/word_batch';out.mkdir(exist_ok=True);report={'case':a.case,'q':a.q,'repeats':a.repeats,'scope':__doc__,'provided_candidate_pool':'eight different JSON plans, intentionally same augmented operational word; not representative of arbitrary search','rows':[]}
 for i in range(a.repeats):
  row={'rep':i};outs={}
  for engine in (['E0','WORD'] if i%2==0 else ['WORD','E0']):
   gc.collect();secs,rs,info=once(a.case,a.q,engine);row[engine+'_seconds']=secs;row[engine+'_info']=info;outs[engine]=rs
  strict_equal(outs['E0'],outs['WORD']);row['full_equal']=True;report['rows'].append(row);save_json(out/f'{a.case}_q{a.q}.json',report);print(row,flush=True)
 report['E0_median']=statistics.median(r['E0_seconds']for r in report['rows']);report['WORD_median']=statistics.median(r['WORD_seconds']for r in report['rows']);report['ratio_of_medians']=report['E0_median']/report['WORD_median'];save_json(out/f'{a.case}_q{a.q}.json',report)
