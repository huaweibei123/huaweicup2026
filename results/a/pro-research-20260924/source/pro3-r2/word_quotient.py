"""Exact score quotient for Q2/Q3 under a fixed op->core map.

No identifier normalization, no real-number substitute. The raw Task graph and
literal augmented operation word are the sufficient compiler key. Cache hits
relabel diagnostic subgraph fields; all event times/cache/float values are reused
from an identical operational program, never from an approximate simulator.
"""
from __future__ import annotations
import ast,copy,types,hashlib,json,time
from collections import defaultdict
from runtime import load,settings,evaluate


def raw_builder(module):
    # Freeze-specific extraction of official construction phase; no file changes.
    from pathlib import Path
    source=Path(module.__file__).read_text()
    f=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_build_scene_b_tasks')
    prefix=[]
    for node in f.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tasks' for t in node.targets):
            break
        prefix.append(node)
    else: raise RuntimeError('raw Task phase anchor missing')
    f.name='route3_raw_builder';f.body=prefix+ast.parse('return tasks_data, cross_links, cross_task_traffic, plan_view').body
    tree=ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[]));ns=dict(module.__dict__)
    exec(compile(tree,'<route3-raw-task-phase>','exec'),ns)
    return ns[f.name]


class WordEvaluator:
    """Prepared single-graph fixed-core-map evaluator. Not a general E1 service.
    prepare cost and all evaluate costs must be included in an end-to-end run.
    """
    def __init__(self,mods,q,graph,seed_plan,cfg=None):
        if q not in (2,3):raise ValueError('word quotient only for Q2/Q3')
        self.mods,self.q,self.graph=mods,q,graph;self.cfg=cfg or settings(mods)
        self.mod=mods[f'multicore_cut_evaluate_problem_{q}'];self.cache={};self.hits=self.misses=self.fallbacks=0
        start=time.perf_counter()
        data,links,cross,view=raw_builder(self.mod)(graph,seed_plan,self.cfg['bandwidth'],self.cfg['capacity'])
        self.seed_core={v:view['core_by_subgraph'][sg] for v,sg in view['mapping'].items()}
        self.mapping_order=tuple(view['mapping']);self.num_cores=view['num_cores'];self.links=links;self.cross=cross
        self.graphs={c:{'ops':d['ops'],'tensors':list(d['tensors'].values()),'edges':d['edges']} for c,d in data.items()}
        self.raw_seq={c:self.mod.step1_schedule(g) if g['ops'] else [] for c,g in self.graphs.items()}
        producers,consumers,direct=self.mod._original_tensor_views(graph)
        # Direct op-op inputs are accepted by code but outside the paper domain;
        # this specialized public prototype deliberately does not cover them.
        if direct:raise ValueError('direct op-op graph not supported by word quotient')
        self.anchors={};self.eligible=set(view['mapping'])
        for c,g in self.graphs.items():
            ins,outs,_,_=mods['schedule_step3']._build_graph_views(g['ops'],g['edges'])
            for op in g['ops']:
                oid=op['id']
                if oid in self.eligible:continue
                if op['op']=='COPY_IN':
                    tids=outs[oid];orig=consumers;mode='min'
                elif op['op']=='COPY_OUT':
                    tids=ins[oid];orig=producers;mode='max'
                else:raise ValueError('unexpected generated operation')
                if len(tids)!=1:raise ValueError('multi-tensor generated COPY unsupported')
                candidates=tuple(sorted(v for v in orig.get(tids[0],()) if self.seed_core.get(v)==c))
                if not candidates:raise ValueError('missing boundary label anchors')
                self.anchors[(c,oid)]=(mode,candidates)
        original=self.mod._copy_traffic_bytes(graph)
        raw=sum(self.mod._copy_traffic_bytes(g) for g in self.graphs.values())
        self.traffic0={'original_graph_copy_bytes':original,'partition_added_copy_bytes':raw-original}
        self.raw_bytes=raw
        self.prepare_seconds=time.perf_counter()-start

    def view_and_words(self,plan):
        view=self.mod.derive_multicore_plan(self.graph,plan)
        core={v:view['core_by_subgraph'][sg] for v,sg in view['mapping'].items()}
        if core!=self.seed_core or tuple(view['mapping'])!=self.mapping_order or view['num_cores']!=self.num_cores:
            raise ValueError('plan outside fixed-core/order specialization')
        labels={c:{} for c in self.graphs}
        for v,sg in view['mapping'].items():labels[core[v]][v]=sg
        ranks={c:{sg:i for i,sg in enumerate(order)} for c,order in view['core_orders'].items()}
        for (c,oid),(mode,vs) in self.anchors.items():
            rank=ranks[c]
            fn=min if mode=='min' else max
            labels[c][oid]=fn((view['mapping'][v] for v in vs),key=lambda sg:rank[sg])
        words={c:self.mod._prioritize_task_seq(self.graphs[c],seq,labels[c],view['core_orders'][c]) for c,seq in self.raw_seq.items()}
        key=tuple(tuple(words[c]) for c in range(self.num_cores))
        return view,labels,words,key

    def _labels_with_spills(self,labels,spills):
        result={c:dict(v) for c,v in labels.items()}
        for c,recs in spills.items():
            for sp in recs:
                nxt=result[c].get(sp.get('next_use_op'));prev=result[c].get(sp.get('prev_use_op'))
                if sp['spill_out_id'] is not None:result[c][sp['spill_out_id']]=prev if prev is not None else nxt
                result[c][sp['spill_in_id']]=nxt
        return result

    def _retag(self,result,view,labels):
        # Only labels/spans reference the partition. Reuse all immutable data
        # elsewhere (caller must treat returned objects as read-only).
        out=dict(result);out['per_core_timeline']=[]
        for oldcore in result['per_core_timeline']:
            c=oldcore['core_id'];core=dict(oldcore);ops=[];by=defaultdict(list)
            for old in oldcore['ops']:
                e={**old,'subgraph_id':labels[c].get(old['op_id'])};ops.append(e);by[e['subgraph_id']].append(e)
            spans=[]
            for sg in view['core_orders'][c]:
                vals=by.get(sg,())
                if not vals:raise self.mod.SceneBEvaluationError(f'subgraph {sg} has no scheduled op')
                a=min(e['start'] for e in vals);b=max(e['end'] for e in vals)
                spans.append({'subgraph_id':sg,'start':a,'end':b,'duration':b-a})
            core['ops']=ops;core['subgraphs']=spans
            core['tasks']=[{**t,'subgraph_ids':view['core_orders'][c]} for t in oldcore['tasks']]
            out['per_core_timeline'].append(core)
        return out

    def evaluate(self,plan,full=True):
        view,labels,words,key=self.view_and_words(plan)
        if key in self.cache:
            self.hits+=1;result,spills=self.cache[key]
        else:
            self.misses+=1;tasks={};spills={};spill_bytes=0
            for c,g in self.graphs.items():
                r2=self.mod.step2_spill_insertion(g,words[c],capacity=self.cfg['capacity']) if words[c] else {'new_ops':[],'new_tensors':[],'new_edges':[],'spill_records':[],'seq_ext':[]}
                spills[c]=r2.get('spill_records',[])
                spill_bytes+=sum(sp['size']*(1+int(sp['spill_out_copies_data'])) for sp in spills[c])
                ext=self.mod._build_extended_graph(g,r2)
                tasks[c]=self.mod.prepare_step3_execution(ext,capacity=self.cfg['capacity'],bandwidth=self.cfg['bandwidth'])
            extended_labels=self._labels_with_spills(labels,spills)
            for c,t in tasks.items():t.update(task_id=c,core_id=c,subgraph_ids=view['core_orders'][c],op_subgraph=extended_labels[c])
            traffic={**self.traffic0,'scheduled_copy_bytes':self.raw_bytes+spill_bytes,'spill_added_copy_bytes':spill_bytes,'added_copy_bytes':self.traffic0['partition_added_copy_bytes']+spill_bytes}
            fn=self.mod.evaluate_scene_b if self.q==2 else self.mod.evaluate_problem_3
            gl=dict(fn.__globals__);gl['_build_scene_b_tasks']=lambda *a:(tasks,self.links,self.cross,traffic,view)
            execute=types.FunctionType(fn.__code__,gl,fn.__name__,fn.__defaults__,fn.__closure__)
            kw=dict(bandwidth=self.cfg['bandwidth'],capacity=self.cfg['capacity'],cross_core_copy_delay=self.cfg['cross_core_copy_delay_cycles'])
            if self.q==3:kw.update(cache_capacity_bytes=self.cfg['cache_capacity_bytes'],cache_bandwidth_bytes_per_cycle=self.cfg['cache_bandwidth_bytes_per_cycle'])
            result=execute(self.graph,plan,**kw);self.cache[key]=(result,spills)
        if not full:return {'makespan':result['makespan'],'data_movement_bytes':result['data_movement_bytes'],'cache_stats':result.get('cache_stats')}
        return self._retag(result,view,self._labels_with_spills(labels,spills))
