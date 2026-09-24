#!/usr/bin/env python3
"""Synthetic graph inputs. These are not recovered official case008 bytes."""
from pathlib import Path
import json

def chains(n=2,a=1000,b=1500,c=1000,cut_bytes=60,skip=False):
    ops=[];tensors=[];edges=[];opid=1;tid=10001
    def tensor(size,pos='UB'):
        nonlocal tid
        t=tid;tid+=1;tensors.append({'id':t,'pos':pos,'size':size});return t
    def op(kind,pipe,cycles,ins,outs):
        nonlocal opid
        u=opid;opid+=1;ops.append({'id':u,'op':kind,'pipe':pipe,'cycles':cycles})
        edges.extend({'source':t,'target':u} for t in ins)
        edges.extend({'source':u,'target':t} for t in outs);return u
    for i in range(n):
        din=tensor(60,'DDR');inp=tensor(60)
        op('COPY_IN','PIPE_MTE2',1,[din],[inp])
        if skip:
            big=tensor(cut_bytes);scalar=tensor(60);norm=tensor(60);out=tensor(60);dout=tensor(60,'DDR')
            op('MATMUL','PIPE_M',a,[inp],[big])
            op('REDUCE','PIPE_V',b//2,[big],[scalar])
            op('NORMALIZE','PIPE_V',b-b//2,[big,scalar],[norm])
            op('MATMUL','PIPE_M',c,[norm],[out])
        else:
            mid=tensor(60);ret=tensor(cut_bytes);out=tensor(60);dout=tensor(60,'DDR')
            op('MATMUL','PIPE_M',a,[inp],[mid])
            op('VECTOR','PIPE_V',b,[mid],[ret])
            op('MATMUL','PIPE_M',c,[ret],[out])
        op('COPY_OUT','PIPE_MTE3',1,[out],[dout])
    return {'ops':ops,'tensors':tensors,'edges':edges}

if __name__=='__main__':
    root=Path(__file__).parent/'experiments'/'inputs';root.mkdir(parents=True,exist_ok=True)
    for name,g in [('A-small-interface',chains()),('B-large-interface',chains(cut_bytes=30000)),
                   ('C-skip-interface',chains(n=1,cut_bytes=30000,skip=True))]:
        p=root/(name+'.json')
        with p.open('x') as f:json.dump(g,f,indent=2);f.write('\n')
