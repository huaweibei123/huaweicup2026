#!/usr/bin/env python3
"""Build the anonymous review checkpoint from chapter Markdown and frozen figures.

No solver/evaluator calls. Figure captions remain searchable LaTeX text.
"""
from pathlib import Path
import csv, json, re, shutil, subprocess, hashlib, os

P=Path(__file__).resolve().parents[1]
CHECKPOINT=os.environ.get('PAPER_CHECKPOINT','checkpoint-02')
B=P/'build'/CHECKPOINT
OUT=P/'checkpoints'/CHECKPOINT
if (OUT/'annotation-lock.json').exists():
    raise SystemExit('This checkpoint is frozen for user annotations. Set PAPER_CHECKPOINT to a new checkpoint directory.')
T=P.parent/'template-2026'
FIG=P/'figures'
B.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
for n in ['gmcm2026.cls','gmcm-numerical.bst']:
    shutil.copy2(T/n,B/n)
for n,src in [('fonts',T/'fonts'),('figures',FIG)]:
    if not (B/n).exists(): (B/n).symlink_to(src,target_is_directory=True)

used=[]
def figure(file,caption,label,trim=None):
    path=FIG/file
    assert path.is_file(),path
    used.append(dict(file=str(path.relative_to(P)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),caption=caption,label=label))
    options=r'width=\linewidth,height=.84\textheight,keepaspectratio'
    if trim: options+=',trim='+trim+',clip'
    return '\n\n'+r'\begin{figure}[!htbp]'+'\n'+r'\centering'+'\n'+r'\includegraphics['+options+']{figures/'+file+'}\n'+r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}'+'\n\n'

def datafig(name,caption,label):
    return figure('paper-v2/'+name+'.pdf',caption,label)

def timeline_pair(first,second,caption,label):
    parts=[]
    for name in [first,second]:
        path=FIG/'paper-v2'/(name+'.pdf')
        used.append(dict(file=str(path.relative_to(P)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),caption=caption,label=label))
        parts.append(r'\includegraphics[width=\linewidth]{figures/paper-v2/'+name+'.pdf}')
    return '\n\n'+r'\begin{figure}[!htbp]\centering'+'\n'+ ('\n'+r'\par\vspace{4pt}'+'\n').join(parts)+'\n'+r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}'+'\n\n'

