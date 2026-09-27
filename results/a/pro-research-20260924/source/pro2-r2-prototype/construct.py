"""Structured constructors. No op renumbering, graph changes or simulated waits.
Eligible weak components stay on a core; temporal tiling controls only sg priorities.
"""
from collections import defaultdict
from product import bundle_products

def plan_from_groups(groups,k):
    mapping={}; schedules=[[] for _ in range(k)];sg=0
    for core,gs in enumerate(groups):
        for ops in gs:
            if not ops: continue
            schedules[core].append(sg)
            for u in ops:
                if str(u) in mapping:raise ValueError('duplicate op in constructor')
                mapping[str(u)]=sg
            sg+=1
    return {'node_to_subgraph':mapping,'core_schedules':schedules}

def component_assignment(a,k,mode='lpt',product_shape=None):
    cs=a['components'];e=a['eligible']; by=[[] for _ in range(k)]
    if mode=='rr':
        for i in range(len(cs)):by[i%k].append(i)
        return by
    if mode=='contiguous':
        for i in range(len(cs)):by[min(k-1,i*k//max(1,len(cs)))].append(i)
        return by
    if mode=='product':
        b=bundle_products(a); products=[p for p in b['products'] if min(p['shape'])>1]
        if len(products)!=1 or len(products[0]['jobs'])!=len(cs):raise ValueError('requires a closed nontrivial product covering all components')
        p=products[0];nr,nc=product_shape
        if nr*nc>k or nr>p['shape'][0] or nc>p['shape'][1]:raise ValueError('invalid grid shape')
        R,C=p['shape']
        for j in p['jobs']:
            r,c=p['coords'][j];by[(r*nr//R)*nc+c*nc//C].append(j)
        return by
    pipes=('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3')
    work=[[sum(e[u]['cycles'] for u in c if e[u]['pipe']==p) for p in pipes] for c in cs]
    totals=[sum(w[p] for w in work) for p in range(4)]
    load=[[0]*4 for _ in range(k)]
    order=sorted(range(len(cs)),key=lambda j:(-max(work[j]),-sum(work[j]),min(cs[j])))
    for j in order:
        core=min(range(k),key=lambda x:(max((load[x][p]+work[j][p])/max(1,totals[p]) for p in range(4)),sum(load[x]),x))
        by[core].append(j)
        for p in range(4):load[core][p]+=work[j][p]
    for js in by:js.sort(key=lambda j:min(cs[j]))
    return by

def component_plan(a,k,assignment='lpt',wave=0,band=0,grid=None,order='id'):
    by=component_assignment(a,k,assignment,grid);cs=a['components']
    product=None
    if order in ('row','col','snake'):
        prod=bundle_products(a)['products'];product=max(prod,key=lambda p:len(p['jobs']),default=None)
    groups=[]
    for js in by:
        if product:
            coords=product['coords']
            def key(j):
                r,c=coords.get(j,(j,0))
                return (c,r) if order=='col' else ((r,c if r%2==0 else -c) if order=='snake' else (r,c))
            js=sorted(js,key=key)
        gs=[];w=wave or max(1,len(js))
        for off in range(0,len(js),w):
            jobs=js[off:off+w];length=max((len(cs[j]) for j in jobs),default=0);b=band or max(1,length)
            for lo in range(0,length,b):
                gs.append([u for j in jobs for u in cs[j][lo:lo+b]])
        groups.append(gs)
    return plan_from_groups(groups,k)

def topo_plan(a,k,chunk=0,order='id'):
    if order=='depth':seq=sorted(a['top'],key=lambda v:(a['depth'][v],v))
    else:seq=a['top']
    if not chunk:chunk=max(1,(len(seq)+k-1)//k)
    gs=[[] for _ in range(k)]
    for i,off in enumerate(range(0,len(seq),chunk)):gs[i%k].append(seq[off:off+chunk])
    return plan_from_groups(gs,k)

def make(a,k,spec):
    spec=dict(spec);kind=spec.pop('kind')
    if kind=='whole':return plan_from_groups([[a['top']]]+[[] for _ in range(k-1)],k)
    if kind=='topo':return topo_plan(a,k,**spec)
    if kind=='component':return component_plan(a,k,**spec)
    if kind=='affine':return affine_plan(a,k,**spec)
    if kind=='heavy':
        from coarsen import heavy_plan
        return heavy_plan(a,k,**spec)
    raise ValueError(kind)

def affine_plan(a,k,assignment='lpt',wave=0,lag_fraction=0.5,grid=None,granularity=0,order='id'):
    """Sort actual ops by an affine (job, local compute-prefix) coordinate.
    Coordinates are discarded. No start times, pauses or physical instructions are submitted.
    With fraction > 0, each component's topo order is strictly increasing.
    """
    by=component_assignment(a,k,assignment,grid);cs=a['components'];e=a['eligible'];groups=[]
    for js in by:
        w=wave or max(1,len(js));gs=[]
        for off in range(0,len(js),w):
            jobs=js[off:off+w]
            length=max((sum(max(1,e[u]['cycles']) for u in cs[j]) for j in jobs),default=1)
            lag=max(1,int(length*lag_fraction))
            tagged=[]
            for i,j in enumerate(jobs):
                prefix=0
                for u in cs[j]:
                    tagged.append((prefix+i*lag,u));prefix+=max(1,e[u]['cycles'])
            tagged.sort()
            last=None
            for score,u in tagged:
                key=score//granularity if granularity else (score,u)
                if key!=last:gs.append([]);last=key
                gs[-1].append(u)
        groups.append(gs)
    return plan_from_groups(groups,k)
