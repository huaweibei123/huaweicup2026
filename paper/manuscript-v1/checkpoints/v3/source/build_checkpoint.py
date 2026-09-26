#!/usr/bin/env python3
"""Build the anonymous review checkpoint from chapter Markdown and frozen figures.

No solver/evaluator calls. Figure captions remain searchable LaTeX text.
"""
from pathlib import Path
import csv, json, re, shutil, subprocess, hashlib, os

P=Path(__file__).resolve().parents[1]
CHECKPOINT=os.environ.get('PAPER_CHECKPOINT','checkpoint-03')
VERSION=os.environ.get('PAPER_VERSION','v2')
if not re.fullmatch(r'v[1-9][0-9]*', VERSION):
    raise SystemExit('PAPER_VERSION must be v followed by a positive integer')
B=P/'build'/CHECKPOINT
OUT=P/'checkpoints'/CHECKPOINT
if (OUT/'annotation-lock.json').exists():
    raise SystemExit('This checkpoint is frozen for user annotations. Set PAPER_CHECKPOINT to a new checkpoint directory.')
T=P.parent/'template-2026'
FIG=P/'figures'
B.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
# Freeze inputs before conversion; later agent edits cannot leak into this build.
snapshot={str(f.relative_to(P)): f.read_bytes() for folder in ['chapters','appendix-code','data']
          for f in (P/folder).rglob('*') if f.is_file()}
for relative,content in snapshot.items():
    target=B/'source'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(content)
CHAPTERS=B/'source/chapters'
for n in ['gmcm2026.cls','gmcm-numerical.bst']:
    shutil.copy2(T/n,B/n)
for n,src in [('fonts',T/'fonts')]:
    if not (B/n).exists(): (B/n).symlink_to(src,target_is_directory=True)
# Selected image bytes are frozen by figure()/timeline_pair() before compilation.
if (B/'figures').is_symlink(): (B/'figures').unlink()
(B/'figures').mkdir(exist_ok=True)

def freeze_figure(path):
    content=path.read_bytes()
    target=B/'figures'/path.relative_to(FIG)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(content)
    return hashlib.sha256(content).hexdigest()

used=[]
def figure(file,caption,label,trim=None):
    path=FIG/file
    assert path.is_file(),path
    used.append(dict(file=str(path.relative_to(P)),sha256=freeze_figure(path),caption=caption,label=label))
    options=r'width=\linewidth,height=.84\textheight,keepaspectratio'
    if trim: options+=',trim='+trim+',clip'
    return '\n\n'+r'\begin{figure}[!htbp]'+'\n'+r'\centering'+'\n'+r'\includegraphics['+options+']{figures/'+file+'}\n'+r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}'+'\n\n'

def datafig(name,caption,label):
    return figure('paper-v2/'+name+'.pdf',caption,label)

def timeline_pair(first,second,caption,label):
    parts=[]
    for name in [first,second]:
        path=FIG/'paper-v2'/(name+'.pdf')
        used.append(dict(file=str(path.relative_to(P)),sha256=freeze_figure(path),caption=caption,label=label))
        parts.append(r'\includegraphics[width=\linewidth]{figures/paper-v2/'+name+'.pdf}')
    return '\n\n'+r'\begin{figure}[!htbp]\centering'+'\n'+ ('\n'+r'\par\vspace{4pt}'+'\n').join(parts)+'\n'+r'\caption{'+caption+'}\n'+r'\label{'+label+'}\n'+r'\end{figure}'+'\n\n'

