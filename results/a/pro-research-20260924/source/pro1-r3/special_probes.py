#!/usr/bin/env python3
"""Actual E0 public graphs distinguishing legal coarsening and performance."""
import argparse,contextlib,gzip,hashlib,io,json,sys,time,traceback
from pathlib import Path
from packet_construct import construct
from cover_fusion import fuse_cover

def save(path,obj):path.write_bytes(gzip.compress(json.dumps(obj,ensure_ascii=False).encode(),mtime=0))
def graph_reentrant():
    tensors=[(1,'DDR'),(2,'L1'),(3,'UB'),(4,'L1'),(5,'UB'),(6,'DDR'),(7,'DDR'),(8,'L1'),(9,'UB'),(1000,'DDR')]
    ops=[(101,'COPY_IN','PIPE_MTE2',0),(10,'MATMUL','PIPE_M',1),(11,'RELU','PIPE_V',100),(12,'MATMUL','PIPE_M',1),(102,'COPY_OUT','PIPE_MTE3',0),(103,'COPY_IN','PIPE_MTE2',0),(20,'MATMUL','PIPE_M',100),(104,'COPY_OUT','PIPE_MTE3',0)]
    chains=[[1,101,2,10,3,11,4,12,5,102,6],[7,103,8,20,9,104,1000]]
    return {'tensors':[{'id':i,'pos':p,'size':60} for i,p in tensors],'ops':[{'id':i,'op':o,'pipe':p,'cycles':c} for i,o,p,c in ops],'edges':[{'source':a,'target':b} for ch in chains for a,b in zip(ch,ch[1:])]}

def graph_export():
    tensors=[(1,'DDR'),(2,'UB'),(3,'UB'),(4,'UB'),(5,'DDR'),(6,'DDR'),(7,'L1'),(8,'UB'),(9,'DDR')]
    ops=[(101,'COPY_IN','PIPE_MTE2',0),(10,'RELU','PIPE_V',10),(11,'RELU','PIPE_V',5000),(102,'COPY_OUT','PIPE_MTE3',0),(103,'COPY_IN','PIPE_MTE2',0),(20,'MATMUL','PIPE_M',5000),(104,'COPY_OUT','PIPE_MTE3',0)]
    chains=[[1,101,2,10,3,11,4,102,5],[6,103,7,20,8,104,9]]
    return {'tensors':[{'id':i,'pos':p,'size':60} for i,p in tensors],'ops':[{'id':i,'op':o,'pipe':p,'cycles':c} for i,o,p,c in ops],'edges':[{'source':a,'target':b} for ch in chains for a,b in zip(ch,ch[1:])]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(a.official/'code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config
    cfg=a.official/'data/config.txt';conf=read_evaluation_config(cfg);ca=read_scene_a_config(cfg);cc=read_cache_config(cfg)
    allrows=[]
    for name,g in [('reentrant',graph_reentrant()),('export',graph_export())]:
        (a.out/(name+'.json')).write_text(json.dumps(g))
        if name=='reentrant':
            plans={'coarse':{'node_to_subgraph':{'10':0,'11':0,'12':0,'20':1},'core_schedules':[[0,1]]},'interleaved':{'node_to_subgraph':{'10':0,'11':0,'20':1,'12':2},'core_schedules':[[0,1,2]]}}
            for kind in ['chain','refine','nr']:plans[kind]=construct(g,1,kind,True)[0]
            qs=[2,3]
        else:
            base={'node_to_subgraph':{'10':0,'20':1,'11':2},'core_schedules':[[0,1],[2]]}
            fused,fd=fuse_cover(g,base,32);guarded,gd=fuse_cover(g,base,32,True)
            plans={'separate':base,'cover_fused':fused,'guard_exports':guarded};qs=[1]
            (a.out/'fusion_diags.json').write_text(json.dumps({'unguarded':fd,'guarded':gd}))
        for tag,plan in plans.items():
            for q in qs:
                folder=a.out/f'{name}_{tag}_q{q}';folder.mkdir();(folder/'plan.json').write_text(json.dumps(plan));st=time.perf_counter();buf=io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
                        if q==1:r=evaluate_scene_a(g,plan,**conf,cross_core_wait=ca['task_cross_core_wait_cycles'],same_core_wait=ca['task_same_core_wait_cycles'])
                        elif q==2:r=evaluate_scene_b(g,plan,**conf,cross_core_copy_delay=500)
                        else:r=evaluate_problem_3(g,plan,**conf,cross_core_copy_delay=500,**cc)
                    row={'graph':name,'plan':tag,'q':q,'status':'ok','makespan':r['makespan'],'movement':r['data_movement_bytes'],'seconds':time.perf_counter()-st};save(folder/'result.json.gz',r)
                except Exception as e:row={'graph':name,'plan':tag,'q':q,'status':'error','error':str(e)};(folder/'exception.txt').write_text(traceback.format_exc())
                (folder/'stdout_stderr.txt').write_text(buf.getvalue());(folder/'run.json').write_text(json.dumps(row));allrows.append(row);print(row,flush=True)
    (a.out/'summary.json').write_text(json.dumps(allrows,indent=2))
if __name__=='__main__':main()
