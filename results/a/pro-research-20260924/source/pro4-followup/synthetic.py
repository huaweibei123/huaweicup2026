"""Typed bipartite public-input-domain generator; all labels must be obtained from E0.
No graph uses rematerialization, arbitrary waits, or modified hardware configuration.
"""
from __future__ import annotations
import json,random,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Builder:
    def __init__(self):self.next=1;self.ts=[];self.ops=[];self.edges=[]
    def tensor(self,pos,size):
        i=self.next;self.next+=1;self.ts.append(dict(id=i,pos=pos,size=size));return i
    def op(self,name,pipe,cycles,ins,out):
        i=self.next;self.next+=1;self.ops.append(dict(id=i,op=name,pipe=pipe,cycles=cycles))
        self.edges.extend(dict(source=t,target=i) for t in ins)
        self.edges.append(dict(source=i,target=out));return i
    def input(self,size,pos='L1'):
        a=self.tensor('DDR',size);b=self.tensor(pos,size);self.op('COPY_IN','PIPE_MTE2',1,[a],b);return b
    def compute(self,p,d,ins,size):
        t=self.tensor('L1' if p=='M' else 'UB',size)
        self.op('MATMUL' if p=='M' else 'ADD','PIPE_'+p,d,ins,t);return t
    def output(self,t,size):
        d=self.tensor('DDR',size);self.op('COPY_OUT','PIPE_MTE3',1,[t],d)
    def graph(self):return dict(tensors=self.ts,ops=self.ops,edges=self.edges)

def generate(family,seed):
    rng=random.Random(seed);b=Builder();n=rng.choice([8,12,20,32,40]);size=rng.choice([512,2048,8192,16384,32768,49152])
    sharedcount=rng.choice([0,1,2]);shared=[b.input(rng.choice([128,512,2048])) for _ in range(sharedcount)]
    a=rng.choice([32,128,512,1158,4096]);ratio=rng.choice([0.25,0.5,1,1.9,3,8])
    for j in range(n):
        x=b.input(size);aj=max(1,int(a*rng.uniform(.3,2))) if family in [1,3,4] else a
        bj=max(1,int(a*ratio*rng.uniform(.5,1.5))) if family in [1,3,4] else max(1,int(a*ratio))
        if family in [0,1]:
            y=b.compute('M',aj,[x]+shared,size)
            z=b.compute('V',bj,[y],size)
            out=b.compute('M',aj,[z,y] if j%2==0 else [z],size)
        elif family==2:
            p=rng.choice(['M','V']);q='V' if p=='M' else 'M'
            y=b.compute(p,aj,[x]+shared,size);out=b.compute(q,bj,[y],size)
        elif family==3:
            y=b.compute('M',aj,[x]+shared,size)
            z=b.compute('V',bj,[y],size)
            w=b.compute('M',max(1,aj//2),[z],size)
            out=b.compute('V',max(1,bj//2),[w],size)
        elif family==4:
            y=b.compute('M',aj,[x]+shared,size)
            z=b.compute('V',bj,[y],size//2)
            w=b.compute('V',max(1,bj//3),[y],size//2)
            out=b.compute('M',aj,[z,w],size)
        b.output(out,size)
    # Guarantee the paper's per-op capacity condition using separate pools.
    obj=b.graph();ts={t['id']:t for t in obj['tensors']}
    for op in obj['ops']:
        if op['op'] in {'COPY_IN','COPY_OUT'}:continue
        touched={e['source'] if e['target']==op['id'] else e['target'] for e in obj['edges'] if e['source']==op['id'] or e['target']==op['id']}
        for pos,cap in [('L1',524288),('UB',131072)]:
            assert sum(ts[t]['size'] for t in touched if ts[t]['pos']==pos)<=cap
    return obj,dict(family=family,seed=seed,jobs=n,tensor_size=size,a=a,ratio=ratio,shared_inputs=sharedcount)

if __name__=='__main__':
    folder=ROOT/'synthetic';folder.mkdir(exist_ok=True);index=[];requests=[]
    for family,count,split in [(0,24,'train'),(1,24,'train'),(2,24,'train'),(3,12,'calibration'),(4,12,'test')]:
        for j in range(count):
            case=10000+family*100+j;seed=20260923+family*1000+j
            obj,meta=generate(family,seed);path=folder/f'case_{case:05d}.json';path.write_text(json.dumps(obj,separators=(',',':')))
            index.append(dict(case=case,split=split,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),**meta))
            for method,gamma in [('coarse',1),('id',1),('unguarded',1),('frontier',1),('stage_tail',.5)]:
                requests.append(dict(case=case,problem=2,k=4,assignment='component',method=method,gamma=gamma,tag='synthetic1',graph_path=str(path),timeout=20))
    (ROOT/'audit/synthetic_index.json').write_text(json.dumps(index,indent=2))
    (ROOT/'audit/synthetic_protocol.json').write_text(json.dumps(dict(name='synthetic1',notes='72 train graphs from families0/1/2, 12 calibration family3, 12 held-out fork-family4. 5 fully E0-labelled candidates each. Not an E2 acceptance pool.',requests=requests),indent=2))
