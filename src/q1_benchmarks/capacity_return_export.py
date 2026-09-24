"""Export the existing P1 capacity-return case 084 probe; zero scoring calls."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'output/p1-capacity-return/20260924T1830Z-capacity084'
DEST = ROOT/'results/a/q1-capacity-return-20260925/20260924T1830Z-capacity084'
BASE_COMMIT = '6fcec11ccc472a1a652b21feb6fccf85a4555598'
BASE_PATH = 'results/benchmark-board/official-singlecore-20260924/084'
SOURCE_COMMIT = 'e566dd5ce6a1737880ca88d35964bfd846bc4512'
REPO = 'huaweibei123/huaweicup2026'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def rel(path): return path.relative_to(ROOT).as_posix()
def artifact(path): return {'path':rel(path),'sha256':sha(path.read_bytes())}
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def blob(path): return subprocess.check_output(['git','show',f'{BASE_COMMIT}:{path}'],cwd=ROOT)
def source(path,entry): return {'repo':REPO,'commit':SOURCE_COMMIT,'path':path,'entrypoint':entry}

def main():
    run_raw=(SOURCE/'run.json').read_bytes(); run=json.loads(run_raw)
    result_raw=(SOURCE/'result.json').read_bytes(); result=json.loads(result_raw)
    plan_raw=(SOURCE/'plan.json').read_bytes(); trace_raw=(SOURCE/'trace.json').read_bytes()
    diagnostics=json.loads((SOURCE/'diagnostics.json').read_bytes())
    assert run['status']=='ok' and run['cleanup_confirmed'] and run['source_commit']==SOURCE_COMMIT
    assert run['case_id']=='084' and run['cores']==5
    assert run['calls']=={'solver':1,'E0':1,'E1':0,'E2':0,'retry':0}
    assert result['scene']=='A' and result['num_cores']==5 and result['makespan']==run['makespan']==399121
    assert result['data_movement_bytes']==run['movement']
    assert diagnostics==run['diagnostics']
    for name,info in run['artifacts'].items():
        assert sha((ROOT/info['path']).read_bytes())==info['sha256'],name
    base_run_raw=blob(BASE_PATH+'/run.json'); base_run=json.loads(base_run_raw)
    base_result_raw=blob(BASE_PATH+'/result.json.gz'); base_result=json.loads(gzip.decompress(base_result_raw))
    assert base_run['status']=='ok' and base_run['entrypoint']=='singlecore_evaluate.evaluate_singlecore'
    assert base_result['scene']=='A' and base_result['num_cores']==1
    assert base_result['makespan']==base_run['makespan_cycles']==2507412
    assert sha(base_result_raw)==base_run['artifacts']['result.json']['sha256']
    for k,other in [('graph_sha256','graph_sha256'),('config_sha256','config_sha256'),('official_code_hash','official_code_hash')]: assert run[k]==base_run[other]
    assert not DEST.exists()
    DEST.mkdir(parents=True)
    (DEST/'plan.json').write_bytes(plan_raw)
    (DEST/'result.json.gz').write_bytes(gzip.compress(result_raw,mtime=0))
    (DEST/'trace.json.gz').write_bytes(gzip.compress(trace_raw,mtime=0))
    (DEST/'graph.json.gz').write_bytes(gzip.compress((SOURCE/'graph.json').read_bytes(),mtime=0))
    (DEST/'official.log').write_bytes((SOURCE/'official.log').read_bytes())
    (DEST/'official-singlecore-result.json.gz').write_bytes(base_result_raw)
    (DEST/'official-singlecore-run.json').write_bytes(base_run_raw)
    safe=json.loads(run_raw)
    for name in ('solver','evaluation'):
        safe[name]['argv']=['<local-python>' if arg.startswith('/') else arg for arg in safe[name]['argv']]
    safe['derivation']={'original_sha256':sha(run_raw),'change':'Absolute interpreter paths in solver/evaluation argv replaced with <local-python>. All other receipt fields unchanged.','original_local_path':'output/p1-capacity-return/20260924T1830Z-capacity084/run.json'}
    write(DEST/'run-derived.json',safe)
    identity={'graph_sha256':run['graph_sha256'],'config_sha256':run['config_sha256'],'official_sha256':run['official_code_hash'],'plan_sha256':sha(plan_raw)}
    movement=result['data_movement_bytes']
    record={
      'attempt_id':'nikolastarx-20260924T1830Z-capacity084-P1-084-k5-r0','revision':1,'run_id':run['run_id'],
      'algorithm_id':diagnostics['algorithm_id'],'algorithm_name':'P1 容量推导返程切分探针','variant':diagnostics['variant'],
      'solver_commit':SOURCE_COMMIT,'problem':'P1','case_id':'084','cores':5,'status':'ok',
      'parameters':{'cores':5,'packet':diagnostics['packet'],'cut_chains':diagnostics['cut_chains'],'policy':'Graph-derived all-cut single candidate; no online model scoring or search','solver_timeout_seconds':15,'external_E0_timeout_seconds':60,'batch_timeout_seconds':90,'workers':1,'retries':0},
      'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':run['solver']['wall_seconds'],'evaluation_wall_seconds':run['evaluation']['wall_seconds'],'ddr_bytes':movement['scheduled_copy_bytes'],'extra_ddr_bytes':movement['added_copy_bytes'],'spill_bytes':movement['spill_added_copy_bytes']},
      'evaluator':{'route':'E0','commit':SOURCE_COMMIT,'entrypoint':'multicore_cut_evaluate_problem_1.evaluate_scene_a'},
      'identity':identity,'artifacts':{'plan':artifact(DEST/'plan.json'),'result':artifact(DEST/'result.json.gz'),'run':artifact(DEST/'run-derived.json'),'trace':artifact(DEST/'trace.json.gz')},
      'runtime_id':'nikolastarx-m5pro-macos-py312-20260924','observed_at':run['finished_at'],
      'timing':{'solver_includes_evaluation':False,'evaluation_precision':'time.perf_counter elapsed seconds','utc':'Original timestamps UTC; external E0 separate from solver wall'},
      'provenance':{'producer_session':'nikolastarx/s-6607cb2735304751b36662035723372b','task_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
        'solver':{'source':source('src/q1/capacity_return.py','main'),'authors':['nikolastarx'],'method':'One capacity-derived all-cut packet plan for private M/V/M chains; direct construction, no scoring model.','references':[],'upstream':[source('AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py','recognize/encode')],'selected_algorithm_id':None,'selected_solver_commit':None},
        'runner':{'source':source('src/q1_benchmarks/capacity_return_probe.py','run'),'argv':['<local-python>','-B','src/q1_benchmarks/capacity_return_probe.py',run['run_id'],'--execute'],'working_directory':'.'},
        'environment':{'os':run['environment']['platform'],'cpu':None,'gpu':None,'ram_bytes':None,'python':run['environment']['python'],'dependencies':None,'threads':None,'workers':1,'peak_rss_bytes':None},
        'measurement':{'started_at':run['started_at'],'finished_at':run['finished_at'],'seed':None,'repeat_index':0,'cold_start':None,
          'solver_scope':'Fresh child interpreter, graph read, one direct constructor, diagnostics and plan write through process exit. External E0 excluded.',
          'evaluation_scope':'One independent unmodified official E0 CLI through result, trace and log write and process exit.',
          'budget':{'wall_seconds':15,'candidate_limit':1,'stop_reason':'One authorized structural candidate completed; no retry'},
          'calls':{'solver':1,'E0':1,'E1':0,'E2':0},'offline_costs':'No offline training or compilation in this probe; existing archived recognizer source reused.','failure':None},
        'missing_reasons':{'provenance.environment.cpu':'Original run receipt did not record CPU model','provenance.environment.gpu':'Original run receipt did not record GPU usage','provenance.environment.ram_bytes':'Original run receipt did not record installed RAM','provenance.environment.dependencies':'Original run receipt did not record dependency lock hash','provenance.environment.threads':'Runtime thread count not measured','provenance.environment.peak_rss_bytes':'Darwin cumulative child maximum is not isolated process peak','provenance.measurement.seed':'Deterministic constructor; no seed recorded','provenance.measurement.cold_start':'Fresh interpreter, but OS page cache was not flushed'}},
      'notes':['One graph mechanism probe only; not the unified solver or a 100-graph result.','Original run receipt contains local absolute interpreter paths; committed run-derived.json is a path-redacted derivative. Original SHA256='+sha(run_raw),
               'Original result SHA256='+sha(result_raw)+'; result.json.gz decompresses to exact source bytes.','Original trace SHA256='+sha(trace_raw)+'; trace.json.gz decompresses to exact source bytes.',
               f'Official singlecore denominator {base_result["makespan"]} from {BASE_COMMIT}:{BASE_PATH}/result.json.gz; no baseline rerun.'],
      'source_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
      'baseline':{'graph_sha256':identity['graph_sha256'],'config_sha256':identity['config_sha256'],'official_sha256':identity['official_sha256'],'route':'E0','entrypoint':'singlecore_evaluate.evaluate_singlecore','result':artifact(DEST/'official-singlecore-result.json.gz')}
    }
    feed=DEST/'board-feed-20260924T1830Z-capacity084.json'
    write(feed,{'schema_version':1,'submission_version':1,'records':[record]})
    write(DEST/'export-receipt.json',{'source_commit':SOURCE_COMMIT,'original_run_sha256':sha(run_raw),'original_plan_sha256':sha(plan_raw),'original_result_sha256':sha(result_raw),'original_trace_sha256':sha(trace_raw),'original_graph_sha256':sha((SOURCE/'graph.json').read_bytes()),'graph_archive':artifact(DEST/'graph.json.gz'),'official_log':artifact(DEST/'official.log'),'baseline_commit':BASE_COMMIT,'baseline_result_sha256':sha(base_result_raw),'feed':artifact(feed),'new_calls':{'solver':0,'E0':0,'E1':0,'E2':0}})
    print(rel(feed),sha(feed.read_bytes()))
if __name__=='__main__': main()
