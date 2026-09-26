"""Detect exact two-axis input-incidence products; propose rectangle assignments.
The coordinate representation does not identify or renumber official op/tensor IDs.
"""
from collections import defaultdict,deque
from plans import logical,from_blocks

def detect(g):
 ops,elig,p,s,comps,producers,consumers=logical(g)
 compof={v:i for i,vs in enumerate(comps) for v in vs};size={t['id']:t['size'] for t in g['tensors']}
 classes=defaultdict(list);inputs={}
 for tid,users in consumers.items():
  if any(v in compof for v in producers[tid]):continue
  cells=frozenset(compof[v] for v in users if v in compof)
  if cells:classes[cells].append(tid);inputs[tid]=cells
 informative={members:ids for members,ids in classes.items() if 1<len(members)<len(comps)}
 class_members=sorted(informative,key=lambda x:tuple(sorted(x)));classof={x:i for i,x in enumerate(class_members)}
 memberships=[[] for _ in comps]
 for j,members in enumerate(class_members):
  for i in members:memberships[i].append(j)
 if not comps or any(len(x)!=2 for x in memberships):return None
 adj=[set() for _ in class_members]
 for a,b in memberships:adj[a].add(b);adj[b].add(a)
 colors={0:0};queue=deque([0])
 while queue:
  u=queue.popleft()
  for v in adj[u]:
   if v not in colors:colors[v]=1-colors[u];queue.append(v)
   elif colors[v]==colors[u]:return None
 if len(colors)!=len(adj):return None
 left=sorted(j for j,c in colors.items() if c==0);right=sorted(j for j,c in colors.items() if c==1)
 if len(comps)!=len(left)*len(right):return None
 lr={x:i for i,x in enumerate(left)};rr={x:i for i,x in enumerate(right)};grid={}
 for cell,pair in enumerate(memberships):
  a,b=pair
  if a in rr:a,b=b,a
  ij=(lr[a],rr[b])
  if ij in grid:return None
  grid[ij]=cell
 if len(grid)!=len(left)*len(right):return None
 # Strong check: every off-axis external input is global or private; there are
 # no discarded medium-sized incidence classes.
 for tid,mem in inputs.items():
  if 1<len(mem)<len(comps) and mem not in informative:return None
 return dict(rows=len(left),cols=len(right),grid=grid,components=comps,ops=ops,
             row_weights=[sum(size[t] for t in informative[class_members[j]]) for j in left],
             col_weights=[sum(size[t] for t in informative[class_members[j]]) for j in right],
             classes=[{'members':sorted(mem),'tensor_ids':informative[mem],'bytes':sum(size[t] for t in informative[mem])} for mem in class_members],
             input_sets={t:set(mem) for t,mem in inputs.items()},sizes=size)

def rects_uniform(R,C,a,b):
 rs=[i*R//a for i in range(a+1)];cs=[i*C//b for i in range(b+1)]
 return [(rs[i],rs[i+1],cs[j],cs[j+1]) for i in range(a) for j in range(b)]

def rectangle_candidates(d,cores):
 R,C=d['rows'],d['cols'];out=[]
 for a in range(1,min(R,cores)+1):
  for b in range(1,min(C,cores//a)+1):
   if a*b!=cores:continue
   for orientation in ['row','col']:
    rects=rects_uniform(R,C,a,b);blocks=[];assign=[]
    for c,(r0,r1,c0,c1) in enumerate(rects):
     coords=[(i,j) for i in range(r0,r1) for j in range(c0,c1)]
     if orientation=='col':coords.sort(key=lambda ij:(ij[1],ij[0]))
     for ij in coords:blocks.append(d['components'][d['grid'][ij]]);assign.append(c)
    out.append((f'grid_{a}x{b}_{orientation}',from_blocks(blocks,assign,cores)))
 return out

def exact_boundary_inputs(d,p):
 owners={sg:c for c,ss in enumerate(p['core_schedules']) for sg in ss};cop={int(v):owners[sg] for v,sg in p['node_to_subgraph'].items()};cellcore={i:cop[vs[0]] for i,vs in enumerate(d['components'])}
 return sum(d['sizes'][t]*len({cellcore[i] for i in cells}) for t,cells in d['input_sets'].items())
