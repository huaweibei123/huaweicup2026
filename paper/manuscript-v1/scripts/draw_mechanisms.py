#!/usr/bin/env python3
"""Editable mechanism stories. Source JSON distinguishes real data and schematics."""
import json
from matplotlib.patches import Rectangle,FancyBboxPatch,FancyArrowPatch
import numpy as np
from figure_style import PAPER,C,PIPE,plt,save,clean
from draw_figures import source,FIG

def page(height):
    fig=plt.figure(figsize=(6.5,height));ax=fig.add_axes([0,0,1,1])
    ax.set(xlim=(0,6.5),ylim=(0,height));ax.axis('off');return fig,ax

def box(ax,x,y,w,h,text,edge=None,fill='white',ls='-',align='center'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.025,rounding_size=.04',fc=fill,ec=edge or C['gray'],lw=1,ls=ls))
    ax.text(x+w/2 if align=='center' else x+.12,y+h/2,text,ha=align,va='center',linespacing=1.4)

def arrow(ax,a,b,color=None,ls='-',rad=0):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,linewidth=1,
       color=color or C['gray'],linestyle=ls,connectionstyle=f'arc3,rad={rad}'))

def label(ax,x,y,text,**kw):ax.text(x,y,text,va='center',**kw)

def record(name,d):
    (FIG/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def progression():
    # Every row reuses the same original op IDs and core assignment.
    f,a=page(6.0)
    label(a,.2,5.78,'同一真实片段，逐问增加机器状态（语义示意）')
    rows=[('P1 · Task 边界独立编译','同核跨 Task 仍经 COPY 边界','核0：sg0 → sg5',True),
          ('P2 · 同核 Task 合并','t721 可留在核内；跨核 t723 仍需传输','核0：合并 Task',False),
          ('P3 · 只读 Cache','保留 P2；DDR COPY_IN 再查共享 Cache','核0：合并 Task + Cache',False)]
    for j,(title,desc,state,copy) in enumerate(rows):
        y=4.64-j*1.7
        label(a,.2,y+.59,title)
        box(a,.25,y-.14,1.23,.4,'ADD 720',C['V'],'#EEEAF4')
        box(a,4.88,y-.14,1.23,.4,'ADD 724',C['V'],'#EEEAF4')
        if copy:
            box(a,2.44,y-.14,1.58,.4,'DDR / COPY',C['out']);arrow(a,(1.52,y+.06),(2.39,y+.06),C['out']);arrow(a,(4.07,y+.06),(4.84,y+.06),C['out'])
        else:
            arrow(a,(1.52,y+.06),(4.84,y+.06),C['in']);label(a,3.23,y+.23,'t721 · 2 B · 核内驻留',ha='center')
        label(a,.25,y-.46,desc)
        label(a,.25,y-.75,state,color=C['M'])
    record('fig-progression',dict(type='official-rule schematic on real fragment',case='026',source_op=720,target_op=724,tensor=721,bytes=2,
        core=0,subgraphs=[0,5],rows=rows,claim='Same P1 example plan interpreted under changing semantics; not measured P2/P3 solver plan.'))
    save(f,'fig-progression')

def coherent():
    f,a=page(6.8);label(a,.2,6.52,'Coherent：结构负责提出方案，真实语义负责判定收益')
    box(a,2.1,5.76,2.3,.42,'原图 G + 核数 K + 配置',C['ink'])
    items=[('P1','组件 / 波次','分叉援助','秩与增广无环',C['M']),
           ('P2','日历 / gap','张量超图','固定锚点局部割',C['V']),
           ('P3','结构构造','归约森林','h − r 与候选下界',C['in'])]
    for j,(p,m1,m2,cert,color) in enumerate(items):
        x=.2+j*2.12
        arrow(a,(3.25,5.73),(x+.94,5.32),color)
        box(a,x,3.34,1.94,1.96,'',color)
        label(a,x+.12,5.03,p,color=color)
        box(a,x+.15,4.34,1.64,.38,m1,color,'#F6F7F9')
        box(a,x+.15,3.84,1.64,.38,m2,color,'#F6F7F9')
        label(a,x+.97,3.55,cert,ha='center')
        arrow(a,(x+.97,3.3),(3.25,2.95),color)
    box(a,1.32,2.48,3.87,.43,'完整计划 P = (切分，分核，每核次序)',C['ink'])
    arrow(a,(3.25,2.43),(3.25,2.19))
    box(a,.42,1.63,2.5,.5,'合法性 / 适用的必要界',C['gray'])
    box(a,3.5,1.63,2.5,.5,'完整执行语义评价',C['ink'])
    arrow(a,(3.25,2.19),(1.67,2.16));arrow(a,(2.97,1.88),(3.45,1.88))
    arrow(a,(4.75,1.6),(4.75,1.16))
    box(a,3.5,.58,2.5,.5,'接受改善或保留 incumbent',C['ink'],'#E7EBEF')
    label(a,.43,1.04,'代理：指导构造')
    label(a,.43,.66,'证书：只保证声明的性质')
    label(a,.43,.28,'结果：对应完整固定算法')
    record('fig-coherent',dict(type='implemented mechanism architecture',lanes=items,
      shared=['full plan','legality and conditional lower bounds','full evaluation','accept or retain'],
      caveat='Not a universal minimal sufficient state controller; mechanisms within a lane are alternatives subject to guards and budgets.'))
    save(f,'fig-coherent')

def state_meaning():
    f,a=page(4.3);label(a,.2,4.05,'同一当前分数，不能保证同一未来（定义示意）')
    for y,s in [(3.18,'P'),(2.27,'Q')]:
        box(a,.35,y-.2,.85,.4,s,C['M'])
        arrow(a,(1.25,y),(2.05,y));box(a,2.1,y-.2,1.65,.4,'当前观测 = m',C['gray'])
        arrow(a,(3.8,y),(4.4,y));label(a,4.1,y+.22,'动作 a',ha='center')
        box(a,4.45,y-.2,1.63,.4,'可能分离',C['out'])
    label(a,.35,1.65,'未来充分表示必须同时保持：')
    for x,t in [(.35,'能否执行 a'),(2.41,'如何更新 S'),(4.47,'当前观测 Φ')]:box(a,x,.86,1.7,.43,t,C['in'])
    label(a,.35,.32,'对全部有限动作词归纳；不把“分数相等”当作状态相等。')
    record('fig-state-meaning',dict(type='definition schematic, no measured numbers',conditions=['enabled actions','state update closure','observation closure']))
    save(f,'fig-state-meaning')

def residency():
    f,a=page(3.9);label(a,.2,3.64,'同一条依赖：保留驻留，还是付出跨核传输？')
    label(a,.2,3.18,'(a) 同核不同子图，P2 编译为同一 Task')
    box(a,.35,2.30,1.55,.44,'720 / 核0',C['V'],'#EEEAF4');box(a,4.60,2.30,1.55,.44,'724 / 核0',C['V'],'#EEEAF4')
    arrow(a,(1.95,2.52),(4.55,2.52),C['in']);label(a,3.25,2.78,'t721 · 2 B',ha='center')
    label(a,3.25,2.02,'容量与引用生命周期仍须检查',ha='center')
    label(a,.2,1.58,'(b) 跨核依赖，保留真实同步和搬运')
    box(a,.35,.72,1.55,.44,'722 / 核1',C['V'],'#EEEAF4');box(a,4.60,.72,1.55,.44,'724 / 核0',C['V'],'#EEEAF4')
    box(a,2.47,.72,1.56,.44,'DDR',C['out']);arrow(a,(1.95,.94),(2.42,.94),C['out']);arrow(a,(4.08,.94),(4.55,.94),C['out'])
    label(a,3.25,1.30,'t723 · 2 B',ha='center');label(a,3.25,.33,'COPY_OUT → 跨核释放 → COPY_IN',ha='center')
    record('fig-p2-transition',dict(type='official-rule schematic',case='026',original_edges=[dict(u=720,v=724,tensor=721,bytes=2),dict(u=722,v=724,tensor=723,bytes=2)],core_assignment='same P1 example; explanatory, not measured P2 output'))
    save(f,'fig-p2-transition')

def hypercut():
    f,a=page(4.8);label(a,.2,4.55,'超边按“触及的核心”计费，避免逐消费者重复计数')
    for j,(y,title,assignment) in enumerate([(3.6,'(a) 同一张量，两个消费者在核1',[0,1,1]),(1.55,'(b) 联合移动消费者，触核数从 2 降为 1',[0,0,0])]):
        label(a,.2,y+.39,title)
        for x,name,k in zip([.45,2.55,4.7],['产生者 u','消费者 v₁','消费者 v₂'],assignment):
            box(a,x,y-.52,1.32,.46,name,C['M'] if k==0 else C['in']);label(a,x+.66,y-.83,f'核{k}',ha='center')
        a.plot([1.11,1.11,5.36,5.36],[y-.02,y+.13,y+.13,y-.02],color=C['out'],lw=1.5)
        a.plot([3.21,3.21],[y+.13,y-.02],color=C['out'],lw=1.5)
        label(a,3.25,y-1.16,'λ = '+('2，变量代价 w' if j==0 else '1，变量代价 0'),ha='center')
    label(a,.2,.23,'结构示意；适用域内 C + Σ wₜ(λₜ − 1) 表示编译前 COPY 字节。')
    record('fig-hypercut',dict(type='symbolic hypergraph cost example',before=[0,1,1],after=[0,0,0],cost='C + sum w_t(lambda_t - 1)',caveat='not a Makespan or spill model'))
    save(f,'fig-hypercut')

def cache_story():
    d=source('p3-021-k3')['cache'];events=d['cache_events'];tid=1000000001
    chosen=[next(e for e in events if e['event']==ev and e['tensor_id']==tid) for ev in ('miss','insert','hit')]
    chosen.append(next(e for e in events if tid in e.get('evicted_tensor_ids',[])))
    f,a=page(5.05);label(a,.2,4.8,'case_021 / 3 核：一份 4096 B 数据的 Cache 生命周期')
    a.plot([.55,.55],[.7,4.14],color=C['gray'],lw=1.2)
    descriptions=['COPY_IN 发射时未命中；尚未插入', 'DDR COPY_IN 完成；此时插入 FIFO', '另一个核心读命中；FIFO 年龄不刷新', '插入 t1000000487，最老项被淘汰']
    for e,y,t,color in zip(chosen,[4.05,3.0,1.95,.9],descriptions,[C['out'],C['M'],C['in'],C['gray']]):
        a.scatter([.55],[y],s=80,color=color,zorder=3)
        label(a,.84,y+.16,f"{e['time']:,} cycle",color=color)
        label(a,.84,y-.19,t)
    label(a,.2,.23,'张量标识为编译后 ID；来自官方事件，不将请求时刻当作插入时刻。')
    record('fig-cache-story',dict(type='observed official cache events',case='021',cores=3,tensor_id=tid,cache_capacity_bytes=d['cache_capacity_bytes'],events=chosen))
    save(f,'fig-cache-story')

def forest():
    d=dict(type='proof example, not measured memory or time',unit='KiB',A=dict(h=8,r=2),B=dict(h=7,r=5),parent_output=3,
           stages=['开始','首树峰值','首树保留','次树峰值','两根保留','父输出分配','父结果'],
           AB=[0,8,2,9,7,10,3],BA=[0,7,5,13,7,10,3])
    f,(a,b)=plt.subplots(2,1,figsize=(6.5,6.1),gridspec_kw={'left':.14,'right':.97,'bottom':.11,'top':.95,'hspace':.53})
    a.axis('off');a.set(xlim=(0,6),ylim=(0,2))
    box(a,.05,.65,2.35,.73,'A: h = 8，r = 2\nh − r = 6',C['M'],'#F3F6F9')
    box(a,3.55,.65,2.35,.73,'B: h = 7，r = 5\nh − r = 2',C['in'],'#F3F8F7')
    arrow(a,(2.47,1),(3.48,1),C['M']);label(a,3,.31,'大 h − r 优先；父输出大小 = 3',ha='center')
    a.set_title('(a) 非交错处理、先分配父输出的证明示例',loc='left')
    b.plot(range(7),d['BA'],'o--',color=C['gray'],label='B → A：峰值 13')
    b.plot(range(7),d['AB'],'s-',color=C['M'],label='A → B：峰值 10')
    b.set(xticks=range(7),xticklabels=['起点','树1峰','留根1','树2峰','留两根','分配父','完成'],ylim=(0,15))
    b.axvline(5,color=C['out'],ls=':',lw=1);b.legend(loc='upper left')
    clean(b,'子树处理步骤（不是模拟时间）','内部前沿量 / KiB')
    b.set_title('(b) 相邻交换降低峰值；相同后续保持不变',loc='left')
    record('fig-forest-frontier',d);save(f,'fig-forest-frontier')

def policy():
    data=[('064',7029,6899,6981,6877),('068',131631,98913,116345,97971),('088',97305,66729,85789,66224)]
    f,axs=plt.subplots(3,1,figsize=(6.5,8.1));f.subplots_adjust(left=.16,right=.95,bottom=.08,top=.95,hspace=.70)
    for a,(case,m2,n2,m3,n3) in zip(axs,data):
        mx=max(m2,m3)*1.08/1000
        a.plot([0,mx],[0,mx*m3/m2],ls=':',color=C['gray'],label='原方案等 G 线')
        a.scatter([m2/1000],[m3/1000],s=45,marker='o',color=C['gray'],label='原方案')
        a.scatter([n2/1000],[n3/1000],s=45,marker='s',color=C['M'],label='候选')
        arrow(a,(m2/1000,m3/1000),(n2/1000,n3/1000),C['M'])
        a.set(xlim=(0,mx),ylim=(0,mx),title=f'case_{case} / 5 核：M₃ {m3:,} → {n3:,} cycle')
        clean(a,'无 L2 完工时间 M₂ / 千 cycle','Cache 完工时间 M₃ / 千 cycle')
        a.legend(loc='upper left',ncol=1)
    record('fig-policy-tradeoff',dict(type='frozen R9F policy counterexamples',values=data,source='chapters/06-p3.md fixed R9F audit',caveat='Not mixed into Forest full500'))
    save(f,'fig-policy-tradeoff')

def main():
    FIG.mkdir(exist_ok=True)
    progression();coherent();state_meaning();residency();hypercut();cache_story();forest();policy()
    print('Rendered 8 mechanism figures with editable semantic JSON and SVG.')

if __name__=='__main__':main()
