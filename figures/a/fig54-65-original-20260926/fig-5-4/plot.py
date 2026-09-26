"""User-authorized local layout repair of farmer fig5-4 v3.
Read the five already-audited CSVs; run no solver or teammate script.
Run from any directory: python plot.py
"""
from pathlib import Path
import csv,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from PIL import Image

R=Path(__file__).resolve().parent
def rows(n):
 with (R/n).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
events=rows('events.csv');trade=rows('tradeoff.csv');results={r['variant']:r for r in rows('results.csv')};bb={r['variant']:r for r in rows('bytes.csv')};markers=rows('markers.csv')
assert len(events)==67385 and len(trade)==500
ms={v:int(r['makespan']) for v,r in results.items()}
colors={'PIPE_MTE2':'#2E86AB','PIPE_MTE3':'#5DA7CC','PIPE_V':'#E67E22','PIPE_M':'#C0392B'}
pipes=['PIPE_MTE2','PIPE_MTE3','PIPE_V','PIPE_M']
bases={('seed',1):12.7,('seed',2):8.7,('recovered',1):4.,('recovered',2):0.}
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':8,'axes.unicode_minus':False,'svg.fonttype':'path'})
fig=plt.figure(figsize=(6.5,9.7))
gs=fig.add_gridspec(5,1,height_ratios=[.65,3.3,2.05,2.55,.5],left=.15,right=.975,top=.96,bottom=.045,hspace=.85)
leg1=fig.add_subplot(gs[0]);ax1=fig.add_subplot(gs[1]);ax2=fig.add_subplot(gs[2]);ax3=fig.add_subplot(gs[3]);leg3=fig.add_subplot(gs[4])
for ax in (leg1,leg3):ax.set_axis_off()
leg1.set_title('面板 1｜S15 R05 @e6ae369：case003 / 2 核配对时间线\nseed=旧初解；rec=recovered=R05 恢复候选',loc='left',fontsize=8,pad=4)
handles=[Patch(color=colors[p],label=p.replace('PIPE_','')+(' 搬入' if p=='PIPE_MTE2' else ' 搬出' if p=='PIPE_MTE3' else ' 计算' if p=='PIPE_V' else '')) for p in pipes]
handles += [Patch(color='#BDC3C7',alpha=.35,label='task（SUBGRAPH）背景'),Line2D([0],[0],color='#C0392B',ls='--',label='端点=各自 E0 makespan')]
l1=leg1.legend(handles=handles,loc='center',ncol=3,frameon=False,fontsize=7.5)
groups={(v,c,p):[] for v,c in bases for p in pipes+['SUBGRAPH']}
for e in events:
 v=e['variant'];c=int(e['core']);s=int(e['start']);end=int(e['end']);assert 0<=s<=end<=ms[v]
 groups[v,c,e['pipe']].append((s,end-s))
ticks=[];labels=[];rendered=[]
for (v,c),base in bases.items():
 ax1.broken_barh(groups[v,c,'SUBGRAPH'],(base-.45,3.9),color='#BDC3C7',alpha=.35,linewidth=0,zorder=1)
 for j,p in enumerate(reversed(pipes)):
  segs=groups[v,c,p];ax1.broken_barh(segs,(base+j-.35,.7),color=colors[p],linewidth=0,zorder=3)
  ticks.append(base+j);labels.append(p.replace('PIPE_',''))
 ax1.text(-.10,base+1.5,('seed' if v=='seed' else 'rec')+'\n核'+str(c),transform=ax1.get_yaxis_transform(),ha='right',va='center',fontsize=7.5)
 ax1.axhline(base+3.65,color='#D5D8DC',lw=.5,zorder=0)
for v in ms:
 bs=[b for (vv,c),b in bases.items() if vv==v]
 ax1.plot([ms[v]]*2,[min(bs)-.45,max(bs)+3.45],color='#C0392B',ls='--',lw=1)
ax1.set(yticks=ticks,yticklabels=labels,xlim=(0,max(ms.values())*1.06),ylim=(-.65,16.4),xlabel='时间（cycles，绝对时间）');ax1.tick_params(labelsize=7.5)
ax2.set_title('面板 2｜S15 @e6ae369：新增 COPY −22.57%；总 COPY −18.01%\nMakespan 反升 +2.56%（248,166 → 254,508 cycles）',loc='left',fontsize=8,pad=6)
for j,(field,col,label) in enumerate([('base','#5DA7CC','基础 COPY'),('extra','#E67E22','新增 COPY'),('total','#1A5276','scheduled 合计')]):
 vals=[int(bb[v][field]) for v in ['seed','recovered']];xs=[i+(j-1)*.24 for i in [0,1]]
 ax2.bar(xs,[n/1e6 for n in vals],width=.24,color=col,label=label)
 for x,n in zip(xs,vals):ax2.text(x,n/1e6+.12,f'{n:,}',ha='center',fontsize=7.5)
ax2.set(xticks=[0,1],xticklabels=['seed（旧初解）','recovered（恢复候选）'],ylim=(0,9.4),ylabel='搬运量（10^6 B）');l2=ax2.legend(loc='upper center',ncol=3,fontsize=7.5,frameon=False)
styles={'both_down':('#27AE60','o','同降（55 格）'),'mk_down_ddr_up':('#E67E22','s','Makespan 降但 DDR 升（199 格）'),'mk_down_ddr_same':('#2980B9','D','Makespan 降且 DDR 不变（14 格）'),'unchanged':('#BDC3C7','.','两项不变（232 格）')}
for cat,(col,mk,lab) in styles.items():
 pts=[r for r in trade if r['category']==cat];ax3.scatter([int(r['delta_cycles']) for r in pts],[int(r['delta_bytes'])/1e6 for r in pts],s=8,color=col,marker=mk,alpha=.75,label=lab,linewidths=0)
ax3.axhline(0,color='#7F8C8D',lw=.7);ax3.axvline(0,color='#7F8C8D',lw=.7)
ax3.set_title('面板 3｜S16 @70f2e8bd：全量 500 格（2794ceba→c665）\n周期与额外 DDR 的取舍（绝对量）',loc='left',fontsize=8,pad=6)
ax3.set(xlabel='ΔMakespan = 新−旧（cycles，负=改善）',ylabel='Δ额外 DDR（10^6 B，正=退化）')
h,l=ax3.get_legend_handles_labels();l3=leg3.legend(h,l,loc='center',ncol=2,fontsize=7.5,frameon=False,markerscale=1.4)
leg1.set_position([.15,.89,.825,.055]);ax1.set_position([.15,.62,.825,.25]);ax2.set_position([.15,.38,.825,.155]);ax3.set_position([.15,.12,.825,.18]);leg3.set_position([.15,.025,.825,.04])
fig.canvas.draw();rend=fig.canvas.get_renderer()
b1=l1.get_window_extent(rend);bdata=ax1.get_window_extent(rend);b3=l3.get_window_extent(rend);bx=ax3.xaxis.label.get_window_extent(rend)
assert b1.y0>bdata.y1 and b3.y1<bx.y0
proof={'top_legend_to_data_gap_px':b1.y0-bdata.y1,'bottom_xlabel_to_legend_gap_px':bx.y0-b3.y1,'events':len(events),'scatter_rows':len(trade),'dpi':300,'matplotlib':matplotlib.__version__,'teammate_scripts_executed':False}
fig.savefig(R/'figure.svg');fig.savefig(R/'figure.png',dpi=300)
im=Image.open(R/'figure.png');im.resize((624,round(im.height*624/im.width)),Image.Resampling.LANCZOS).save(R/'preview-insert-width.png')
(R/'layout-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(proof)
