#!/usr/bin/env python3
"""Independent scalar certificate checker. Never imports generation/official code.
Checks witness validity (not optimality of witness search) using exact integers.
Usage: python verify_certificates.py --root /path/evidence --report /path/report
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile, heapq
from pathlib import Path
from collections import defaultdict
PIPES=('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')
def digest(b):return hashlib.sha256(b).hexdigest()
def cd(a,b):return (a+b-1)//b

def check(root,report):
    cfg=digest((root/'data/raw/a/official/data/config.txt').read_bytes())
    assert cfg=='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
    wc={(r['case_id'],r['cores']):r for r in json.loads((report/'window_certificates.json').read_text())}
    sc={(r['case_id'],r['cores']):r for r in json.loads((report/'separator_certificates.json').read_text())}
    table=json.loads((report/'audit_tables.json').read_text())
    rows={(r['case_id'],r['cores']):r for r in table['rows']}
    numjobs=numblocks=0
    with zipfile.ZipFile(root/'data/raw/a/official-cases.zip') as z:
        for name in sorted(z.namelist()):
            cid=Path(name).stem[-3:];raw=z.read(name);g=json.loads(raw)
            ops={x['id']:x for x in g['ops'] if x['op'] not in ('COPY_IN','COPY_OUT')}
            allt={x['id'] for x in g['tensors']};children={v:set() for v in ops};parents={v:set() for v in ops}
            prod=defaultdict(set);cons=defaultdict(set)
            for e in g['edges']:
                x,y=e['source'],e['target']
                if x in ops and y in ops:children[x].add(y)
                elif x in ops and y in allt:prod[y].add(x)
                elif x in allt and y in ops:cons[x].add(y)
            for t in allt:
                for u in prod[t]:children[u].update(cons[t])
            for u,cs in children.items():
                for v in cs:parents[v].add(u)
            indeg={u:len(ps) for u,ps in parents.items()};heap=[u for u in ops if not indeg[u]];heapq.heapify(heap);order=[]
            while heap:
                u=heapq.heappop(heap);order.append(u)
                for v in children[u]:
                    indeg[v]-=1
                    if indeg[v]==0:heapq.heappush(heap,v)
            assert len(order)==len(ops)
            d={u:max(1,ops[u]['cycles']) for u in ops};r={};q={}
            for u in order:r[u]=max((r[v]+d[v] for v in parents[u]),default=0)
            for u in reversed(order):q[u]=max((d[v]+q[v] for v in children[u]),default=0)
            cp=max((r[u]+d[u] for u in ops),default=0)
            # Independent anchor check: forward/backward reachability inside each
            # reported interval, not the generator's unique-source/sink test.
            pos={u:i for i,u in enumerate(order)}
            anchor_ids=sc[cid,1]['anchors'];as_set=set(anchor_ids)
            assert len(as_set)==len(anchor_ids)
            assert anchor_ids==sorted(anchor_ids,key=lambda u:pos[u])
            bdata=[];left=None;work={p:0 for p in PIPES};count=0;members=[]
            def interval_check(a,b,vs):
                if a is not None:
                    reachable={a}
                    for u in vs+([b] if b is not None else []):
                        assert any(v in reachable for v in parents[u]),(cid,a,b,u,'not reached from left')
                        reachable.add(u)
                if b is not None:
                    reaches={b}
                    for u in list(reversed(vs))+([a] if a is not None else []):
                        assert any(v in reaches for v in children[u]),(cid,a,b,u,'does not reach right')
                        reaches.add(u)
            for u in order:
                if u in as_set:
                    interval_check(left,u,members)
                    bdata.append((left,u,count,work));left=u;work={p:0 for p in PIPES};count=0;members=[]
                else:count+=1;work[ops[u]['pipe']]+=d[u];members.append(u)
            interval_check(left,None,members)
            bdata.append((left,None,count,work))
            for k in range(1,6):
                w=wc[cid,k];s=sc[cid,k];row=rows[cid,k]
                assert row['config_sha256']==cfg
                assert w['graph_sha256']==s['graph_sha256']==row['graph_sha256']==digest(raw)
                assert w['cp']==cp
                certified=[cp]
                for p,cert in w['windows'].items():
                    population=[u for u in ops if ops[u]['pipe']==p]
                    if cert.get('empty'):
                        assert not population and cert['bound']==0;continue
                    a,b=cert['a'],cert['b'];ids=sorted(u for u in population if r[u]>=a and q[u]>=b)
                    W=sum(d[u] for u in ids)
                    assert ids and cert['selected_count']==len(ids) and cert['selected_work']==W
                    assert cert['selected_id_sha256']==digest(json.dumps(ids,separators=(',',':')).encode())
                    assert cert['bound']==a+b+cd(W,k)
                    certified.append(cert['bound']);numjobs+=len(ids)
                assert w['L']==max(certified)==row['L_safe_compute_window']
                assert s['anchors']==anchor_ids and s['anchor_work']==sum(d[u] for u in anchor_ids)
                assert len(s['blocks'])==len(bdata)
                result=s['anchor_work']
                for rec,(a,b,count,work) in zip(s['blocks'],bdata):
                    h=int(a is not None)+int(b is not None)
                    vals={p:min(W,cd(W+h*1000*(k-1),k)) if h else cd(W,k) for p,W in work.items()}
                    assert (rec['left'],rec['right'],rec['op_count'])==(a,b,count)
                    assert rec['pipe_work']==work and rec['endpoints']==h and rec['bounds']==vals
                    assert rec['bound']==max(vals.values());result+=rec['bound'];numblocks+=1
                assert result==s['bound']==row['L_safe_separator']
                assert max(w['L'],s['bound'])==row['L_safe_global']<=row['U']
    result={'status':'pass','cases':100,'cells':500,'window_resource_certificates':2000,
            'selected_compute_memberships_checked':numjobs,'separator_blocks_checked':numblocks,
            'note':'Independent exact arithmetic checker; validates witness lower bounds, not maximality of window generation; no evaluation/simulation calls.'}
    (report/'independent_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/mnt/data/p1_r4_evidence'));p.add_argument('--report',type=Path,default=Path('/mnt/data/p1_r4_report'));a=p.parse_args();check(a.root,a.report)