def replace_plan(m):
    key=m.group(1)
    if key=='fig-progression':
        return figure('fig-progression-v2.png',r'三问条件的差别。相同计算片段在问题一中经过独立Task边界，数据经DDR中转；问题二允许同一Core保留数据；问题三另为符合条件的COPY\_IN提供共享只读Cache。下部示意数据能够装入Cache时的读取过程；所有请求仍须满足原依赖及规定等待。','fig:progression')
    if key=='fig-coherent':
        return figure('fig-framework-v2.png','三问共用的方案构造与比较步骤。各分支只在结构条件满足时采用，所形成的完整方案需检查依赖与容量，并通过执行评价比较完成时间。下界只在其证明条件成立时用于提前排除候选。','fig:framework')
    if key=='fig-p1-cuts':
        return figure('fig-p1-cuts-zh.png',r'case\_026、5 Core 的真实归约片段。左为原始划分，右为将独立支路改分到另一Core；八个 ADD 节点的编号和依赖不变。点线端口连接裁剪范围外的输入或后继，橙色虚线为位于不同子图中的操作之间的依赖。','fig:p1-cuts','0 235 0 0')
    if key=='fig-p1-overlap':
        return timeline_pair('fig-p1-overlap-old','fig-p1-overlap-new',
            r'case\_026、5 Core 两种切分的执行时间线。上：修改前方案，$M=44{,}114$ cycles，额外搬运211,680 B；下：分支重新分配后，$M=42{,}014$ cycles，额外搬运375,532 B。每组分别显示Task持续区间及四条Pipe的操作区间，横轴范围相同，数据来自官方模拟事件。','fig:p1-overlap')
    if key=='fig-p1-results':
        return datafig('fig-p1-results','问题一的完整版本比较。上：每个Core数量的 100 图平均加速比；下：全部500种图与Core数量组合的时间与搬运量配对变化。Core数量用点形区分，横轴采用对称对数。','fig:p1-results')
    if key=='fig-p2-transition':
        return '\n同一个Core保留数据与在不同Core之间复制数据的区别见图 \\ref{fig:progression}。后续按这个区别计算边界复制量。\n'
    if key=='fig-state-meaning': return '\n'
    if key=='fig-p2-results':
        return datafig('fig-p2-results','问题二的完整版本比较。上：按题目要求计算的平均加速比；下：500种组合配对结果。部分时间改善伴随额外搬运增加，两项指标分别报告。','fig:p2-results')
    if key=='fig-p2-counterexample':
        return timeline_pair('fig-p2-counterexample-control','fig-p2-counterexample-c04',
            r'case\_019、5 Core 的官方模拟的执行时间线。上：主算法，$M=16{,}247$ cycles；下：C04，$M=28{,}514$ cycles。每组分别显示Task和四条Pipe，共用横轴范围。C04的搬运量较少，且没有容量不足引起的缓存换入换出，但完成时间更长。','fig:p2-counterexample')
    if key=='fig-cache-story':
        return r'''
例如，case\_021、3 Core 的编译后张量 t1000000001 大小为 4096 B。官方事件给出以下生命周期；事件时刻为 cycles，表中间隔不表示等长处理阶段。

\begin{table}[!htbp]\centering
\caption{同一张量的 Cache 事件}\label{tab:cache-events}
\begin{tabularx}{\linewidth}{rX}\toprule
时刻 / cycle & 事件 \\\midrule
0 & COPY\_IN开始时未命中 \\
207 & DDR COPY\_IN 完成，张量放入Cache，记下插入顺序 \\
4,956 & 另一Core读命中，插入次序不变 \\
323,850 & 插入张量 t1000000487 时，该最早插入的项被移除 \\\bottomrule
\end{tabularx}\end{table}
'''
    if key=='fig-forest-frontier':
        return datafig('fig-forest-example','两种子树处理顺序的内部结果占用。左：先A后B，峰值10 KiB；右：先B后A，峰值13 KiB。横轴为处理步骤，不是模拟时钟；数字为第6章的公式示例。','fig:forest-example')
    if key=='fig-p3-results':
        return datafig('fig-p3-results','问题三的保持方案不变的配对评价。上：无 L2 与只读 Cache 的平均基线加速比；下：逐图$M_2/M_3$的均值，每种Core数量包含100对结果。','fig:p3-results')
    if key=='fig-cache-gain':
        return datafig('fig-cache-gain','500 个保持方案不变的配对结果中的字节命中率与 Cache 收益。保留低于 1 的负收益点；100 个用例的不同Core数量结果相关，不能当作 500 个独立随机样本。','fig:cache-gain')
    if key=='fig-policy-tradeoff': return '\n'
    if key=='fig-dataset':
        return datafig('fig-dataset','官方 100 张计算图的结构统计。上：非 COPY 操作数与张量大小总和；下：按矩阵计算的时长占两类计算总时长的比例排序的用例分布。','fig:dataset')
    if key=='fig-runtime':
        return datafig('fig-runtime','三种求解程序的实际经过时间累计分布，每题500次。时间包含方案构造及在线评价，横轴采用对数刻度；批次资源不同，不据此比较独占机器的速度。','fig:runtime')
    if key=='fig-bound-gap':
        return datafig('fig-bound-gap',r'同一输入、配置与方案范围下的时间上界和下界。$L\le\mathrm{OPT}\le U$，阴影是必要界给出的上限与当前结果之间的差距，不代表一定可实现的收益。','fig:bound-gap')
    raise ValueError(key)

def pandoc(s):
    proc=subprocess.run(['pandoc','-f','markdown+raw_tex+implicit_figures-auto_identifiers','-t','latex','--wrap=none'],input=s,text=True,capture_output=True,check=True)
    x=proc.stdout.replace(r'\def\LTcaptype{none}', r'\def\LTcaptype{table}')
    # Short tables should stay together. Keep the long symbol list breakable.
    def short_table(m):
        t=m.group(0)
        if t.count(r"\\") > 12:
            return t
        t=t.replace(r'\begin{longtable}[]',r'\begin{tabular}').replace(r'\end{longtable}',r'\bottomrule\end{tabular}')
        t=t.replace(r'\endhead','').replace(r'\bottomrule\noalign{}'+'\n'+r'\endlastfoot','')
        return r'\begin{table}[!htbp]\centering\small'+'\n'+t+'\n'+r'\end{table}'
    x=re.sub(r'\\begin\{longtable\}[\s\S]*?\\end\{longtable\}',short_table,x)
    x=re.sub(r'\\texttt\{([^{}]{28,})\}',lambda m:r'\texttt{\seqsplit{'+m.group(1)+'}}',x)
    x=re.sub(r'\\textbf\{证明。\}([\s\S]*?)\\\(\\square\\\)', lambda m: r'\begin{proof}'+m.group(1)+r'\end{proof}', x)
    # Pandoc emits unnumbered display math. Keep the manuscript's formula content.
    return x

