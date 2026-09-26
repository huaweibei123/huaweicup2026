"""Recompute headline numbers from recorded outputs, never from prose summaries."""
from pathlib import Path
import json, statistics, math
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text())
def main():
 s={'run_identity':'route3-round2-20260923','official_verification':read('evidence/official_verification.json'),'bundle_verification':read('evidence/bundle_verification.json'),'environment':read('evidence/environment.json'),'claims':'bounded research experiments, not all-case final solver or complete E1/E2 acceptance'}
 s['scan_benchmarks']=[]
 for p in ['001_q1_components','003_q1_intervals','003_q2_intervals']:
  d=read(f'results/benchmark/{p}/summary.json');assert d['completed'] and len(d['runs'])==d['repeats_requested']
  s['scan_benchmarks'].append({'source':f'results/benchmark/{p}/summary.json','case':d['case'],'question':d['q'],'pairs':len(d['runs']),'warmups_per_engine':d['warmups_per_engine'],'E0_median_seconds':d['E0_median_seconds'],'S_median_seconds':d['R2_median_seconds'],'ratio_of_medians':d['speedup'],'all_full_equal':all(r['E0_full_equal'] and r['R2_full_equal']for r in d['runs'])})
 reps=[read(f'results/benchmark/025_isolated/rep{i}.json')for i in range(3)];assert all(x['full_equal']for x in reps)
 a=statistics.median(x['E0_seconds']for x in reps);b=statistics.median(x['R2_seconds']for x in reps)
 s['scan_benchmarks'].append({'source':'results/benchmark/025_isolated/rep{0,1,2}.json','case':'025','question':1,'pairs':3,'warmups_per_engine':0,'fresh_process_per_pair':True,'E0_median_seconds':a,'S_median_seconds':b,'ratio_of_medians':a/b,'geomean_paired_ratios':math.exp(statistics.mean(math.log(x['E0_seconds']/x['R2_seconds'])for x in reps)),'all_full_equal':True,'comparison_process_peak_rss_kib':max(x['peak_rss_kib']for x in reps)})
 ws=[json.loads(p.read_text())for p in sorted((ROOT/'results/word').glob('*/summary.json'))]
 s['word_equivalence']={'graphs':[d['case']for d in ws],'comparisons':sum(len(d['rows'])for d in ws),'all_full_equal':all(r['full_equal']for d in ws for r in d['rows']),'misses':sum(d['cache_misses']for d in ws),'hits':sum(d['cache_hits']for d in ws),'distribution':'syntactic refinements designed around fixed-core raw words; not arbitrary candidate stream'}
 s['word_batch_with_S']=[read(f'results/word_batch/{x}.json')for x in ['001_q2','080_q3']]
 s['word_ablation']=read('results/word_ablation/080_q3/summary.json')
 s['canonical']=read('results/canonical/097_q3/summary.json')
 gs=[json.loads(p.read_text())for p in sorted((ROOT/'results/grid').glob('*/summary.json'))]
 s['grid']={'comparisons':sum(len(d['rows'])for d in gs),'all_full_equal':all(r['full_equal']for d in gs for r in d['rows']),'pools':[]}
 for d in gs:
  b=d['rows'][0];best=min(d['rows'],key=lambda r:r['makespan']);s['grid']['pools'].append({'case':d['case'],'question':d['q'],'candidates':len(d['rows']),'baseline':b['makespan'],'best':best['makespan'],'best_name':best['name'],'relative_reduction':1-best['makespan']/b['makespan'],'rows':d['rows']})
 s['input_products']=read('evidence/incidence_products_100.json')
 rs=[json.loads(p.read_text())for p in sorted((ROOT/'results/regression64').glob('*.run.json'))];assert len(rs)==64
 s['provided64_fresh_replay']={'candidates':len(rs),'fresh_full_outputs':3*len(rs),'E0_S_memberE1_all_equal':all(x['fresh_full_equal'] and all(x[f'{e}_matches_supplied_JSON']for e in ['E0','R2','member_E1'])for x in rs),'scope':'same original case001/P1 developer pool, fresh identity; not missing historical 295 outputs'}
 rr=read('results/random_regression/summary.json')['rows'];s['random_regression']={'comparisons':len(rr),'success':sum(r['status']=='ok'for r in rr),'rejection':sum(r['status']=='error'for r in rr),'all_equal':all(r['equal']for r in rr),'rejection_scope':'all deliberately missing mapping, not a complete failure matrix'}
 epochs=read('results/epochs/summary.json');s['pool_epoch_states']={'rows':epochs,'count':sum(x['events']for x in epochs),'all_equal':all(x['equal']for x in epochs),'scope':'helper return snapshots; read-only hooks, not performance benchmark'}
 s['cli']=read('results/cli/summary.json')
 s['counterexamples']={name:read(f'results/counterexamples/{name}/summary.json')for name in ['float_epochs_with_input','fork','head_blocking','hit_reinsert']}
 s['counterexamples']['S_on_float_boundary']=read('results/counterexamples/float_epochs_with_input/S_check.json')
 s['solver']=[read(f'results/solver080_q{x}/run.json')for x in [2,3]]
 s['official_cases_scored_at_least_once']=['001','003','004','008','011','019','025','027','037','059','080','097']
 s['not_done']=['100-case x 2-5 core final optimization matrix','full E1 release acceptance','E2 error/speed acceptance','CUDA/Metal/Apple/Windows execution','representative-stream word cache hit rate','automatic general trace-guided HOL/export refinement','hard preemptible parent preparation','per-patch isolated speed ablation','recovery of missing 295 historical full results']
 (ROOT/'evidence/SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print('SUMMARY recomputed:',len(s['official_cases_scored_at_least_once']),'official cases,',s['word_equivalence']['comparisons'],'word,',s['grid']['comparisons'],'grid,',len(rs),'provided-pool,',len(rr),'random,',s['pool_epoch_states']['count'],'epoch states')
if __name__=='__main__':main()
