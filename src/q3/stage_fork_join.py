"""Repeated vector-lane stages with the original scalar reduction tree.

Immutable input tensor IDs fix lane/core affinity. Original ADDs wholly inside
one owner stay local; mixed ADDs return to a fixed collector by default. An
explicit rotate_heavy policy alternates exactly two most-loaded lane cores.
No vector chain is split; every gather path crosses cores at most once.
This is a restricted direct constructor, not a full memory-feasibility proof.
"""
from .construct import UnsupportedStructure, derive_multicore_plan


def recognize(index):
    def need(ok,msg):
        if not ok:raise UnsupportedStructure(msg)
    need(len(index.components)==1,'requires one weak component')
    need(all(o['pipe']=='PIPE_V' for o in index.ops.values()),'requires one V pipe family')
    tensors={t['id']:t for t in index.graph['tensors']}
    all_ops={o['id']:o for o in index.graph['ops']}
    compute_ids=set(index.ops)
    raw_inputs={u:[] for u in all_ops};raw_outputs={u:[] for u in all_ops}
    raw_producers={t:set() for t in tensors};raw_consumers={t:set() for t in tensors}
    inputs={u:[] for u in index.ops}; outputs={u:[] for u in index.ops}
    eligible_producers={t:set() for t in tensors}
    for e in index.graph['edges']:
        a,b=e['source'],e['target']
        need(not(a in index.ops and b in index.ops),'direct compute edges are outside the exact tensor-port guard')
        if a in all_ops and b in tensors:raw_producers[b].add(a);raw_outputs[a].append(b)
        if a in tensors and b in all_ops:raw_consumers[a].add(b);raw_inputs[b].append(a)
        if a in tensors and b in index.ops:inputs[b].append(a)
        if a in index.ops and b in tensors:outputs[a].append(b);eligible_producers[b].add(a)
    for u in index.ops:
        need(len(outputs[u])==1,'requires exactly one output tensor per original compute op')
        tid=outputs[u][0]
        need(raw_producers[tid]=={u},'compute tensor has multiple or ambiguous producers')
        need(tensors[tid]['pos']=='UB','compute intermediates and scalars must be UB')
        need((raw_consumers[tid] & compute_ids)==index.succ[u],'COPY contraction or tensor successor mismatch')
    position={u:i for i,u in enumerate(index.order)}
    heads=sorted(u for u in index.ops if not index.pred[u])
    lane_count=len(heads);need(lane_count>=2,'requires multiple lanes')
    stages=[]; seen=set(); previous_root=None; lane_ids=None; expected_shape=None; expected_signature=None; immutable_copy_ops=set(); expected_join_signature=None
    while heads:
        need(len(heads)==lane_count,'broadcast fanout changed')
        chains={}; leaf_lane={}
        for head in heads:
            need(index.pred[head]==(set() if previous_root is None else {previous_root}),'unexpected stage head predecessor')
            constants=[t for t in inputs[head] if not eligible_producers[t]]
            need(len(constants)==1,'each lane needs exactly one immutable graph input tensor')
            lane=constants[0];need(lane not in chains,'duplicate immutable lane input')
            need(tensors[lane]['pos']=='L1','immutable input must be L1')
            need(len(raw_producers[lane])==1,'immutable input needs one original COPY_IN producer')
            cp=next(iter(raw_producers[lane]));need(all_ops[cp]['op']=='COPY_IN','immutable input producer must be COPY_IN')
            immutable_copy_ops.add(cp)
            need(raw_outputs[cp]==[lane],'COPY_IN must have exactly the immutable lane output')
            cp_inputs=raw_inputs[cp]
            need(len(cp_inputs)==1 and tensors[cp_inputs[0]]['pos']=='DDR' and tensors[cp_inputs[0]]['size']==tensors[lane]['size'],'COPY_IN must have one matching DDR source')
            expected_head_inputs={lane} if previous_root is None else {lane,outputs[previous_root][0]}
            need(len(inputs[head])==len(expected_head_inputs) and set(inputs[head])==expected_head_inputs,'unexpected head tensor port')
            chain=[head]
            while len(index.succ[chain[-1]])==1:
                v=next(iter(index.succ[chain[-1]]))
                if index.pred[v]!={chain[-1]}:break
                chain.append(v)
            for a,b in zip(chain,chain[1:]):
                need(inputs[b]==[outputs[a][0]],'unexpected extra or changed lane-internal tensor input')
            need(index.ops[chain[-1]]['op']=='REDUCE','chain must end in original REDUCE')
            need(all(len(outputs[u])==1 for u in chain),'requires one output tensor per lane op')
            vector=tensors[lane]['size'];scalar=tensors[outputs[chain[-1]][0]]['size']
            need(vector>scalar>0,'requires large-vector to smaller-scalar reduction')
            need(all(tensors[outputs[u][0]]['size']==vector for u in chain[:-1]),'internal vector shape changed')
            sig=(len(chain),tuple(index.duration(u) for u in chain),tuple(index.ops[u]['op'] for u in chain[1:]),vector,scalar)
            if expected_signature is None:expected_signature=sig
            need(sig==expected_signature,'lane work/type/size signature differs')
            need(index.ops[head]['op']==('RELU' if previous_root is None else 'ADD'),'unexpected first/later stage head operation')
            chains[lane]=chain;leaf_lane[chain[-1]]=lane
        current_lane_ids=sorted(chains)
        if lane_ids is None:lane_ids=current_lane_ids
        need(current_lane_ids==lane_ids,'immutable lane identities changed across stages')
        joins=set(); sinks=set()
        for leaf in leaf_lane:
            need(len(index.succ[leaf])==1,'lane reduction must feed one original reduction tree')
            u=next(iter(index.succ[leaf]))
            while True:
                need(index.ops[u]['op']=='ADD' and len(index.pred[u])==2,'requires original binary ADD tree')
                need(len(outputs[u])==1 and tensors[outputs[u][0]]['size']==expected_signature[-1],'ADD must preserve scalar size')
                need(index.duration(u)<min(expected_signature[1]),'scalar ADD must be cheaper than each vector op')
                expected_inputs={outputs[p][0] for p in index.pred[u]}
                need(len(inputs[u])==2 and set(inputs[u])==expected_inputs,'ADD tensor ports do not equal its two original predecessors')
                joins.add(u)
                if len(index.succ[u])!=1:sinks.add(u);break
                u=next(iter(index.succ[u]))
        need(len(sinks)==1,'stage reduction tree needs a unique sink')
        root=next(iter(sinks));need(len(joins)==lane_count-1,'not a full binary reduction tree over lanes')
        join_order=sorted(joins,key=position.__getitem__)
        descendants={u:frozenset([lane]) for u,lane in leaf_lane.items()};shapes={u:('lane',lane) for u,lane in leaf_lane.items()}
        for u in join_order:
            pp=sorted(index.pred[u]);need(all(p in descendants for p in pp),'unrecognized reduction predecessor')
            need(not (descendants[pp[0]] & descendants[pp[1]]),'repeated lane in original reduction tree')
            descendants[u]=descendants[pp[0]]|descendants[pp[1]]
            shapes[u]=tuple(sorted((shapes[p] for p in pp),key=repr))
        need(descendants[root]==frozenset(lane_ids),'reduction misses a lane')
        join_signature=tuple((shapes[u],index.duration(u)) for u in join_order)
        if expected_join_signature is None:expected_join_signature=join_signature
        need(join_signature==expected_join_signature,'scalar ADD durations/order-shape signature changed')
        if expected_shape is None:expected_shape=shapes[root]
        need(shapes[root]==expected_shape,'original reduction tree shape changes between stages')
        nodes=set(joins)|{u for chain in chains.values() for u in chain}
        need(not(nodes&seen),'stage overlap');seen.update(nodes)
        stages.append({'root':root,'chains':chains,'join_order':join_order,'descendants':descendants})
        previous_root=root; heads=sorted(index.succ[root])
    need(seen==set(index.ops),'stage recognition does not cover original compute graph')
    final_copy_ops=raw_consumers[outputs[previous_root][0]]-compute_ids
    need(len(final_copy_ops)==1 and all(all_ops[u]['op']=='COPY_OUT' for u in final_copy_ops),'final scalar must have one original COPY_OUT')
    for cp in final_copy_ops:
        need(raw_inputs[cp]==[outputs[previous_root][0]] and len(raw_outputs[cp])==1,'final COPY_OUT ports differ')
        tid=raw_outputs[cp][0]
        need(tensors[tid]['pos']=='DDR' and tensors[tid]['size']==expected_signature[-1],'final COPY_OUT must write matching scalar DDR')
    for u in index.ops:
        extras=raw_consumers[outputs[u][0]]-compute_ids
        need(extras==(final_copy_ops if u==previous_root else set()),'unexpected COPY consumer inside stage compute graph')
    need(set(all_ops)-compute_ids==immutable_copy_ops|final_copy_ops,'unrecognized original COPY operations')
    return {'lane_ids':lane_ids,'signature':expected_signature,'stages':stages}