def replace_plan(m):
    key=m.group(1)
    if key=='fig-progression':
        return figure('fig-progression-v3.png',r'三问条件的差别。问题一为图中不同子图所对应的操作分别建立Task，数据经DDR中转；问题二允许同一个核心保留数据；问题三另为符合条件的COPY\_IN提供共享只读Cache。下部示意数据能够装入Cache时的读取过程；所有请求仍须满足原依赖及规定等待。','fig:progression')
    if key=='fig-coherent':
        return figure('fig-framework-v2.png','三问共用的方案构造与比较步骤。各分支只在结构条件满足时采用，所形成的完整方案需检查依赖与容量，并通过执行评价比较完成时间。下界只在其证明条件成立时用于提前排除候选。','fig:framework')
    if key=='fig-p1-cuts':
        return figure('fig-p1-cuts-xy-corrected.png',r'case\_026、5个核心的真实归约片段。左为原始划分，右为将独立支路改分到另一个核心；八个 ADD 节点的编号和依赖不变。点线端口连接裁剪范围外的输入或后继，橙色虚线为位于不同子图中的操作之间的依赖。','fig:p1-cuts','0 235 0 0')
    if key=='fig-p1-overlap':
        return timeline_pair('fig-p1-overlap-old','fig-p1-overlap-new',
            r'case\_026、5个核心 两种切分的执行时间线。上：修改前方案，$M=44{,}114$ cycles，额外搬运211,680 B；下：分支重新分配后，$M=42{,}014$ cycles，额外搬运375,532 B。每组分别显示Task持续区间及四条Pipe的操作区间，横轴范围相同，数据来自官方模拟事件。','fig:p1-overlap')
    if key=='fig-p1-results':
        return datafig('fig-p1-results','问题一的完整版本比较。上：每个核心数量的 100 图平均加速比；下：全部500种图与核心数量组合的时间与搬运量配对变化。核心数量用点形区分，横轴采用对称对数。','fig:p1-results')
    if key=='fig-p2-transition':
        return '\n同一个核心保留数据与在不同核心之间复制数据的区别见图 \\ref{fig:progression}。后续按这个区别计算边界复制量。\n'
    if key=='fig-state-meaning': return '\n'
    if key=='fig-p2-results':
        return datafig('fig-p2-results','问题二的完整版本比较。上：按题目要求计算的平均加速比；下：500种组合配对结果。部分时间改善伴随额外搬运增加，两项指标分别报告。','fig:p2-results')
    if key=='fig-p2-counterexample':
        return timeline_pair('fig-p2-counterexample-control','fig-p2-counterexample-c04',
            r'case\_019、5个核心的官方模拟的执行时间线。上：主算法，$M=16{,}247$ cycles；下：C04，$M=28{,}514$ cycles。每组分别显示Task和四条Pipe，共用横轴范围。C04的搬运量较少，且没有容量不足引起的缓存换入换出，但完成时间更长。','fig:p2-counterexample')
    if key=='fig-cache-story':
        return r'''
例如，case\_021、3个核心的编译后张量 t1000000001 大小为 4096 B。官方事件给出以下生命周期；事件时刻为 cycles，表中间隔不表示等长处理阶段。

\begin{table}[!htbp]\centering
\caption{同一张量的 Cache 事件}\label{tab:cache-events}
\begin{tabularx}{\linewidth}{rX}\toprule
时刻 / cycle & 事件 \\\midrule
0 & COPY\_IN开始时未命中 \\
207 & DDR COPY\_IN 完成，张量放入Cache，记下插入顺序 \\
4,956 & 另一个核心读命中，插入次序不变 \\
323,850 & 插入张量 t1000000487 时，该最早插入的项被移除 \\\bottomrule
\end{tabularx}\end{table}
'''
    if key=='fig-forest-frontier':
        return datafig('fig-forest-example','两种子树处理顺序的内部结果占用。左：先A后B，峰值10 KiB；右：先B后A，峰值13 KiB。横轴为处理步骤，不是模拟时钟；数字为第6章的公式示例。','fig:forest-example')
    if key=='fig-p3-results':
        return datafig('fig-p3-results','问题三的保持方案不变的配对评价。上：无 L2 与只读 Cache 的平均基线加速比；下：逐图$M_2/M_3$的均值，每种核心数量包含100对结果。','fig:p3-results')
    if key=='fig-cache-gain':
        return datafig('fig-cache-gain','500 个保持方案不变的配对结果中的字节命中率与 Cache 收益。保留低于 1 的负收益点；100 个用例的不同核心数量结果相关，不能当作 500 个独立随机样本。','fig:cache-gain')
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
    x=re.sub(r'\\texttt\{([^{}]{12,})\}',lambda m:r'\texttt{\seqsplit{'+m.group(1)+'}}',x)
    x=re.sub(r'\\textbf\{证明。\}([\s\S]*?)\\\(\\square\\\)', lambda m: r'\begin{proof}'+m.group(1)+r'\end{proof}', x)
    # EQ-01: gmcm2026 numbers equations within each section (the paper chapter).
    # Pandoc's default display delimiters suppress that numbering.
    x=re.sub(r'\\\[([\s\S]*?)\\\]',
             lambda m: '\\begin{equation}\n'+m.group(1).strip()+'\n\\end{equation}', x)
    return x

