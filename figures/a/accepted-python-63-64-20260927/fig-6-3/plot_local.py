"""Render the two configuration curves from an already prepared 500-pair table.

No solver, evaluator, network request, or approval state is changed here.
"""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def draw(folder):
    with (folder/'summary.csv').open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=5 or {int(r['cores']) for r in rows}!={1,2,3,4,5} or any(int(r['n'])!=100 for r in rows):
        raise ValueError('Five complete groups of 100 paired observations are required')
    rows.sort(key=lambda r:int(r['cores']))
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':9,'axes.unicode_minus':False,'svg.hashsalt':'fig63-local-complete-v1'})
    fig,ax=plt.subplots(figsize=(160/25.4,130/25.4))
    fig.subplots_adjust(left=.15,right=.96,top=.87,bottom=.42)
    x=[int(r['cores']) for r in rows]
    ax.plot(x,[float(r['mean_no_cache_speedup']) for r in rows],'--s',color='#b34e32',markerfacecolor='white',lw=1.5,ms=4,label='同计划无 L2')
    ax.plot(x,[float(r['mean_cache_speedup']) for r in rows],'-o',color='#214b9a',lw=1.7,ms=4,label='同计划只读 Cache')
    ax.set(xlabel='NPU 核心数',ylabel='平均加速比（倍）',xticks=x,xlim=(.85,5.15))
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',color='#e6eaf0',lw=.6)
    ax.legend(frameon=False,fontsize=8,loc='upper left')
    fig.text(.15,.955,'图 6-3｜同计划无 L2 与只读 Cache 性能对比',fontsize=10,weight='bold')
    tax=fig.add_axes([.15,.135,.81,.17]);tax.axis('off')
    table=tax.table(cellText=[[r['cores'],'100',f"{float(r['mean_no_cache_speedup']):.6f}",f"{float(r['mean_cache_speedup']):.6f}"] for r in rows],colLabels=['核数','配对数','无 L2 / 倍','只读 Cache / 倍'],cellLoc='center',loc='center')
    table.auto_set_font_size(False);table.set_fontsize(7.5);table.scale(1,1.08)
    for (i,j),c in table.get_celld().items():
        c.set_edgecolor('#ddd');c.set_linewidth(.4)
        if i==0:c.set_facecolor('#edf1f4')
    fig.text(.15,.065,'先逐例计算共同官方 A 单核基线 B / M，再对 100 例求均值。',fontsize=7.5)
    fig.text(.15,.025,'单核保留真实比值；与图 6-4 使用同一 500 对；不外推真机速度。',fontsize=7.5)
    for ext in ['svg','png','pdf']:fig.savefig(folder/f'fig63_cache_comparison.{ext}',dpi=300)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,default=Path(__file__).resolve().parent);draw(p.parse_args().prepared)
