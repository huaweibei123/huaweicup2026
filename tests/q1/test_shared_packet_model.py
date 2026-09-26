import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'data/raw/a/official/code'))
from src.q1_yuanzhifang.shared_packet_model import construct, Unsupported
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def graph():
    ops=[]; tensors=[]; edges=[]
    for p in range(8): tensors.append(dict(id=1000+p,pos='L1',size=16))
    for j in range(3):
        for p in range(9): tensors.append(dict(id=2000+j*100+p,pos='UB',size=8))
        for p in range(8):
            u=1+j*10+p
            ops.append(dict(id=u,op='MATMUL' if p%2==0 else 'RELU',
                            pipe='PIPE_M' if p%2==0 else 'PIPE_V',cycles=1000 if p%2==0 else 300))
            edges.extend([dict(source=1000+p,target=u),dict(source=2000+j*100+p,target=u),
                          dict(source=u,target=2000+j*100+p+1)])
    return dict(ops=ops,tensors=tensors,edges=edges)


class SharedPacket(unittest.TestCase):
    def test_capacity_selected_rectangles_have_valid_augmented_dag(self):
        g=graph(); plan,info=construct(g,3,{'L1':256,'UB':64},60,100,1000)
        validate_task_order(derive_multicore_plan(g,plan))
        self.assertEqual(set(plan),{'node_to_subgraph','core_schedules'})
        self.assertEqual(len(plan['node_to_subgraph']),24)
        self.assertGreater(info['selected']['stages'],1)
        self.assertTrue(all(x['L1']<=256 and x['UB']<=64
                            for x in info['selected']['max_resident_union_bytes']))

    def test_shape_and_shared_position_mismatch_are_rejected(self):
        g=graph(); g['ops'][-1]['cycles']+=1
        with self.assertRaises(Unsupported): construct(g,3,{'L1':256,'UB':64},60,100,1000)

    def test_excluded_copy_bridge_cannot_hide_a_cross_job_dependency(self):
        g=graph(); g['ops'].append(dict(id=100,op='COPY_IN',pipe='PIPE_MTE2',cycles=0))
        g['edges'].extend([dict(source=8,target=100),dict(source=100,target=11)])
        with self.assertRaisesRegex(Unsupported,'COPY bridge'):
            construct(g,3,{'L1':256,'UB':64},60,100,1000)
        g=graph(); g['edges'].append(dict(source=1000,target=2))
        with self.assertRaises(Unsupported): construct(g,3,{'L1':256,'UB':64},60,100,1000)


if __name__=='__main__': unittest.main()
