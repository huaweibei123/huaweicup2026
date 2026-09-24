"""Small mathematical/compiler-transcription checks. No official imports/calls."""
import json,unittest
from dataclasses import replace
import archived_r1 as ar
from port_response import Task,PortOp,simulate,quotient,compile_plan
from renewal_dp import construct,shortest_packet_path


def synthetic_chains(n=12, a=13,b=17,c=13,size=8000):
    ops=[];ts=[];edges=[]
    for i in range(n):
        base=10*i+1; tb=100000+20*i
        labels=[('COPY_IN','PIPE_MTE2',1),('M','PIPE_M',a),('V','PIPE_V',b),
                ('V','PIPE_V',b),('M','PIPE_M',c),('COPY_OUT','PIPE_MTE3',1)]
        for j,(kind,pipe,d) in enumerate(labels):ops.append(dict(id=base+j,op=kind,pipe=pipe,cycles=d))
        for j in range(7):ts.append(dict(id=tb+j,pos='DDR' if j in (0,6) else 'UB',size=size))
        for j in range(6):
            edges += [dict(source=tb+j,target=base+j),dict(source=base+j,target=tb+j+1)]
    return dict(ops=ops,tensors=ts,edges=edges)


def tie_graph():
    ops=[];ts=[];edges=[]
    for base,tb in ((1,100),(11,110)):
        for j,(pipe,d) in enumerate((('PIPE_M',10),('PIPE_V',30),('PIPE_M',10))):
            ops.append(dict(id=base+j,op='C',pipe=pipe,cycles=d))
        ops.append(dict(id=base+3,op='COPY_OUT',pipe='PIPE_MTE3',cycles=1))
        for j in range(4):ts.append(dict(id=tb+j,pos='DDR' if j==3 else 'UB',size=60))
        for j in range(3):
            edges.append(dict(source=base+j,target=tb+j))
            edges.append(dict(source=tb+j,target=base+j+1))
        edges.append(dict(source=base+3,target=tb+3))
    return dict(ops=ops,tensors=ts,edges=edges)


class MicroTests(unittest.TestCase):
    def test_clone_quotient_shared_pool_integer_retirement(self):
        t=Task(((PortOp(7,True,(0,0,0,0)),PortOp(3,True,(0,0,0,0))),
                (PortOp(11,True,(0,0,1,0)),PortOp(5,True,(0,0,0,1))),
                (PortOp(13,False,(1,0,0,0)),),
                (PortOp(17,False,(2,0,1,0)),)))
        for k in range(1,6):
            lines=[[t,t,t] for _ in range(k)]
            x=simulate(lines);q=quotient(lines)
            self.assertEqual(x['makespan'],q['makespan'])
            self.assertEqual(q['distinct_round_responses'],1)
            self.assertEqual(q['explicit_tail_tasks'],0)

    def test_broken_symmetry_falls_back_to_explicit_tail(self):
        t=Task(((),(),(PortOp(7,False,(0,0,0,0)),),()))
        u=Task(((),(),(PortOp(8,False,(0,0,0,0)),),()))
        lines=[[t,t],[t,u]]
        q=quotient(lines)
        self.assertEqual(q['equal_rounds'],1)
        self.assertEqual(simulate(lines)['makespan'],q['makespan'])

    def test_depth_tie_reverses_assumed_return_fifo(self):
        g=tie_graph();_,cs,_,_,_=ar.recognize(g)
        p=ar.encode(cs,g['ops'],1,1,len(cs),1)
        locals_=ar.local_model(g,p,60)
        middle=locals_[p['core_schedules'][0][1]]
        seq=ar.reference_step1(middle);v=ar.views(middle)
        ms=[u for u in seq if v.ops[u]['pipe']=='PIPE_M']
        self.assertEqual(ms,[3,11])  # old return BEFORE new prefix
        self.assertLess(sum(t['size'] for t in middle['tensors'] if t['pos']=='UB'),131072)

    def test_generic_dp_known_path(self):
        # Three pending states; a cut-run is cheaper than whole or hybrid.
        states=(0,1,2)
        normals=[{(0,0):(9,1,1),(0,2):(4,2,1),(0,1):(8,1,1)},
                 {(0,0):(9,1,1),(0,2):(4,2,1),(2,2):(3,2,1),(1,1):(7,1,1)},
                 {(0,0):(9,1,1),(2,2):(3,2,1),(1,1):(7,1,1)}]
        drains=[{}, {1:(3,1,1),2:(2,1,1)}, {1:(3,1,1),2:(2,1,1)}, {1:(3,1,1),2:(2,1,1)}]
        val,actions=shortest_packet_path(states,normals,drains)
        self.assertEqual(val[0],12)
        self.assertEqual([a[0] for a in actions],['normal','normal','normal','drain'])

    def test_raw_graph_dp_plan_vs_expanded_port_execution(self):
        g=synthetic_chains();before=json.dumps(g)
        plan,info=construct(g,2,{'L1':524288,'UB':131072})
        self.assertEqual(json.dumps(g),before)
        ar.validate_plan_structure(g,plan)
        self.assertEqual(set(plan),{'node_to_subgraph','core_schedules'})
        lines,_=compile_plan(g,plan,{'L1':524288,'UB':131072})
        self.assertEqual(info['model_makespan'],simulate(lines)['makespan'])
        boundary=ar.boundary_counts(g,plan,60)
        self.assertEqual(info['model_scheduled_bytes'],boundary['boundary_copy_bytes'])

if __name__=='__main__':unittest.main(verbosity=2)
