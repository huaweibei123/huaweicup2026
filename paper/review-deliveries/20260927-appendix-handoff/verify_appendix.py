"""Independently extract all actual PDF rows and compare with frozen CSV.
AI-assisted using OpenAI Codex; exact model/release date unverified.
Requires PyMuPDF; does not run the solver or official evaluator.
"""
import argparse, collections, csv, hashlib, json, re
from pathlib import Path
import pymupdf

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--graphs',type=Path,help='Optional directory containing official case_001.json ... case_100.json')
    args=ap.parse_args(); root=args.directory
    rows=list(csv.DictReader((root/'all-results.csv').open(encoding='utf-8-sig')))
    source={(r['problem'],int(r['cores']),r['case_id']):r for r in rows}
    assert len(rows)==len(source)==1500
    pdf=pymupdf.open(root/'case-results-appendix.pdf')
    found={}; unknown=[]; duplicate=[]; captions=[]; current=None; visual_rows=0; deltas=[]; bounds=[]
    for pi,page in enumerate(pdf):
      groups=[]
      for w in sorted(page.get_text('words'),key=lambda w:(round(w[1],1),w[0])):
        g=next((g for g in reversed(groups[-4:]) if abs(g[0]-w[1])<2),None)
        if g is None:groups.append([w[1],[w]])
        else:g[1].append(w)
      last_y=None
      for y,words in sorted(groups):
        line=' '.join(w[4] for w in sorted(words,key=lambda w:w[0]))
        cap=re.search(r'问题\s*([123])、\s*([1-5])\s*个核心',line)
        if cap:
          current=(f'P{cap[1]}',int(cap[2]));captions.append({'problem':current[0],'cores':current[1],'page':pi+1});last_y=None
        if not re.match(r'^\d{3}\s',line):continue
        tokens=line.split(); recs=[]
        if current and current[0]!='P3' and len(tokens)==8:
          for off in [0,4]:recs.append(((*current,'main',tokens[off]),tokens[off+1:off+4]))
        elif current and current[0]=='P3' and len(tokens)==7:
          recs=[((*current,'no_l2',tokens[0]),tokens[1:3]),((*current,'main',tokens[0]),tokens[3:7])]
        else:unknown.append({'page':pi+1,'line':line});continue
        visual_rows+=1
        if last_y is not None:deltas.append(round(y-last_y,3))
        last_y=y
        for key,values in recs:
          if key in found:duplicate.append(key)
          found[key]={'values':values,'page':pi+1}
      for b in page.get_text('dict')['blocks']:
        if 'lines' not in b:continue
        for l in b['lines']:
          for s in l['spans']:
            if s['bbox'][0]<63 or s['bbox'][2]>533 or s['bbox'][1]<78 or s['bbox'][3]>810:
              bounds.append({'page':pi+1,'text':s['text'],'bbox':s['bbox']})
    expected={(p,k,'main',c) for p,k,c in source}|{('P3',k,'no_l2',c) for p,k,c in source if p=='P3'}
    mismatch=[]; cells=0
    for (p,k,kind,c),v in found.items():
      r=source[(p,k,c)]
      if kind=='no_l2': want=[r['no_l2_makespan_cycles'],r['no_l2_extra_ddr_bytes']]
      elif p=='P3':want=[r['makespan_cycles'],r['extra_ddr_bytes'],f"{100*float(r['cache_hit_rate_bytes']):.3f}",f"{float(r['solver_wall_seconds']):.3f}"]
      else:want=[r['makespan_cycles'],r['extra_ddr_bytes'],f"{float(r['solver_wall_seconds']):.3f}"]
      cells+=len(want)
      if v['values']!=want:mismatch.append({'key':[p,k,kind,c],'want':want,'actual':v})
    font_sizes=collections.Counter(round(s['size'],3) for pg in pdf for b in pg.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans'])
    graph_checks=0
    if args.graphs:
      hashes={f'{i:03}':hashlib.sha256((args.graphs/f'case_{i:03}.json').read_bytes()).hexdigest() for i in range(1,101)}
      for r in rows:assert r['graph_sha256']==hashes[r['case_id']];graph_checks+=1
    report={'pdf_pages':len(pdf),'source_csv_rows':len(rows),'configuration_records':len(found),'visual_data_rows':visual_rows,'numeric_cells_checked':cells,'missing':[list(k) for k in sorted(expected-set(found))],'extra':[list(k) for k in sorted(set(found)-expected)],'duplicates':duplicate,'unparsed_rows':unknown,'mismatches':mismatch,'page_boundary_violations':bounds,'font_sizes':dict(font_sizes),'row_baseline_deltas':collections.Counter(deltas).most_common(6),'tables':[{'problem':p,'cores':k,'pages':sorted({v['page'] for key,v in found.items() if key[:2]==(p,k)})} for p in ['P1','P2','P3'] for k in range(1,6)],'official_graph_hash_checks':graph_checks,'pdf_sha256':hashlib.sha256((root/'case-results-appendix.pdf').read_bytes()).hexdigest(),'data_sha256':hashlib.sha256((root/'all-results.csv').read_bytes()).hexdigest(),'scope':'Actual PDF compared against frozen CSV; no new solver/evaluator calls or full plan re-audit.'}
    (root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (root/'pdf-extracted-records.csv').open('w',encoding='utf-8',newline='') as f:
      w=csv.writer(f);w.writerow(['problem','cores','configuration','case','values','pdf_page'])
      for key,v in sorted(found.items()):w.writerow([*key,'|'.join(v['values']),v['page']])
    assert len(found)==2000 and cells==6000 and visual_rows==1000
    assert not any([report['missing'],report['extra'],duplicate,unknown,mismatch,bounds])
    assert abs(collections.Counter(deltas).most_common(1)[0][0]-15.6)<0.01
    print(json.dumps({k:report[k] for k in ['pdf_pages','configuration_records','visual_data_rows','numeric_cells_checked','official_graph_hash_checks','tables','row_baseline_deltas']}))

if __name__=='__main__':main()
