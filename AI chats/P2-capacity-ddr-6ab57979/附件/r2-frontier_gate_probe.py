"""Minimal capacity-gated reorder probe, NOT the full joint scheduler.

Uses frozen existing TensorIndex.pipe_window, preserves placement and singleton
mapping, and adopts exactly one candidate only with a full bucket certificate.
No E0 or score-based selection. Supports complete-component placement, unique
original producers (checked by TensorIndex), and no logical_tid aliases.
"""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path

def repair(evidence_root: Path, graph: dict, plan: dict, capacity: dict):
    sys.path.insert(0,str(evidence_root))
    from src.q2.feedback.tensor_packet import TensorIndex
    from src.q2.feedback.capacity_window import footprint
    from src.q2.feedback.construct import derive_multicore_plan
    ix=TensorIndex(graph)
    derive_multicore_plan(graph,plan)
    mapping=plan['node_to_subgraph']
    if len(set(mapping.values()))!=len(mapping):
        return plan,{'accepted':False,'reason':'requires singleton mapping'}
    if any('logical_tid' in t for t in graph['tensors']):
        return plan,{'accepted':False,'reason':'logical aliases outside certificate domain'}
    inverse={sg:int(u) for u,sg in mapping.items()}
    sequences=[[inverse[sg] for sg in s] for s in plan['core_schedules']]
    details=[];new_schedules=[]
    for c,sequence in enumerate(sequences):
        jobs=list(dict.fromkeys(ix.owner[u] for u in sequence))
        if set(sequence)!={u for j in jobs for u in ix.components[j]}:
            return plan,{'accepted':False,'reason':'split component outside this minimal probe domain'}
        width=ix.window_size(jobs)
        revised,clock=ix.pipe_window(jobs,width,prefer_fill=False) if jobs else ([],{})
        peak=footprint(ix,revised)
        if any(peak[p]>capacity[p] for p in capacity):
            return plan,{'accepted':False,'reason':'candidate not certified','failed_core':c,'peak':peak}
        new_schedules.append([mapping[str(u)] for u in revised])
        details.append({'core':c,'width':width,'bucket_peak_bytes':peak,'priority_coordinates':clock})
    candidate={'node_to_subgraph':dict(mapping),'core_schedules':new_schedules}
    derive_multicore_plan(graph,candidate)
    return candidate,{'accepted':True,'details':details,'online_E0_calls':0,'claim':'Step2 no-spill certificate only; no makespan guarantee; not the full joint DDR algorithm'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-root',type=Path,required=True)
    ap.add_argument('--graph',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    sys.path.insert(0,str(a.evidence_root/'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    cfg=read_evaluation_config(a.evidence_root/'data/raw/a/official/data/config.txt')
    candidate,meta=repair(a.evidence_root,json.loads(a.graph.read_bytes()),json.loads(a.plan.read_bytes()),cfg['capacity'])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(candidate,separators=(',',':'))+'\n')
    print(json.dumps(meta,sort_keys=True))
if __name__=='__main__':main()