def clean_md(s):
    s=re.sub(r'<!--[\s\S]*?-->','',s)
    s=re.sub(r'::: figure-plan \{#([^}]+)\}[\s\S]*?\n:::',replace_plan,s)
    def results_table(m):
        lines=m.group(0).strip().splitlines()
        rows=[line.strip().strip('|').split('|') for line in lines]
        rows=[r for r in rows if not all(re.fullmatch(r'\s*:?[-]+:?\s*',c) for c in r)]
        rendered=[]
        for row in rows:
            row=[c.strip() for c in row]
            row[0]=row[0].replace('按题目要求计算平均加速比','官方平均加速比').replace('算法输出方案的','优化方案').replace('优化方案的','优化方案').replace('对前一固定完整版本改善/持平/退化','改善/持平/退化').replace('对前版改善/持平/退化','改善/持平/退化')
            rendered.append(' & '.join(row)+r' \\')
        return '\n'+r'\begin{table}[!htbp]\centering\small'+ '\n'+r'\begin{tabularx}{\linewidth}{@{}Xrrrrr@{}}\toprule'+'\n'+rendered[0]+'\n'+r'\midrule'+'\n'+'\n'.join(rendered[1:])+'\n'+r'\bottomrule\end{tabularx}\end{table}'+'\n'
    s=re.sub(r'^\| Core数量 \| 1 \| 2 \| 3 \| 4 \| 5 \|\n(?:\|[^\n]+\n)+',results_table,s,flags=re.M)
    def code(m):
        lines=m.group(1).strip().splitlines()
        return '\n\\begin{quote}\n'+ '\n\n'.join(lines)+'\n\\end{quote}\n'
    s=re.sub(r'```(?:text)?\n([\s\S]*?)```',code,s)
    s=s.replace('框架 为主线','框架为主线')
    s=re.sub(r'(?<=[\u4e00-\u9fff])Core',' Core',s)
    s=re.sub(r'Core(?=[\u4e00-\u9fff])','Core ',s)
    return s

abstract=(P/'chapters/00-abstract.md').read_text().split('\n',1)[1]
abstract,keywords=abstract.split('**关键词：**')
body=[]
for f in sorted((P/'chapters').glob('*.md')):
    if f.name.startswith(('00','09','10')): continue
    s=clean_md(f.read_text())
    # This figure is already a real Markdown image; emit caption in LaTeX.
    s=re.sub(r'!\[(.*?)\]\(\.\./figures/fig-hypercut-v2.png\)\{[^}]+\}',lambda m:figure('fig-hypercut-v2.png',m.group(1),'fig:hypercut'),s)
    body.append(pandoc(s)+'\n')

# Bibliography text remains explicit and numbered, without editorial web-check notes.
bib=r'''\begin{thebibliography}{9}
\bibitem{official} 第二十三届中国研究生数学建模竞赛. A题：通用神经网络处理器下的多核调度问题及官方附件[Z]. 2026.
\bibitem{graham} GRAHAM R L. Bounds for Certain Multiprocessing Anomalies[J]. Bell System Technical Journal, 1966, 45(9): 1563--1581. DOI: 10.1002/j.1538-7305.1966.tb01709.x.
\bibitem{hypergraph} ÇATALYÜREK Ü V, AYKANAT C. Hypergraph-Partitioning-Based Decomposition for Parallel Sparse-Matrix Vector Multiplication[J]. IEEE Transactions on Parallel and Distributed Systems, 1999, 10(7): 673--693. DOI: 10.1109/71.780863.
\bibitem{sethi} SETHI R, ULLMAN J D. The Generation of Optimal Code for Arithmetic Expressions[J]. Journal of the ACM, 1970, 17(4): 715--728. DOI: 10.1145/321607.321620.
\bibitem{nist} BLACK P E. Hyperedge; Hypergraph[EB/OL]. Dictionary of Algorithms and Data Structures, NIST. [2026-09-26]. \url{https://xlinux.nist.gov/dads/HTML/hyperedge.html}.
\end{thebibliography}
'''
bodytext='\n'.join(body)
for k,ref in [('1','official'),('2','graham'),('3','hypergraph'),('4','sethi'),('5','nist')]:
    bodytext=bodytext.replace('['+k+']',r'\cite{'+ref+'}')

app=(P/'chapters/10-appendix.md').read_text().split('## 附录B 补充数学推导',1)[1]
app=app.split('## 附录C',1)[0]
app=re.sub(r'^### B\.\d+ ',r'## ',app,flags=re.M)
appendix=pandoc('# 补充数学推导\n'+app)
math_appendix=appendix
appendix=''
rows=list(csv.DictReader((P/'data/all-results.csv').open()))
assert len(rows)==1500
appendix+=r'''
\section{逐用例完整结果}
周期单位为 cycle，搬运单位为 B。各表来自同一份1500行冻结CSV；M为Makespan，D为额外DDR搬运量。P3另给相同方案关闭L2的M和D，以及按字节计算的命中率H。正文平均值使用未舍入原值计算。
'''
def table(caption,head,cols,values):
    return ('\n\\begin{longtable}{'+cols+'}\n\\caption{'+caption+'}\\\\\n\\toprule\n'+head+'\\\\\\midrule\n\\endfirsthead\n\\toprule\n'+head+'\\\\\\midrule\n\\endhead\n\\bottomrule\\endfoot\n'+'\n'.join(' & '.join(v)+r' \\' for v in values)+'\n\\end{longtable}\n')
