"""Independent finite capacity-envelope checks; no evaluator or Step2 calls.

The small event oracle below derives endpoint COPY touches from raw edges,
enumerates every legal within-bucket order, and counts closed event lifetimes.
It does not use capacity_window.footprint or official scheduling helpers.
"""
import itertools
import unittest
from collections import defaultdict

from src.q2.feedback.capacity_window import build, footprint, memory_window
from src.q2.feedback.construct import UnsupportedStructure
from src.q2.feedback.tensor_packet import TensorIndex


def fixture(jobs=4):
    tensors = [{'id': 10000, 'pos': 'L1', 'size': 64},
               {'id': 10001, 'pos': 'DDR', 'size': 8}]
    ops, edges = [], []
    for j in range(jobs):
        a, b, c, out = 10*j+1, 10*j+2, 10*j+3, 10*j+4
        private, x, y, z, backing = [11000+10*j+i for i in range(5)]
        ops += [{'id': a, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 100},
                {'id': b, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 60},
                {'id': c, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 60},
                {'id': out, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 0}]
        tensors += [{'id': private, 'pos': 'L1', 'size': 13},
                    {'id': x, 'pos': 'UB', 'size': 34},
                    {'id': y, 'pos': 'UB', 'size': 19},
                    {'id': z, 'pos': 'DDR', 'size': 23},
                    {'id': backing, 'pos': 'DDR', 'size': 19}]
        pairs=[(10000,a),(10000,c),(10001,a),(10001,c),(private,a),
               (private,c),(a,x),(x,b),(x,c),(b,y),(y,c),(y,out),
               (out,backing),(c,z)]
        edges += [{'source': u, 'target': v} for u,v in pairs]
    return {'ops':ops,'tensors':tensors,'edges':edges}


def closed_event_peak(events, tensors):
    """Raw event alloc/use/free oracle; includes one-use transient buffers."""
    touched = defaultdict(list)
    for step, tids in enumerate(events):
        for tid in tids:
            touched[tid].append(step)
    peak={'L1':0,'UB':0}
    for step in range(len(events)):
        used={'L1':0,'UB':0}
        for tid, positions in touched.items():
            if positions[0] <= step <= positions[-1]:
                t=tensors[tid]
                used['UB' if t['pos']=='DDR' else t['pos']]+=t['size']
        for pool in peak:
            peak[pool]=max(peak[pool],used[pool])
    return peak


def bucket_orders(graph, sequence):
    """Enumerate endpoint-event orders from raw edges, for a one-core fixture."""
    original={o['id']:o for o in graph['ops']}
    tensors={t['id']:t for t in graph['tensors']}
    eligible=set(sequence)
    incoming=defaultdict(set);outgoing=defaultdict(set)
    producers=defaultdict(set);consumers=defaultdict(set)
    final=set()
    for e in graph['edges']:
        u,v=e['source'],e['target']
        if u in eligible and v in tensors:
            outgoing[u].add(v);producers[v].add(u)
        if u in tensors and v in eligible:
            incoming[v].add(u);consumers[u].add(v)
        if u in tensors and v in original and original[v]['op']=='COPY_OUT':
            final.add(u)
    rank={u:i for i,u in enumerate(sequence)}
    imports=defaultdict(list);exports=defaultdict(list)
    for tid in tensors:
        pp,cc=producers[tid],consumers[tid]
        if cc and not pp:
            imports[min(cc,key=rank.get)].append(tid)
        if pp and (not cc or tid in final):
            assert len(pp)==1
            exports[next(iter(pp))].append(tid)
    choices=[]
    for u in sequence:
        before=[[{tid} for tid in order] for order in itertools.permutations(imports[u])]
        after=[[{tid} for tid in order] for order in itertools.permutations(exports[u])]
        choices.append([a+[incoming[u]|outgoing[u]]+b for a in before for b in after])
    return choices,tensors


