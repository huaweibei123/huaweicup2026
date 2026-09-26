"""Derive mechanism summaries from saved complete official results; no new E0 calls."""
import json,gzip,statistics,collections
from pathlib import Path
R=Path('/mnt/data/r2_research')
def result(rel): return json.load(gzip.open(R/'runs'/rel/'result.json.gz','rt'))
def plan(rel):return json.loads((R/'runs'/rel/'plan.json').read_text())
def coremap(p):
 cs={s:k for k,order in enumerate(p['core_schedules']) for s in order}
 return {u:cs[s] for u,s in p['node_to_subgraph'].items()}
def details(rel):
 d=result(rel)
 return {'path':'runs/'+rel,'makespan':d['makespan'],'movement':d['data_movement_bytes'],'memory_peak_by_core':d['memory_peak_by_core'],'pipes':[{'core':c['core_id'],'work':dict(collections.Counter({p:sum(o['duration'] for o in c['ops'] if o['pipe']==p) for p in ['PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3']})),'first_M_ops':[o['op_id'] for o in c['ops'] if o['pipe']=='PIPE_M'][:14]} for c in d['per_core_timeline']]}
base='resource_word/case_008_p2_components';word='resource_word/case_008_p2_word'
out={'pipe_word':{'baseline':details(base),'word':details(word),'same_core_assignment':coremap(plan(base))==coremap(plan(word)),'same_movement':result(base)['data_movement_bytes']==result(word)['data_movement_bytes'],'global_compute_lower_bound':62532,'official_gap_upper_bound':63768/62532-1}}
paths=[str(p.parent.relative_to(R/'runs')) for p in (R/'runs/first').glob('case_044_p2_*/run.json')]
b='first/case_044_p2_comp_lpt';s=next(p for p in paths if p.endswith('wave_all_band4'))
out['spill_elimination']={'baseline':details(b),'band4':details(s),'same_core_assignment':coremap(plan(b))==coremap(plan(s))}
comp=json.loads((R/'runs/compaction/summary.json').read_text());group=collections.defaultdict(list)
for x in comp:group[(x['case'],x['groups'])].append(x)
out['compaction']={str(k):{'median_total_seconds':statistics.median(x['paired_total_seconds'] for x in v),'median_e0_seconds':statistics.median(x['official_cli_seconds'] for x in v),'groups':k[1],'repeats':len(v)} for k,v in group.items()}
large=json.loads((R/'runs/large/summary.json').read_text());horizon=min(x['elapsed_seconds'] for x in large)
out['large_common_internal_horizon']={'seconds':horizon}
for policy in ['baseline','structured']:
 h=json.loads((R/'runs/large'/policy/'history.json').read_text());v=[x['makespan'] for x in h if x.get('status')=='ok' and x.get('elapsed_seconds',float('inf'))<=horizon]
 out['large_common_internal_horizon'][policy]=min(v) if v else None
(R/'analysis/mechanism_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k in ['compaction','large_common_internal_horizon']},indent=2));print('same cores/movement',out['pipe_word']['same_core_assignment'],out['pipe_word']['same_movement']);print('44samecores',out['spill_elimination']['same_core_assignment'])
