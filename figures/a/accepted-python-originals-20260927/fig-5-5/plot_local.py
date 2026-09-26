"""Plot verified c665 data; no experiment code."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from PIL import Image
p=Path(__file__).resolve().parent;r=list(csv.DictReader((p/'metrics.csv').open(encoding='utf-8')));s=list(csv.DictReader((p/'summary.csv').open(encoding='utf-8')))
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':9,'axes.unicode_minus':False,'svg.hashsalt':'fig55-local-source-v1'})
colors=['#286a96','#b34e32','#33846c','#84559b','#866323'];markers=['o','s','^','D','x'];styles=['-','--','-.',':',(0,(5,1,1,1))]
fig,ax=plt.subplots(2,1,figsize=(6.5,8.3));fig.subplots_adjust(left=.16,right=.96,top=.87,bottom=.33,hspace=.6)
for k in range(1,6):
 g=[x for x in r if int(x['cores'])==k];v=np.array([float(x['solver_wall']) for x in g]);y=[int(x['makespan']) for x in g]
 ax[0].scatter(v,y,color=colors[k-1],marker=markers[k-1],s=20,alpha=.6,linewidths=.5,label=f'{k} 核')
 x=np.sort(v);ax[1].step(x,np.arange(1,101)/100,where='post',color=colors[k-1],ls=styles[k-1],lw=1.4)
 ax[1].plot(x[::10],np.arange(1,101)[::10]/100,ls='none',marker=markers[k-1],ms=3,color=colors[k-1])
ax[0].set(xscale='log',yscale='log',xlabel='完整求解墙钟（s，对数轴）',ylabel='官方 Makespan（cycles，对数轴）');ax[0].set_title('(a) 500 格同次运行的质量与耗时',loc='left',fontsize=10,weight='bold')
ax[1].set(xscale='log',xlabel='完整求解墙钟（s，对数轴）',ylabel='累计比例',ylim=(0,1.03),yticks=[0,.25,.5,.75,1],yticklabels=['0%','25%','50%','75%','100%']);ax[1].set_title('(b) 分核经验累积分布（每组 100 用例）',loc='left',fontsize=10,weight='bold')
for a in ax:
 a.spines[['top','right']].set_visible(False);a.grid(axis='y',which='major',color='#ddd',lw=.6);a.xaxis.set_minor_locator(NullLocator());a.yaxis.set_minor_locator(NullLocator());a.tick_params(labelsize=8)
fig.text(.16,.973,'图 5-5｜P2 c665 质量、求解耗时与尾部延迟',fontsize=11,weight='bold')
fig.legend(*ax[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.942),ncol=5,frameon=False,fontsize=8.5)
tax=fig.add_axes([.16,.12,.8,.105]);tax.axis('off');table=tax.table(cellText=[[x['cores'],x['n'],f"{float(x['median']):.3f}",f"{float(x['p95']):.3f}",f"{float(x['max']):.3f}"] for x in s],colLabels=['核数','n','Median / s','P95 / s','Max / s'],cellLoc='center',loc='center');table.auto_set_font_size(False);table.set_fontsize(8);table.scale(1,1.2)
for (i,j),cell in table.get_celld().items():
 cell.set_edgecolor('#ddd');cell.set_linewidth(.4)
 if i==0:cell.set_facecolor('#edf1f4')
fig.text(.16,.072,'macOS arm64 / Python 3.12.13；worker = 1；CPU 型号未记录。',fontsize=8)
fig.text(.16,.052,'墙钟含在线 E2，独立 E0 另列；P95 线性插值；每格单次观测。',fontsize=8)
fig.text(.16,.032,'未控制 OS 缓存；不称严格冷启动，也不推断跨平台速度或 Pareto 前沿。',fontsize=8)
for ext in ['svg','png','pdf']:fig.savefig(p/('fig55_p2_quality_cost.'+ext),dpi=300)
with Image.open(p/'fig55_p2_quality_cost.png') as im:im.resize((624,797),Image.Resampling.LANCZOS).save(p/'preview-insert-width.png')
