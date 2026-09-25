"""Synthetic, non-official checks. No E0/E1/E2 or Step1/2/3 invocation."""
from __future__ import annotations
import itertools, json, random, time
from pathlib import Path
from reuse_corridor import Net, physical_nets, cost, delta_all, exact_one_way_cut, repair_gap_witness

ROOT = Path(__file__).resolve().parent


def rule_bytes(graph, owner):
    """Independent direct transcription of source/target-core counting."""
    ops={o['id']:o for o in graph['ops']}; ts={t['id']:t for t in graph['tensors']}
    eligible={u for u,o in ops.items() if o['op'] not in {'COPY_IN','COPY_OUT'}}
    ps={t:set() for t in ts}; cs={t:set() for t in ts}; ds=[]
    for e in graph['edges']:
        u,v=e['source'],e['target']
        if u in ops and v in ts: ps[v].add(u)
        elif u in ts and v in ops: cs[u].add(v)
        elif u in ops and v in ops and u!=v: ds.append(e)
    total=0
    for t,x in ts.items():
        a={owner[u] for u in ps[t]&eligible}; b={owner[u] for u in cs[t]&eligible}
        if b and not a: total+=x['size']*len(b)
        if a and (not b or any(ops[u]['op']=='COPY_OUT' for u in cs[t])):
            total+=x['size']*len(a)
        total+=2*x['size']*sum(i!=j for i in a for j in b)
    for e in ds:
        u,v=e['source'],e['target']
        if u in eligible and v in eligible and owner[u]!=owner[v]: total+=2*e.get('data_size',0)
    return total


def accounting_fixture():
    ops=[{'id':u,'op':'ADD','pipe':'PIPE_V','cycles':1} for u in (1,2,3)]
    ops.append({'id':9,'op':'COPY_OUT','pipe':'PIPE_MTE3','cycles':1})
    ts=[{'id':100,'pos':'L1','size':7},{'id':101,'pos':'UB','size':11},
        {'id':102,'pos':'DDR','size':11},{'id':103,'pos':'UB','size':0},
        {'id':104,'pos':'UB','size':13}]
    edges=[(100,1),(100,2),(1,101),(101,2),(101,3),(101,9),(9,102),
           (2,103),(103,3),(3,104)]
    graph={'ops':ops,'tensors':ts,'edges':[{'source':u,'target':v} for u,v in edges]}
    graph['edges'] += [{'source':1,'target':2,'data_size':5} for _ in range(2)]
    graph['edges'].append({'source':1,'target':3,'data_size':0})
    return graph


def diamond_fixture(m=1):
    graph={'ops':[],'tensors':[],'edges':[]}; chains=[]; owners={}; starts={}; delays={}
    for j in range(m):
        op=[10*j+i+1 for i in range(4)]
        tid=[1000000+10*j+i for i in range(5)]
        pipes=['PIPE_M','PIPE_V','PIPE_V','PIPE_M']; durations=[1,10,10,1]
        times=[2000*j,2000*j+503,2000*j+513,2000*j+1025]
        for i,u in enumerate(op):
            graph['ops'].append({'id':u,'op':'ADD','pipe':pipes[i],'cycles':durations[i]})
            chains.append([u]); owners[4*j+i]=1 if i in (0,3) else 0; starts[u]=times[i]
        for i,t in enumerate(tid):
            graph['tensors'].append({'id':t,'pos':'L1' if i==1 else 'UB','size':3 if i==1 else 1})
        p,u,v,z=op; t,x,ut,vt,zt=tid
        graph['edges'] += [{'source':a,'target':b} for a,b in
                           ((p,t),(t,u),(t,v),(x,u),(x,v),(u,ut),(ut,z),(v,vt),(vt,z),(z,zt))]
        for a,b in ((0,1),(0,2),(1,3),(2,3)): delays[4*j+a,4*j+b]=502
    mapping={str(u):i for i,u in enumerate(starts)}
    return graph,chains,owners,starts,delays,mapping


