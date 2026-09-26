"""Controlled workbench layout, derived from verified farmer CSV, no solver."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image
P=Path(__file__).resolve().parent
rows=list(csv.DictReader((P/'aligned_ops.csv').open(encoding='utf-8')))
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':8,'axes.unicode_minus':False,'svg.hashsalt':'fig66-local-layout-v1'})
pipes=['PIPE_MTE2','PIPE_M','PIPE_V','PIPE_MTE3'];colors=['#23759b','#74519a','#d17929','#56a3b5'];pc=dict(zip(pipes,colors));short=['MTE2','M','V','MTE3']
fig=plt.figure(figsize=(6.5,10.5));axes=[fig.add_axes([.14,y,.81,h]) for y,h in [(.73,.18),(.475,.18),(.255,.12),(.055,.12)]]
def decorate(ax,keys):
 ax.set_yticks(range(len(keys)));ax.set_yticklabels([f'核{c} {p[5:]}' for c,p in keys],fontsize=7.5);ax.set_ylim(len(keys)-.5,-.5)
 ax.tick_params(axis='x',labelsize=7.5);ax.ticklabel_format(axis='x',style='plain',useOffset=False)
 # Absolute cycles are shared and stated in the figure footer.
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',color='#dddddd',lw=.45);ax.set_axisbelow(True)
for i,v in enumerate(['p2','p3']):
 ax=axes[i];keys=[(c,p) for c in [1,2,3] for p in pipes]
 for y,(c,p) in enumerate(keys):
  rr=[r for r in rows if int(r['core'])==c and r['pipe']==p]
  ax.broken_barh([(int(r[v+'_start']),int(r[v+'_end'])-int(r[v+'_start'])) for r in rr],(y-.36,.72),facecolors=pc[p],linewidth=0)
 for y in [3.5,7.5]:ax.axhline(y,color='#cccccc',lw=.5)
 ax.axvline([2140720,2140863][i],ls=':',color='#aa3333',lw=.9);ax.set_xlim(0,2180000);decorate(ax,keys)
fig.text(.14,.957,'(a) P2 无 L2｜Makespan = 2,140,720 cycles',fontsize=9,weight='bold')
fig.legend([Patch(color=pc[p]) for p in pipes],['MTE2 搬入','M 矩阵乘','V 加法','MTE3 搬出'],loc='upper left',bbox_to_anchor=(.13,.947),ncol=4,frameon=False,fontsize=7.5,handlelength=1,columnspacing=1)
fig.text(.14,.688,'(b) P3 只读 Cache｜Makespan = 2,140,863 cycles',fontsize=9,weight='bold')
fig.text(.14,.667,'比 P2 慢 143 cycles；CacheGain = 0.99993（保留负收益）',fontsize=8,color='#923c34')
for ax,core,window in [(axes[2],3,(4900,7000)),(axes[3],1,(443050,443250))]:
 keys=[(core,p) for p in pipes]
 for y,(c,p) in enumerate(keys):
  for r in rows:
   if int(r['core'])!=c or r['pipe']!=p:continue
   for v,offset,col in [('p2',-.38,'#77838e'),('p3',.04,'#db812d')]:
    start,end=int(r[v+'_start']),int(r[v+'_end'])
    if end<=window[0] or start>=window[1]:continue
    if v=='p3' and r['op_id']=='1000004905':col='#25925d'
    ax.broken_barh([(start,end-start)],(y+offset,.34),facecolors=col,linewidth=.25,edgecolors='white')
 ax.set_xlim(*window);decorate(ax,keys)
fig.text(.14,.439,'(c) 窗口 1｜核 3，4,900–7,000 cycles',fontsize=9,weight='bold')
fig.text(.14,.422,'op 1000004905：207 → 17 cycles（P3 命中）',fontsize=8)
fig.text(.14,.406,'op 1000006255：起点 5,163 → 4,973；DDR 309 → 308 cycles',fontsize=8)
fig.text(.14,.39,'两窗口均为：行上半 P2（灰）／下半 P3（橙）；绿色为标注的命中事件',fontsize=7.5)
axes[2].annotate('4905',xy=(4973,.2),xytext=(5230,-.15),fontsize=7,color='#156943',arrowprops=dict(arrowstyle='->',color='#156943',lw=.7))
fig.text(.14,.221,'(d) 窗口 2｜核 1，443,050–443,250 cycles',fontsize=9,weight='bold')
fig.text(.14,.204,'op 1000006089：同起点 443,077；DDR 69 → 138 cycles',fontsize=8)
fig.text(.14,.188,'全表同起点变慢的 COPY_IN 共 3 笔；局部窗口两端事件不平移',fontsize=7.5)
fig.text(.14,.012,'横轴：绝对时间（cycles）；同计划 case 021 / 3 核。仅事件观察，不作完整因果认定。',fontsize=7.5,color='#555555')
fig.savefig(P/'figure.svg');fig.savefig(P/'figure.png',dpi=300)
with Image.open(P/'figure.png') as im:im.resize((624,1008),Image.Resampling.LANCZOS).save(P/'preview-insert-width.png')
print('Rendered 17,762 full timeline events and two absolute windows; local layout only.')