def clean_md(s, chapter=None):
    s=re.sub(r'<!--[\s\S]*?-->','',s)
    s=re.sub(r'::: figure-plan \{#([^}]+)\}[\s\S]*?\n:::',replace_plan,s)
    table_heading = ''
    if chapter == '04-p1' and r'\ref{tab:p1-results}' in s:
        table_heading = r'\caption{全量实验评测与结果分析}\label{tab:p1-results}'
    def results_table(m):
        lines=m.group(0).strip().splitlines()
        rows=[line.strip().strip('|').split('|') for line in lines]
        rows=[r for r in rows if not all(re.fullmatch(r'\s*:?[-]+:?\s*',c) for c in r)]
        rendered=[]
        for row in rows:
            row=[c.strip() for c in row]
            row[0]=row[0].replace('按题目要求计算平均加速比','官方平均加速比').replace('算法输出方案的','优化方案').replace('优化方案的','优化方案').replace('对前一固定完整版本改善/持平/退化','改善/持平/退化').replace('对前版改善/持平/退化','改善/持平/退化')
            rendered.append(' & '.join(row)+r' \\')
        return '\n'+r'\begin{table}[!htbp]\centering\small'+ '\n'+table_heading+'\n'+r'\begin{tabularx}{\linewidth}{@{}Xrrrrr@{}}\toprule'+'\n'+rendered[0]+'\n'+r'\midrule'+'\n'+'\n'.join(rendered[1:])+'\n'+r'\bottomrule\end{tabularx}\end{table}'+'\n'
    s=re.sub(r'^\| 核心数量(?: \$K\$)? \| 1 \| 2 \| 3 \| 4 \| 5 \|\n(?:\|[^\n]+\n)+',results_table,s,flags=re.M)
    def code(m):
        return '\n\\begin{lstlisting}[style=gmcmappendix,language={}]\n'+m.group(1).strip()+'\n\\end{lstlisting}\n'
    s=re.sub(r'```(?:text)?\n([\s\S]*?)```',code,s)
    # LIST-01: preserve colon-introduced Markdown lists in the PDF.
    s=re.sub(r'(?m)([：:])\n(?=(?:1[.)]|[-+*]) )', r'\1\n\n', s)
    s=s.replace('框架 为主线','框架为主线')
    s=re.sub(r'(?<=[\u4e00-\u9fff])Core',' Core',s)
    s=re.sub(r'Core(?=[\u4e00-\u9fff])','Core ',s)
    return s

abstract=(CHAPTERS/'00-abstract.md').read_text().split('\n',1)[1]
abstract,keywords=abstract.split('**关键词：**')
body=[]
for f in sorted(CHAPTERS.glob('*.md')):
    if f.name.startswith(('00','09','10')): continue
    s=clean_md(f.read_text(), f.stem)
    # Authored Markdown captions are preserved for selected diagram files.
    s=re.sub(r'!\[(.*?)\]\(\.\./figures/([^()]+)\)\{#([^} ]+)[^}]*\}',
             lambda m:figure(m.group(2),m.group(1),m.group(3)),s)
    body.append(pandoc(s)+'\n')

# Authored bibliography is the sole source. Stable keys survive display renumbering.
reference_md=re.sub(r'<!--[\s\S]*?-->','',(CHAPTERS/'09-references.md').read_text())
references={m.group(1):m.group(2).strip() for m in re.finditer(
    r'^\[(\d+)\] (.*?)(?=^\[\d+\] |\Z)',reference_md,re.M|re.S)}
if not references: raise ValueError('No authored references')
bodytext='\n'.join(body)
app=(CHAPTERS/'10-appendix.md').read_text()
app=re.sub(r'^# 附录\s*\n','',app)
app=re.sub(r'^## 附录[A-Z] ', '# ',app,flags=re.M)
app=re.sub(r'^### [A-Z]\.\d+ ', '## ',app,flags=re.M)
appendix=pandoc(clean_md(app))
# Keep short appendix tables with their explanatory paragraphs.
appendix=appendix.replace(r'\begin{table}[!htbp]',r'\begin{table}[H]')
if r'\section{核心程序代码}' not in appendix:
    appendix+='\n'+r'\section{核心程序代码}'+'\n'
code_manifest=json.loads((B/'source/appendix-code/manifest.json').read_text())
for item in code_manifest['files']:
    code_path=B/'source/appendix-code'/item['file']
    assert hashlib.sha256(code_path.read_bytes()).hexdigest()==item['sha256'], item['file']
    title=item['problem']+' '+item['file'].split('/')[-1]
    appendix+=r'\subsection{'+title.replace('_',r'\_')+'}\n'
    appendix+=r'\lstinputlisting[style=gmcmappendix,language=Python]{source/appendix-code/'+item['file']+'}\n'

citation_order=[]
def cite_match(m):
    key=m.group(1) or m.group(2)
    if key not in references: raise ValueError('Undefined reference '+key)
    if key not in citation_order: citation_order.append(key)
    return r'\cite{ref'+key+'}'
def convert_citations(x):
    return re.sub(r'\{\[\}(\d+)\{\]\}|\[(\d+)\]',cite_match,x)
