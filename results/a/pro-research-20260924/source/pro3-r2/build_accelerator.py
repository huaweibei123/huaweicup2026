"""Source-verified, event-preserving transformations. No float algebra rewrites.
Output is a separate source tree. Use --parts counters,depth,credits to ablate.
"""
from pathlib import Path
import argparse,ast,difflib,json,shutil
from runtime import ROOT,OFF,verify

def replace(s,a,b):
 if s.count(a)!=1:raise RuntimeError(f'expected one anchor, got {s.count(a)}: {a[:100]}')
 return s.replace(a,b)

def transform(name,s,parts):
 if name=='schedule_step1.py' and 'depth' in parts:
  tree=ast.parse(s);f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='precompute_depth')
  ls=s.splitlines(True)
  repl='''def precompute_depth(pred_map, succ_map, V):
    """Exact DAG longest-path depth via a topological sweep (same integer map)."""
    degree = {v: len(pred_map[v]) for v in V}
    depth = {v: 0 for v in V}
    queue = deque(v for v in V if degree[v] == 0)
    while queue:
        u = queue.popleft()
        du = depth[u] + 1
        for v in succ_map[u]:
            if du > depth[v]:
                depth[v] = du
            degree[v] -= 1
            if degree[v] == 0:
                queue.append(v)
    return depth
'''
  s=''.join(ls[:f.lineno-1])+repl+''.join(ls[f.end_lineno:])
 if name=='schedule_step3.py':
  if 'credits' in parts:
   s=replace(s,'from collections import Counter, defaultdict','from collections import Counter, defaultdict, deque')
   s=replace(s,'free_credits = {pos: [] for pos in capacity}','free_credits = {pos: deque() for pos in capacity}')
   s=replace(s,'credits.pop(0)','credits.popleft()')
  if 'counters' in parts:
   s=replace(s,"op_status = {op_id: 'pending' for op_id in op_by_id}","op_status = {op_id: 'pending' for op_id in op_by_id}\n    remaining_op_count = len(op_by_id)")
   s=replace(s,'    def retire_step():\n','    def retire_step():\n        nonlocal remaining_op_count\n')
   s=replace(s,"                    op_status[op_id] = 'done'\n","                    op_status[op_id] = 'done'\n                    remaining_op_count -= 1\n")
   s=replace(s,"if all(status == 'done' for status in op_status.values()):","if remaining_op_count == 0:")
 if name=='multicore_cut_evaluate_problem_1.py' and 'counters' in parts:
  s=replace(s,"    task_start, task_end = {}, {}","    task_start, task_end = {}, {}\n    remaining_tasks = len(tasks)\n    task_remaining = {tid: len(task['seq']) for tid, task in tasks.items()}\n    active_tasks = set()")
  s=replace(s,"        task_status[task_id] = 'active'","        task_status[task_id] = 'active'\n        active_tasks.add(task_id)")
  s=replace(s,'    def retire(now):\n','    def retire(now):\n        nonlocal remaining_tasks\n')
  s=replace(s,"                op_status[item] = 'done'","                op_status[item] = 'done'\n                task_remaining[task_id] -= 1")
  s=replace(s,"        for task_id, status in list(task_status.items()):\n            if status != 'active':\n                continue\n            task_items = [key(task_id, op_id) for op_id in tasks[task_id]['seq']]\n            if all(op_status[item] == 'done' for item in task_items):", "        # tasks are created in sorted task-id order; preserve completion order.\n        for task_id in sorted(active_tasks):\n            if task_remaining[task_id] == 0:")
  s=replace(s,"                task_status[task_id] = 'done'","                task_status[task_id] = 'done'\n                active_tasks.remove(task_id)\n                remaining_tasks -= 1")
  s=replace(s,"if all(status == 'done' for status in task_status.values()):","if remaining_tasks == 0:")
 return s

def build(parts,out):
 verify();out=Path(out);out.mkdir(parents=True,exist_ok=True);patch=[]
 for p in sorted((OFF/'code').glob('*.py')):
  original=p.read_text();changed=transform(p.name,original,parts);ast.parse(changed)
  (out/p.name).write_text(changed)
  patch.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='E0/'+p.name,tofile='R2/'+p.name))
 (out/'changes.diff').write_text(''.join(patch))
 return out
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--parts',default='counters,depth,credits');ap.add_argument('--out',default=str(ROOT/'fast_code'));a=ap.parse_args();build(set(a.parts.split(',')),a.out)
