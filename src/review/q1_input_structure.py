"""Static reading of100 graphs and500 old results; no solver/evaluator calls.

Uses only official graph-adjacency helpers. Window bins are geometry diagnostics,
not emitted candidates; does not import/call any q1 construct or evaluation.
"""
from collections import Counter,defaultdict,deque
import gzip,hashlib,json,math,platform,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'data/raw/a/official/code'))
from stub_multicore_cut_and_schedule import _build_op_adjacency,_contract_excluded_copy_nodes
SOURCE='161cdb35de11b0d174a5a0ca149aa36657af2abd'
COMPARISON='results/a/q1-bounded-timeout-20260924/20260924T1524Z-timeout4/full500-filled-comparison.json'
K4_FEEDS=['results/a/q1-bounded-full4-20260924/20260924T1439Z-boundedfull4-99/board-feed.json','results/a/q1-bounded-probe-20260924/20260924T1432Z-bounded014/board-feed.json']
OUT=ROOT/'results/a/q1-input-structure-20260924/static_audit.json'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads((ROOT/path).read_text())
def checked(ref):
    raw=(ROOT/ref['path']).read_bytes();assert sha(raw)==ref['sha256'],ref['path']
    return json.loads(gzip.decompress(raw)if ref['path'].endswith('.gz')else raw)
def analyze(g,row,run):
    ops={x['id']:x for x in g['ops']if x['op']not in{'COPY_IN','COPY_OUT'}}
    ts={x['id']:x for x in g['tensors']};prod,cons=defaultdict(set),defaultdict(set)
    for e in g['edges']:
        u,v=e['source'],e['target']
        if u in ops and v in ts:prod[v].add(u)
        if u in ts and v in ops:cons[u].add(v)
    ext={t for t in cons if not prod[t]};reads=defaultdict(set)
    for t in ext:
        for u in cons[t]:reads[u].add(t)
    _,full=_build_op_adjacency(g);pred,succ=_contract_excluded_copy_nodes(sorted(ops),full)
    deg={u:len(pred[u])for u in ops};q=deque(sorted(u for u in ops if not deg[u]));depth=dict.fromkeys(ops,0)
    while q:
        u=q.popleft()
        for v in succ[u]:
            depth[v]=max(depth[v],depth[u]+1);deg[v]-=1
            if not deg[v]:q.append(v)
    assert not any(deg.values())
    parent={u:u for u in ops}
    def find(u):
        while parent[u]!=u:parent[u]=parent[parent[u]];u=parent[u]
        return u
    for u in ops:
        for v in succ[u]:
            a,b=find(u),find(v)
            if a!=b:parent[max(a,b)]=min(a,b)
    groups=defaultdict(list)
    for u in ops:groups[find(u)].append(u)
    plan=checked(run['artifacts']['plan']);mp={int(u):t for u,t in plan['node_to_subgraph'].items()}
    tc={t:k for k,order in enumerate(plan['core_schedules'])for t in order};old=defaultdict(list)
    for u,t in mp.items():old[t].append(u)
    def size(ids):return sum(ts[t]['size']for t in ids)
    oldinputs={t:{i for u in ns for i in reads[u]}for t,ns in old.items()}
    coreinputs=[set()for _ in range(5)]
    for t,ins in oldinputs.items():coreinputs[tc[t]].update(ins)
    compinputs={a:{t for u in ns for t in reads[u]}for a,ns in groups.items()}
    shared={t for t in ext if len({find(u)for u in cons[t]})>1}
    levels=defaultdict(list)
    for u in ops:levels[depth[u]].append(u)
    windows=[];ns=[];ins=set()
    for _,nodes in sorted(levels.items()):
        needed={t for u in nodes for t in reads[u]}
        if ns and ins and needed-ins and size(ins|needed)>262144:
            windows.append((ns,ins));ns=[];ins=set()
        ns.extend(nodes);ins.update(needed)
    if ns:windows.append((ns,ins))
    at={u:i for i,(ns,_)in enumerate(windows)for u in ns};counts=[];localbytes=[];works=[]
    for ns,_ in windows:
        bins=[[]for _ in range(5)]
        for u in ns:bins[tc[mp[u]]].append(u)
        counts.append(list(map(len,bins)));localbytes.append([size({t for u in ns for t in reads[u]})for ns in bins]);wp=[]
        for ns in bins:
            c=Counter()
            for u in ns:c[ops[u]['pipe']]+=max(1,ops[u]['cycles'])
            wp.append(dict(c))
        works.append(wp)
    boundary={t for t in ts if prod[t]and cons[t]and any(at[u]!=at[v]for u in prod[t]for v in cons[t])}
    pos=Counter()
    for t in ext:pos[ts[t]['pos']]+=ts[t]['size']
    compwork=[]
    for ns in groups.values():
        c=Counter()
        for u in ns:c[ops[u]['pipe']]+=max(1,ops[u]['cycles'])
        compwork.append(dict(c))
    total=Counter()
    for c in compwork:total.update(c)
    dominant=max(total,key=total.get)
    movement=checked(run['artifacts']['result'])['data_movement_bytes']
    uniform_work=all(c==compwork[0]for c in compwork)
    shared_by_all=all(len({find(u)for u in cons[t]})==len(groups)for t in shared)
    curve=[]
    # Closed-form diagnostics of equal-work/all-shared component families only.
    # No partition is generated, and the two-copies-per-cut term is a proxy.
    if uniform_work and shared_by_all:
        for a in range(1,min(5,len(groups))+1):
            pipe=math.ceil(len(groups)/a)*max(compwork[0].values())
            copy=movement['original_graph_copy_bytes']+(a-1)*size(shared)+2*size(boundary)
            curve.append({'active_cores':a,'pipe_wave_cycles':pipe,'no_spill_copy_proxy_bytes':copy,
                          'ddr_service_proxy_cycles':math.ceil(copy/60),'max_proxy_cycles':max(pipe,math.ceil(copy/60))})
    return {'case':row['case'],'cores':5,'existing_makespan':row['makespan_cycles'],'existing_spill_bytes':row['spill_bytes'],'existing_extra_ddr_bytes':row['extra_ddr_bytes'],
        'components':len(groups),'compute_ops':len(ops),'old_tasks':len(old),'old_max_task_ops':max(map(len,old.values())),
        'global_external_bytes':size(ext),'external_bytes_by_original_pos':dict(pos),'max_old_task_external_union_bytes':max(map(size,oldinputs.values())),
        'core_external_union_bytes':list(map(size,coreinputs)),'shared_external_bytes_across_components':size(shared),'component_input_min_max':[min(map(size,compinputs.values())),max(map(size,compinputs.values()))],
        'component_dominant_pipe_max_fraction':max(c.get(dominant,0)for c in compwork)/total[dominant],
        'total_compute_pipe_work':dict(total),'equal_component_pipe_work':uniform_work,'all_shared_inputs_read_by_every_component':shared_by_all,
        'shared_input_saved_by_whole_component_colocation_bytes':sum(map(size,coreinputs))-size(ext),
        'existing_data_movement_bytes':movement,'equal_family_active_core_proxy':curve,
        'static_activation':len(groups)>=5 and size(ext)>524288 and 1<len(windows)<=32,'static_global_windows':len(windows),
        'estimated_recombined_tasks':sum(sum(n>0 for n in c)for c in counts),'estimated_recombined_max_task_ops':max(map(max,counts)),
        'static_window_core_ops':counts,'static_window_global_input_bytes':[size(ins)for _,ins in windows],'static_window_core_input_bytes':localbytes,'static_window_core_pipe_work':works,
        'estimated_external_window_reload_bytes_global':sum(size(ins)for _,ins in windows)-size(ext),'cut_tensor_payload_bytes_once':size(boundary),
        'existing_run':row['source_run'],'existing_plan':run['artifacts']['plan'],'existing_result':run['artifacts']['result']}
