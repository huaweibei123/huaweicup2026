#!/usr/bin/env python3
"""Static DAG/chain/diamond survey of three archived P2 plans; never builds a plan."""
import sys
sys.dont_write_bytecode=True
import argparse,gzip,hashlib,json,subprocess
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
PILOT='a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075'
def git_blob(rev,path): return subprocess.check_output(['git','-C',str(ROOT),'show',f'{rev}:{path}'])
def sha(b): return hashlib.sha256(b).hexdigest()
def stat_hist(vals): return {str(k):v for k,v in sorted(Counter(vals).items())}
def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--raw-root',type=Path,required=True,help='directory containing the three manifest-hashed case_*.json files'); args=parser.parse_args()
 from src.q2_nikolastarx.dag_direct import DAGIndex
 from src.q2_nikolastarx.gap_candidate import _chain_dag
 base='results/a/q2-nikolastarx/gap-solver-pilot-20260925/'
 mr=git_blob(PILOT,base+'manifest.json'); manifest=json.loads(mr)
 archive=json.loads(git_blob(PILOT,base+'archive-manifest.json')); af={x['archive_path']:x for x in archive['files']}
 run=json.loads(git_blob(PILOT,base+'run/summary.json'))
 recs=[]
 for row in manifest['rows']:
  case=row['case']
  if case not in ('003','005','056'): continue
  gb=(args.raw_root/Path(row['graph']['path']).name).read_bytes()
  if sha(gb)!=row['graph']['sha256']: raise ValueError('graph hash mismatch '+case)
  graph=json.loads(gb); folder=base+f"run/{case}-k{row['cores']}/"
  pp=folder+'plan.json.gz'; rp=folder+'result.json.gz'
  pb=git_blob(PILOT,pp); rb=git_blob(PILOT,rp)
  for path,b in ((pp,pb),(rp,rb)):
   if path not in af or sha(b)!=af[path]['stored_sha256']: raise ValueError('archive hash mismatch '+path)
  plan_b=gzip.decompress(pb); plan=json.loads(plan_b)
  if sha(plan_b)!=af[pp]['original_sha256'] or sha(gzip.decompress(rb))!=af[rp]['original_sha256']: raise ValueError('archive roundtrip hash mismatch '+case)
  idx=DAGIndex(graph) # static graph/index construction only
  chains,pred,succ,delay,order=_chain_dag(idx,60,0) # chain DAG only; no placement/build
  owner={u:i for i,ch in enumerate(chains) for u in ch}
  sgcore={sg:c for c,seq in enumerate(plan['core_schedules']) for sg in seq}
  opcore={int(op):sgcore[sg] for op,sg in plan['node_to_subgraph'].items()}
  if set(opcore)!=set(idx.ops): raise ValueError('pilot assignment does not cover eligible ops')
  chain_cores=[{opcore[u] for u in ch} for ch in chains]
  # Find only strict local 2-way diamonds with bounded deterministic branch walks.
  diamonds=[]; scanned=0; truncated=0
  for f in range(len(chains)):
   starts=sorted(succ[f])
   if len(starts)!=2: continue
   paths=[]; joins=[]
   for start in starts:
    path=[]; prev=f; cur=start; found=None
    for _ in range(32):
     scanned+=1
     if len(pred[cur])>1:
      found=cur; break
     if pred[cur]!={prev} or len(succ[cur])!=1: break
     path.append(cur)
     prev,cur=cur,next(iter(succ[cur]))
    else: truncated+=1
    paths.append(path); joins.append(found)
   if joins[0] is None or joins[0]!=joins[1]: continue
   j=joins[0]
   # Branch interiors have unique in/out; the join has precisely the two path tails.
   tails={p[-1] if p else f for p in paths}
   if len(tails)!=2 or pred[j]!=tails: continue
   if set(paths[0]) & set(paths[1]): continue
   region_chains={f,j,*paths[0],*paths[1]}; region_ops=set(u for ci in region_chains for u in chains[ci])
   # Internal tensors have all eligible producers and consumers within the region.
   tensors=[]; internal_bytes=0; internal_cross=0
   for tid,t in idx.tensors.items():
    ps=set(idx.producers.get(tid,())); cs=set(idx.consumers.get(tid,()))
    if ps and cs and ps|cs <= region_ops:
     size=t['size']; tensors.append(tid); internal_bytes+=size
     sp={opcore[u] for u in ps}; tp={opcore[u] for u in cs}
     internal_cross+=2*size*sum(a!=b for a in sp for b in tp)
   direct_bytes=0
   for dst,ins in idx.direct_inputs.items():
    for src,size in ins:
     if src in region_ops and dst in region_ops and opcore[src]!=opcore[dst]: direct_bytes+=2*size
   pipe_work={p:sum(idx.duration(u) for u in region_ops if idx.ops[u]['pipe']==p) for p in ('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')}
   diamonds.append({'fork_chain':f,'join_chain':j,'branch_chains':paths,'chain_ids':sorted(region_chains),'eligible_ops':len(region_ops),'current_cores':sorted({opcore[u] for u in region_ops}),'pipe_work':pipe_work,'internal_tensor_count':len(tensors),'internal_tensor_payload_bytes':internal_bytes,'current_internal_cross_tensor_copy_bytes':internal_cross,'current_internal_cross_direct_copy_bytes':direct_bytes})
  pipe_names=('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')
  pipe_work={p:sum(idx.duration(u) for u,o in idx.ops.items() if o['pipe']==p) for p in pipe_names}
  tensors=[t for t in idx.tensors.values() if idx.producers.get(t['id']) and idx.consumers.get(t['id'])]
  consumer_counts=[len(idx.consumers[t['id']]) for t in tensors]
  internal_total=sum(t['size'] for t in tensors)
  # Candidate-region union counters are deduplicated.
  union_ops=set(u for d in diamonds for ci in d['chain_ids'] for u in chains[ci])
  union_tensors=[]
  for t in tensors:
   ps=set(idx.producers[t['id']]); cs=set(idx.consumers[t['id']])
   if ps|cs <= union_ops: union_tensors.append(t)
  union_cross_tensor=0
  for t in union_tensors:
   sp={opcore[u] for u in idx.producers[t['id']]}; tp={opcore[u] for u in idx.consumers[t['id']]}
   union_cross_tensor+=2*t['size']*sum(a!=b for a in sp for b in tp)
  union_cross_direct=sum(2*size for dst,ins in idx.direct_inputs.items() for src,size in ins if src in union_ops and dst in union_ops and opcore[src]!=opcore[dst])
  op_fork={u:len(idx.succ[u]) for u in idx.ops if len(idx.succ[u])>1}; op_join={u:len(idx.pred[u]) for u in idx.ops if len(idx.pred[u])>1}
  recs.append({'case':case,'cores':row['cores'],'graph_sha256':sha(gb),'selected_plan_sha256':sha(plan_b),'selected_result_gzip_sha256':sha(rb),'selected_cores_assignment_from_archived_pilot':True,'eligible_ops':len(idx.ops),'pipe_duration_totals':pipe_work,'contracted_dag':{'fork_ops':len(op_fork),'fork_outdegree_histogram':stat_hist(op_fork.values()),'join_ops':len(op_join),'join_indegree_histogram':stat_hist(op_join.values()),'fork_chains':sum(len(s)>1 for s in succ),'fork_chain_outdegree_histogram':stat_hist(len(s) for s in succ if len(s)>1),'join_chains':sum(len(p)>1 for p in pred),'join_chain_indegree_histogram':stat_hist(len(p) for p in pred if len(p)>1)},'serial_chains':{'count':len(chains),'op_count_histogram':stat_hist(len(c) for c in chains),'max_ops':max(map(len,chains),default=0),'max_duration':max((sum(idx.duration(u) for u in c) for c in chains),default=0),'wholly_one_core':sum(len(c)==1 for c in chain_cores),'split_across_cores':sum(len(c)>1 for c in chain_cores),'occupied_cores_histogram':stat_hist(len(c) for c in chain_cores)},'internal_tensors':{'count':len(tensors),'payload_bytes':internal_total,'consumer_op_count_total':sum(consumer_counts),'consumer_count_histogram':stat_hist(consumer_counts),'mean_size_bytes':(internal_total/len(tensors) if tensors else 0),'max_size_bytes':max((t['size'] for t in tensors),default=0)},'fork_join_regions':{'strict_region_count':len(diamonds),'scanned_chain_steps':scanned,'per_fork_scan_cap':32,'cap_hits':truncated,'covered_ops_union':len(union_ops),'covered_ops_fraction':len(union_ops)/len(idx.ops),'covered_internal_tensor_count_union':len(union_tensors),'covered_internal_tensor_payload_bytes_union':sum(t['size'] for t in union_tensors),'current_internal_cross_tensor_copy_bytes_union':union_cross_tensor,'current_internal_cross_direct_copy_bytes_union':union_cross_direct,'regions':diamonds[:12],'multi_pipe_regions':sum(sum(x>0 for x in d['pipe_work'].values())>1 for d in diamonds),'region_count_truncated_to_12':len(diamonds)>12},'selected_plan_chain_core_assignment':{'chain_count':len(chains),'split_chain_count':sum(len(c)>1 for c in chain_cores),'region_count_spanning_multiple_cores':sum(len(d['current_cores'])>1 for d in diamonds)},'gap_chain_guard':{'status':'available','chain_count':len(chains),'uses_static_dag_only':True}})
 out={'pilot_commit':PILOT,'manifest_sha256':sha(mr),'structural_method':'DAGIndex.__init__ + gap_candidate._chain_dag only; no DAGIndex.build and no gap_candidate.build. Fork/join region scan is bounded to <=32 chain steps per branch/fork.','diamond_definition':'A 2-successor chain fork; each branch follows unique serial chains until first common join; join has exactly the two branch tails as predecessors; branch interiors have no external in/out edges. Fork inputs and join outputs are allowed as region boundary.','byte_definition':'Internal tensor payload is each tensor size once when every eligible producer and consumer is in region. Current internal cross-tensor/direct bytes use exact COPY count by current selected core assignment; all-core co-location would remove these internal cuts only, without any M/legality guarantee.','graphs':recs}
 (OUT/'STRUCTURE.json').write_text(json.dumps(out,indent=2)+'\n'); write_md(out)
 print(json.dumps([{'case':r['case'],'ops':r['eligible_ops'],'chains':r['serial_chains']['count'],'max_chain':r['serial_chains']['max_ops'],'forks':r['contracted_dag']['fork_ops'],'joins':r['contracted_dag']['join_ops'],'diamonds':r['fork_join_regions']['strict_region_count'],'covered_ops':r['fork_join_regions']['covered_ops_union']} for r in recs]))
