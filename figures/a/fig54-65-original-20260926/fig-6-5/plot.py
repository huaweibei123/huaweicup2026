"""Workbench controlled layout repair; original farmer 18a0d9ff CSV bytes unchanged.
Run: python plot.py. Reads only CSV beside this file; no solver or uploaded code.
"""
from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image
P=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((P/n).open(encoding='utf-8')))
a=read('prefix_ops.csv');c=read('critical_path_ops.csv');e=read('evidence_points.csv')
ev={(x['object'],x['evidence_type']):int(x['cycles']) for x in e}
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':8,'axes.unicode_minus':False,'svg.hashsalt':'fig65-local-v1'})
colors={'COPY_IN':'#2E86AB','COPY_OUT':'#5DA7CC','CONV':'#E67E22','RELU':'#D35400','ADD':'#F5B041'}
fig=plt.figure(figsize=(6.5,8.8));ax=fig.add_axes([.20,.59,.75,.27]);bx=fig.add_axes([.24,.115,.71,.30])
fig.text(.04,.97,'A  冷读前缀与已核关键路径',fontsize=10,weight='bold')
fig.text(.04,.943,'case044 / 5 核 · 固定前缀机制单格 · 官方结果 38,024 cycles',fontsize=8)
for j in range(1,5):
 rows=[r for r in a if r['prefix_id']==f'prefix{j}'];y=5-j
 ax.broken_barh([(int(r['start']),int(r['duration'])) for r in rows],(y-.27,.54),facecolors=colors['COPY_IN'],edgecolors='white',linewidth=.15)
 for key,col,style in [('conditional_shared_bound','#7D3C98','--'),('official_measured','#C0392B',':')]:
  x=ev[(f'prefix{j}',key)];ax.plot([x,x],[y-.38,y+.38],color=col,ls=style,lw=1)
for op,col in colors.items():
 ax.broken_barh([(int(r['start']),int(r['duration'])) for r in c if r['op']==op],(-.27,.54),facecolors=col,linewidth=0)
ax.annotate('',xy=(16847,.4),xytext=(16847,2.6),arrowprops={'arrowstyle':'->','linestyle':'--','color':'#C0392B','linewidth':.9})
ax.axvline(38024,color='#C0392B',ls=':',lw=1)
ax.set(yticks=[4,3,2,1,0],yticklabels=['前缀1 / 核2','前缀2 / 核3','前缀3 / 核4','前缀4 / 核5','关键路径\n366 个操作'],xlim=(0,40000),ylim=(-.55,4.6),xlabel='绝对时间（cycles）');ax.set_xticks([0,10000,20000,30000,40000]);ax.tick_params(labelsize=8)
fig.legend(handles=[Patch(facecolor=col,label=op) for op,col in colors.items()],loc='upper left',bbox_to_anchor=(.04,.922),ncol=5,frameon=False,fontsize=7.4,handlelength=1,columnspacing=1)
fig.legend(handles=[Line2D([0],[0],color='#7D3C98',ls='--',label='条件模型完成下界'),Line2D([0],[0],color='#C0392B',ls=':',label='官方完成事件'),Line2D([0],[0],color='#C0392B',ls='--',marker='>',label='前缀2 → 关键路径')],loc='upper left',bbox_to_anchor=(.04,.89),ncol=3,frameon=False,fontsize=7.4,handlelength=1.5,columnspacing=1)
fig.text(.04,.508,'B  三类证据值（同一对象，非三种算法的实测成绩）',fontsize=9,weight='bold')
styles=[('exclusive_optimistic','#666666','o','乐观独占值（模型）'),('conditional_shared_bound','#7D3C98','s','条件共享界（研究界）'),('official_measured','#C0392B','D','官方实测（E0）')]
fig.legend(handles=[Line2D([0],[0],marker=m,color=col,ls='',label=lab) for _,col,m,lab in styles],loc='upper left',bbox_to_anchor=(.04,.482),ncol=3,frameon=False,fontsize=7.5,handletextpad=.3,columnspacing=1)
labels=[]
for j,obj in enumerate(['prefix1','prefix2','prefix3','prefix4','overall']):
 y=4-j;xs=[ev[(obj,k)] for k,_,_,_ in styles];bx.plot(xs,[y]*3,color='#BDC3C7',ls=':',lw=.8)
 for idx,(k,col,m,_) in enumerate(styles):
  v=ev[(obj,k)];bx.scatter([v],[y],c=col,marker=m,s=25,zorder=3)
  offset=((-12,22) if obj=='overall' else (-5,9)) if idx==0 else ((12,9) if idx==1 else (2,-11))
  bx.annotate(f'{v:,}',(v,y),xytext=offset,textcoords='offset points',ha='center',color=col,fontsize=7.5)
 labels.append(f'前缀{j+1}\nW={xs[0]:,}' if j<4 else '整体\nmakespan')
bx.set_xscale('log');bx.set(xlim=(95,65000),ylim=(-.7,4.8),yticks=[4,3,2,1,0],yticklabels=labels,xlabel='周期（cycles，对数刻度）');bx.tick_params(labelsize=8)
for axes in [ax,bx]:
 axes.spines[['top','right']].set_visible(False);axes.grid(axis='x',alpha=.16);axes.set_axisbelow(True)
fig.text(.04,.046,'条件界仅适用于固定前缀 / 归核 / Task；不是浮点实现剪枝证书。',fontsize=7.5)
fig.text(.04,.023,'与界的差不代表可实现提升；路径为事后分解，不能预测新方案。',fontsize=7.5)
fig.canvas.draw();renderer=fig.canvas.get_renderer();bad=[]
for text in fig.findobj(matplotlib.text.Text):
 if text.get_visible() and text.get_text():
  box=text.get_window_extent(renderer)
  if box.width and box.height and (box.x0<0 or box.y0<0 or box.x1>fig.bbox.width or box.y1>fig.bbox.height):bad.append(text.get_text())
# Ignore unused off-axis locator labels; visible custom labels verified by rendered preview.
proof={'canvas_px_100dpi':[650,880],'out_of_canvas_text':bad,'prefix_bars':len(a),'path_bars':len(c),'evidence_points':len(e),'source':'fixed farmer CSV, unchanged','matplotlib':matplotlib.__version__}
(P/'layout-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
fig.savefig(P/'figure.svg',metadata={'Date':None});fig.savefig(P/'figure.png',dpi=300)
im=Image.open(P/'figure.png');im.resize((624,round(im.height*624/im.width)),Image.Resampling.LANCZOS).save(P/'preview-insert-width.png');print(proof)