class CapacityWindowAuditTests(unittest.TestCase):
    def test_all_endpoint_copy_orders_bounded_by_bucket_envelope(self):
        graph=fixture(2)
        index=TensorIndex(graph)
        sequence=[1,11,2,12,3,13]
        choices,tensors=bucket_orders(graph,sequence)
        bound=footprint(index,sequence)
        count=0
        for order in itertools.product(*choices):
            observed=closed_event_peak([tids for bucket in order for tids in bucket],tensors)
            self.assertTrue(all(observed[p]<=bound[p] for p in bound))
            count+=1
        self.assertEqual(count,6)
        self.assertEqual(bound,{'L1':90,'UB':137})

    def test_shared_multiuse_inputs_two_pools_and_window_certificate(self):
        index=TensorIndex(fixture())
        capacity={'L1':90,'UB':160}
        width,detail=memory_window(index,list(range(4)),capacity)
        self.assertEqual(width,2)
        self.assertEqual(detail['shared_reservation_bytes'],{'L1':64,'UB':8})
        self.assertEqual(detail['private_peak_bytes'],{'L1':13,'UB':76})
        sequence,_=index.pipe_window(list(range(4)),width)
        self.assertTrue(all(footprint(index,sequence)[p]<=capacity[p] for p in capacity))
        for j,job in enumerate(index.components):
            self.assertEqual([u for u in sequence if index.owner[u]==j],job)

    def test_unreferenced_tensor_and_copy_only_backing_are_not_local_buffers(self):
        graph=fixture(2)
        index=TensorIndex(graph)
        expected=footprint(index,index.order)
        graph['tensors'].append({'id':99999,'pos':'UB','size':10**8})
        for t in graph['tensors']:
            if t['id'] in (11004,11014):
                t['size']=10**8
        actual=footprint(TensorIndex(graph),index.order)
        self.assertEqual(actual,expected)

    def test_contracted_copy_path_and_direct_edge_cannot_cross_jobs(self):
        graph={'ops':[{'id':1,'op':'COMPUTE','pipe':'PIPE_M','cycles':1},
                      {'id':2,'op':'COPY_OUT','pipe':'PIPE_MTE3','cycles':1},
                      {'id':3,'op':'COPY_IN','pipe':'PIPE_MTE2','cycles':1},
                      {'id':4,'op':'COMPUTE','pipe':'PIPE_V','cycles':1},
                      {'id':5,'op':'COMPUTE','pipe':'PIPE_M','cycles':1}],
               'tensors':[{'id':10001,'pos':'UB','size':3},
                          {'id':10002,'pos':'DDR','size':3},
                          {'id':10003,'pos':'L1','size':3}],
               'edges':[{'source':a,'target':b} for a,b in [(1,10001),(10001,2),(2,10002),(10002,3),(3,10003),(10003,4),(4,5)]]}
        index=TensorIndex(graph)
        self.assertEqual(index.components,[[1,4,5]])

    def test_alias_and_infeasible_reservation_keep_base_plan(self):
        graph=fixture()
        index=TensorIndex(graph)
        expected,_=index.build_tensor_plan(1,60,500)
        actual,meta=build(index,1,60,500,{'L1':63,'UB':1000})
        self.assertEqual(actual,expected)
        self.assertEqual(meta['core_details'][0]['window'],0)
        self.assertNotIn('bucket_footprint_bytes',meta['core_details'][0])
        graph['tensors'][0]['logical_tid']=10000
        index=TensorIndex(graph)
        expected,_=index.build_tensor_plan(1,60,500)
        actual,meta=build(index,1,60,500,{'L1':90,'UB':160})
        self.assertEqual(actual,expected)
        self.assertEqual(meta['selected'],'capacity_window_guard_unchanged')

    def test_unique_original_producer_guard(self):
        graph=fixture(2)
        graph['edges'].append({'source':11,'target':11000})
        graph['edges'].append({'source':12,'target':11000})
        with self.assertRaises(UnsupportedStructure):
            TensorIndex(graph)

    def test_heavy_override_is_not_a_capacity_certificate(self):
        graph={'ops':[{'id':u,'op':'COMPUTE','pipe':'PIPE_M','cycles':100} for u in range(1,7)]
                     +[{'id':u,'op':'COMPUTE','pipe':'PIPE_V','cycles':1} for u in (7,8,9)],
               'tensors':[{'id':10001,'pos':'L1','size':10}],
               'edges':[{'source':u,'target':7} for u in range(1,7)]
                      +[{'source':10001,'target':u} for u in (8,9)]}
        plan,meta=build(TensorIndex(graph),4,60,500,{'L1':0,'UB':0})
        self.assertEqual(meta['selected'],'heavy_component_packet_override')
        self.assertNotIn('core_details',meta)
        self.assertIn('no spill certificate',meta['scope'])
        self.assertEqual(sum(map(len,plan['core_schedules'])),9)


if __name__=='__main__':
    unittest.main()
