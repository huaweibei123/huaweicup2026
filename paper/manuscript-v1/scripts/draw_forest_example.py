#!/usr/bin/env python3
"""Exact illustrative arithmetic from chapter 6; not evaluator measurements."""
from pathlib import Path
import json
import numpy as np
from figure_style import plt, save, C
P=Path(__file__).resolve().parents[1]
spec={'kind':'mathematical illustration, not an official case','unit':'KiB','A':{'peak':8,'result':2},'B':{'peak':7,'result':5},'parent_result':3,'orders':[{'labels':['A','B','分配父操作\n的输出'],'retained':[0,2,7],'processing':[8,7,0],'parent':[0,0,3]},{'labels':['B','A','分配父操作\n的输出'],'retained':[0,5,7],'processing':[7,8,0],'parent':[0,0,3]}]}
(P/'data/forest-order-example.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(6.5,3.7),sharey=True)
fig.subplots_adjust(left=.13,right=.985,bottom=.24,top=.82,wspace=.16)
colors=['#D4DCE4','#8877A8','#76BDB6']
for ax,order in zip(axes,spec['orders']):
 x=np.arange(3);bottom=np.zeros(3)
 for key,col,label in zip(['retained','processing','parent'],colors,['已保留的结果','当前子树的最大占用量','父操作新分配的输出']):
  v=np.array(order[key]);ax.bar(x,v,bottom=bottom,color=col,width=.58,label=label,edgecolor='white',linewidth=.7);bottom+=v
 for j,y in enumerate(bottom):ax.text(j,y+.25,f'{y:g}',ha='center',va='bottom',fontsize=12)
 ax.set_xticks(x,order['labels']);ax.set_ylim(0,14.5);ax.set_yticks([0,5,10]);ax.grid(axis='y',alpha=.65);ax.set_axisbelow(True)
 ax.tick_params(axis='x',length=0,pad=7);ax.set_xlabel('处理步骤',labelpad=8)
axes[0].set_ylabel('内部计算结果占用 / KiB')
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,.995),ncol=3,fontsize=9.5,handlelength=1.3,columnspacing=1.25)
save(fig,'fig-forest-example',P/'figures/paper-v2')
