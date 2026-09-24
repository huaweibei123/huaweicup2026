"""Audit frozen k5 results and static bounds; never construct a plan or score."""
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.q1.lower_bounds import lower_bounds
from src.q1.sink_peel import peel_packets, PeelBudgetExceeded
from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes

BASE = '161cdb35de11b0d174a5a0ca149aa36657af2abd'
COMPARISON = 'results/a/q1-bounded-timeout-20260924/20260924T1524Z-timeout4/full500-filled-comparison.json'
BOUNDS = 'results/a/q1-lower-bounds-20260924/static_bounds.json'
OUTPUT = Path(__file__).parent
PRIORITY = ['049','088','056','068','003','054','066','050','009','035','044','046','090','071','048']
GIANTS = ['056','003','068','088','049','050','066','054','009','035']
MULTISINK = ['005','047','048','064','069','071','075','082','085','086']
SPILL = ['044','046','090']
FANG = ['016','024','051']


def sha(b): return hashlib.sha256(b).hexdigest()
def load(p): return json.loads((ROOT / p).read_bytes())
def assert_sha(p, expected):
    actual = sha((ROOT / p).read_bytes())
    if actual != expected: raise AssertionError((str(p), actual, expected))
    return actual


def pipe_work(nodes, ops):
    work = Counter()
    for u in nodes: work[ops[u]['pipe']] += max(1, ops[u]['cycles'])
    return dict(sorted(work.items()))


def weak_components(ids, pred, succ):
    parent = {u: u for u in ids}
    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]; u = parent[u]
        return u
    for u in ids:
        for v in succ[u]:
            a, b = find(u), find(v)
            if a != b: parent[max(a,b)] = min(a,b)
    groups = defaultdict(set)
    for u in ids: groups[find(u)].add(u)
    return list(groups.values())


