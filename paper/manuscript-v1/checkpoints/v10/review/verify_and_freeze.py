import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import unicodedata

R=Path(__file__).resolve().parent
P=R.parents[1]
before=R/'before-chapters'
after=P/'chapters'
algorithm=re.compile(r'^::: algorithm[^\n]*\n.*?^:::\s*$',re.M|re.S)
code=re.compile(r'^::: algorithm[^\n]*\n```python\n(.*?)\n```',re.M|re.S)
digest=lambda raw:hashlib.sha256(raw).hexdigest()
records=[]
changed=[]
def width(line):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line)
for f in sorted(before.glob('*.md')):
    a=f.read_text();b=(after/f.name).read_text()
    if a!=b: changed.append(f.name)
    if f.name in ('04-p1.md','05-p2.md','06-p3.md'):
        assert algorithm.sub('<ALGORITHM>',a)==algorithm.sub('<ALGORITHM>',b),f.name
        old=list(code.finditer(a));new=list(code.finditer(b))
        assert len(old)==len(new)==2
        for x,y in zip(old,new):
            label=re.search(r'\{#([^ ]+)',y.group()).group(1)
            assert re.search(r'\{#([^ ]+)',x.group()).group(1)==label
            value=y.group(1)
            compile('def pseudocode():\n'+''.join('    '+s+'\n' for s in value.splitlines()),label,'exec')
            records.append(dict(label=label,chapter=f.name,
                                before_lines=len(x.group(1).splitlines()),after_lines=len(value.splitlines()),
                                before_bytes=len(x.group(1).encode()),after_bytes=len(value.encode()),
                                max_display_columns=max(map(width,value.splitlines())),
                                sha256=digest(value.encode())))
    elif f.name=='10-appendix.md':
        omit=lambda s: re.sub(r'^## 附录E .*\Z','<E>',re.sub(r'^### C\.1 .*?(?=^### C\.2 )','<C1>',s,flags=re.M|re.S),flags=re.M|re.S)
        assert omit(a)==omit(b),'appendix outside C1/E changed'
        tables=lambda s:[line for line in s.splitlines() if line.startswith('|')]
        assert tables(a)==tables(b),'appendix tables changed'
    else:
        assert a==b,f.name
assert len(records)==6
target=R/'content-source'
assert not (P/'checkpoints/v10/annotation-lock.json').exists(),'checkpoint already frozen'
target.mkdir(exist_ok=True)
for name in ['chapters','appendix-code','data','ai-disclosure']:
    shutil.copytree(P/name,target/name,dirs_exist_ok=True)
(target/'manuscript.md').write_text('\n\n'.join(f.read_text() for f in sorted((target/'chapters').glob('*.md'))))
doc=dict(scope='Six algorithms and source explanations; appendix C1/E; no other edits in this request',
    changed_files=changed, algorithms=records,
    before_lines=sum(x['before_lines'] for x in records),
    after_lines=sum(x['after_lines'] for x in records),
    chapter_hashes={f.name:digest(f.read_bytes()) for f in sorted((target/'chapters').glob('*.md'))},
    non_algorithm_prose_unchanged_this_request=True, appendix_tables_unchanged=True,
    inherited_draft='Current working manuscript, including earlier title/structure edits; this audit does not claim a new whole-paper language acceptance.',
    source_checks=['P1 independent Counter copies, lexicographic objective and fallback',
                   'P1 existing-task helpers and strict max-load reduction',
                   'P2 finite anchoring, initial feasibility and copy-cost guarantee',
                   'P2 fatal/skip distinction, valid copy evidence, strict lexical selection',
                   'P3 explicit retained-output recurrence and noninterleaved postorder',
                   'P3 shared budget, fixed-candidate lower bound and strict Makespan acceptance'],
    solver_calls=0,evaluator_calls=0,
    attachment=json.loads((P/'attachments/v10/attachment-receipt.json').read_text()))
(R/'independent-verification.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:doc[k] for k in ['changed_files','before_lines','after_lines']},ensure_ascii=False))
