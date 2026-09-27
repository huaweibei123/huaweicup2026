"""Small, explicitly limited learning experiment. No E0 values enter input features.
Synthetic graph-family split; full official CLI labels, not proxy labels.
"""
from __future__ import annotations
import json,math,time,os,sys,glob
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
METHODS=['coarse','id','unguarded','frontier','stage_tail']
from graph_features import Graph

FEATURE_NAMES=['log_n','log_tensors','log_edges','component_fraction','max_component_fraction','m_work_fraction',
 'log_work','critical_work_ratio','shared_input_fraction','log_input_bundles','log_max_tensor','input_bytes_work_ratio',
 'log_LB','log_subgraphs','certificate_present','certified_no_spill','max_L1_ratio','max_UB_ratio','virtual_over_LB',
 'soft_budget_forced_ratio']+['method_'+x for x in METHODS]

def feature(g,stat,r):
    n=len(g.ids);work=sum(g.duration(o) for o in g.ids)
    wm=stat['work'].get('PIPE_M',0);wv=stat['work'].get('PIPE_V',0)
    lb=max(stat['critical_path'],wm/r['cores'],wv/r['cores'],1)
    c=r['constructor'];present='no_spill_sufficient' in c
    peaks=c.get('bucket_peak_by_core',[])
    l1=max([x.get('L1',0)/524288 for x in peaks],default=0);ub=max([x.get('UB',0)/131072 for x in peaks],default=0)
    nsg=n if r['method']!='coarse' else c['groups']
    inputbytes=sum(g.ts[t]['size'] for t in g.ts if g.cons[t]&g.eligible and not g.prod[t]&g.eligible)
    a=[math.log1p(n),math.log1p(len(g.ts)),math.log1p(len(g.obj['edges'])),len(g.components)/n,
       max(map(len,g.components))/n,wm/max(1,work),math.log1p(work),stat['critical_path']/max(work,1),
       stat['input_shared_fraction'],math.log1p(stat['input_bundles']),math.log1p(stat['max_tensor_size']),
       inputbytes/(60*max(work,1)),math.log1p(lb),math.log1p(nsg),float(present),float(c.get('no_spill_sufficient',False)),l1,ub,
       c.get('virtual_compute_finish',0)/lb,c.get('forced_soft_budget_steps',0)/n]
    return a+[float(r['method']==m) for m in METHODS],lb

def metrics(pred,Y):
    chosen=np.argmin(pred,axis=1);best=Y.min(axis=1);sel=Y[np.arange(len(Y)),chosen]
    regret=np.expm1(sel-best)
    err=np.abs(np.exp(pred-Y)-1)
    top2=np.argsort(pred,axis=1)[:,:2];r2=np.expm1(np.take_along_axis(Y,top2,axis=1).min(axis=1)-best)
    return dict(graphs=len(Y),top1_regret_median=float(np.median(regret)),top1_regret_mean=float(np.mean(regret)),top1_regret_p95=float(np.percentile(regret,95)),
                top1_regret_max=float(regret.max()),top2_regret_mean=float(np.mean(r2)),within_1pct=float(np.mean(regret<=.01)),
                numeric_relative_error_median=float(np.median(err)),numeric_relative_error_p95=float(np.percentile(err,95)),chosen=chosen.tolist(),regrets=regret.tolist())

