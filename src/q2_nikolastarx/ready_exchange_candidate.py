"""Project adapter for the r05 ready-exchange prototype.

Ported from ChatGPT 6 Pro r05 attachment ``ready_exchange_candidate.py``
(SHA-256 c2a1695618d917d974a184c0574222b391242b484159e09bee8a9c8ae133c998).
Local changes: package documentation points to the existing gap_calendar;
build_from_seed exposes the core's existing final_proxy_guard for isolated
falsification, while build() keeps its original guarded default. Uses public
existing imports only; no evaluator call.
Real graph compatibility and official score remain unverified by this port.
"""
from __future__ import annotations
from collections import defaultdict


def build_from_seed(graph, seed_plan, witness, cores, config, *, final_proxy_guard=True):
    if type(final_proxy_guard) is not bool:
        raise ValueError('final_proxy_guard must be bool')
    from .dag_direct import DAGIndex
    from .direct import derive_multicore_plan, UnsupportedStructure
    from .gap_corridor import physical_nets
    from .candidate_ddr import mandatory_copy_work
    from .ready_exchange import Op, rebuild
    if cores == 1:
        derive_multicore_plan(graph, seed_plan)
        return seed_plan, {'method':'ready_injective_tensor_matching', 'returned':'seed',
                           'reason':'no cross-core assignment at one core',
                           'final_proxy_guard_enabled':final_proxy_guard,
                           'calls':{'E0':0,'E1':0,'E2':0}}
    index=DAGIndex(graph)
    bandwidth=config['bandwidth']; delay=config['cross_core_copy_delay_cycles']
    if type(bandwidth) is not int or bandwidth<=0 or type(delay) is not int or delay<0:
        raise UnsupportedStructure('r05 prototype uses positive integral bandwidth and integer lag')
    derive_multicore_plan(graph,seed_plan)
    chains=witness['chains']
    packets=[]
    for chain in chains:
        run=[]; pipe=None
        for u in chain:
            p=index.ops[u]['pipe']
            if p not in {'PIPE_M','PIPE_V'}:
                raise UnsupportedStructure('first r05 prototype requires M/V compute operations')
            if run and p!=pipe:
                packets.append(run); run=[]
            run.append(u); pipe=p
        if run: packets.append(run)
    inverse={sg:int(u) for u,sg in seed_plan['node_to_subgraph'].items()}
    if len(inverse)!=len(index.ops): raise ValueError('singleton map required')
    seed_sequences=[[inverse[sg] for sg in row] for row in seed_plan['core_schedules']]
    if len(seed_sequences)!=cores: raise ValueError('core budget mismatch')
    op_owner={u:c for c,row in enumerate(seed_sequences) for u in row}
    owner={}
    for j,row in enumerate(packets):
        touched={op_owner[u] for u in row}
        if len(touched)!=1: raise ValueError('phase packet split in the seed')
        owner[j]=next(iter(touched))
    op_packet={u:j for j,row in enumerate(packets) for u in row}
    constant,nets=physical_nets(graph,op_packet)
    sizes=defaultdict(list)
    for t,ps in index.producers.items():
        for u in ps:
            for v in index.consumers[t]:
                if u!=v: sizes[u,v].append(index.tensors[t]['size'])
    for v,ps in index.direct_inputs.items():
        for u,size in ps:
            if type(size) is not int or size<0: raise UnsupportedStructure('direct size guard')
            sizes[u,v].append(size)
    if set(sizes)!={(u,v) for u in index.ops for v in index.succ[u]}:
        raise UnsupportedStructure('contracted and retained operation-edge relations differ')
    # The same OPERATION-level lag definition is used to replay both plans.
    # This quantity is ONLY a timing heuristic, not a bandwidth certificate.
    lags={uv:delay+2*sum(max(1,(s+bandwidth-1)//bandwidth) for s in values)
          for uv,values in sizes.items()}
    ops={u:Op(o['pipe'],index.duration(u)) for u,o in index.ops.items()}
    sequences,meta=rebuild(ops,packets,lags,nets,constant,owner,seed_sequences,
                           final_proxy_guard=final_proxy_guard)
    mapping=seed_plan['node_to_subgraph']
    plan={'node_to_subgraph':dict(mapping),'core_schedules':[
        [mapping[str(u)] for u in row] for row in sequences]}
    derive_multicore_plan(graph,plan)
    old=mandatory_copy_work(graph,seed_plan,bandwidth)['transfer_bytes']
    new=mandatory_copy_work(graph,plan,bandwidth)['transfer_bytes']
    assert old==meta['pre_step2_bytes_seed']
    expected=meta['pre_step2_bytes_rebuilt'] if meta['returned']=='rebuilt' else old
    assert new==expected<=old
    meta.update(final_proxy_guard_enabled=final_proxy_guard,
                original_chains=len(chains), independent_bytes_returned=new,
                original_starts_retained=False, low_slack_groups_retained=False,
                original_chain_ownership_retained=False)
    return plan,meta


def build_from_plan(graph, seed_plan, cores, config, *, final_proxy_guard=True):
    """Refine a caller-selected singleton plan without a gap-seed witness.

    Every eligible op is its own packet. The existing guarded matching and
    byte checks remain in build_from_seed; this entrypoint chooses no seed.
    """
    from .dag_direct import DAGIndex
    from .direct import derive_multicore_plan, UnsupportedStructure
    if type(final_proxy_guard) is not bool:
        raise ValueError('final_proxy_guard must be bool')
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be positive')
    view = derive_multicore_plan(graph, seed_plan)
    if view['num_cores'] != cores:
        raise ValueError('core budget mismatch')
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('caller plan requires singleton subgraphs')
    index = DAGIndex(graph)
    witness = {'chains': [[u] for u in index.order]}
    plan, meta = build_from_seed(graph, seed_plan, witness, cores, config,
                                 final_proxy_guard=final_proxy_guard)
    meta.update(packetization='singleton', source='caller_selected_plan')
    return plan, meta


def build(graph,cores,config):
    from .gap_candidate import build_with_witness
    seed,seed_meta,witness=build_with_witness(graph,cores,config)
    from .direct import UnsupportedStructure
    try:
        plan,meta=build_from_seed(graph,seed,witness,cores,config)
    except UnsupportedStructure as error:
        plan,meta=seed, {'method':'ready_injective_tensor_matching', 'returned':'seed',
                        'guard_rejected':str(error), 'final_proxy_guard_enabled':True,
                        'calls':{'E0':0,'E1':0,'E2':0}}
    meta['seed_metadata']=seed_meta
    return plan,meta
