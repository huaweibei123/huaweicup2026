"""Lossless coarsening of Q2/Q3 priority buckets for the frozen E0 version.

The official file is never modified. An AST slice executes only its pure Task-
boundary/Step1 prefix, before Step2/3. Exact prefix identity is a safety guard.
This is a constructor, not an E1 evaluator. New sg labels change group diagnostics.
"""
from pathlib import Path
import ast, copy, hashlib, importlib, sys, time

FROZEN_B = '0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464'

def prefix_builder(official):
    path=Path(official)/'code/multicore_cut_evaluate_problem_2.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=FROZEN_B:
        raise ValueError('unsupported official builder hash; skip compaction')
    sys.path.insert(0,str(path.parent))
    mod=importlib.import_module('multicore_cut_evaluate_problem_2')
    if Path(mod.__file__).resolve()!=path.resolve():
        raise RuntimeError('conflicting imported official module')
    root=ast.parse(path.read_text());fn=copy.deepcopy(next(x for x in root.body if isinstance(x,ast.FunctionDef) and x.name=='_build_scene_b_tasks'))
    fn.name='_capture_prefix';found=False;newbody=[]
    for stmt in fn.body:
        if isinstance(stmt,ast.For) and any(isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='raw_seq' for t in x.targets) for x in stmt.body):
            body=[]
            for x in stmt.body:
                if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result2' for t in x.targets):break
                body.append(x)
            body.extend(ast.parse("tasks[core_id] = {'graph': graph, 'raw_seq': raw_seq, 'seq': seq, 'op_subgraph': dict(data['op_subgraph']), 'subgraph_order': list(data['subgraph_order'])}").body)
            stmt.body=body;newbody.append(stmt);found=True;break
        newbody.append(stmt)
    if not found:raise RuntimeError('frozen AST shape mismatch')
    fn.body=newbody+ast.parse('return tasks, cross_links, plan_view').body
    tree=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));ns=dict(vars(mod));exec(compile(tree,'<frozen-official-prefix-slice>','exec'),ns)
    return ns[fn.name],mod

def compact(graph,plan,official,bandwidth=60,capacity=None,check_native=False):
    """Only merge adjacent current buckets whose full raw-Step1 ranges increase.
    Returns the original plan on no useful compression; identity is checked before return.
    """
    if capacity is None:capacity={'L1':524288,'UB':131072}
    t0=time.perf_counter();prefix,mod=prefix_builder(official)
    before,links,view=prefix(graph,plan,bandwidth,capacity)
    native_checks=[]
    if check_native:
        # Diagnostic only: capture the original helper's actual returned sequence.
        # No function patching; no official file or return value is changed.
        captured=[]
        def profiler(frame,event,arg):
            if event=='return' and frame.f_code is mod._prioritize_task_seq.__code__:
                captured.append(copy.deepcopy({'graph':frame.f_locals['graph'],'raw_seq':frame.f_locals['raw_seq'],'seq':arg}))
        sys.setprofile(profiler)
        try:mod._build_scene_b_tasks(graph,plan,bandwidth,capacity)
        finally:sys.setprofile(None)
        for k,x in sorted(before.items()):
            native_checks.append(all(x[field]==captured[k][field] for field in ['graph','raw_seq','seq']))
        if not all(native_checks):raise RuntimeError('AST prefix differs from captured native prefix')
    sgmap={};orders=[];sg=0;cert=[]
    for core,task in sorted(before.items()):
        rpos={u:i for i,u in enumerate(task['raw_seq'])};buckets={s:[] for s in task['subgraph_order']}
        for u in task['seq']:buckets[task['op_subgraph'][u]].append(u)
        order=[];lastmax=None;descents=[]
        for old in task['subgraph_order']:
            vals=[rpos[u] for u in buckets[old]]
            if vals!=sorted(vals):raise RuntimeError('not a stable Step1 bucket')
            # Eligible-containing groups guarantee nonempty bucket.
            if not vals:raise RuntimeError('unexpected empty bucket')
            if lastmax is None or lastmax>=vals[0]:
                if lastmax is not None:descents.append([lastmax,vals[0]])
                current=sg;sg+=1;order.append(current)
            sgmap[old]=current;lastmax=vals[-1]
        orders.append(order);cert.append({'core':core,'before':len(task['subgraph_order']),'after':len(order),'mandatory_descents':descents})
    new={'node_to_subgraph':{u:sgmap[s] for u,s in plan['node_to_subgraph'].items()},'core_schedules':orders}
    after,links2,view2=prefix(graph,new,bandwidth,capacity)
    checks={str(k):{f:before[k][f]==after[k][f] for f in ['graph','raw_seq','seq']} for k in before}
    if links!=links2 or not all(all(x.values()) for x in checks.values()):
        raise RuntimeError('compaction changed a semantic prefix; retain original plan')
    return new,{'seconds':time.perf_counter()-t0,'groups':cert,'prefix_identity':checks,'cross_links_identity':links==links2,'native_prefix_checks':native_checks,'purpose':'Q2/Q3 scoring behavior; not full JSON identity of subgraph diagnostics'}
