"""Union all recorded pipe intervals to find genuinely all-pipe idle windows."""
import gzip
import hashlib
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent
RUN=OUT.parent/'tree-pilot-20260924/run'
rows=[]
for k in [2,4,5]:
 path=RUN/f'062-k{k}/final/result.json.gz'
 result=json.loads(gzip.decompress(path.read_bytes()))
 for c in result['per_core_timeline']:
  merged=[]
  for e in sorted(c['ops'],key=lambda e:(e['start'],e['end'])):
   if merged and e['start']<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],e['end'])
   else:merged.append([e['start'],e['end']])
  gaps=[{'start':a[1],'end':b[0],'cycles':b[0]-a[1]} for a,b in zip(merged,merged[1:])]
  rows.append({'cores':k,'core':c['core_id'],'all_pipe_idle_internal_sum':sum(g['cycles'] for g in gaps),
               'largest_all_pipe_idle':sorted(gaps,key=lambda g:-g['cycles'])[:5]})
report={'scope':'existing trace union gaps only, excludes tail after core task ends','calls':{'solver':0,'E0':0,'E1':0,'E2':0},
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':rows}
with (OUT/'core-idle.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
