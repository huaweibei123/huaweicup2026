"""Bounded mathematical checks only; not official timing experiments."""
import random,json,time,itertools,heapq
from pathlib import Path
from coarsen import scc
R=random.Random(20260923)
def parts(n):
 a=[0]*n
 def go(i,m):
  if i==n:yield tuple(a);return
  for c in range(m+2):a[i]=c;yield from go(i+1,max(m,c))
 if n:yield from go(1,0)
 else:yield ()
def dag(adj):return all(len(c)==1 for c in scc(adj)) and all(i not in adj[i] for i in range(len(adj)))
def quotient(adj,p):
 q=[set() for _ in range(max(p,default=-1)+1)]
 for u,vs in enumerate(adj):
  for v in vs:
   if p[u]!=p[v]:q[p[u]].add(p[v])
 return q
start=time.perf_counter();checks=0;comparisons=0
for _ in range(150):
 n=6;G=[set(j for j in range(i+1,n) if R.random()<.35) for i in range(n)];initial=R.choice(list(parts(n)));Q=quotient(G,initial);closure=scc(Q)
 assert dag(quotient(Q,tuple(next(j for j,c in enumerate(closure) if i in c) for i in range(len(Q)))))
 for p in parts(len(Q)):
  if dag(quotient(Q,p)):
   assert all(len({p[u] for u in c})==1 for c in closure);comparisons+=1
 checks+=1
compact_cases=0
for _ in range(200):
 n=8;perm=list(range(n));R.shuffle(perm);expect=1+sum(x>y for x,y in zip(perm,perm[1:]));best=n
 for mask in range(1<<(n-1)):
  chunks=[];last=0
  for i in range(n-1):
   if mask>>i&1:chunks.append(perm[last:i+1]);last=i+1
  chunks.append(perm[last:]);
  if all(x==sorted(x) for x in chunks):best=min(best,len(chunks))
 assert best==expect;compact_cases+=1
word_cases=0;maxratio=0
for m in range(1,33):
 for a in range(1,5):
  for b in range(1,2*a+1):
   h=1+(b+a-1)//a;n=3*m;adj=[set() for _ in range(n)];d=[a,b,a]*m
   M=[3*i for i in range(min(m,h))]
   for i in range(m):
    M.append(3*i+2)
    if i+h<m:M.append(3*(i+h))
   for i in range(m):adj[3*i].add(3*i+1);adj[3*i+1].add(3*i+2)
   for word in [M,[3*i+1 for i in range(m)]]:
    for u,v in zip(word,word[1:]):adj[u].add(v)
   indeg=[0]*n
   for vs in adj:
    for v in vs:indeg[v]+=1
   q=[i for i in range(n) if not indeg[i]];E=[0]*n;vis=0
   while q:
    u=q.pop();vis+=1
    for v in adj[u]:E[v]=max(E[v],E[u]+d[u]);indeg[v]-=1;q.extend([v] if not indeg[v] else [])
   assert vis==n;T=max(E[u]+d[u] for u in range(n));assert T<=2*a*(m+1);maxratio=max(maxratio,T/(2*a*(m+1)));word_cases+=1
out={'seed':20260923,'scope':'abstract finite graphs/fixed-duration word model; no DDR, cache, or floating E0 equivalence claim','scc_random_cases':checks,'acyclic_coarsening_comparisons':comparisons,'bucket_permutations':compact_cases,'word_fixed_duration_cases':word_cases,'all_passed':True,'elapsed_seconds':time.perf_counter()-start}
Path('/mnt/data/r2_research/analysis/math_checks.json').write_text(json.dumps(out,indent=2));print(out)