def write_md(d):
 lines=['# Three-graph fork/join structure survey','','Static-only survey of the archived selected pilot plans. It reads the graph and current selected assignment; no solver plan is built and no evaluator or schedule step is called. Chain indices come from `DAGIndex.__init__` and `gap_candidate._chain_dag`; the chain-placement/build methods are not called. Each fork scan is capped at 32 chain steps per branch.','', '| Case | Eligible ops | MTE2/MTE3/M/V duration | Chains (max ops) | Forks / joins | Strict diamonds | Diamond op union | Internal tensors (n; mean/max B; consumers) | Internal tensor payload / current cross-copy in union |','|---|---:|---|---:|---:|---:|---:|---|---:|']
 for r in d['graphs']:
  f=r['fork_join_regions']; p=r['pipe_duration_totals']; t=r['internal_tensors']; lines.append(f"| {r['case']} | {r['eligible_ops']} | {p['PIPE_MTE2']}/{p['PIPE_MTE3']}/{p['PIPE_M']}/{p['PIPE_V']} | {r['serial_chains']['count']} ({r['serial_chains']['max_ops']}) | {r['contracted_dag']['fork_ops']} / {r['contracted_dag']['join_ops']} | {f['strict_region_count']} | {f['covered_ops_union']} ({f['covered_ops_fraction']:.1%}) | {t['count']}; {t['mean_size_bytes']:.0f}/{t['max_size_bytes']}; {t['consumer_op_count_total']} | {f['covered_internal_tensor_payload_bytes_union']:,} / {f['current_internal_cross_tensor_copy_bytes_union']:,} B |")
 details=[]
 for r in d['graphs']:
  h=r['serial_chains']['op_count_histogram']; short=(int(h.get('1',0))+int(h.get('2',0)))/r['serial_chains']['count']; f=r['fork_join_regions']; c=r['contracted_dag']; p=r['pipe_duration_totals']; total=p['PIPE_M']+p['PIPE_V']; mix=f"M/V={p['PIPE_M']/total:.0%}/{p['PIPE_V']/total:.0%}" if total else 'no M/V work'; details.append(f"{r['case']}: 1–2-op chains {short:.1%}; fork out-degree {c['fork_chain_outdegree_histogram']}; all joins have in-degree 2. {mix}; {f['multi_pipe_regions']}/{f['strict_region_count']} diamonds contain work on multiple pipes; selected placement splits {r['selected_plan_chain_core_assignment']['region_count_spanning_multiple_cores']} regions across cores.")
 lines+=['','## Interpretation','',*details,'','This is a bounded structural scan, not a performance result. Strict diamonds cover only a minority of eligible ops, so the structure is useful as a targeted region proposal, not a graph-wide rule. Multi-pipe work suggests possible throughput complementarity, but does not prove overlap or lower Makespan. The archived assignment’s internal cross-copy estimates under all-region co-location appear in the table and detailed regions in `STRUCTURE.json`; they are not promises about legal regrouping or preserved makespan.','', '## Diamond and byte definitions','','A strict region has exactly two successor chains from its fork, two uniquely serial paths, and a common join whose only incoming chains are those two path tails. Interior nodes have no external in/out edges; fork input and join output boundary edges are allowed. Internal tensor payload counts each tensor once when all eligible producers and consumers lie in the region. Current internal cross-copy bytes are removable only under full co-location of the region in the current assignment; any such change still needs legal plan construction and official evaluation to establish its makespan and spill effects.','',f"Pilot commit `{d['pilot_commit']}`; manifest SHA-256 `{d['manifest_sha256']}`. Run `python3 survey.py --raw-root <directory-with-case-json-files>` to reproduce using the manifest-hashed raw graphs."]
 (OUT/'SURVEY.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()
