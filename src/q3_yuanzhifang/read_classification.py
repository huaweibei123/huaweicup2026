from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import argparse, gzip, hashlib, json, time

parser=argparse.ArgumentParser(description='Read-only reclassification of fixed archived cache events; no solver/evaluator.')
parser.add_argument('--graph-dir', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
raw=args.graph_dir
if args.output.exists(): raise SystemExit('output already exists; preserve previous audit')
t0=datetime.now(timezone.utc).isoformat(); clock=time.perf_counter()
rows=[]
for case, rel in [('067','pipeline-family-followup-20260925/067/pipeline_stages/P3/result.json.gz'),('044','pipeline-setup-followup-20260924/044/pipeline_cold_setup/P3/result.json.gz')]:
    gbytes=(raw/f'case_{case}.json').read_bytes(); g=json.loads(gbytes)
    eligible={o['id'] for o in g['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
    tensors={t['id']:t for t in g['tensors']}
    producers=defaultdict(set); consumers=defaultdict(set)
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a in eligible and b in tensors: producers[b].add(a)
        if a in tensors and b in eligible: consumers[a].add(b)
    # Independent characterization in these archived cases: input tensors
    # read by multiple eligible computations, with no eligible writer.
    shared={t for t in tensors if not producers[t] and len(consumers[t])>1}
    source=root/'results/a/q3-yuanzhifang'/rel
    packed=source.read_bytes(); body=gzip.decompress(packed); result=json.loads(body)
    observed=set(); totals=defaultdict(int); event_count=0
    for e in result['cache_events']:
        if e['event'] not in ('hit','miss'): continue
        assert e['op']=='COPY_IN'
        key=(e['core_id'],e['tensor_id'])
        label=('shared_' if e['tensor_id'] in shared else 'other_')+('repeat' if key in observed else 'first')
        totals[label]+=e['size_bytes']; observed.add(key); event_count+=1
    stats=result['cache_stats']; movement=result['data_movement_bytes']
    assert sum(totals.values())==stats['hit_bytes']+stats['miss_bytes']
    expected={'shared_first':3721600,'shared_repeat':202303488,'other_first':5452800,'other_repeat':0} if case=='067' else None
    if expected:
        assert {k:totals[k] for k in expected}==expected
    assert totals['shared_repeat']==movement['spill_added_copy_bytes']
    assert totals['other_repeat']==0
    rows.append(dict(case_id=case,result=source.relative_to(root).as_posix(),
        graph_sha256=hashlib.sha256(gbytes).hexdigest(),result_gzip_sha256=hashlib.sha256(packed).hexdigest(),
        result_raw_sha256=hashlib.sha256(body).hexdigest(),shared_input_tensor_count=len(shared),
        shared_consumer_counts=sorted({len(consumers[t]) for t in shared}),
        classified_copy_in_events=event_count,bytes=dict(totals),
        official_spill_bytes=movement['spill_added_copy_bytes'],equal_repeat_to_spill=True))
out=dict(schema='q3-pro-read-classification-local-audit-v1',started_at=t0,
    finished_at=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-clock,
    constructor_calls=0,derive_calls=0,Step_calls=0,E0_calls=0,rows=rows,
    driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Local independent reclassification of two archived P3 cache event lists only. No replay, new plan, performance claim or Pro attachment execution; not all eight trace validation.',
    inference_limit='Bytes exactly match shared logical-input repeat reads; equality alone is not a proof about every latent spill allocation or a counterfactual Makespan.')
dest=args.output
dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
