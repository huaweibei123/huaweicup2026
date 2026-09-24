"""Read-only analysis of three existing official results; no solver/evaluator.

PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/tree-trace-diagnosis-20260925/diagnose.py
No imports from solver or official execution code. No subprocesses/network.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
RUN=ROOT/'results/a/q2-nikolastarx/tree-pilot-20260924/run'
GRAPH=ROOT/'data/raw/a/official/data/case_062.json'
SOURCES=['src/q2_nikolastarx/tree_frontier.py','docs/a/q2-nikolastarx/PRO_R01_REVIEW.md',
         'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py',
         'data/raw/a/official/code/step3.py']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
def dump(name,value):
 with (OUT/name).open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

graph=read(GRAPH);ops={o['id']:o for o in graph['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
tensors={t['id']:t for t in graph['tensors']}
producers=defaultdict(list);consumers=defaultdict(list)
for e in graph['edges']:
 a,b=e['source'],e['target']
 if a in ops and b in tensors:producers[b].append(a)
 if a in tensors and b in ops:consumers[a].append(b)
pred={u:set() for u in ops}
for t,ps in producers.items():
 assert len(ps)==1
 for v in consumers[t]:pred[v].update(ps)
assert all(len(consumers[t])<=1 for t in producers)

def longest_path(nodes,edges,durations,actual=None):
 """A DAG bound/witness only: no event simulation or candidate construction."""
 succ=defaultdict(list);degree=Counter();parents=defaultdict(list)
 for (a,b),(lag,label) in edges.items():
  succ[a].append((b,lag,label));degree[b]+=1;parents[b].append((a,lag,label))
 ready=[u for u in nodes if degree[u]==0];heapq.heapify(ready)
 distance={u:durations[u] for u in nodes};back={};visited=0
 while ready:
  a=heapq.heappop(ready);visited+=1
  for b,lag,label in succ[a]:
   value=distance[a]+lag+durations[b]
   if value>distance[b] or (value==distance[b] and a<back.get(b,(10**30,))[0]):
    distance[b]=value;back[b]=(a,lag,label)
   degree[b]-=1
   if not degree[b]:heapq.heappush(ready,b)
 assert visited==len(nodes),'constraint cycle'
 end=max(nodes,key=lambda u:(distance[u],-u));path=[];u=end
 while True:
  before=back.get(u)
  row={'op':u,'duration':durations[u],'path_finish':distance[u],
       'incoming_lag':before[1] if before else 0,'incoming_constraint':before[2] if before else 'source'}
  if actual:
   row.update(core=actual[u]['core'],pipe=actual[u]['pipe'],start=actual[u]['start'],end=actual[u]['end'])
  path.append(row)
  if not before:break
  u=before[0]
 path.reverse()
 return distance[end],path,parents

report={'kind':'posthoc trace diagnosis; no solver, candidate or score produced',
        'created_at':datetime.now(timezone.utc).isoformat(),'calls':{'solver':0,'E0':0,'E1':0,'E2':0},
        'seed':None,'input_sha256':sha(GRAPH),'script_sha256':sha(Path(__file__)),
        'source_sha256':{p:sha(ROOT/p) for p in SOURCES if (ROOT/p).exists()},'rows':[]}
for k in [2,4,5]:
 folder=RUN/f'062-k{k}';result=read(folder/'final/result.json.gz');plan=read(folder/'plan.json')
 detail=read(folder/'online/solver.json')['attempts'][0]['detail'];trace=read(folder/'final/trace.json.gz')
 assert result['data_movement_bytes']['spill_added_copy_bytes']==0
 reverse={sg:int(u) for u,sg in plan['node_to_subgraph'].items()}
 sequences=[[reverse[sg] for sg in seq] for seq in plan['core_schedules']]
 owner={u:c for c,seq in enumerate(sequences) for u in seq}
 actual={};core_rows=[];by_pipe={};compute_edges={};all_edges={}
 def edge(edges,a,b,lag,label):
  if a==b:return
  prior=edges.get((a,b))
  if prior is None or lag>prior[0]:edges[a,b]=(lag,label)
 for core in result['per_core_timeline']:
  c=core['core_id'];entries=core['ops'];pipes=defaultdict(list)
  for e in entries:
   assert e['op_id'] not in actual
   actual[e['op_id']]={**e,'core':c};pipes[e['pipe']].append(e)
  p_rows={}
  for p,es in sorted(pipes.items()):
   es.sort(key=lambda e:(e['start'],e['op_id']));by_pipe[c,p]=es
   gaps=[];last=0;prev=None
   for e in es:
    assert e['start']>=last
    if e['start']>last:gaps.append({'start':last,'end':e['start'],'cycles':e['start']-last,
                                      'previous_op':prev,'next_op':e['op_id']})
    if prev is not None:edge(all_edges,prev,e['op_id'],0,'fixed pipe FIFO')
    last=e['end'];prev=e['op_id']
   busy=sum(e['duration'] for e in es)
   p_rows[p]={'count':len(es),'busy_cycles':busy,'first_start':es[0]['start'],'last_end':last,
              'idle_through_last_end':last-busy,'tail_idle_to_makespan':result['makespan']-last,
              'utilization_full_run':busy/result['makespan'],'largest_gaps':sorted(gaps,key=lambda g:-g['cycles'])[:8]}
  core_rows.append({'core':c,'task_end':core['tasks'][0]['end'],'pipes':p_rows})
 # Verify trace operation records against result.json; SUBGRAPH spans are not ops.
 trace_ops=[e for e in trace['traceEvents'] if e['ph']=='X' and e.get('cat','').startswith('PIPE_')]
 assert len(trace_ops)==len(actual)
 for e in trace_ops:
  a=actual[e['args']['op_id']]
  assert (e['args']['core_id'],e['ts'],e['dur'])==(a['core'],a['start'],a['duration'])
 for c,seq in enumerate(sequences):
  for p in ['PIPE_M','PIPE_V']:
   word=[u for u in seq if ops[u]['pipe']==p]
   observed=[e['op_id'] for e in by_pipe.get((c,p),[]) if e['op_id'] in ops]
   assert word==observed
   for a,b in zip(word,word[1:]):edge(compute_edges,a,b,0,'fixed compute FIFO')
 for b,ps in pred.items():
  for a in ps:
   edge(compute_edges,a,b,0,'retained original compute dependency')
 # Reconstruct only COPY incidence labels, not Step1/2/3. On this guarded graph
 # each singleton bucket's sorted COPY IDs follow sorted original tensor IDs.
 inputs=defaultdict(list);outputs=defaultdict(list)
 for t,cs in consumers.items():
  if not producers[t]:
   for c in sorted({owner[u] for u in cs}):
    first=min((u for u in cs if owner[u]==c),key=lambda u:sequences[c].index(u))
    inputs[c,first].append((t,[u for u in cs if owner[u]==c],None))
  else:
   a=producers[t][0]
   for b in cs:
    if owner[a]==owner[b]:edge(all_edges,a,b,0,'retained local tensor dependency')
    else:
     inputs[owner[b],b].append((t,[b],a));outputs[owner[a],a].append((t,'cross'))
 for t,ps in list(producers.items()):
  if ps and not consumers[t]:outputs[owner[ps[0]],ps[0]].append((t,'output'))
 copy_groups=defaultdict(list)
 for u,e in actual.items():
  if u not in ops:copy_groups[e['core'],reverse[e['subgraph_id']],e['op']].append(u)
 copy_tid={}
 for (c,u),items in inputs.items():
  ids=sorted(copy_groups[c,u,'COPY_IN']);items.sort()
  assert len(ids)==len(items)
  for copy_id,(tid,cs,source) in zip(ids,items):
   copy_tid[copy_id]=tid
   for v in cs:edge(all_edges,copy_id,v,0,'tensor COPY_IN to compute')
 for (c,u),items in outputs.items():
  ids=sorted(copy_groups[c,u,'COPY_OUT']);items.sort()
  assert len(ids)==len(items)
  for copy_id,(tid,kind) in zip(ids,items):
   copy_tid[copy_id]=tid;edge(all_edges,u,copy_id,0,'compute to tensor COPY_OUT')
 for link in result['cross_core_transfers']:
  a,b=link['source_copy_out_id'],link['target_copy_in_id']
  assert copy_tid[a]==copy_tid[b]==link['tensor_id']
  edge(all_edges,a,b,result['cross_core_copy_delay_cycles'],'cross-core release')
 assert set(copy_tid)==set(actual)-set(ops)
 for (a,b),(lag,label) in all_edges.items():
  assert actual[a]['end']+lag<=actual[b]['start'],(a,b,label)
 original_dur={u:max(1,o['cycles']) for u,o in ops.items()}
 compute_lb,compute_path,_=longest_path(list(ops),compute_edges,original_dur,actual)
 min_dur={u:original_dur[u] if u in ops else max(1,math.ceil(tensors[copy_tid[u]]['size']/60)) for u in actual}
 copy_lb,copy_path,parents=longest_path(list(actual),all_edges,min_dur,actual)
 observed_dur={u:e['duration'] for u,e in actual.items()}
 observed_lp,observed_path,_=longest_path(list(actual),all_edges,observed_dur,actual)
 residual=[]
 for u,e in actual.items():
  readiness=max((actual[a]['end']+lag for a,lag,_ in parents[u]),default=0)
  if readiness<e['start']:residual.append({'op':u,'core':e['core'],'pipe':e['pipe'],
                                        'known_ready':readiness,'start':e['start'],'unexplained_wait':e['start']-readiness})
 packet_rows=[];packet_of={}
 for p in detail['packets']:
  members=[];stack=[p['root']]
  while stack:
   u=stack.pop();members.append(u);stack.extend(pred[u])
  assert len(members)==p['ops'] and all(owner[u]==p['core'] for u in members)
  for u in members:
   assert u not in packet_of;packet_of[u]=p['root']
  es=[actual[u] for u in members]
  packet_rows.append({**p,'compute_start':min(e['start'] for e in es),'compute_end':max(e['end'] for e in es),
                      'compute_span':max(e['end'] for e in es)-min(e['start'] for e in es),
                      'pipe_work':dict(Counter({pipe:sum(ops[u]['cycles'] for u in members if ops[u]['pipe']==pipe)
                                               for pipe in ['PIPE_M','PIPE_V']}))})
 for seq in sequences:
  for u in seq:
   if u not in packet_of:packet_of[u]='skeleton'
 transfer_rows=[]
 for link in result['cross_core_transfers']:
  inc=actual[link['target_copy_in_id']];word=by_pipe[inc['core'],'PIPE_MTE2'];pos=next(i for i,e in enumerate(word) if e['op_id']==inc['op_id'])
  previous=word[pos-1] if pos else None;following=word[pos+1] if pos+1<len(word) else None
  transfer_rows.append({**link,'release_to_start':link['copy_in_start']-link['copy_in_release'],
                       'previous_mte2':previous,'next_mte2':following,
                       'head_idle_before_copy':inc['start']-(previous['end'] if previous else 0),
                       'parent_compute':reverse[inc['subgraph_id']]})
 def summarize_path(path):
  return {'nodes':len(path),'work_by_pipe':dict(Counter({p:sum(x['duration'] for x in path if x['pipe']==p) for p in ['PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3']})),
          'lag_cycles':sum(x['incoming_lag'] for x in path),'core_changes':sum(a['core']!=b['core'] for a,b in zip(path,path[1:])),
          'packet_runs':list(dict.fromkeys(packet_of.get(x['op'],'COPY') for x in path if x['op'] in ops))}
 row={'cores':k,'makespan':result['makespan'],'spill_bytes':0,'extra_ddr_bytes':result['data_movement_bytes']['added_copy_bytes'],
      'input_hashes':{p:sha(folder/p) for p in ['final/result.json.gz','final/trace.json.gz','plan.json','online/solver.json']},
      'pipe_load_bound':max(x['pipes'][p]['busy_cycles'] for x in core_rows for p in ['PIPE_M','PIPE_V']),
      'fixed_compute_fifo_bound':compute_lb,'fixed_all_pipe_fifo_isolated_copy_bound':copy_lb,
      'observed_duration_known_constraint_longest_path':observed_lp,
      'actual_minus_observed_known_path':result['makespan']-observed_lp,
      'bound_scope':'candidate-specific bounds; no claim for other ownership/FIFO choices',
      'observed_path_scope':'posthoc with observed DDR durations; not a predictive evaluator or portable bound',
      'compute_path_summary':summarize_path(compute_path),'observed_path_summary':summarize_path(observed_path),
      'unexplained_readiness_residual_count':len(residual),'largest_unexplained_waits':sorted(residual,key=lambda x:-x['unexplained_wait'])[:12],
      'per_core':core_rows,'packets':packet_rows,'transfers':transfer_rows}
 dump(f'062-k{k}-paths.json',{'compute_fifo_path':compute_path,'all_pipe_isolated_copy_path':copy_path,'observed_duration_path':observed_path})
 dump(f'062-k{k}-diagnosis.json',row);report['rows'].append({key:row[key] for key in ['cores','makespan','pipe_load_bound','fixed_compute_fifo_bound','fixed_all_pipe_fifo_isolated_copy_bound','observed_duration_known_constraint_longest_path','actual_minus_observed_known_path','unexplained_readiness_residual_count']})
 print(json.dumps(report['rows'][-1]),flush=True)
dump('report.json',report)
