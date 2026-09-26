#!/usr/bin/env python3
"""Apply the reviewed v10 outline to Markdown and TeX without rewriting prose.

Inputs are a frozen checkpoint; outputs go to a new directory. Heading/source
maps are regenerated from actual positions. No network or evaluator is used.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

COMMANDS = {1: 'section', 2: 'subsection', 3: 'subsubsection', 4: 'paragraph'}
RENAMES = {
 '01-problem.md': {
  '研究对象与优化目标': (2, '问题背景与优化目标'),
  '计算图的数据表示与数据依赖': (3, '计算图表示与数据依赖'),
  '硬件执行资源与计算通信重叠': (3, '执行资源与计算通信重叠'),
  '计算操作切分与调度方案表示': (3, '子图划分与调度方案'),
  '多核调度核心难点与求解思路': (2, '问题分析与求解思路'),
 },
 '02-assumptions.md': {
  '硬件参数与执行约束': (2, '模型假设与执行约束'),
  '原始张量、物理副本与逻辑标识约定': (2, '张量与物理副本的表示'),
  '主要符号': (2, '符号说明'),
  '性能评价指标与统计方法': (2, '评价指标与计算方法'),
  '执行完成时间与加速比指标': (3, '完成时间与多核加速比'),
  '额外数据搬运量与缓存命中率': (3, '额外DDR搬运量与缓存命中率'),
  '求解耗时度量与运行时间建议': (3, '端到端求解耗时'),
  '评测程序分工与在线调用预算': (3, '评测方法与调用预算'),
 },
 '03-framework.md': {
  '计算图切分与调度模型': (1, '多核调度的数学模型与求解框架'),
  '多核切分与调度形式化模型': (2, '多核切分与调度模型'),
  '三个问题的通用求解策略与递进关系': (3, '结构化候选方案的构造与筛选'),
  '相关研究与编译优化技术对比': (3, '相关研究与方法适用性'),
  '调度方案拓扑无环性判定准则': (3, '扩展依赖图的无环性判定'),
  '总体完成时间下界与候选剪枝准则': (3, '完成时间下界与候选剪枝'),
  '求解时间组成与计算复杂度分析': (2, '求解耗时与计算复杂度'),
 },
 '04-p1.md': {
  '问题一：子图独立执行场景下的多核切分与调度': (1, '问题一：独立任务执行下的多核调度'),
  '问题分析与硬件时序约束': (2, '问题分析与时序约束'),
  '基础调度方案生成与结构化细化': (2, '结构化候选方案的构造'),
  '支路重分配算法与无环性证明': (2, '基于支路重分配的调度优化'),
  '拓扑波次划分与支路角色识别': (3, '拓扑波次与支路识别'),
  '依赖关系与全序构建规则': (3, '执行全序的构造'),
  '调度依赖图的无环性证明': (3, '调度依赖图的无环性证明'),
  '搜索规模控制与方案采纳准则': (2, '候选规模与采纳准则'),
  '实验结果与案例分析': (2, '结果与分析'),
  '全量基准评测结果分析': (3, '全量用例的性能比较'),
  '典型算例微架构时序分析（case_026）': (3, '典型算例的执行时序分析'),
 },
 '05-p2.md': {
  '问题二：联合安排计算位置与数据搬运': (1, '问题二：数据复用下的多核调度'),
  '问题分析与片上数据复用权衡': (2, '问题分析与数据复用约束'),
  '核心分配与复制量模型': (2, '基于超图的复制量模型'),
  '基于空闲区间的算子初始分配': (3, '基于空闲区间的初始分配'),
  '基于超图连接度模型的复制量度量': (3, '超图表示与适用条件'),
  '超图模型定义与适用范围': (4, '模型定义与适用条件'),
  '超边构成与权值定义': (3, '超边与复制代价'),
  '换入换出前原始复制字节数公式': (4, '换入换出前的原始复制字节数'),
  '链分组移动的增量更新法则': (3, '链分组移动的代价增量'),
  '局部超图割优化算法': (3, '局部超图割与辅助流网络'),
  '辅助流网络构建与等价映射': (4, '辅助网络构造与等价性'),
  '流水线工作量上限约束与超额回退': (3, '流水线工作量约束与回退'),
  '算法设计与时间复杂度分析': (2, '基于局部最小割的模型求解'),
  '多阶段候选方案生成与优选': (3, '候选方案生成与择优'),
  '算法时间复杂度与开销分析': (3, '时间复杂度分析'),
  '实验结果与反例分析': (2, '结果与分析'),
  '全量基准实验结果与分析': (3, '全量用例的性能比较'),
  '搬运量与完成时间权衡反例分析（C04）': (3, '搬运量与完成时间的权衡分析'),
 },
 '06-p3.md': {
  '问题三：安排计算顺序并利用共享只读Cache': (1, '问题三：共享只读缓存下的多核调度'),
  '共享只读缓存的访问规则与硬件时序': (2, '问题分析与缓存访问约束'),
  '归约树计算建模与排序准则': (2, '基于归约树的存储峰值模型'),
  '归约树结构与数据存储峰值': (3, '归约树表示与存储峰值'),
  '非交错子树最优处理次序及证明': (3, '非交错子树的最优排序及证明'),
  '归约树森林的结构匹配与执行定序': (3, '归约树识别与执行序列构造'),
  '归约树森林的结构判定准则': (4, '归约树森林的结构判定'),
  '核心指派与后序遍历序列生成': (4, '核心分配与后序遍历'),
  '求解算法设计与在线优选': (2, '基于归约树排序的模型求解'),
  '级联候选方案生成流程': (3, '分层候选方案构造'),
  '多层级候选方案生成算法': (4, '候选方案的生成次序'),
  '评测调用控制与终止状态分类': (4, '评测预算与终止条件'),
  '固定候选方案的完成时间下界': (3, '固定候选方案的完成时间下界'),
  '静态下界模型与时序不等式构建': (4, '必要时序不等式与下界计算'),
  '完整算法流程与在线择优': (3, '在线择优与回退'),
  '算法时间复杂度分析': (3, '时间复杂度分析'),
  '实验结果与反例分析': (2, '结果与分析'),
  '共享缓存性能收益配对实验': (3, '共享缓存的配对实验'),
  '启发式选择条件消融与反例分析（R9F）': (3, '启发式选择条件的消融分析'),
 },
 '07-experiments.md': {
  '实验结果与分析': (1, '综合实验与结果分析'),
  '实验基准、对比设定与统计口径': (2, '实验设置'),
  '三个问题的多核加速比综合对比': (3, '多核加速比比较'),
  '算法求解耗时与评测调用次数统计': (3, '求解耗时与评测开销'),
  '算法版本演进对比与消融分析': (3, '算法版本比较与消融'),
  '理论完成时间下界与最优性差距': (3, '完成时间下界与最优性差距'),
  '实验结论适用范围与局限性分析': (3, '实验结论的适用范围'),
 },
 '08-conclusion.md': {
  '方法评价与结论': (1, '模型评价与总结'),
  '研究工作与主要方法总结': (2, '方法特点'),
  '全量实验结果与性能总结': (2, '主要结果'),
  '方法适用范围与局限性分析': (2, '模型局限性'),
  '全文结语': (2, '结论'),
 },
}

def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()

def headings(text, kind):
    result = []
    fence = False
    offset = 0
    for i, line in enumerate(text.splitlines(keepends=True), 1):
        if kind == 'md' and line.startswith('```'):
            fence = not fence
        if not fence:
            pat = r'^(#{1,4}) (.+?)\s*$' if kind == 'md' else r'^\\(section|subsection|subsubsection|paragraph)\{(.+)\}\s*$'
            m = re.match(pat, line.rstrip('\n'))
            if m:
                level = len(m[1]) if kind == 'md' else next(k for k,v in COMMANDS.items() if v == m[1])
                title = m[2].replace(r'\_', '_')
                title = re.sub(r'^\d+\. ', '', title)
                result.append(dict(level=level,title=title,start=offset,end=offset+len(line),line=i,raw=line))
        offset += len(line)
    return result

def header(level, title, kind):
    if kind == 'md':
        return '#' * level + ' ' + title + '\n'
    return '\\' + COMMANDS[level] + '{' + title.replace('_',r'\_') + '}\n'

def locate(text, title, kind):
    hits=[h for h in headings(text,kind) if h['title']==title]
    if len(hits)!=1:
        raise ValueError(f'{kind}: expected unique heading {title!r}, found {len(hits)}')
    return hits[0]

def insert_before(text, anchor, level, title, kind):
    if text.count(anchor)!=1:
        raise ValueError(f'non-unique body anchor: {anchor}')
    pos=text.index(anchor)
    # Insert before the complete paragraph, never inside a formula or sentence.
    pos=text.rfind('\n',0,pos)+1
    return text[:pos]+header(level,title,kind)+'\n'+text[pos:]

def before_heading(text, target, level, title, kind):
    h=locate(text,target,kind)
    return text[:h['start']]+header(level,title,kind)+'\n'+text[h['start']:]

def after_heading(text, target, level, title, kind):
    h=locate(text,target,kind)
    return text[:h['end']]+'\n'+header(level,title,kind)+text[h['end']:]

def transform(text, filename, kind):
    # Move complete, unedited source blocks; preserve every diagram and equation.
    if filename=='05-p2.md':
        titles=['核心分配与复制量模型','基于空闲区间的算子初始分配',
                '基于超图连接度模型的复制量度量','局部超图割优化算法',
                '算法设计与时间复杂度分析','多阶段候选方案生成与优选','实验结果与反例分析']
        a,b,c,d,e,f,g=[locate(text,t,kind) for t in titles]
        pieces=[text[a['end']:b['start']],text[b['start']:c['start']],
                text[c['start']:d['start']],text[d['start']:e['start']],
                text[e['end']:f['start']],text[f['start']:g['start']]]
        # The old initial-assignment tail introduces the copy model: move that
        # exact paragraph to the model opening, so "后续" still points forward.
        intro=''
        if kind=='tex':
            pat=r'同一个核心保留数据与在不同核心之间复制数据的区别见图[^\n]+\n\n'
            matches=list(re.finditer(pat,pieces[1]))
            if len(matches)!=1: raise ValueError('copy-model transition not found')
            m=matches[0];intro=m[0];pieces[1]=pieces[1][:m.start()]+pieces[1][m.end():]
        text=(text[:a['start']]+a['raw']+'\n'+intro+pieces[2]
              +e['raw']+pieces[0]+pieces[1]+pieces[3]+pieces[4]+pieces[5]+text[g['start']:])
    if filename=='06-p3.md':
        a=locate(text,'归约树森林的结构匹配与执行定序',kind)
        b=locate(text,'求解算法设计与在线优选',kind)
        c=locate(text,'级联候选方案生成流程',kind)
        text=text[:a['start']]+text[b['start']:c['start']]+text[a['start']:b['start']]+text[c['start']:]
    rename=RENAMES.get(filename,{})
    for h in reversed(headings(text,kind)):
        if h['title'] in rename:
            level,title=rename[h['title']]
            text=text[:h['start']]+header(level,title,kind)+text[h['end']:]
    if filename=='01-problem.md':
        text=before_heading(text,'计算图表示与数据依赖',2,'计算图与硬件执行约束',kind)
    elif filename=='03-framework.md':
        text=after_heading(text,'多核切分与调度模型',3,'决策变量与方案表示',kind)
        text=insert_before(text,'为了严谨刻画多核心场景下',3,'数据依赖与执行顺序约束',kind)
        text=insert_before(text,'在方案满足拓扑无环性及格式规范的前提下',3,'目标函数与可行域',kind)
        text=before_heading(text,'结构化候选方案的构造与筛选',2,'求解框架与方法选择',kind)
        text=before_heading(text,'扩展依赖图的无环性判定',2,'可行性判定与完成时间下界',kind)
    elif filename=='04-p1.md':
        text=after_heading(text,'结构化候选方案的构造',3,'基础候选方案',kind)
        text=insert_before(text,'在上述基础方案的基础上',3,'多级细化与在线择优',kind)
    elif filename=='07-experiments.md':
        text=before_heading(text,'多核加速比比较',2,'求解质量与计算效率',kind)
        text=before_heading(text,'算法版本比较与消融',2,'方法比较与局限性',kind)
    return text

def body_lines(text,kind):
    skip={h['line'] for h in headings(text,kind)}
    return Counter(l for i,l in enumerate(text.splitlines(),1) if i not in skip and l.strip())

def numbered(text,kind,chapter=0):
    counters=[chapter-1,0,0,0]
    out=[]
    for h in headings(text,kind):
        n=h['level']-1;counters[n]+=1
        for k in range(n+1,4):counters[k]=0
        h['number']='.'.join(map(str,counters[:n+1]))
        out.append(h)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();src=args.checkpoint;out=args.output
    out.mkdir(parents=True,exist_ok=True);(out/'chapters').mkdir(exist_ok=True)
    input_manifest=json.loads((out/'input-manifest.json').read_text())
    for relative,digest in input_manifest['files'].items():
        if sha((src/relative).read_bytes())!=digest: raise ValueError(f'input changed: {relative}')
    rows=[];validation=[];outline=[]
    tex=(src/'main.tex').read_text();original_tex=tex
    # Process TeX chapter ranges backwards because earlier ranges grow.
    sections=[h for h in headings(tex,'tex') if h['level']==1][:8]
    files=sorted(RENAMES)
    for idx in range(7,-1,-1):
        a=sections[idx]['start']
        b=sections[idx+1]['start'] if idx<7 else tex.index('\\begin{thebibliography}')
        part=tex[a:b];new=transform(part,files[idx],'tex')
        if body_lines(part,'tex')!=body_lines(new,'tex'):raise ValueError('TeX body changed: '+files[idx])
        tex=tex[:a]+new+tex[b:]
    tex=tex.replace(r'\setcounter{tocdepth}{2}',r'\setcounter{tocdepth}{3}'+'\n'+r'\setcounter{secnumdepth}{3}',1)
    tex=tex.replace('Paper review v10','Paper review v10 TOC structure',1)
    tex=tex.replace('审阅稿 v10','审阅稿 v10 · 目录结构修订',1)
    # Keep the short conclusion chapter together in the printed contents.
    tex=tex.replace(r'\section{模型评价与总结}',
                    r'\addtocontents{toc}{\protect\needspace{7\baselineskip}}'+'\n'
                    +r'\section{模型评价与总结}',1)
    for p in sorted((src/'source/chapters').glob('*.md')):
        old=p.read_text();new=transform(old,p.name,'md') if p.name in RENAMES else old
        if body_lines(old,'md')!=body_lines(new,'md'):raise ValueError('Markdown body changed: '+p.name)
        (out/'chapters'/p.name).write_text(new)
        validation.append(dict(file=p.name,nonheading_lines_preserved=True,source_sha256=sha(old),target_sha256=sha(new)))
        if p.name not in RENAMES:continue
        num=int(p.name[:2]);olds=numbered(old,'md',num);news=numbered(new,'md',num)
        texheads=headings(tex,'tex')
        for n in news:
            if n['level']<=3:outline.append('  '*(n['level']-1)+n['number']+' '+n['title'])
            candidates=[o for o in olds if RENAMES[p.name].get(o['title'],(o['level'],o['title']))[1]==n['title']]
            oldh=candidates[0] if candidates else None
            th=[h for h in texheads if h['title']==n['title']]
            # Repeated standard headings are disambiguated by chapter boundaries.
            ts=[h for h in texheads if h['level']==1][:8]
            lo=ts[num-1]['start'];hi=ts[num]['start'] if num<8 else tex.index('\\begin{thebibliography}')
            th=[h for h in th if lo<=h['start']<hi]
            if len(th)!=1:raise ValueError(f'cannot map TeX heading {p.name} {n["title"]}')
            following=next((line for line in new[n['end']:].splitlines()
                            if line.strip() and not re.match(r'^#{1,4} ',line)), '')
            anchor_hits=[i for i,line in enumerate(old.splitlines(),1) if line==following]
            source_anchor_line=anchor_hits[0] if len(anchor_hits)==1 else None
            oldtexheads=headings(original_tex,'tex')
            oldsections=[h for h in oldtexheads if h['level']==1][:8]
            oldlo=oldsections[num-1]['start']
            oldhi=oldsections[num]['start'] if num<8 else original_tex.index('\\begin{thebibliography}')
            oldth=[h for h in oldtexheads if oldlo<=h['start']<oldhi and oldh and h['title']==oldh['title']]
            rows.append(dict(id=f'TOC-{num:02d}-{len([r for r in rows if r["file"]==p.name])+1:03d}',
                file=p.name,old_title=oldh['title'] if oldh else None,old_number=oldh['number'] if oldh else None,
                old_line=oldh['line'] if oldh else None,new_title=n['title'],new_number=n['number'],
                new_line=n['line'],new_tex_line=th[0]['line'],level=n['level'],
                old_tex_line=oldth[0]['line'] if len(oldth)==1 else None,
                source_anchor_line=source_anchor_line,next_source_line=following,
                kind='renamed_or_reparented' if oldh else 'inserted_at_existing_boundary'))
    (out/'main.tex').write_text(tex)
    (out/'outline.md').write_text('# 修订目录\n\n目录显示三级；四级题头保留在正文，不进入目录。附录结构与v10一致。\n\n```text\n'+'\n'.join(outline)+'\n```\n')
    (out/'heading-map.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(dict(chapters=validation,
        manuscript_body_lines_preserved=True,tex_sha256=sha(tex),old_tex_sha256=sha(original_tex),
        changed_chapters=8,heading_count=len(rows),toc_depth=3,
        evaluator_calls=0,scientific_revalidation=False,human_acceptance=False),ensure_ascii=False,indent=2)+'\n')
    table=['# 目录与正文逐项对应','', '基准为冻结v10，行号分别指源Markdown与本次输出；新增父标题在原段落边界插入。','',
           '|新编号与标题|旧编号与标题|原Markdown行|新Markdown行|新TeX行|','|---|---|---:|---:|---:|']
    for r in rows:
        old=(r['old_number']+' '+r['old_title']) if r['old_title'] else '新增分组或段落题头'
        table.append(f'|{r["new_number"]} {r["new_title"]}|{old}|{r["file"]}:{r["old_line"] or "原段落边界"}|{r["new_line"]}|{r["new_tex_line"]}|')
    (out/'heading-map.md').write_text('\n'.join(table)+'\n')
    print(json.dumps({'output':str(out),'mapped_headings':len(rows),'body_preserved':True},ensure_ascii=False))

if __name__=='__main__':main()
