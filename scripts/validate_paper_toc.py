#!/usr/bin/env python3
"""Verify compiled outline links against printed pages and precise source maps."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from pypdf import PdfReader, PdfWriter

def norm(s):
    return re.sub(r'\s+', '', s.replace(r'\_', '_'))

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def toc_entries(p):
    out=[]
    for line in p.read_text().splitlines():
        m=re.match(r'\\contentsline \{([^}]+)\}\{(.*)\}\{(\d+)\}\{([^}]+)\}',line)
        if not m:continue
        typ,title,page,dest=m.groups()
        nm=re.match(r'\\numberline \{([^}]+)\}(.*)',title)
        num=nm[1] if nm else None; title=nm[2] if nm else title
        out.append(dict(type=typ,title=title,number=num,page=int(page),destination=dest))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--review',type=Path,required=True)
    ap.add_argument('--build',type=Path,required=True)
    args=ap.parse_args();review=args.review;build=args.build
    reader=PdfReader(build/'paper-v10-toc.pdf')
    old=PdfReader(args.checkpoint/'anonymous-paper-v10.pdf')
    entries=toc_entries(build/'main.toc')
    firstbody=reader.get_destination_page_number(reader.named_destinations['section.1'])
    toc_start=reader.get_destination_page_number(reader.named_destinations['gmcm.contents.0']) if 'gmcm.contents.0' in reader.named_destinations else 1
    toc_pages=list(range(toc_start,firstbody))
    link_targets=set()
    for i in toc_pages:
        for annotation in reader.pages[i].get('/Annots',[]).get_object():
            a=annotation.get_object();action=a.get('/A',{}).get_object()
            target=action.get('/D',a.get('/Dest'))
            if isinstance(target,str):link_targets.add(target)
    visible=[e for e in entries if e['type']!='paragraph']
    failures=[]
    texts={}
    for e in visible:
        dest=reader.named_destinations.get(e['destination'])
        if dest is None:
            failures.append('missing destination '+e['destination']);continue
        page=reader.get_destination_page_number(dest)
        if reader.page_labels[page]!=str(e['page']):failures.append('page mismatch '+e['destination'])
        if e['destination'] not in link_targets:failures.append('missing contents link '+e['destination'])
        if e['number'] and re.match(r'^[1-8](?:\.|$)',e['number']):
            if page not in texts:texts[page]=norm(reader.pages[page].extract_text())
            if norm(e['title']) not in texts[page]:failures.append('heading absent on target page '+e['destination'])
    mapping=json.loads((review/'heading-map.json').read_text())
    oldtexts={}
    def old_text_page(fragment):
        hits=[]
        first=old.get_destination_page_number(old.named_destinations['section.1'])
        for i in range(first,len(old.pages)):
            if i not in oldtexts:oldtexts[i]=norm(old.pages[i].extract_text())
            if norm(fragment) in oldtexts[i]:hits.append(i+1)
        return hits[0] if len(hits)==1 else None
    for row in mapping:
        hits=[e for e in entries if norm(e['title'])==norm(row['new_title'])
              and (e['number']==row['new_number'] or
                   e['type']=='paragraph')]
        if len(hits)!=1:raise ValueError('new page map ambiguous: '+row['new_title'])
        row['new_pdf_page']=hits[0]['page'];row['destination']=hits[0]['destination']
        if row['old_number']:
            oldlevel=len(row['old_number'].split('.'))
            oldkey={1:'section',2:'subsection',3:'subsubsection',4:'paragraph'}[oldlevel]+'.'+row['old_number']
            dest=old.named_destinations.get(oldkey)
            row['old_pdf_page']=old.get_destination_page_number(dest)+1 if dest else old_text_page(row['old_title'])
        else:
            fragment=re.split(r'[$\\]',row['next_source_line'].replace('**',''))[0][:28]
            row['old_pdf_page']=old_text_page(fragment) if len(fragment)>8 else None
    (review/'heading-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    lines=['# 目录与正文的精确位置映射','',
           '页码为完整PDF中的印刷页码；本稿恰与物理页序相同。冻结v10与本次稿件分别定位，不串用旧批注坐标。',
           '新增父标题没有旧标题；“原文锚点”给出插入点后第一段原文的行号。完整逐字锚点见JSON。','',
           '|新编号与标题|新PDF页|旧编号与标题|旧PDF页|源文件|原文行/锚点|新Markdown行|新TeX行|',
           '|---|---:|---|---:|---|---:|---:|---:|']
    for r in mapping:
        prev=(r['old_number']+' '+r['old_title']) if r['old_title'] else '新增分组/段落标题'
        source=r['old_line'] or ('锚点 '+str(r['source_anchor_line']))
        lines.append(f'|{r["new_number"]} {r["new_title"]}|{r["new_pdf_page"]}|{prev}|{r["old_pdf_page"] or "—"}|{r["file"]}|{source}|{r["new_line"]}|{r["new_tex_line"]}|')
    (review/'heading-map.md').write_text('\n'.join(lines)+'\n')
    # A convenient contents extract carries original page numbers. Strip links
    # whose destinations lie outside the extract; full manuscript is clickable.
    writer=PdfWriter()
    for i in toc_pages:writer.add_page(reader.pages[i])
    writer.remove_annotations(subtypes='/Link')
    writer.add_metadata({'/Title':'论文目录结构修订（v10）','/Subject':'目录摘页；跳转请使用完整论文PDF'})
    with (build/'toc-only.pdf').open('wb') as f:writer.write(f)
    report=dict(source_pdf_sha256=digest(args.checkpoint/'anonymous-paper-v10.pdf'),
                pdf_sha256=digest(build/'paper-v10-toc.pdf'),toc_pdf_sha256=digest(build/'toc-only.pdf'),
                old_pages=len(old.pages),new_pages=len(reader.pages),toc_physical_pages=[i+1 for i in toc_pages],
                visible_toc_entries=len(visible),toc_links_verified=len(visible),
                main_text_heading_positions_verified=sum(e['number'] is not None and bool(re.match(r'^[1-8](?:\.|$)',e['number'])) for e in visible),
                mapped_source_headings=len(mapping),failures=failures,
                final_log_warnings=[l for l in (build/'compile-5.txt').read_text().splitlines()
                                    if any(s in l for s in ['Warning','Overfull','Missing character'])],
                scope='Source preservation, outline/page/link consistency; not scientific or whole-paper format acceptance')
    (review/'pdf-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if failures or report['final_log_warnings']:raise SystemExit(1)

if __name__=='__main__':main()
