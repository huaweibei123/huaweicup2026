"""Bounded constructive portfolio; every retained incumbent is fresh-E0 confirmed.
Only official two-field plan is written to --output. All diagnostics go to --evidence.
Cross-platform spawn workers permit a hard evaluator timeout; no paid/cloud service.
"""
from runtime import *
from plans import component_plan,intervals
from incidence_grid import detect,rectangle_candidates
from word_quotient import WordEvaluator
import argparse,multiprocessing as mp,traceback

def worker(graph,plan,cfg,out,conn):
 try:
  mods=load();t=time.perf_counter();result=evaluate(mods,cfg.pop('_problem'),graph,plan,cfg)
  eval_time=time.perf_counter()-t;save_json(Path(out)/'E0.full.json.gz',result)
  conn.send({'status':'ok','makespan':result['makespan'],'eval_seconds':eval_time,'traffic':result['data_movement_bytes'],'cache':result.get('cache_stats')})
 except BaseException as ex:
  conn.send({'status':'error','error_type':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()})
 finally:conn.close()

def candidates(g,cores,q):
 yield 'component_lpt_bins',component_plan(g,cores=cores)
 if q in (2,3):
  product=detect(g)
  if product:
   yield from rectangle_candidates(product,cores)
 for chunks in [cores,2*cores,4*cores]:
  yield f'topo_intervals_{chunks}',intervals(g,cores=cores,chunks=chunks)
 # A different Task grouping; no general equivalence is assumed in question 1.
 yield 'component_tasks',component_plan(g,cores=cores,granularity='components')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('--config',type=Path,required=True);ap.add_argument('--problem',type=int,choices=[1,2,3],required=True);ap.add_argument('--cores',type=int,choices=range(1,6),required=True);ap.add_argument('--budget',type=float,default=300);ap.add_argument('--max-candidates',type=int,default=10);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evidence',type=Path,required=True);ap.add_argument('--no-word-quotient',action='store_true');a=ap.parse_args()
 if a.budget<=0 or a.max_candidates<1:ap.error('budget and max-candidates must be positive')
 if a.evidence.exists():ap.error('evidence directory already exists; use a fresh run identity')
 start=time.perf_counter();deadline=start+a.budget;a.evidence.mkdir(parents=True)
 e=load();cfg=settings(e,a.config);g=json.loads(a.graph.read_bytes());ctxs={};seenplans=set();seenwords=set();best=None;rows=[];process_ctx=mp.get_context('spawn')
 report={'official_code_hash':HASH,'graph_sha256':hashlib.sha256(a.graph.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(a.config.read_bytes()).hexdigest(),'problem':a.problem,'cores':a.cores,'budget_seconds':a.budget,'rows':rows,'quality_scope':'small constructive portfolio, not exhaustive or globally optimal; all accepted candidates evaluated by unchanged E0','host_execution':'one spawn worker at a time; parent preparation/worker startup/I/O included in total wall time'}
 for i,(name,p) in enumerate(candidates(g,a.cores,a.problem)):
  if i>=a.max_candidates or time.perf_counter()>=deadline-0.5:break
  pd=json.dumps(p,separators=(',',':'));row={'i':i,'name':name};rows.append(row)
  if pd in seenplans:row['status']='same_plan_skipped';continue
  seenplans.add(pd);folder=a.evidence/f'{i:02d}_{name}';folder.mkdir();save_json(folder/'plan.json',p)
  if a.problem in (2,3) and not a.no_word_quotient:
   t=time.perf_counter()
   try:
    sgcore={sg:c for c,ss in enumerate(p['core_schedules']) for sg in ss};core_signature=tuple((int(v),sgcore[sg])for v,sg in p['node_to_subgraph'].items())
    if core_signature not in ctxs:ctxs[core_signature]=WordEvaluator(e,a.problem,g,p,cfg)
    context=ctxs[core_signature];word=context.view_and_words(p)[-1];certificate=(core_signature,word)
    row['word_sha256']=hashlib.sha256(repr(certificate).encode()).hexdigest()
    if certificate in seenwords:
     row.update(status='same_operational_word_skipped',prepare_seconds=time.perf_counter()-t);continue
    # Only mark as evaluated after E0 succeeds. An exception is never a score.
   except (ValueError,RuntimeError) as ex:
    row['word_specialization_unsupported']=str(ex);certificate=None
   row['prepare_seconds']=time.perf_counter()-t
  else:certificate=None
  left=deadline-time.perf_counter()-0.5
  if left<=0:row['status']='budget_exhausted';break
  parent,child=process_ctx.Pipe(duplex=False);proc=process_ctx.Process(target=worker,args=(g,p,{**cfg,'_problem':a.problem},str(folder),child));t=time.perf_counter();proc.start();child.close();proc.join(left)
  if proc.is_alive():
   proc.terminate();proc.join();row.update(status='timeout',wall_seconds=time.perf_counter()-t);parent.close();break
  row.update(parent.recv() if parent.poll() else {'status':'worker_error','exitcode':proc.exitcode});parent.close();row['wall_seconds']=time.perf_counter()-t
  if row['status']=='ok':
   if certificate is not None:seenwords.add(certificate)
   if best is None or row['makespan']<best['makespan']:
    best={'makespan':row['makespan'],'candidate':i,'name':name,'result_path':str(folder/'E0.full.json.gz')};save_json(a.output,p)
  report.update(elapsed_seconds=time.perf_counter()-start,best=best);save_json(a.evidence/'run.json',report)
 report.update(elapsed_seconds=time.perf_counter()-start,best=best);save_json(a.evidence/'run.json',report)
 if best is None:raise SystemExit('No E0-confirmed incumbent within budget. No successful result is claimed.')
 print(json.dumps({'best':best,'elapsed_seconds':report['elapsed_seconds'],'plan':str(a.output)},ensure_ascii=False))
if __name__=='__main__':main()
