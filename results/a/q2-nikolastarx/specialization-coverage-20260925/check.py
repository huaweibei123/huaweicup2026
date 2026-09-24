"""Recognize structures only on all100 graphs; no candidate construction/scoring."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sys,time
from unittest.mock import patch
from contextlib import ExitStack
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure
from src.q2_nikolastarx.tree_frontier import _guard
from src.q2_nikolastarx.vector_lanes import recognize
HOME=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (HOME/'coverage.json').exists()
 started=time.perf_counter();rows=[]
 sources={s:sha(ROOT/s) for s in ['src/q2_nikolastarx/dag_direct.py','src/q2_nikolastarx/direct.py','src/q2_nikolastarx/tree_frontier.py','src/q2_nikolastarx/vector_lanes.py']}
 official={f['path']:f['sha256'] for f in json.loads((ROOT/'docs/a/source-manifest.json').read_text())['files']}
 with ExitStack() as guard:
  for entry in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:guard.enter_context(patch(entry,side_effect=AssertionError('No scoring')))
  for number in range(1,101):
   case=f'{number:03}';path=ROOT/f'data/raw/a/official/data/case_{case}.json';digest=sha(path);assert digest==official[f'data/case_{case}.json']
   ix=DAGIndex(json.loads(path.read_bytes()));row=dict(case=case,graph_sha256=digest,ops=len(ix.ops),components=len(ix.components))
   for name,check in [('tree',_guard),('vector',recognize),('word',lambda x:x.word_descriptor())]:
    try:
     result=check(ix);row[name]=True
     if name=='vector':row['lanes']=len(result['anchors']);row['stages']=len(result['stages'])
    except UnsupportedStructure as e:row[name]=False;row[name+'_reason']=str(e)
   rows.append(row)
 report=dict(created_at=datetime.now(timezone.utc).isoformat(),source_sha256=sources,script_sha256=sha(Path(__file__)),rows=rows,recognized={name:[r['case'] for r in rows if r[name]] for name in ['tree','vector','word']},elapsed_seconds=time.perf_counter()-started,actual_calls=dict(candidate=0,E0=0,E1=0,E2=0),scope='source/hash-checked structural recognition, not runtime feasibility or score')
 (HOME/'coverage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['rows','source_sha256']},indent=2))
if __name__=='__main__':main()