def main():
    started=time.perf_counter(); rnd=random.Random(402926)
    accounting=0
    g=accounting_fixture(); const,nets=physical_nets(g,{1:0,2:1,3:2})
    for labels in itertools.product(range(3),repeat=3):
        c=dict(enumerate(labels)); expected=rule_bytes(g,{u:c[u-1] for u in (1,2,3)})
        assert cost(nets,c,const)==expected
        accounting+=1
    # Chain contraction deduplicates producer and consumer pins in the same unit.
    const,nets=physical_nets(g,{1:0,2:0,3:1})
    for labels in itertools.product(range(3),repeat=2):
        c=dict(enumerate(labels)); expected=rule_bytes(g,{1:c[0],2:c[0],3:c[1]})
        assert cost(nets,c,const)==expected
        accounting+=1
    multi={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':1} for i in range(1,5)],
           'tensors':[{'id':100,'pos':'UB','size':1}],
           'edges':[{'source':u,'target':v} for u,v in ((1,100),(2,100),(100,3),(100,4))]}
    assert rule_bytes(multi,{1:0,2:1,3:0,4:1})==4
    try: physical_nets(multi,{i:i for i in range(1,5)})
    except ValueError: pass
    else: raise AssertionError('multiple-producer guard missing')

    delta_tests=0; flow_tests=0; brute_subsets=0
    for _ in range(320):
        n=rnd.randint(2,9); owner={i:rnd.randrange(3) for i in range(n)}
        a,b=rnd.sample(range(3),2)
        movable={u for u in owner if owner[u]==a and rnd.randrange(4)!=0}
        nets=[Net(str(j),frozenset(rnd.sample(range(n),rnd.randint(1,n))),rnd.randrange(9))
              for j in range(rnd.randint(1,12))]
        chosen,info=exact_one_way_cut(nets,owner,movable,a,b)
        original=cost(nets,owner)
        best=original
        for bits in itertools.product((0,1),repeat=len(movable)):
            moved={u for u,x in zip(sorted(movable),bits) if x}
            new={**owner,**{u:b for u in moved}}
            assert cost(nets,new)-original==delta_all(nets,owner,moved,a,b)
            best=min(best,cost(nets,new)); delta_tests+=1; brute_subsets+=1
        actual=cost(nets,{**owner,**{u:b for u in chosen}})
        assert actual==best and original-actual==info['saving_bytes']
        flow_tests+=1

    # Larger binary domains: full enumeration is TEST-ONLY, never construction.
    for _ in range(64):
        r=rnd.randint(6,10); n=r+2
        owner={i:(0 if i<r else i-r+1) for i in range(n)}
        movable=set(range(r)); a,b=0,1
        nets=[Net(str(j),frozenset(rnd.sample(range(n),rnd.randint(1,n))),rnd.randrange(15))
              for j in range(rnd.randint(6,18))]
        selected,info=exact_one_way_cut(nets,owner,movable,a,b)
        original=cost(nets,owner); best=original
        for mask in range(1<<r):
            moved={i for i in range(r) if mask>>i&1}
            new={**owner,**{i:b for i in moved}}
            value=cost(nets,new)
            assert value-original==delta_all(nets,owner,moved,a,b)
            best=min(best,value); delta_tests+=1
        assert cost(nets,{**owner,**{i:b for i in selected}})==best
        flow_tests+=1

    # A=move set, explicit submodularity over a donor-only binary domain.
    submodular_checks=0
    for _ in range(30):
        owner={i:(0 if i<4 else 1) for i in range(6)}
        nets=[Net(str(j),frozenset(rnd.sample(range(6),rnd.randint(1,6))),rnd.randrange(7)) for j in range(8)]
        sets=[{i for i in range(4) if mask>>i&1} for mask in range(16)]
        f=lambda S:cost(nets,{**owner,**{u:1 for u in S}})
        for A in sets:
            for B in sets:
                assert f(A)+f(B)>=f(A|B)+f(A&B)
                submodular_checks+=1

    graph,chains,owner,starts,delays,mapping=diamond_fixture(1)
    const,nets=physical_nets(graph,{u:j for j,row in enumerate(chains) for u in row})
    base=cost(nets,owner,const)
    singles=[delta_all(nets,owner,{u},0,1) for u in (1,2)]
    together=delta_all(nets,owner,{1,2},0,1)
    assert (base,singles,together)==(10,[1,1],-6)
    plan,detail=repair_gap_witness(graph,chains,owner,starts,delays,2,mapping)
    assert detail['saved_pre_step2_bytes']==6
    result_owner={int(u):c for u,sg in plan['node_to_subgraph'].items()
                  for c,row in enumerate(plan['core_schedules']) if sg in row}
    assert rule_bytes(graph,result_owner)==detail['pre_step2_bytes_after']==4
    (ROOT/'diamond_graph.json').write_text(json.dumps(graph,indent=2))
    (ROOT/'diamond_seed_witness.json').write_text(json.dumps({'chains':chains,'placement':owner,'starts':starts,
        'delays':[[u,v,w] for (u,v),w in delays.items()],'mapping':mapping},indent=2))
    (ROOT/'diamond_repaired_plan.json').write_text(json.dumps(plan,indent=2))
    (ROOT/'diamond_report.json').write_text(json.dumps(detail,indent=2))

    repeated=[]
    for j in range(1000):
        repeated.extend([Net(f'parent{j}',frozenset({0,1,2}),2),
                         Net(f'shared{j}',frozenset({1,2}),3),
                         Net(f'left{j}',frozenset({1,3}),2),
                         Net(f'right{j}',frozenset({2,3}),2)])
    selected,compression=exact_one_way_cut(repeated,{0:1,1:0,2:0,3:1},{1,2},0,1)
    assert selected=={1,2} and compression['saving_bytes']==6000
    assert compression['incident_nets']==4000 and compression['decision_supports']==3

    # Tight edges are contracted; no migration may create their missing delay.
    tight_graph={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':1} for i in (1,2)],
                 'tensors':[{'id':100,'pos':'UB','size':1},{'id':101,'pos':'UB','size':1}],
                 'edges':[{'source':u,'target':v} for u,v in ((1,100),(100,2),(2,101))]}
    _,tight=repair_gap_witness(tight_graph,[[1],[2]],{0:0,1:0},{1:0,2:1},{(0,1):502},2,{'1':0,'2':1})
    assert tight['tight_group_count']==1 and tight['flow_calls']==0

    large=diamond_fixture(1000)
    t=time.perf_counter()
    _,large_report=repair_gap_witness(*large[:5],cores=2,mapping=large[5])
    large_seconds=time.perf_counter()-t
    assert large_report['saved_pre_step2_bytes']==6000
    assert large_report['changed_groups_final']==2000
    assert large_report['flow_calls']==1
    results={'official_calls':{'Step1':0,'Step2':0,'Step3':0,'E0':0,'E1':0,'E2':0},
        'accounting_assignments':accounting,'random_exact_cut_domains':flow_tests,
        'enumerated_subsets_delta_checks':delta_tests,'submodular_inequalities':submodular_checks,
        'diamond':{'pre_bytes':base,'single_move_deltas':singles,'joint_delta':together},
        'exact_signature_compression':compression,
        'fragment_family':{'diamonds':1000,'compute_operations':4000,'eligible_moves':2000,
            'saved_pre_step2_bytes':large_report['saved_pre_step2_bytes'],
            'flow_calls':large_report['flow_calls'],'prototype_refinement_seconds':large_seconds,
            'not_an_official_makespan_or_end_to_end_solver_measurement':True},
        'status':'all assertions passed','synthetic_test_wall_seconds':time.perf_counter()-started}
    (ROOT/'test_results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__': main()