def main():
    old = load(BOUNDS)
    identity = old['code_identity']
    for name, digest in identity['official_source_sha256'].items():
        assert_sha('data/raw/a/official/code/' + name, digest)
    assert_sha('data/raw/a/official/data/config.txt', identity['config_sha256'])
    assert_sha('src/q1/lower_bounds.py', identity['implementation_sha256'])
    archive = ROOT / 'data/raw/a/official-cases.zip'
    assert_sha(archive, old['input_identity']['sha256'])
    old_cases = {x['input_member']: x for x in old['cases']}
    all_results = load(COMPARISON)
    assert len(all_results) == 500 and len({(x['case'],x['cores']) for x in all_results}) == 500
    baselines = {x['case']:x for x in all_results if x['cores'] == 1}
    current = [x for x in all_results if x['cores'] == 5]
    assert len(current) == 100 and all(x['status'] == 'ok' for x in current)
    rows, batch_evidence, feeds = [], {}, {}
    with zipfile.ZipFile(archive) as z:
        for x in sorted(current, key=lambda x:x['case']):
            case = x['case']; member = 'data/case_' + case + '.json'
            raw = z.read(member); previous = old_cases[member]
            assert sha(raw) == previous['input_sha256']
            graph = json.loads(raw)
            bound = lower_bounds(graph, 5, 60)
            assert bound == next(b for b in previous['bounds'] if b['cores'] == 5)
            run_path = x['source_run']['path']
            assert_sha(run_path, x['source_run']['sha256'])
            run = load(run_path)
            assert run['graph_sha256'] == sha(raw)
            assert run['status'] == 'ok' and run['makespan_cycles'] == x['makespan_cycles']
            assert run['evaluation']['status'] == 'ok' and run['evaluation']['exit_code'] == 0
            batch_path = str(Path(run_path).parents[3] / 'batch.json')
            batch = load(batch_path)
            assert batch['config_sha256'] == identity['config_sha256']
            assert batch['solver_commit'] == '05f8fa0f7e52f5914f14815f6bdbcb851b631556'
            batch_evidence[batch_path] = {k:batch[k] for k in ('solver_commit','runner_commit','official_code_hash','config_sha256')}
            plan_ref = run['artifacts']['plan']
            assert_sha(plan_ref['path'], plan_ref['sha256'])
            plan = load(plan_ref['path'])
            ops = {o['id']:o for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
            tensors = {t['id']:t for t in graph['tensors']}
            _, full = _build_op_adjacency(graph)
            pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
            groups = weak_components(ops, pred, succ)
            assert len(groups) == x['components']
            total_work = pipe_work(ops, ops)
            giant = max(groups, key=lambda ns:(max(pipe_work(ns,ops).values()),-min(ns)))
            small = set(ops)-giant; giant_work = pipe_work(giant,ops)
            dominant_pipe = max(total_work, key=total_work.get)
            pp, cc = defaultdict(set), defaultdict(set)
            for e in graph['edges']:
                a,b=e['source'],e['target']
                if a in ops and b in tensors: pp[b].add(a)
                if a in tensors and b in ops: cc[a].add(b)
            gi={t for t in tensors if not pp[t] and cc[t]&giant}
            si={t for t in tensors if not pp[t] and cc[t]&small}
            local_pred={u:pred[u]&giant for u in giant};local_succ={u:succ[u]&giant for u in giant}
            try:
                waves=peel_packets(giant,local_pred,local_succ)
                peeling={'status':'ok','waves':len(waves),'packets_per_wave':[len(w) for w in waves],
                         'k5_task_count_upper_bound':sum(min(5,len(w)) for w in waves)}
            except PeelBudgetExceeded as exc: peeling={'status':'declined','reason':str(exc)}
            task_core={t:c for c,order in enumerate(plan['core_schedules']) for t in order}
            mapping={int(u):t for u,t in plan['node_to_subgraph'].items()}
            assert set(mapping)==set(ops)
            core_work=[Counter() for _ in range(5)]
            for u in ops: core_work[task_core[mapping[u]]][ops[u]['pipe']]+=max(1,ops[u]['cycles'])
            assigned_bound=max(max(w.values(),default=0) for w in core_work)
            restricted=max(max(pipe_work(ns,ops).values()) for ns in groups)
            B,U,L=x['baseline_cycles'],x['makespan_cycles'],bound['lower_bound_cycles']
            feed_path = str(Path(batch_path).with_name('board-feed.json'))
            if feed_path not in feeds: feeds[feed_path] = load(feed_path)['records']
            baseline = next(a for a in feeds[feed_path] if a['case_id']==case and a['cores']==5)['baseline']
            assert baseline['graph_sha256'] == sha(raw) and baseline['config_sha256'] == identity['config_sha256']
            assert baseline['entrypoint'] == 'singlecore_evaluate.evaluate_singlecore'
            assert_sha(baseline['result']['path'],baseline['result']['sha256'])
            assert json.loads(gzip.decompress((ROOT / baseline['result']['path']).read_bytes()))['makespan'] == B
            assert L <= U and abs(B/U-x['singlecore_speedup']) < 1e-12
            # The bounds deliberately retain fewer edges than COPY contraction.
            persistent={u:set() for u in ops}
            for e in graph['edges']:
                a,b=e['source'],e['target']
                if a in ops and b in ops: persistent[a].add(b)
            for t in tensors:
                for u in pp[t]: persistent[u].update(cc[t])
            bridge_edges=sum(len(succ[u]-persistent[u]) for u in ops)
            share=giant_work.get(dominant_pipe,0)/total_work[dominant_pipe]
            traffic_ratio=x['ddr_bytes']/60/U
            if x['components']==1:
                cluster='single-sink-gates' if sum(not succ[u] for u in ops)==1 else 'single-component-multisink'
            elif x['spill_bytes'] and traffic_ratio>0.5: cluster='DDR-spill-and-replication'
            elif max(giant_work.values())/max(total_work.values())>=0.5: cluster='indivisible-component-imbalance'
            elif x['singlecore_speedup']>=4.7 and B/L>6: cluster='loose-bound-already-near-five'
            else: cluster='other-or-balanced'
            rows.append({'case':case,'cores':5,'baseline_cycles':B,'current_makespan_cycles':U,
                         'current_speedup':B/U,'lower_bound_cycles':L,'speedup_ceiling_allowed_by_bound':B/L,
                         'mean_gain_ceiling_allowed_by_bound':(B/L-B/U)/100,
                         'not_achievability_claim':True,'cluster':cluster,
                         'bound_components':{k:bound[k] for k in ('pipe_load_bound_cycles','mandatory_ddr_service_bound_cycles','relaxed_critical_path_cycles','lower_bound_cycles')},
                         'components':len(groups),'compute_ops':len(ops),'total_pipe_work':total_work,
                         'dominant_pipe':dominant_pipe,'giant_component':{'anchor':min(giant),'ops':len(giant),'pipe_work':giant_work,
                         'share_of_graph_dominant_pipe':share,'source_count':sum(not local_pred[u] for u in giant),
                         'sink_count':sum(not local_succ[u] for u in giant),'is_in_tree':all(len(local_succ[u])<=1 for u in giant),'sink_peeling':peeling,
                         'external_input_bytes':sum(tensors[t]['size'] for t in gi)},
                         'small_components':{'count':len(groups)-1,'ops':len(small),'pipe_work':pipe_work(small,ops),
                         'sizes':sorted(len(ns) for ns in groups if ns!=giant),
                         'external_input_bytes':sum(tensors[t]['size'] for t in si),'shared_with_giant_input_count':len(gi&si),
                         'shared_with_giant_input_bytes':sum(tensors[t]['size'] for t in gi&si)},
                         'restricted_bounds_NOT_global':{'fixed_core_map_pipe_bound_cycles':assigned_bound,
                         'fixed_core_map_speedup_ceiling':B/assigned_bound,
                         'whole_components_indivisible_bound_cycles':restricted,
                         'whole_components_indivisible_speedup_ceiling':B/restricted},
                         'recorded_movement':{k:x[k] for k in ('ddr_bytes','extra_ddr_bytes','spill_bytes')},
                         'recorded_DDR_bytes_over_bandwidth_over_makespan':traffic_ratio,
                         'conditional_spill_only_removal_speedup_ceiling':B/((x['ddr_bytes']-x['spill_bytes']+59)//60),
                         'bound_checks':{'input_hash_matches':True,'config_and_official_files_match':True,'recomputed_bound_equals_archived':True,
                         'source_run_and_plan_hashes_match':True,'source_run_official_success_recorded':True,'bound_not_above_recorded_score':True,
                         'retained_edges':sum(map(len,persistent.values())),'extra_COPY_contracted_edges_not_used_for_bound':bridge_edges,
                         'compute_zero_cycle_ops':sum(o['cycles']==0 for o in ops.values()),'multiple_compute_producer_tensors':sum(len(pp[t])>1 for t in tensors),
                         'max_compute_cycles':max(o['cycles'] for o in ops.values()),'total_compute_work_below_2pow53':sum(total_work.values())<2**53},
                         'source':{'graph_member':member,'graph_sha256':sha(raw),'run':x['source_run'],'plan':plan_ref,
                         'recorded_result':run['artifacts']['result'],'official_singlecore_baseline':baseline,'batch':batch_path}})
    bycase={r['case']:r for r in rows}
    mean=sum(Fraction(r['baseline_cycles'],r['current_makespan_cycles']) for r in rows)/100
    def scenario(groups):
        delta=Fraction(0);items=[]
        for name,cases,target in groups:
            target=Fraction(str(target));dg=Fraction(0)
            for c in cases:
                r=bycase[c];new=r['baseline_cycles']*target.denominator//target.numerator
                assert new>=r['lower_bound_cycles']
                dg+=Fraction(r['baseline_cycles'],new)-Fraction(r['baseline_cycles'],r['current_makespan_cycles'])
                items.append({'case':c,'mechanism':name,'hypothetical_target_speedup':float(target),'required_makespan_at_most':new,
                              'target_over_lower_bound':new/r['lower_bound_cycles'],
                              'DDR_bytes_must_not_exceed_for_target':new*60,
                              'hypothesis_only_not_a_generated_or_verified_plan':True})
            delta+=dg/100
        return {'mean_if_all_targets_met_and_all_other_cases_unchanged':float(mean+delta),'gain':float(delta),
                'necessary_target_conditions':items,'all_targets_achievable':None,'not_a_performance_result':True}
    report={'kind':'static-priority-audit-not-performance','source_commit':BASE,
            'source_sha256':{COMPARISON:sha((ROOT/COMPARISON).read_bytes()),BOUNDS:sha((ROOT/BOUNDS).read_bytes()),
                            'data/raw/a/official-cases.zip':sha(archive.read_bytes()),'audit_static.py':sha(Path(__file__).read_bytes())},
            'batch_evidence':batch_evidence,'lower_bound_identity':identity,
            'calls':{'solver':0,'E0':0,'E1':0,'E2':0,'task_compilation':0,'plans_generated':0},
            'current_mean_speedup':float(mean),'target_strictly_above':3.85,
            'sum_of_per_case_speedup_gains_needed_to_reach_3_85':float((Fraction('3.85')-mean)*100),
            'theoretical_mean_ceiling_allowed_by_bound':sum(r['speedup_ceiling_allowed_by_bound'] for r in rows)/100,
            'priority_order_experimental_mechanisms_not_bound_ranking':PRIORITY,
            'rows':rows,'scenarios':{
            'coordinated_three_routes_plus_Fang':scenario([('dominant-multisink-component',GIANTS,3.5),('single-component-multisink',MULTISINK,2.5),('DDR-and-spill',SPILL,3.0),('Fang-single-sink-owner',FANG,2.0)]),
            'without_single_sink_gain':scenario([('dominant-multisink-component',GIANTS,3.7),('single-component-multisink',MULTISINK,2.5),('DDR-and-spill',SPILL,3.0)])}}
    with (OUTPUT/'audit.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    header='case,current_speedup,lower_bound,speedup_ceiling,mean_gain_ceiling,cluster,components,giant_ops,giant_dominant_pipe_share,spill_bytes\n'
    with (OUTPUT/'ranking.csv').open('x') as f:
        f.write(header)
        for r in sorted(rows,key=lambda r:r['mean_gain_ceiling_allowed_by_bound'],reverse=True):
            f.write(','.join(map(str,[r['case'],r['current_speedup'],r['lower_bound_cycles'],r['speedup_ceiling_allowed_by_bound'],r['mean_gain_ceiling_allowed_by_bound'],r['cluster'],r['components'],r['giant_component']['ops'],r['giant_component']['share_of_graph_dominant_pipe'],r['recorded_movement']['spill_bytes']]))+'\n')
    print(json.dumps({'mean':float(mean),'ceiling':report['theoretical_mean_ceiling_allowed_by_bound'],'scenarios':{k:v['mean_if_all_targets_met_and_all_other_cases_unchanged'] for k,v in report['scenarios'].items()},'rows':len(rows),'calls':report['calls']}))


if __name__=='__main__':main()
