"""Deterministic candidate constructors; no additional runtime controls."""
from collections import defaultdict
import heapq,math
COPY={'COPY_IN','COPY_OUT'}
def logical(g):
 ops={o['id']:o for o in g['ops']}; elig=sorted(k for k,o in ops.items() if o['op'] not in COPY)
 prod=defaultdict(list);con=defaultdict(list)
 p={v:set() for v in ops};s={v:set() for v in ops}
 for e in g['edges']:
  a,b=e['source'],e['target']
  if a in ops and b in ops:s[a].add(b);p[b].add(a)
  elif a in ops:prod[b].append(a)
  elif b in ops:con[a].append(b)
 for t,vs in prod.items():
  for a in vs:
   for b in con[t]:
    if a!=b:s[a].add(b);p[b].add(a)
 es={v:set() for v in elig};ep={v:set() for v in elig};iselig=set(elig)
 for a in elig:
  stack=list(s[a]);seen=set()
  while stack:
   b=stack.pop()
   if b in iselig:es[a].add(b);ep[b].add(a)
   elif b not in seen:seen.add(b);stack.extend(s[b])
 seen=set();cs=[]
 for v in elig:
  if v in seen:continue
  stack=[v];seen.add(v);c=[]
  while stack:
   a=stack.pop();c.append(a)
   for b in ep[a]|es[a]:
    if b not in seen:seen.add(b);stack.append(b)
  cs.append(sorted(c))
 return ops,elig,ep,es,cs,prod,con

def topo(elig,p,s):
 deg={v:len(p[v]) for v in elig};ready=[v for v in elig if not deg[v]];heapq.heapify(ready);out=[]
 while ready:
  a=heapq.heappop(ready);out.append(a)
  for b in s[a]:
   deg[b]-=1
   if deg[b]==0:heapq.heappush(ready,b)
 if len(out)!=len(elig):raise ValueError('cycle')
 return out

def from_blocks(blocks,assign,cores):
 mapping={};schedules=[[] for _ in range(cores)]
 for sg,(vs,c) in enumerate(zip(blocks,assign)):
  for v in vs:mapping[str(v)]=sg
  schedules[c].append(sg)
 # fixed mapping insertion order, independent of block partition
 return {'node_to_subgraph':{v:mapping[v] for v in sorted(mapping,key=int)},'core_schedules':schedules}

def whole(g,cores=4):
 vs=sorted(o['id'] for o in g['ops'] if o['op'] not in COPY)
 return from_blocks([vs],[0],cores)

def component_plan(g,cores=4,granularity='bins',affinity=0.0):
 ops,elig,p,s,cs,prod,con=logical(g);compof={v:i for i,vs in enumerate(cs) for v in vs};tin=defaultdict(set);sz={t['id']:t['size'] for t in g['tensors']}
 for t,cons in con.items():
  if not any(v in compof for v in prod[t]):
   for v in cons:
    if v in compof:tin[compof[v]].add(t)
 work=[]
 for i,vs in enumerate(cs):
  wm=sum(max(1,ops[v]['cycles']) for v in vs if ops[v]['pipe']=='PIPE_M');wv=sum(max(1,ops[v]['cycles']) for v in vs if ops[v]['pipe']=='PIPE_V')
  work.append((wm,wv))
 loads=[[0,0] for _ in range(cores)];resident=[set() for _ in range(cores)];assign=[0]*len(cs)
 for i in sorted(range(len(cs)),key=lambda i:(-max(work[i]),min(cs[i]))):
  wm,wv=work[i]
  c=min(range(cores),key=lambda k:(max(loads[k][0]+wm,loads[k][1]+wv)+affinity*sum(sz[t] for t in tin[i]-resident[k])/60.0,k))
  assign[i]=c;loads[c][0]+=wm;loads[c][1]+=wv;resident[c].update(tin[i])
 if granularity=='components':return from_blocks(cs,assign,cores)
 bins=[[] for _ in range(cores)]
 for vs,c in zip(cs,assign):bins[c].extend(vs)
 blocks=[sorted(vs) for vs in bins if vs];cc=[c for c,vs in enumerate(bins) if vs]
 return from_blocks(blocks,cc,cores)

def intervals(g,cores=4,chunks=16):
 ops,elig,p,s,cs,_,_=logical(g);order=topo(elig,p,s);size=max(1,math.ceil(len(elig)/chunks));blocks=[order[i:i+size] for i in range(0,len(order),size)]
 # Sequential topological labels, list-schedule by compute and dependency delay.
 owners={v:i for i,b in enumerate(blocks) for v in b};pred=[set() for _ in blocks]
 for v in elig:
  for u in p[v]:
   if owners[v]!=owners[u]:pred[owners[v]].add(owners[u])
 load=[0]*cores;finish={};assigned=[]
 for i,b in enumerate(blocks):
  wm=sum(max(1,ops[v]['cycles']) for v in b if ops[v]['pipe']=='PIPE_M');wv=sum(max(1,ops[v]['cycles']) for v in b if ops[v]['pipe']=='PIPE_V');dur=max(wm,wv)
  c=min(range(cores),key=lambda c:(max([load[c]]+[finish[j]+(1000 if assigned[j]!=c else 0) for j in pred[i]])+dur,c))
  finish[i]=max([load[c]]+[finish[j]+(1000 if assigned[j]!=c else 0) for j in pred[i]])+dur;load[c]=finish[i]+100;assigned.append(c)
 return from_blocks(blocks,assigned,cores)