def main():
    began=datetime.now(timezone.utc).isoformat();t0=time.monotonic()
    source=read('docs/a/source-manifest.json');files={x['path']:x for x in source['files']};archive=ROOT/source['case_archive']['path']
    protected={p:sha((ROOT/'data/raw/a/official'/p).read_bytes())for p in files if p.startswith('code/')or p=='data/config.txt'}
    assert all(h==files[p]['sha256']for p,h in protected.items())
    assert sha(archive.read_bytes())==source['case_archive']['sha256']
    records=read(COMPARISON);assert len(records)==500
    runs={};oldstats=[]
    k4refs={r['attempt_id']:r['artifacts']['run']for path in K4_FEEDS for r in read(path)['records']}
    for row in records:
        if 'source_run'not in row:
            assert row['cores']==4
            row={**row,'source_run':k4refs[row['attempt_id']]}
        run=checked(row['source_run']);result=checked(run['artifacts']['result']);assert result['makespan']==row['makespan_cycles']
        assert result['data_movement_bytes']['spill_added_copy_bytes']==row['spill_bytes']
        oldstats.append({'case':row['case'],'cores':row['cores'],'makespan':result['makespan'],'spill_bytes':row['spill_bytes'],'extra_ddr_bytes':row['extra_ddr_bytes'],'run':row['source_run'],'result':run['artifacts']['result']})
        if row['cores']==5:runs[row['case']]=(row,run)
    rows=[]
    with zipfile.ZipFile(archive)as z:
        for case,(row,run)in sorted(runs.items()):
            name=f'data/case_{case}.json';raw=z.read(name);assert sha(raw)==files[name]['sha256']
            rows.append(analyze(json.loads(raw),row,run))
    out={'analysis_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'read_source_commit':SOURCE,'comparison_source':COMPARISON,'comparison_sha256':sha((ROOT/COMPARISON).read_bytes()),'k4_run_reference_sources':[{'path':p,'sha256':sha((ROOT/p).read_bytes())}for p in K4_FEEDS],'input_archive_sha256':sha(archive.read_bytes()),'official_code_hash':source['official_code_hash'],'actual_calls':{'solver':0,'E0':0,'E1':0,'E2':0},'all500_existing_results_verified':oldstats,'k5_graph_static_rows':rows,'scope':'Window geometry is static analysis, no plan output or solver/evaluator. Unions and payload cut sizes are neither peaks nor exact added DDR predictions.'}
    assert all(sha((ROOT/'data/raw/a/official'/p).read_bytes())==h for p,h in protected.items())
    assert sha(archive.read_bytes())==source['case_archive']['sha256']
    out.update(started_utc=began,ended_utc=datetime.now(timezone.utc).isoformat(),static_analysis_wall_seconds=time.monotonic()-t0,python_version=platform.python_version(),platform=platform.platform(),official_code_config_hashes_before_after=protected)
    OUT.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'graphs':len(rows),'old_results_verified':len(oldstats),'active':sum(r['static_activation']for r in rows),'new_solver_E0_E1_E2':0}))
if __name__=='__main__':main()