for problem in ['P1','P2','P3']:
    for k in range(1,6):
        rr=[r for r in rows if r['problem']==problem and int(r['cores'])==k]
        assert len(rr)==100
        values=[[r['case_id'],r['makespan_cycles'],r['extra_ddr_bytes'],f"{float(r['solver_wall_seconds']):.3f}"] for r in rr]
        appendix+=table(f'{problem}、{k} Core 的逐用例结果','case & M / cycle & D / B & 求解时间 / s','lrrr',values)
        if problem=='P3':
            values=[[r['case_id'],r['no_l2_makespan_cycles'],r['no_l2_extra_ddr_bytes'],f"{float(r['cache_hit_rate_bytes'])*100:.3f}"] for r in rr]
            appendix+=table(f'P3、{k} Core 的相同方案关闭L2对照及Cache命中率','case & 无L2 M / cycle & 无L2 D / B & H / \\%','lrrr',values)
tables_appendix=appendix
appendix=''
appendix+=r'''
\Needspace{14\baselineskip}
\section{固定实现与复现信息}
三题固定求解器的提交分别为下列SHA。逐输入的图、方案与结果来源及完整SHA-256见配套CSV与来源收据。固定版本结果不能用不同算法的历史赢家拼接。
\begin{itemize}
\item P1：\texttt{\seqsplit{834d8c957538ee069c66aadac9509552a4cc69d7}}；求解过程中的评分至多10次E1。
\item P2：\texttt{\seqsplit{c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f}}；求解过程中的评分至多3次E2。
\item P3：\texttt{\seqsplit{311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1}}；求解过程中的评分至多3次E0。
\end{itemize}
官方代码与配置身份分别为\texttt{\seqsplit{de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0}}和\texttt{\seqsplit{dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9}}。来源收据记录822个固定Git对象；本稿的数据导出仅读取已有原件，没有新增求解器或评价器调用。
'''
preamble=r'''\documentclass[anonymous,notoc]{gmcm2026}
\usepackage{placeins,seqsplit,calc,needspace,float}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{#1}
\setlength{\emergencystretch}{2em}
\makeatletter\setlength{\@fptop}{0pt}\makeatother
\renewcommand{\topfraction}{.90}
\renewcommand{\bottomfraction}{.85}
\renewcommand{\textfraction}{.08}
\renewcommand{\floatpagefraction}{.84}
\setcounter{topnumber}{3}
\setcounter{bottomnumber}{2}
\setcounter{totalnumber}{4}
\setlength{\textfloatsep}{12pt plus 2pt minus 2pt}
\setlength{\intextsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{10pt plus 2pt minus 2pt}
\widowpenalty=10000
\clubpenalty=10000
\displaywidowpenalty=10000
\renewcommand{\qedsymbol}{\ensuremath{\scriptstyle\square}}
\gmcmsetup{title={多核神经网络处理器的计算图切分与调度优化},year=2026,edition={第二十三届},problem=A}
\begin{document}
\maketitle
\begin{abstract}
'''
tex=preamble+pandoc(clean_md(abstract))+r'\keywords{'+keywords.strip()+'}\n'+r'\end{abstract}'+'\n'+bodytext+'\n\\FloatBarrier\n'+bib+'\n\\appendix\n\\setcounter{section}{1}\n'+math_appendix+appendix+'\n\\end{document}\n'
(B/'figure-manifest.json').write_text(json.dumps(used,ensure_ascii=False,indent=2)+'\n')
supplement=preamble.split(r'\begin{document}')[0]+r'\begin{document}\pagestyle{plain}'+tables_appendix+'\n'+r'\end{document}'
for name,source,output in [('main',tex,'anonymous-paper-v1.pdf'),('result-tables',supplement,'result-tables.pdf')]:
    (B/(name+'.tex')).write_text(source)
    for run in range(2):
        with (B/f'{name}-compile-{run+1}.txt').open('w') as out:
            result=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error',name+'.tex'],cwd=B,stdout=out,stderr=subprocess.STDOUT)
        if result.returncode:
            print((B/f'{name}-compile-{run+1}.txt').read_text()[-5000:]);raise SystemExit(result.returncode)
    shutil.copy2(B/(name+'.pdf'),OUT/output)
    shutil.copy2(B/(name+'.tex'),OUT/(name+'.tex'))
shutil.copy2(B/'figure-manifest.json',OUT/'figure-manifest.json')
print(OUT/'anonymous-paper-v1.pdf')