def construct(index,cores,*,collector_policy="fixed"):
    if type(cores)is not int or cores<1:raise ValueError('positive integer cores required')
    if collector_policy not in {"fixed", "rotate_heavy"}:
        raise ValueError('collector_policy must be fixed or rotate_heavy')
    rec=recognize(index); lanes=rec['lane_ids'];q=len(lanes)
    lane_core={lane:min(cores-1,j*cores//q) for j,lane in enumerate(lanes)}
    # A less-loaded lane core absorbs mixed scalar ADDs; this is fixed, not online EFT.
    lane_load=[sum(rec['signature'][1])*sum(lane_core[l]==c for l in lanes) for c in range(cores)]
    active=set(lane_core.values());collector=min(active,key=lambda c:(lane_load[c],c))
    collector_cycle=[collector]
    if collector_policy == "rotate_heavy":
        collector_cycle=sorted(c for c in active if lane_load[c]==max(lane_load))
        if len(collector_cycle)!=2:
            raise UnsupportedStructure('rotate_heavy requires exactly two most-loaded lane cores')
    owner={};global_order=[];stage_meta=[]
    for stage_index,stage in enumerate(rec['stages']):
        # Distinct preceding/current heavy roots each pay one remote leg;
        # lighter lane cores may hide both legs. This is not an E0 bound.
        collector=collector_cycle[stage_index % len(collector_cycle)]
        for lane in lanes:
            chain=stage['chains'][lane];global_order.extend(chain)
            owner.update((u,lane_core[lane]) for u in chain)
        pure=[];mixed=[]
        for u in stage['join_order']:
            cs={lane_core[l] for l in stage['descendants'][u]}
            if len(cs)==1:owner[u]=next(iter(cs));pure.append(u)
            else:owner[u]=collector;mixed.append(u)
        global_order.extend(pure);global_order.extend(mixed)
        work=[0]*cores
        for lane in lanes:
            for u in stage['chains'][lane]:work[owner[u]]+=index.duration(u)
        for u in stage['join_order']:work[owner[u]]+=index.duration(u)
        stage_meta.append({'root':stage['root'],'work_by_core':work,'pure_adds':len(pure),'mixed_adds':len(mixed)})
        if collector_policy == 'rotate_heavy':
            stage_meta[-1]['collector_core']=collector
    position={u:i for i,u in enumerate(global_order)}
    if len(position)!=len(index.ops) or any(position[u]>=position[v] for u in index.ops for v in index.succ[u]):raise AssertionError('constructed global order is not a compute linear extension')
    mapping={str(u):j for j,u in enumerate(index.order)};schedules=[[] for _ in range(cores)]
    for u in global_order:schedules[owner[u]].append(mapping[str(u)])
    plan={'node_to_subgraph':mapping,'core_schedules':schedules}
    derive_multicore_plan(index.graph,plan)
    metadata={'strategy':'stage_fork_join','guard':'constant-input homogeneous vector-lane chains + unchanged binary scalar ADD tree + scalar broadcast stage chain','lane_count':q,'stage_count':len(rec['stages']),'chain_signature':rec['signature'],'lane_core':lane_core,'collector_core':collector if collector_policy=='fixed' else None,'stage_diagnostics':stage_meta,'total_work_by_core':[sum(s['work_by_core'][c] for s in stage_meta) for c in range(cores)],'cross_core_compute_edges':sum(owner[u]!=owner[v] for u in index.ops for v in index.succ[u]),'order':'per stage: full original lane chains, pure-local original ADDs, mixed original ADDs on fixed collector','official_e0_calls':0,'legality':'compute/plan static validation only, no memory or full official feasibility claim'}
    if collector_policy == 'rotate_heavy':
        metadata.update(collector_policy=collector_policy,collector_cycle=collector_cycle)
        metadata['order']='per stage: full original lane chains, pure-local original ADDs, mixed ADDs on alternating heavy collector'
    return plan,metadata

