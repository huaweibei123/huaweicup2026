#!/usr/bin/env python3
"""Package the already reviewed paper checkpoint; no experiment execution."""
from pathlib import Path
import csv, hashlib, json, re, subprocess, zipfile, os
P=Path(__file__).resolve().parents[1]
CHECKPOINT=os.environ.get('PAPER_CHECKPOINT','checkpoint-02')
O=P/'checkpoints'/CHECKPOINT; B=P/'build'/CHECKPOINT; T=P.parent/'template-2026'
figures=json.loads((O/'figure-manifest.json').read_text())
files={}
for name in ['anonymous-paper-v1.pdf','result-tables.pdf']:
    p=O/name
    info=subprocess.check_output(['pdfinfo',str(p)],text=True)
    files[name]={'pages':int(re.search(r'Pages:\s+(\d+)',info)[1]),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for name in ['main','result-tables']:
    log=(B/(name+'.log')).read_text()
    warnings=re.findall(r'^.*(?:Overfull|Undefined|undefined|Missing character|too large|Warning).*$',log,flags=re.M)
    assert not warnings, warnings
rows=list(csv.DictReader((P/'data/all-results.csv').open()))
assert len(rows)==1500
for q in ['P1','P2','P3']:
    for k in range(1,6):
        assert len([r for r in rows if r['problem']==q and int(r['cores'])==k])==100
receipt={'date':'2026-09-26','stage':'annotation-frozen complete draft; independent language and scientific acceptance pending','files':files,'figure_files':len(figures),'numbered_figures':len({f['label'] for f in figures}),'data_rows':len(rows),'compile_warning_checks':'passed','new_solver_and_evaluator_calls':0,'visual_review':'All 31 main-paper pages rendered and reviewed in contact sheets; mechanism labels checked from native PNG, short result tables and proof marks checked. Supplement: 57-page structure and 1500-row identities checked; no new claim of independent scientific or language acceptance.','pending':['Fang figure inventory reply and duplicate comparison','independent scientific review','runnable fixed-algorithm submission package','L01–L13 independent sentence/paragraph review, user PDF annotations and private cover data']}
(O/'validation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(O/'review-package.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['anonymous-paper-v1.pdf','result-tables.pdf','README.md','validation.json','figure-manifest.json']:
        z.write(O/name,name)
    for name in ['main.tex','result-tables.tex']:z.write(O/name,'source/'+name)
    for name in ['gmcm2026.cls','gmcm-numerical.bst']:z.write(T/name,'source/'+name)
    for f in sorted((T/'fonts').iterdir()):
        if f.is_file() and not f.name.startswith(('.', '._')):z.write(f,'source/fonts/'+f.name)
    for f in figures:z.write(P/f['file'],'source/'+f['file'])
    for name in ['all-results.csv','source-receipt.json','summary.json']:
        if (P/'data'/name).exists():z.write(P/'data'/name,'data/'+name)
    for f in sorted((P/'chapters').glob('*.md')):z.write(f,'manuscript/'+f.name)
    for name in ['FIGURE_PRODUCTION_PROTOCOL.md','TERMINOLOGY.md','VALIDATION.md']:z.write(P/name,'manuscript/'+name)
with zipfile.ZipFile(O/'review-package.zip','a',zipfile.ZIP_DEFLATED) as z:
    for f in sorted((P/'review').glob('*')):
        if f.is_file() and f.suffix in ('.json','.diff','.md'): z.write(f,'review/'+f.name)
    for name in ['annotation-lock.json']:
        if (O/name).exists(): z.write(O/name,name)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
print('Review ZIP:',(O/'review-package.zip').stat().st_size,'bytes')
