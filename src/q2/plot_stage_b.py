"""Data-backed stage B figures; no solver calls.

Style adapted from ChenLiu-1996/figures4papers, CC BY-NC 4.0:
https://github.com/ChenLiu-1996/figures4papers/tree/3c181f85e82c6f24948fcaaf3be6696102b41d8d/scientific-figure-making
Changes: compact 178 mm panels, measured Q2 data, zero-based bars and hatches.
"""
import csv
import hashlib
import json
from pathlib import Path
import platform
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .stage_b import RUN
from .budget_search import ROOT, save, sha


def main():
    metrics=list(csv.DictReader((RUN/'metrics.csv').open(encoding='utf-8',newline='')))
    candidates=list(csv.DictReader((RUN/'candidates.csv').open(encoding='utf-8',newline='')))
    rows={(r['case'],r['method']):r for r in metrics}
    cases=('002','008','044')
    methods=('D','M1','M2')
    colors={'D':'#CFCECE','M1':'#3775BA','M2':'#B64342'}
    hatches={'D':'','M1':'//','M2':'..'}
    output=RUN/'figures'
    output.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':['Arial','DejaVu Sans'],'font.size':9,
        'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':0.9,
        'legend.frameon':False,'svg.fonttype':'none','pdf.fonttype':42,
        'savefig.facecolor':'white'})
    fig,axes=plt.subplots(1,2,figsize=(7.0,3.1))
    x=np.arange(3)
    width=0.24
    for offset,method in enumerate(methods):
        quality=[int(rows[c,method]['best_cycles'])/1000 for c in cases]
        cost=[float(rows[c,method]['unit_seconds']) for c in cases]
        for ax,values in zip(axes,(quality,cost)):
            bars=ax.bar(x+(offset-1)*width,values,width,label=method,color=colors[method],
                        hatch=hatches[method],edgecolor='#272727',linewidth=0.65,zorder=3)
            for i,(bar,value) in enumerate(zip(bars,values)):
                text=f'{value:.1f}'
                if ax is axes[0] and len({rows[cases[i],m]['best_cycles'] for m in methods})==1:
                    if method!='M1':
                        continue
                    text+='\n(all)'
                if ax is axes[1]:
                    text+='\n['+rows[cases[i],method]['calls']+']'
                ax.text(bar.get_x()+bar.get_width()/2,value+1.7 if ax is axes[0] else value+0.7,
                        text,ha='center',va='bottom',fontsize=7.1,linespacing=1.05)
    for ax in axes:
        ax.set_xticks(x,[f'case{c}' for c in cases])
        ax.set_axisbelow(True)
        ax.grid(axis='y',color='#E8E8E8',linewidth=0.5)
    axes[0].set_ylim(0,157)
    axes[0].set_ylabel('Makespan (10³ cycles)')
    axes[0].set_title('(a) Confirmed incumbent',loc='left',fontsize=10,pad=10)
    axes[1].set_ylim(0,49)
    axes[1].set_ylabel('Unit wall time (s)')
    axes[1].set_title('(b) Measured cost [E0 calls]',loc='left',fontsize=10,pad=10)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=3,bbox_to_anchor=(0.52,1.00))
    fig.subplots_adjust(left=0.095,right=0.99,bottom=0.16,top=0.80,wspace=0.30)
    outputs=[]
    for suffix in ('png','pdf','svg'):
        path=output/f'quality_cost.{suffix}'
        fig.savefig(path,dpi=300)
        outputs.append(path)
    plt.close(fig)

    fig,axes=plt.subplots(1,3,figsize=(7.0,2.9),sharey=True)
    for ax,case in zip(axes,cases):
        for x,method,marker in ((0,'M1','o'),(1,'M2','s')):
            pool=[r for r in candidates if r['unit']==f'{case}-{method}' and r['phase']=='explore']
            ratios=[int(r['makespan'])/int(rows[case,method]['initial_cycles']) for r in pool]
            jitter=np.linspace(-0.14,0.14,len(ratios)) if ratios else []
            ax.scatter(x+jitter,ratios,c=colors[method],s=21,alpha=0.65,marker=marker,
                       linewidths=0.4,edgecolors='#272727',zorder=3)
            best=int(rows[case,method]['best_cycles'])/int(rows[case,method]['initial_cycles'])
            ax.scatter([x],[best],c='#111111',s=45,marker='D',zorder=4)
        ax.axhline(1,color='#555555',linestyle='--',linewidth=0.9,zorder=2)
        ax.set_xticks([0,1],['M1','M2'])
        ax.set_xlim(-0.45,1.45)
        ax.set_ylim(0,3.35)
        ax.set_title(f'case{case}',fontsize=10)
        ax.set_axisbelow(True)
        ax.grid(axis='y',color='#E8E8E8',linewidth=0.5)
    axes[0].set_ylabel('Candidate makespan / D')
    fig.text(0.51,0.02,'Dots: every evaluated exploration plan   •   Diamond: selected incumbent   •   Dashed: D',
             ha='center',fontsize=8)
    fig.subplots_adjust(left=0.10,right=0.99,bottom=0.21,top=0.87,wspace=0.18)
    for suffix in ('png','pdf','svg'):
        path=output/f'candidate_regressions.{suffix}'
        fig.savefig(path,dpi=300)
        outputs.append(path)
    plt.close(fig)
    save(output/'provenance.json',{'source':'src/q2/plot_stage_b.py','source_sha256':sha(Path(__file__)),
        'code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'input_hashes':{name:sha(RUN/name) for name in ('metrics.csv','candidates.csv')},
        'python':platform.python_version(),'matplotlib':matplotlib.__version__,'numpy':np.__version__,
        'command':'python -X utf8 -B -m src.q2.plot_stage_b','q2_calls':0,
        'parameters':{'paper_width_mm':177.8,'png_dpi':300,'cases':cases,'cores':4,'seed':0,
                      'bars_start_at_zero':True,'error_bars':'none; deterministic single run, no sampling CI'},
        'style_source':'ChenLiu-1996/figures4papers 3c181f85e82c6f24948fcaaf3be6696102b41d8d, CC BY-NC 4.0',
        'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in outputs}})
    print('Exported two measured figures to PNG/PDF/SVG; zero E0 calls')


if __name__=='__main__':
    main()
