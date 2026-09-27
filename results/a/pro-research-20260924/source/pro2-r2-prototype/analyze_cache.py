"""Extract positive witnesses from preserved, unmodified full Q3 E0 results."""
from pathlib import Path
import json,gzip,sys
ROOT=Path('/mnt/data/r2_research')
found=[]
for p in sorted((ROOT/'runs').glob('*/*/result.json.gz')):
    x=json.loads(gzip.decompress(p.read_bytes()))
    if 'cache_events' not in x:continue
    hits={};evicted={}
    for i,e in enumerate(x['cache_events']):
        item=(e.get('core_id'),e.get('op_id'))
        if e['event']=='hit':hits[item]=(i,e)
        if e['event']=='insert':
            if item in hits:
                hi,h=hits[item];key=e['tensor_id']
                found.append({'result':str(p),'hit_index':hi,'hit':h,'intervening_eviction':evicted.get(key),'reinsertion_index':i,'reinsertion':e})
            for key in e.get('evicted_tensor_ids',[]):evicted[key]={'event_index':i,'event':e}
        # Record an explicit eviction event if implementation later adds such a kind (not assumed).
    del x
(ROOT/'analysis/cache_hit_reinsertion_witnesses.json').write_text(json.dumps({'count':len(found),'witnesses':found[:20]},indent=2))
print('hit completion reinsertions:',len(found));print(json.dumps(found[:1],indent=2))
