"""Version-aligned P1 figure from fixed 834d8c9 results. Layout adapted from workbench local-layout-v1 for LYX figure 4-5. No solver/evaluator calls."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from PIL import Image
p=Path(__file__).resolve().parent;rs=list(csv.DictReader((p/'metrics.csv').open(encoding='utf-8')))
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':9,'axes.unicode_minus':False,'svg.hashsalt':'fig45-834-aligned-v1'})
cs=['#286a96','#b34e32','#33846c','#84559b','#866323'];marks=['o','s','^','D','x']
fig,ax=plt.subplots(3,1,figsize=(6.5,9.6));fig.subplots_adjust(left=.15,right=.96,top=.885,bottom=.11,hspace=.53)
for k in range(1,6):
 rr=[r for r in rs if int(r['cores'])==k]
 ax[0].scatter([float(r['solver_wall']) for r in rr],[int(r['makespan']) for r in rr],s=19,alpha=.6,c=cs[k-1],marker=marks[k-1],label=f'{k} 核',linewidths=.5)
ax[0].set(xscale='log',yscale='log',xlabel='完整求解墙钟（s，对数轴）',ylabel='官方 Makespan（cycles，对数轴）');title_a=ax[0].set_title('(a) 方案质量与求解耗时',loc='left',fontsize=10,weight='bold')
core_legend=fig.legend(*ax[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.95),ncol=5,frameon=False,fontsize=8.5)
vals=[[float(r['solver_wall']) for r in rs if int(r['cores'])==k] for k in range(1,6)]
boxes=ax[1].boxplot(vals,positions=range(1,6),patch_artist=True,widths=.55,showfliers=True,medianprops={'color':'black','lw':1.2},flierprops={'marker':'.','markersize':3,'alpha':.55})
for box,c in zip(boxes['boxes'],cs):box.set(facecolor=c,alpha=.45)
ax[1].set(yscale='log',xlabel='核数',ylabel='求解墙钟（s，对数轴）',xticks=range(1,6));ax[1].set_title('(b) 每核数 100 用例的耗时分布（保留离群点）',loc='left',fontsize=10,weight='bold')
for field,label,c,m,ls in [('ddr_bytes','总 DDR','#286a96','o','-'),('extra_ddr','额外 DDR','#b34e32','s','--')]:
 means=[np.mean([int(r[field]) for r in rs if int(r['cores'])==k])/2**20 for k in range(1,6)];ax[2].plot(range(1,6),means,color=c,marker=m,ls=ls,label=label,lw=1.7)
ax[2].set(xlabel='核数',ylabel='逐例平均搬运量（MiB）',xticks=range(1,6));ax[2].set_title('(c) 搬运代价（1 MiB = 2^20 B）',loc='left',fontsize=10,weight='bold');ax[2].legend(frameon=False,loc='upper right',fontsize=8.5)
for a in ax:
 a.spines[['top','right']].set_visible(False);a.grid(axis='y',which='major',color='#dddddd',lw=.6);a.xaxis.set_minor_locator(NullLocator());a.yaxis.set_minor_locator(NullLocator());a.tick_params(labelsize=8)
main_title=fig.text(.15,.973,'图 4-5｜P1 分支细化方案质量、求解耗时与搬运代价',fontsize=11,weight='bold')
fig.text(.15,.047,'macOS arm64 / Python 3.12.13；批次并发 4；CPU 型号未记录。',fontsize=8)
fig.text(.15,.03,'求解墙钟包含在线 E1，独立 E0 另列；未清 OS 缓存，不称严格冷启动。',fontsize=8)
fig.text(.15,.013,'跨用例散点仅描述分布，不构成 Pareto 前沿；每格为单次观测。',fontsize=8)
assert len(rs) == 500 and len({(r['case'], r['cores']) for r in rs}) == 500
assert len(ax[0].collections) == 5
for k, collection in enumerate(ax[0].collections, 1):
    expected = [[float(r['solver_wall']), int(r['makespan'])] for r in rs if int(r['cores']) == k]
    np.testing.assert_allclose(collection.get_offsets(), expected, rtol=0, atol=0)
for line, field in zip(ax[2].lines, ['ddr_bytes', 'extra_ddr']):
    expected = [np.mean([int(r[field]) for r in rs if int(r['cores']) == k])/2**20 for k in range(1,6)]
    np.testing.assert_allclose(line.get_ydata(), expected, rtol=0, atol=0)
fig.canvas.draw()
renderer=fig.canvas.get_renderer()
title_box=title_a.get_window_extent(renderer)
legend_box=core_legend.get_window_extent(renderer)
main_box=main_title.get_window_extent(renderer)
gap_pt=(legend_box.y0-title_box.y1)*72/fig.dpi
assert gap_pt >= 6, f'Panel (a) title / legend gap too small: {gap_pt:.2f} pt'
assert not main_box.overlaps(legend_box)
proof={'panel_a_title_legend_gap_pt':gap_pt,'main_title_legend_overlap':False,
       'metrics_sha256':hashlib.sha256((p/'metrics.csv').read_bytes()).hexdigest(),
       'change':'Separate panel (a) title and core legend with dedicated vertical spacing; data unchanged.'}
(p/'layout-verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
for ext in ['svg','png','pdf']:fig.savefig(p/('fig45_p1_quality_cost.'+ext),dpi=300)
with Image.open(p/'fig45_p1_quality_cost.png') as im:im.resize((624,922),Image.Resampling.LANCZOS).save(p/'preview-insert-width.png')
print('Three panels rendered from all 500 verified rows.')
