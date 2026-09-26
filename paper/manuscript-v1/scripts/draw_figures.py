#!/usr/bin/env python3
import os
"""Render source-bound data and mechanism figures; no numerical simulation."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
from figure_style import PAPER,C,PIPE,plt,save,clean

DATA=PAPER/'data'; INPUTS=DATA/'figure-inputs'; FIG=PAPER/'figures'
def source(n):return json.loads(gzip.decompress((INPUTS/(n+'.json.gz')).read_bytes()))
def rows():
    raw=list(csv.DictReader((DATA/'all-results.csv').open()))
    for r in raw:
        for k in ('cores','makespan_cycles','extra_ddr_bytes','baseline_cycles','solver_wall_seconds',
                  'official_curve_speedup','baseline_speedup','cache_gain','cache_hit_rate_bytes','no_l2_makespan_cycles'):
            if r[k]!='':r[k]=float(r[k])
    return raw

def timeline(d,name,title,xmax=None,window=None):
    """All cores; Task spans and four distinct resource lanes; actual E0 events."""
    K=d['num_cores']; paper=os.environ.get('PAPER_LAYOUT') == '1'
    height=(1.0+K*.62) if paper else (2.1+K*1.02)
    fig=plt.figure(figsize=(6.5,height))
    gs=fig.add_gridspec(2,1,height_ratios=[K*.22,K*.80],left=.155,right=.97,bottom=(.135 if paper else .075),top=(.985 if paper else .845),hspace=(.17 if paper else .27))
    a=fig.add_subplot(gs[0]);b=fig.add_subplot(gs[1],sharex=a)
    fig.text(.155,.965,title,va='top')
    fig.text(.155,.925,f"M = {d['makespan']:,} cycle    额外搬运 = {d['data_movement_bytes']['added_copy_bytes']:,} B",va='top')
    for c in d['per_core_timeline']:
        k=c['core_id']
        for task in c['tasks']:
            a.broken_barh([(task['start']/1000,task['duration']/1000)],(k-.34,.68),facecolor=C['pale'],edgecolor=C['ink'],linewidth=.7)
            if d['scene']=='A' and task['duration']/(xmax or d['makespan'])>.065:
                a.text((task['start']+task['end'])/2000,k,str(task['task_id']),ha='center',va='center',fontsize=(9 if paper else 12))
        for j,pipe in enumerate(PIPE):
            ops=[o for o in c['ops'] if o['pipe']==pipe]
            b.broken_barh([(o['start']/1000,o['duration']/1000) for o in ops],(k*5+j-.34,.68),facecolor=PIPE[pipe],edgecolor='none')
        if k<K-1:b.axhline(k*5+4,color=C['gray'],linewidth=.5)
    a.set_yticks(range(K),[f'Core {k}' for k in range(K)])
    a.set_ylim(K-.5,-.5); a.set_title('(a) Task 时间跨度' + ('（框内为 Task ID）' if d['scene']=='A' else '（同核已合并）'),loc='left',pad=8)
    b.set_ylim(K*5-1,-1)
    b.set_yticks([k*5+j for k in range(K) for j in range(4)],
                [f'{k} · {p}' for k in range(K) for p in ('M','V','MTE2','MTE3')])
    b.set_title('(b) 每核四条 Pipe 的实际占用区间',loc='left',pad=8)
    b.set_xlabel('时间 / 千 cycle',fontsize=(10 if paper else 12));a.tick_params(axis='x',labelbottom=False)
    if paper: b.tick_params(axis='x',labelsize=10)
    for ax in (a,b):
        ax.set_xlim(*(np.array(window)/1000) if window else (0,(xmax or d['makespan'])*1.012/1000))
        ax.axvline(d['makespan']/1000,color=C['ink'],ls='--',lw=.9)
        ax.grid(axis='x',color=C['pale']);ax.set_axisbelow(True)
        ax.tick_params(axis='y',length=0,labelsize=(8.8 if paper else 12))
    save(fig,name)

def partition_story(d):
    ids=[710,712,714,716,720,722,724,726]
    pos={710:(.85,2.6),712:(2.45,2.6),714:(4.05,2.6),716:(5.65,2.6),
         720:(1.65,1.72),722:(4.85,1.72),724:(3.25,.85),726:(3.25,.08)}
    g=d['graph'];ops={x['id']:x for x in g['ops']};tensor={x['id']:x for x in g['tensors']}
    before={};after={}
    for e in g['edges']:before.setdefault(e['target'],[]).append(e['source']);after.setdefault(e['source'],[]).append(e['target'])
    edges=[];ports=[]
    for i in ids:
        for t in before.get(i,[]):
            parents=before.get(t,[])
            if parents and parents[0] in ids:edges.append((parents[0],i,t,tensor[t]['size']))
            else:ports.append(dict(target=i,tensor=t,producers=parents,size=tensor[t]['size']))
    semantic=dict(case_id='026',nodes=[ops[i] for i in ids],positions=pos,edges=edges,external_inputs=ports,
                  external_outputs=[dict(source=i,tensor=t,targets=after.get(t,[]),size=tensor[t]['size'])
                    for i in ids for t in after.get(i,[]) if any(v not in ids for v in after.get(t,[]))],
                  note='Cropped original op dependency projection; tensor edges preserve original IDs and bytes. Node positions identical in both panels.')
    fig,axs=plt.subplots(2,1,figsize=(6.5,8.0),gridspec_kw={'left':.025,'right':.985,'top':.89,'bottom':.075,'hspace':.30})
    for ax,(key,title) in zip(axs,[('old','(a) 父方案：整个片段在 sg0 / 核0'),('new','(b) 分叉援助：X / 核0，Y / 核1，J / 核0')]):
        ax.set(xlim=(0,6.5),ylim=(-.43,3.4));ax.axis('off');ax.set_title(title,loc='left',pad=10)
        plan=d[key]['plan'];sg={i:plan['node_to_subgraph'][str(i)] for i in ids}
        semantic[key+'_node_to_subgraph']=sg
        if key=='old':
            ax.add_patch(FancyBboxPatch((.13,-.29),6.24,3.5,boxstyle='round,pad=0.02',fc='#F5F6F8',ec=C['gray'],lw=1))
        else:
            for x,y,w,h,label,color in [(.12,1.38,3.02,1.87,'X · sg0',C['M']),(3.36,1.38,3.02,1.87,'Y · sg6',C['in']),(2.5,-.32,1.5,1.64,'J · sg5',C['out'])]:
                ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.02',fc='white',ec=color,lw=1.4,ls='--'))
                ax.text(x+.10,y+h-.10,label,va='top',bbox=dict(fc='white',ec='none',pad=1))
        for u,v,t,b in edges:
            x,y=pos[u];xx,yy=pos[v];cross=sg[u]!=sg[v]
            ax.add_patch(FancyArrowPatch((x,y-.17),(xx,yy+.18),arrowstyle='-|>',mutation_scale=9,color=C['out'] if cross else C['gray'],lw=1.4 if cross else .8,linestyle='--' if cross else '-'))
            if (u,v) in ((720,724),(722,724)):
                ax.text((x+xx)/2+(-.38 if u==720 else .38),(y+yy)/2,f't{t}: {b} B',ha='center',va='center',bbox=dict(fc='white',ec='none',pad=.3))
        for i in ids:
            x,y=pos[i];ax.add_patch(FancyBboxPatch((x-.40,y-.17),.8,.34,boxstyle='round,pad=.01',fc='#EEEAF4',ec=C['V'],lw=.8))
            ax.text(x,y,f'ADD {i}',ha='center',va='center')
        for i in ids[:4]:
            x,y=pos[i];ax.plot([x,x],[y+.18,3.02],color=C['gray'],ls=':',lw=.8)
        ax.annotate('外部 t719 · 2 B',xy=(3.67,.08),xytext=(4.5,.08),va='center',arrowprops=dict(arrowstyle='->',lw=.7,color=C['gray']))
        ax.plot([3.25,3.25],[-.10,-.4],color=C['gray'],ls=':',lw=.8)
    fig.text(.03,.98,'case_026 的真实归约片段：固定节点，只改变分组',va='top')
    fig.text(.03,.035,'点线：接图外依赖；橙色虚线：跨子图传输。完整端口见 JSON。',va='bottom')
    (FIG/'partition-story.json').write_text(json.dumps(semantic,ensure_ascii=False,indent=2)+'\n')
    save(fig,'fig-p1-cuts')

def stat_figures(allrows):
    summary=json.loads((DATA/'summary.json').read_text())
    old1={(r['case_id'],r['cores']):r['metrics'] for r in source('p1-old-metrics')}
    old2={(r['case'],r['cores']):r['baseline'] for r in source('p2-comparison')}
    for p,old in [('P1',old1),('P2',old2)]:
        part=[r for r in allrows if r['problem']==p]
        fig,(a,b)=plt.subplots(2,1,figsize=(6.5,4.9 if os.environ.get('PAPER_LAYOUT') == '1' else 6.5),gridspec_kw={'left':.15,'right':.96,'bottom':.12,'top':.95,'hspace':.55})
        ks=range(1,6);new=[summary[p]['cores'][str(k)]['mean_official_curve_speedup'] for k in ks]
        prev=[1 if k==1 else statistics.fmean(r['baseline_cycles']/old[(r['case_id'],int(r['cores']))]['makespan_cycles' if p=='P1' else 'makespan'] for r in part if r['cores']==k) for k in ks]
        a.plot(ks,prev,'o--',color=C['gray'],label='前一完整算法');a.plot(ks,new,'s-',color=C['M'],label='本文固定算法')
        for k,v in zip(ks,new): a.annotate(f'{v:.3f}',(k,v),xytext=(0,8),textcoords='offset points',ha='center')
        a.set(xticks=list(ks),ylim=(.7,5.15),title='(a) 每个核数均为 100 图的算术平均');a.legend(loc='upper left')
        clean(a,'Core数量 K','平均加速比')
        for k,marker in zip(ks,['o','s','^','D','v']):
            rr=[r for r in part if r['cores']==k];xx=[];yy=[]
            for r in rr:
                o=old[(r['case_id'],k)];m=o['makespan_cycles' if p=='P1' else 'makespan'];dd=o['extra_ddr_bytes' if p=='P1' else 'added_copy_bytes']
                xx.append((r['extra_ddr_bytes']-dd)/2**20); yy.append((m-r['makespan_cycles'])/m*100)
            b.scatter(xx,yy,s=21,marker=marker,color=C['M'],alpha=.5,label=str(k))
        b.axvline(0,color=C['gray'],lw=.7);b.axhline(0,color=C['gray'],lw=.7)
        b.set_xscale('symlog',linthresh=.05)
        clean(b,'额外搬运量变化 / MiB（对称对数）','完工时间下降 / %')
        b.set_title('(b) 500 格配对：更快与更少搬运分别核对',loc='left')
        b.legend(title='K',ncol=5,loc='upper left',handletextpad=.25,columnspacing=.7)
        b.set_xticks([-1,-.1,0,.1,1,10,100] if p=='P2' else [-1,-.1,0,.1,1])
        b.set_xticklabels(['−1','−0.1','0','0.1','1','10','100'] if p=='P2' else ['−1','−0.1','0','0.1','1'])
        save(fig,'fig-'+p.lower()+'-results')
    fig,(a,b)=plt.subplots(2,1,figsize=(6.5,4.8 if os.environ.get('PAPER_LAYOUT') == '1' else 6.1),gridspec_kw={'left':.15,'right':.96,'bottom':.12,'top':.95,'hspace':.5})
    cs=summary['P3']['cores'];ks=np.arange(1,6)
    a.plot(ks,[cs[str(k)]['mean_no_l2_baseline_speedup'] for k in ks],'o--',color=C['gray'],label='同计划，无 L2')
    a.plot(ks,[cs[str(k)]['mean_baseline_speedup'] for k in ks],'s-',color=C['M'],label='同计划，只读 Cache')
    a.set(xticks=ks,ylim=(.9,5.2),title='(a) 同图、同 K、同计划字节，仅改变 Cache 语义');a.legend();clean(a,'Core数量 K','平均 B / M')
    v=[cs[str(k)]['mean_cache_gain'] for k in ks];b.plot(ks,v,'D-',color=C['in'])
    for k,x in zip(ks,v):b.annotate(f'{x:.4f}',(k,x),xytext=(0,9),textcoords='offset points',ha='center')
    b.axhline(1,color=C['gray'],lw=.8);b.set(xticks=ks,ylim=(.99,1.105),title='(b) 每核数 100 对；不以“均值之比”替代“比值均值”');clean(b,'Core数量 K','平均 M₂ / M₃')
    save(fig,'fig-p3-results')
    fig,a=plt.subplots(figsize=(6.5,3.7));fig.subplots_adjust(left=.16,right=.97,bottom=.19,top=.88)
    for k,marker in zip(ks,['o','s','^','D','v']):
        rr=[r for r in allrows if r['problem']=='P3' and r['cores']==k]
        a.scatter([r['cache_hit_rate_bytes']*100 for r in rr],[r['cache_gain'] for r in rr],marker=marker,s=23,alpha=.58,label=f'K={k}')
    a.axhline(1,color=C['ink'],lw=.8,ls='--');a.legend(ncol=3,loc='upper left',columnspacing=.6)
    clean(a,'逐图字节命中率 / %','同计划 M₂ / M₃');a.set_title('500 个配对全部保留；命中率不是收益的充分统计量')
    save(fig,'fig-cache-gain')
    fig,a=plt.subplots(figsize=(6.5,3.7));fig.subplots_adjust(left=.13,right=.97,bottom=.2,top=.88)
    for p,col,ls in [('P1',C['M'],'-'),('P2',C['V'],'--'),('P3',C['in'],'-.')]:
        x=sorted(r['solver_wall_seconds'] for r in allrows if r['problem']==p)
        a.step(x,np.arange(1,len(x)+1)/len(x),where='post',color=col,ls=ls,label=p)
    a.set(xscale='log',ylim=(0,1.03),title='每题 500 次完整求解；含各自在线评价，含共享主机影响')
    clean(a,'求解时间 / s（对数刻度）','不超过该时间的样本比例');a.legend(loc='lower right');save(fig,'fig-runtime')
    ds=source('dataset');fig,(a,b)=plt.subplots(2,1,figsize=(6.5,4.8 if os.environ.get('PAPER_LAYOUT') == '1' else 5.8));fig.subplots_adjust(left=.15,right=.96,bottom=.11,top=.94,hspace=.55)
    a.scatter([x['ops'] for x in ds],[x['tensor_bytes']/2**20 for x in ds],color=C['M'],s=20,alpha=.65)
    a.set(xscale='log',yscale='log',title='(a) 100 张原始图：规模与张量体积');clean(a,'非 COPY 操作数（对数）','张量大小总和 / MiB（对数）')
    ratios=sorted(x['matrix_cycles']/max(1,x['matrix_cycles']+x['vector_cycles']) for x in ds)
    b.plot(range(1,101),ratios,color=C['M']);b.fill_between(range(1,101),ratios,color=C['pale'])
    b.set(ylim=(0,1),title='(b) 计算工作在矩阵与向量 Pipe 间的分布');clean(b,'按矩阵工作占比排列的图序号','M 工作 / (M + V 工作)');save(fig,'fig-dataset')
    audit=source('p2-audit')['core_comparison'];fig,a=plt.subplots(figsize=(6.5,3.8));fig.subplots_adjust(left=.14,right=.96,bottom=.18,top=.88)
    lower=[audit[str(k)]['new_mean_B_over_M'] for k in ks];upper=[audit[str(k)]['relaxation_ceiling_mean_B_over_LB'] for k in ks]
    a.plot(ks,lower,'s-',color=C['M'],label='可行方案 mean(B/U)');a.plot(ks,upper,'o--',color=C['gray'],label='必要界 mean(B/L)')
    a.fill_between(ks,lower,upper,color=C['pale']);a.set(xticks=ks,title='同一优化域：L ≤ OPT ≤ U；阴影并非保证可实现的收益')
    clean(a,'Core数量 K','平均单核基准 / 周期');a.legend(loc='upper left');save(fig,'fig-bound-gap')

def main():
    FIG.mkdir(exist_ok=True);r=rows();p1=source('p1-026-k5');p2=source('p2-019-k5');p3=source('p3-021-k3')
    if os.environ.get("PAPER_LAYOUT") != "1": partition_story(p1)
    for key,label in [('old','父方案'),('new','分叉援助')]:
        timeline(p1[key]['result'],'fig-p1-overlap-'+key,'case_026 / 5 核 · '+label,xmax=44114)
    for key,label in [('control','完整主算法'),('c04','C04 降搬运候选')]:
        timeline(p2[key]['result'],'fig-p2-counterexample-'+key,'case_019 / 5 核 · '+label,xmax=28514)
    for key,label in ([] if os.environ.get('PAPER_LAYOUT') == '1' else [('no_l2','无 L2'),('cache','只读 Cache')]):
        timeline(p3[key],'fig-cache-timeline-'+key,'case_021 / 3 核 · 同计划 '+label,xmax=2140863)
    stat_figures(r)
    print('Rendered source-bound figures; no evaluator calls.')

if __name__=='__main__':main()