bodytext=convert_citations(bodytext)
appendix=convert_citations(appendix)
uncited=set(references)-set(citation_order)
if uncited: raise ValueError('Uncited references: '+str(sorted(uncited)))
bib=r'\begin{thebibliography}{'+str(len(references))+'}\n'
for key in citation_order:
    bib+=r'\bibitem{ref'+key+'} '+pandoc(references[key]).strip()+'\n'
bib+=r'\end{thebibliography}'+'\n'
main_appendix=appendix
appendix=''
rows=list(csv.DictReader((B/'source/data/all-results.csv').open()))
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
        appendix+=table(f'{problem}、{k}个核心的逐用例结果','case & M / cycle & D / B & 求解时间 / s','lrrr',values)
        if problem=='P3':
            values=[[r['case_id'],r['no_l2_makespan_cycles'],r['no_l2_extra_ddr_bytes'],f"{float(r['cache_hit_rate_bytes'])*100:.3f}"] for r in rr]
            appendix+=table(f'P3、{k}个核心的相同方案关闭L2对照及Cache命中率','case & 无L2 M / cycle & 无L2 D / B & H / \\%','lrrr',values)
tables_appendix=appendix
preamble=r'''\documentclass[anonymous,notoc]{gmcm2026}
\usepackage{placeins,seqsplit,calc,needspace,float}
\counterwithin{figure}{subsection}
\renewcommand{\thefigure}{\thesubsection-\arabic{figure}}
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
preamble=preamble.replace(r'\begin{document}',r'\begin{document}'+'\n'+r'\hypersetup{pdfsubject={Paper review '+VERSION+r'}}').replace(r'\maketitle',r'\maketitle'+'\n'+r'\begin{center}\small 审阅稿 '+VERSION+r'\end{center}')
tex=preamble+pandoc(clean_md(abstract))+r'\keywords{'+keywords.strip()+'}\n'+r'\end{abstract}'+'\n'+bodytext+'\n\\FloatBarrier\n'+bib+'\n\\appendix\n'+main_appendix+'\n\\end{document}\n'
(B/'figure-manifest.json').write_text(json.dumps(used,ensure_ascii=False,indent=2)+'\n')
supplement=preamble.split(r'\begin{document}')[0]+r'\begin{document}\pagestyle{plain}'+r'\hypersetup{pdfsubject={Paper review '+VERSION+r' supplementary tables}}'+r'\begin{center}\large 审阅稿 '+VERSION+r'：逐用例结果附表\end{center}'+tables_appendix+'\n'+r'\end{document}'
for name,source,output in [('main',tex,'anonymous-paper-'+VERSION+'.pdf'),('result-tables',supplement,'result-tables.pdf')]:
    (B/(name+'.tex')).write_text(source)
    for run in range(2):
        with (B/f'{name}-compile-{run+1}.txt').open('w') as out:
            result=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error',name+'.tex'],cwd=B,stdout=out,stderr=subprocess.STDOUT)
        if result.returncode:
            print((B/f'{name}-compile-{run+1}.txt').read_text()[-5000:]);raise SystemExit(result.returncode)
    shutil.copy2(B/(name+'.pdf'),OUT/output)
    shutil.copy2(B/(name+'.tex'),OUT/(name+'.tex'))
shutil.copy2(B/'figure-manifest.json',OUT/'figure-manifest.json')
shutil.copytree(B/'source', OUT/'source', dirs_exist_ok=True)
for item in used:
    dest=OUT/item['file']
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(B/item['file'],dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==item['sha256']
shutil.copy2(Path(__file__),OUT/'source/build_checkpoint.py')
for name in ['gmcm2026.cls','gmcm-numerical.bst']:
    shutil.copy2(B/name,OUT/name)
shutil.copytree(T/'fonts',OUT/'fonts',dirs_exist_ok=True)
receipt={'version':VERSION,'checkpoint':CHECKPOINT,'source_hashes':
         {k:hashlib.sha256(v).hexdigest() for k,v in snapshot.items()},
         'tex_sha256':hashlib.sha256(tex.encode()).hexdigest(),
         'template_hashes':{str(f.relative_to(T)):hashlib.sha256(f.read_bytes()).hexdigest()
                            for f in T.rglob('*') if f.is_file() and (f.suffix in ['.cls','.bst','.ttf','.otf'])},
         'citations_in_display_order':citation_order,'uncited_references':sorted(uncited),
         'code_files':len(code_manifest['files']),
         'pdf_sha256':hashlib.sha256((OUT/('anonymous-paper-'+VERSION+'.pdf')).read_bytes()).hexdigest()}
(OUT/'build-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(OUT/('anonymous-paper-'+VERSION+'.pdf'))