def main():
    t0=time.perf_counter();index=json.loads((ROOT/'audit/synthetic_index.json').read_text());groups=[];Y=[];S=[];splits=[];cases=[]
    for entry in index:
        rows=[json.loads(p.read_text()) for p in sorted((ROOT/'runs').glob(f"synthetic1_c{entry['case']:03d}_*/run.json"))]
        if len(rows)!=5 or any(r['status']!='ok' for r in rows):raise RuntimeError(('Incomplete full candidate pool',entry['case'],len(rows)))
        rows.sort(key=lambda r:METHODS.index(r['method']))
        g=Graph(json.loads(Path(entry['path']).read_text()));stat=g.statistics();xs=[];ys=[];ss=[]
        for r in rows:
            f,lb=feature(g,stat,r);xs.append(f);ys.append(math.log(r['makespan']/lb));ss.append(float(r['data_movement_bytes']['spill_added_copy_bytes']>0))
        groups.append(xs);Y.append(ys);S.append(ss);splits.append(entry['split']);cases.append(entry['case'])
    X=np.asarray(groups,dtype=np.float32);Y=np.asarray(Y,dtype=np.float32);S=np.asarray(S,dtype=np.float32)
    train=np.array([s=='train' for s in splits]);cal=np.array([s=='calibration' for s in splits]);test=np.array([s=='test' for s in splits])
    mu=X[train].reshape(-1,X.shape[-1]).mean(0);sd=X[train].reshape(-1,X.shape[-1]).std(0);sd=np.maximum(sd,.01)
    Z=(X-mu)/sd
    outdir=ROOT/'learning';outdir.mkdir(exist_ok=True)
    np.savez_compressed(outdir/'dataset.npz',X=X,Y=Y,spill=S,train=train,cal=cal,test=test,mu=mu,sd=sd,cases=cases)
    from sklearn.linear_model import Ridge
    from sklearn.tree import DecisionTreeRegressor
    # Formal graphs are an additional out-of-distribution diagnostic, not used to fit.
    RX=[];RY=[];real_cases=[]
    for case in [1,6,12,17,26,37,46,48,69,71,89,96]:
        rr=[json.loads(p.read_text()) for p in (ROOT/'runs').glob(f'validation1*_c{case:03d}_q2_*/run.json')]
        rr=[r for r in rr if r['assignment']!='topo64'];rr.sort(key=lambda r:METHODS.index(r['method']))
        if len(rr)!=5 or any(r['status']!='ok' for r in rr):raise RuntimeError(('formal pool incomplete',case))
        g=Graph(json.loads((ROOT.parent/'route4_base/data/raw/a/official/data'/f'case_{case:03d}.json').read_text()));stat=g.statistics()
        xs=[];ys=[]
        for r in rr:
            ft,lb=feature(g,stat,r);xs.append(ft);ys.append(math.log(r['makespan']/lb))
        RX.append(xs);RY.append(ys);real_cases.append(case)
    RX=(np.array(RX,dtype=np.float32)-mu)/sd;RY=np.array(RY,dtype=np.float32)
    models={'ridge':Ridge(alpha=10),'tree_depth4':DecisionTreeRegressor(max_depth=4,min_samples_leaf=8,random_state=0)}
    report={'feature_names':FEATURE_NAMES,'n_graphs':len(X),'pool_size':5,'train_graphs':int(train.sum()),'calibration_graphs':int(cal.sum()),'test_graphs':int(test.sum()),
            'methods':METHODS,'results':{},'splits':'Whole grammar families separated. Calibration is diagnostic only; no checkpoint or hyperparameter selection uses it.','warning':'Not a >=64-candidate E2 acceptance test; no GPU. Constructor/feature/E0 costs separate.'}
    fixed=int(np.argmin(Y[train].mean(axis=0)))
    report['best_fixed_training_action']=METHODS[fixed]
    for name,model in models.items():
        t=time.perf_counter();model.fit(Z[train].reshape(-1,Z.shape[-1]),Y[train].reshape(-1));pred=model.predict(Z.reshape(-1,Z.shape[-1])).reshape(Y.shape)
        report['results'][name]={'real_q2_12':metrics(model.predict(RX.reshape(-1,RX.shape[-1])).reshape(RY.shape),RY),'fit_wall_s':time.perf_counter()-t,'calibration':metrics(pred[cal],Y[cal]),'test':metrics(pred[test],Y[test])}
    for i,name in enumerate(METHODS):
        pred=np.ones_like(Y)*100;pred[:,i]=0
        r=metrics(pred[test],Y[test]);r.pop('numeric_relative_error_median');r.pop('numeric_relative_error_p95')
        rp=np.ones_like(RY)*100;rp[:,i]=0
        rm=metrics(rp,RY);rm.pop('numeric_relative_error_median');rm.pop('numeric_relative_error_p95')
        report['results']['fixed_'+name]={'test':r,'real_q2_12':rm}
    import torch
    torch.set_num_threads(1)
    report['torch_version']=torch.__version__;report['cuda_available']=torch.cuda.is_available();report['mps_available']=torch.backends.mps.is_available()
    x=torch.tensor(Z[train]);y=torch.tensor(Y[train]);sp=torch.tensor(S[train]);allx=torch.tensor(Z)
    for seed in [0,1,2]:
        torch.manual_seed(seed)
        net=torch.nn.Sequential(torch.nn.Linear(X.shape[-1],48),torch.nn.ReLU(),torch.nn.Linear(48,48),torch.nn.ReLU(),torch.nn.Linear(48,2))
        opt=torch.optim.AdamW(net.parameters(),lr=.002,weight_decay=.001);t=time.perf_counter();hist=[]
        for epoch in range(600):
            opt.zero_grad();o=net(x);yp=o[...,0];risk=o[...,1]
            reg=torch.nn.functional.smooth_l1_loss(yp,y)
            dy=y[:,:,None]-y[:,None,:];dp=yp[:,:,None]-yp[:,None,:];mask=dy.abs()>.01
            rank=torch.nn.functional.softplus(-dy.sign()*dp/.1)
            rank=(rank*mask*dy.abs().clamp(max=1)).sum()/mask.sum().clamp(min=1)
            aux=torch.nn.functional.binary_cross_entropy_with_logits(risk,sp)
            loss=reg+.2*rank+.1*aux;loss.backward();opt.step()
            if epoch%100==0:hist.append([epoch,float(loss.detach()),float(reg.detach()),float(rank.detach()),float(aux.detach())])
        train_s=time.perf_counter()-t
        net.eval()
        with torch.no_grad():pred=net(allx)[...,0].numpy()
        # Warm inference timing for one 5-candidate pool, excludes constructing the pool.
        with torch.no_grad():
            for _ in range(20):net(allx[:1])
            t=time.perf_counter()
            for _ in range(1000):net(allx[:1])
            infer=(time.perf_counter()-t)/1000
        torch.save(net.state_dict(),outdir/f'mlp_seed{seed}.pt')
        with torch.no_grad():realpred=net(torch.tensor(RX))[...,0].numpy()
        report['results'][f'mlp_seed{seed}']={'real_q2_12':metrics(realpred,RY),'parameters':sum(p.numel() for p in net.parameters()),'train_wall_s':train_s,'warm_pool_inference_s':infer,'history':hist,'calibration':metrics(pred[cal],Y[cal]),'test':metrics(pred[test],Y[test])}
    report['formal_test_cases']=real_cases
    report['total_wall_s']=time.perf_counter()-t0
    (outdir/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v.get('test',{}) for k,v in report['results'].items()},indent=2))
if __name__=='__main__':main()
