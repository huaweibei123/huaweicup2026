"""Build tables from frozen results; Python standard library + XeLaTeX.

AI-assisted authoring: OpenAI Codex; exact model/release date not exposed
to this task and therefore not guessed. This is a typesetting tool,
not the solver used to produce the frozen experimental results.
"""
import argparse, csv, hashlib, json, subprocess
from pathlib import Path

EXPECTED_SHA='79e537b3f4e21526a504033b9b6b44fee1ab1ca6a4a98b6c0a341d9290d7a293'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--fonts',type=Path,required=True,help='Template fonts directory; not copied into this package')
    ap.add_argument('--xelatex',default='xelatex')
    args=ap.parse_args()
    here=Path(__file__).resolve().parent
    raw=(here/'all-results.csv').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA
    rs=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    expected={(f'P{p}',str(k),f'{i:03}') for p in range(1,4) for k in range(1,6) for i in range(1,101)}
    assert len(rs)==1500 and {(r['problem'],r['cores'],r['case_id']) for r in rs}==expected
    args.output.mkdir(parents=True,exist_ok=True)
    intro=r'''\section{逐用例评测结果}
本附录覆盖题目给定的全部100个计算图及1至5个核心。问题一、二各列500条主方案结果；问题三按相同用例、核心数与调度方案，将无二级缓存（Level-2 Cache，L2）和只读缓存（read-only Cache）两种配置横向配对，共列1000条配置结果。合计2000条结果对应1500种“问题—计算图—核心数”组合，不表示2000次独立求解。

用例编号001至100依次对应官方输入文件\texttt{case\_001.json}至\texttt{case\_100.json}。完成时间（Makespan，记为$M$）的单位为模拟时钟周期（cycle）；总额外数据搬运量记为$D$，单位为字节（byte，B），采用官方评测器的额外外部主存搬运统计字段。题面将外部主存简称为DDR，其名称源自双倍数据率（double data rate）。$D$不等于所有数据搬运字节之和，也不直接代表扣除缓存命中字节后的物理主存净流量。

字节命中率（byte hit rate，记为$H$）按缓存命中字节数除以可查询缓存的输入搬运字节数计算，在表中显示为百分数。问题三的$H_{\mathrm{C}}$仅表示只读Cache配置下的字节命中率；无L2未启用缓存，命中率不适用，不解释为0\%。$T$为端到端求解墙钟时间（wall-clock time），单位为秒（s），与模拟完成时间$M$分开报告。问题三两配置复用同一份调度方案，每个用例只列一次该方案的求解时间。

问题三两行固定方案、核心数和其余评测配置，仅切换L2配置。无L2对照不是问题二重新优化得到的方案；只读Cache采用题面规定的1 MB容量与250 B/cycle带宽。两配置的$D$依原始官方结果列出，即使相等也不省略。$M$和$D$保留整数，$T$和$H$显示3位小数；正文均值及加速比必须由未舍入的原始值计算。本表重排已有冻结结果，不新增求解或评测。

\noindent 问题一、二每行左右两组分别为独立用例，按从左到右、从上到下的顺序读取。问题三每行对应一个用例，下标0表示无L2，下标C表示只读Cache。续页重复问题编号、核心数、表号和列标题。横向合排仅减少版面占用，所有用例及必需指标完整保留。

'''
    parts=[intro]
    for p in range(1,4):
      for k in range(1,6):
        subset=sorted([r for r in rs if r['problem']==f'P{p}' and r['cores']==str(k)],key=lambda r:r['case_id'])
        cap=f'问题{p}、{k}个核心'+('：相同方案的无L2与只读Cache结果' if p==3 else '：固定配置逐用例结果')
        ncol=7 if p==3 else 8
        cols='lrrrrrr' if p==3 else r'lrrr@{\hspace{16bp}}lrrr'
        heads=r'用例 & $M_0$/cycle & $D_0$/B & $M_{\mathrm{C}}$/cycle & $D_{\mathrm{C}}$/B & $H_{\mathrm{C}}$/\% & $T$/s' if p==3 else r'用例 & $M$/cycle & $D$/B & $T$/s & 用例 & $M$/cycle & $D$/B & $T$/s'
        parts += [r'\begin{longtable}{'+cols+'}',r'\caption{'+cap+r'}\label{tab:full-p'+str(p)+'-k'+str(k)+r'}\\',r'\toprule',heads+r'\\\midrule',r'\endfirsthead',r'\multicolumn{'+str(ncol)+r'}{c}{\textbf{表\thetable（续）\quad '+cap+r'}}\\[6bp]',r'\toprule',heads+r'\\\midrule',r'\endhead',r'\midrule',r'\multicolumn{'+str(ncol)+r'}{r}{接下页}\\',r'\endfoot',r'\bottomrule',r'\endlastfoot']
        for idx,r in enumerate(subset):
          case=r['case_id']; m=r['makespan_cycles']; d=r['extra_ddr_bytes']; t=f"{float(r['solver_wall_seconds']):.3f}"
          if p<3:
            if idx%2: continue
            r2=subset[idx+1]
            parts.append(f"{case} & {m} & {d} & {t} & {r2['case_id']} & {r2['makespan_cycles']} & {r2['extra_ddr_bytes']} & {float(r2['solver_wall_seconds']):.3f}"+r'\\')
          else:
            h=f"{100*float(r['cache_hit_rate_bytes']):.3f}"
            parts.append(f"{case} & {r['no_l2_makespan_cycles']} & {r['no_l2_extra_ddr_bytes']} & {m} & {d} & {h} & {t}"+r'\\')
        parts += [r'\end{longtable}','']
    (args.output/'appendix-body.tex').write_text('\n'.join(parts),encoding='utf-8')
    preamble=r'''\documentclass[UTF8,fontset=none,zihao=-4]{ctexart}
\usepackage{fontspec,geometry,longtable,booktabs,caption,hyperref,indentfirst,setspace}
\geometry{a4paper,top=30mm,bottom=18.17mm,left=22.5mm,right=22.5mm,includefoot,footskip=8.33mm,headheight=0pt,headsep=0pt}
\input{font-config.tex}
\providecommand{\heiti}{\CJKfamily{zhhei}}
\providecommand{\songti}{\CJKfamily{zhsong}}
\xeCJKsetup{PunctStyle=plain}
\hypersetup{unicode=true,pdfauthor={},pdftitle={逐用例评测结果附表},pdfsubject={},hidelinks}
\pagestyle{plain}
\setstretch{1}
\ctexset{section={format=\centering\heiti\fontsize{14bp}{18.2bp}\selectfont,afterindent=true}}
\renewcommand{\normalsize}{\fontsize{12bp}{15.6bp}\selectfont}
\normalsize
\setlength{\parindent}{24bp}
\setlength{\parskip}{0pt}
\renewcommand{\arraystretch}{1}
\setlength{\tabcolsep}{4bp}
\setlength{\LTpre}{8bp}
\setlength{\LTpost}{8bp}
\captionsetup{font={normalsize,bf},labelsep=quad,skip=6bp}
\begin{document}
\input{appendix-body.tex}
\end{document}
'''
    (args.output/'case-results-appendix.tex').write_text(preamble,encoding='utf-8')
    fonts=args.fonts.resolve().as_posix()+'/'
    (args.output/'font-config.tex').write_text(r'\setCJKmainfont{SimSun.ttf}[AutoFakeBold=2.5,Path={'+fonts+r'}]'+'\n'+r'\setCJKsansfont{SimHei.ttf}[Path={'+fonts+r'}]'+'\n'+r'\setCJKmonofont{SimSun.ttf}[Path={'+fonts+r'}]'+'\n'+r'\setmainfont{Times.TTF}[Path={'+fonts+r'},BoldFont=Timesbd.TTF,ItalicFont=Timesi.TTF,BoldItalicFont=Timesbi.TTF]'+'\n'+r'\setCJKfamilyfont{zhsong}{SimSun.ttf}[AutoFakeBold=2.5,Path={'+fonts+r'}]'+'\n'+r'\setCJKfamilyfont{zhhei}{SimHei.ttf}[Path={'+fonts+r'}]',encoding='utf-8')
    for _ in range(6):
        subprocess.run([args.xelatex,'-interaction=nonstopmode','-halt-on-error','case-results-appendix.tex'],cwd=args.output,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=(args.output/'case-results-appendix.log').read_text(encoding='utf-8',errors='replace')
        needs_rerun=any(s in log for s in ['Rerun LaTeX','Rerun to get','Please rerun'])
        if not needs_rerun: break
    assert 'Overfull' not in log and 'Missing character' not in log
    assert not needs_rerun
    print(json.dumps({'input_rows':len(rs),'output_records':2000,'tables':15,'pdf':str(args.output/'case-results-appendix.pdf')}))

if __name__=='__main__':main()
