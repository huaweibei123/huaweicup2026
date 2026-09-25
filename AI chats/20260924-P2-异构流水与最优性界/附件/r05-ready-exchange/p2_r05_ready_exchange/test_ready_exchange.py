from __future__ import annotations
import itertools, json, random, time
from pathlib import Path
from ready_exchange import Op,Net,min_assignment,byte_budget_bottleneck,byte_matrix,net_cost,replay,rebuild
from fixed_domain_audit import audit


def main():
    began=time.perf_counter(); rng=random.Random(20260925)
    report={'official_calls':{'Step1':0,'Step2':0,'Step3':0,'E0':0,'E1':0,'E2':0},
            'scope':'Synthetic exact arithmetic/model tests only; no official input or result.', 'tests':{}}
    assignments=0
    for trial in range(300):
        k=rng.randint(1,5); m=rng.randint(1,k)
        a=[[rng.randrange(25) if rng.random()<.8 else None for _ in range(k)] for _ in range(m)]
        oracle=[]
        for p in itertools.permutations(range(k),m):
            if all(a[i][c] is not None for i,c in enumerate(p)):
                oracle.append((sum(a[i][c] for i,c in enumerate(p)),p))
        got=min_assignment(a)
        assert (got is None)==(not oracle)
        if oracle: assert got[0]==min(x[0] for x in oracle)
        assignments+=len(oracle)
    report['tests']['hungarian_random_matrices']=300
    report['tests']['oracle_feasible_matchings']=assignments
    for trial in range(400):
        k=rng.randint(1,5); m=rng.randint(1,k); ref=list(range(m))
        a=[[rng.randrange(31) for _ in range(k)] for _ in range(m)]
        h=[[rng.randint(1,45) if rng.random()<.8 or c==i else None for c in range(k)] for i in range(m)]
        aa=[[a[i][c] if h[i][c] is not None else None for c in range(k)] for i in range(m)]
        budget=sum(a[i][i] for i in range(m)); oracle=[]
        for p in itertools.permutations(range(k),m):
            if all(h[i][c] is not None for i,c in enumerate(p)):
                b=sum(a[i][c] for i,c in enumerate(p))
                if b<=budget:
                    oracle.append((max(h[i][c] for i,c in enumerate(p)),b,sum(c!=i for i,c in enumerate(p))))
        got=byte_budget_bottleneck(aa,h,ref)
        assert (got['horizon'],got['bytes'],sum(c!=i for i,c in enumerate(got['assignment'])))==min(oracle)
    report['tests']['budget_bottleneck_random_matrices']=400
    checks=0
    for trial in range(200):
        k=rng.randint(1,5); m=rng.randint(1,k); n=m+rng.randint(0,4)
        owner={i:i if i<m else rng.randrange(k) for i in range(n)}
        nets=[Net(frozenset(rng.sample(range(n),rng.randint(1,n))),rng.randrange(30)) for _ in range(rng.randint(1,12))]
        batch=list(range(m)); matrix,_=byte_matrix(nets,owner,batch,k)
        initial=net_cost(nets,owner); old=sum(matrix[i][i] for i in range(m))
        for p in itertools.permutations(range(k),m):
            new=dict(owner); new.update(zip(batch,p))
            assert net_cost(nets,new)-initial==sum(matrix[i][c] for i,c in enumerate(p))-old
            checks+=1
    report['tests']['physical_batch_linearization_domains']=200
    report['tests']['physical_batch_assignment_checks']=checks

    fixed_checks=0
    for trial in range(100):
        n=rng.randint(2,7); ops={u:Op(rng.choice(('M','V')),rng.randint(1,5)) for u in range(n)}
        owner={u:rng.randrange(2) for u in ops}
        lags={(u,v):rng.randint(0,5) for u in range(n) for v in range(u+1,n) if rng.random()<.25}
        seq=[[u for u in ops if owner[u]==c] for c in range(2)]
        _,starts,_=replay(ops,lags,owner,seq)
        nets=[Net(frozenset(rng.sample(range(n),rng.randint(1,n))),rng.randint(0,10)) for _ in range(7)]
        diag=audit(ops,[[u] for u in ops],owner,starts,lags,nets)
        best=None
        for flip in itertools.product((0,1),repeat=n):
            target={u:owner[u]^flip[u] for u in ops}
            resource=True
            for u in ops:
                for v in range(u+1,n):
                    if ops[u].pipe==ops[v].pipe and target[u]==target[v]:
                        if max(starts[u],starts[v])<min(starts[u]+ops[u].duration,starts[v]+ops[v].duration):
                            resource=False
            lag_ok=all(starts[v]>=starts[u]+ops[u].duration+(lag if target[u]!=target[v] else 0)
                       for (u,v),lag in lags.items())
            byblock={}; equal=True
            for u in ops:
                b=diag['blocks'][u]
                if b in byblock and byblock[b]!=flip[u]: equal=False
                byblock[b]=flip[u]
            assert (resource and lag_ok)==equal
            if equal:
                value=net_cost(nets,target)
                best=value if best is None else min(best,value)
            fixed_checks+=1
        assert diag['fixed_domain_byte_lower_bound']<=best
        assert diag['byte_lower_bound_attainable_in_fixed_domain']==(best==diag['fixed_domain_byte_lower_bound'])
    report['tests']['fixed_domain_random_instances']=100
    report['tests']['fixed_domain_assignments_checked']=fixed_checks

    improved=0; reconstructed=0
    for trial in range(180):
        n=rng.randint(3,16); k=rng.randint(1,5)
        ops={u:Op(rng.choice(('M','V')),rng.randint(1,20)) for u in range(n)}
        owner={u:rng.randrange(k) for u in ops}
        lags={(u,v):rng.randint(0,9) for u in range(n) for v in range(u+1,n) if rng.random()<.15}
        nets=[Net(frozenset((u,v)),2*rng.randint(0,10)) for u,v in lags]
        nets += [Net(frozenset(rng.sample(range(n),rng.randint(1,n))),rng.randint(0,8)) for _ in range(3)]
        seq=[[u for u in ops if owner[u]==c] for c in range(k)]
        returned,meta=rebuild(ops,[[u] for u in ops],lags,nets,3,owner,seq)
        assert meta['pre_step2_bytes_rebuilt']<=meta['pre_step2_bytes_seed']
        assert all(r['horizon']<=r['reference_horizon'] and r['saved_bytes']>=0 for r in meta['round_details'])
        if meta['returned']=='rebuilt':
            assert meta['rebuilt_common_proxy_cycles']<=meta['seed_common_proxy_cycles']
            reconstructed+=1
        improved+=meta['pre_step2_bytes_rebuilt']<meta['pre_step2_bytes_seed']
    report['tests']['reconstruction_random_instances']=180
    report['tests']['reconstruction_byte_decrease_instances']=improved
    report['tests']['reconstruction_passed_final_model_guard']=reconstructed

    # User's simultaneous-exchange pattern, supplied as a synthetic static model.
    ops={0:Op('M',10),1:Op('M',10),2:Op('V',10),3:Op('V',10)}
    lags={(u,v):2 for u in (0,1) for v in (2,3)}
    owner={0:0,1:1,2:0,3:1}; seq=[[0,2],[1,3]]
    nets=[Net(frozenset((0,3)),2),Net(frozenset((1,2)),2)]
    result,meta=rebuild(ops,[[u] for u in ops],lags,nets,2,owner,seq)
    assert meta['pre_step2_bytes_seed']==6 and meta['pre_step2_bytes_rebuilt']==2
    assert meta['returned']=='rebuilt'
    report['simultaneous_exchange']={key:meta[key] for key in ('pre_step2_bytes_seed','pre_step2_bytes_rebuilt',
                            'seed_common_proxy_cycles','rebuilt_common_proxy_cycles','returned')}

    # Same-Pipe phase packets, not just singleton tests.
    ops={0:Op('M',3),1:Op('M',4),2:Op('V',5),3:Op('M',2),4:Op('M',2),5:Op('V',6)}
    packets=[[0,1],[2],[3,4],[5]]
    lags={(0,1):2,(1,2):2,(3,4):2,(4,5):2}
    owner={0:0,1:1,2:1,3:0}
    nets=[Net(frozenset((0,1)),10),Net(frozenset((2,3)),10)]
    seq=[[0,1,5],[3,4,2]]
    _,meta=rebuild(ops,packets,lags,nets,0,owner,seq)
    assert meta['pre_step2_bytes_rebuilt']<=20
    report['tests']['multi_operation_phase_packet']=1
    # Frozen examples originally found by synthetic model exploration, NOT blind tests.
    for name in ('retiming_fixture.json','retiming_mixed_fixture.json'):
        fixture=json.loads(Path(__file__).with_name(name).read_text())
        ops={int(u):Op(p,d) for u,(p,d) in fixture['ops'].items()}
        owner={int(u):c for u,c in fixture['owner'].items()}
        lags={(u,v):lag for u,v,lag in fixture['lags']}
        nets=[Net(frozenset(row['pins']),row['weight']) for row in fixture['nets']]
        seed=fixture['seed_sequences']
        _,starts,_=replay(ops,lags,owner,seed)
        diag=audit(ops,[[u] for u in ops],owner,starts,lags,nets)
        _,meta=rebuild(ops,[[u] for u in ops],lags,nets,0,owner,seed)
        assert diag['block_count']==1 and diag['potential_saving_upper_bytes']==0
        assert meta['pre_step2_bytes_rebuilt']<diag['fixed_domain_byte_lower_bound']
        assert meta['returned']=='rebuilt'
        report[name]={key:meta[key] for key in ('pre_step2_bytes_seed',
                'pre_step2_bytes_rebuilt','seed_common_proxy_cycles','rebuilt_common_proxy_cycles')}
    report['tests']['frozen_retiming_beyond_fixed_domain']=2
    report['all_assertions_passed']=True
    report['test_wall_seconds']=time.perf_counter()-began
    Path(__file__).with_name('test_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
