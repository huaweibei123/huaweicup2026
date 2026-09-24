#!/usr/bin/env python3
"""Adapter for a LOCAL checkout of the named frozen commit; NOT executed here.

The fixed fallback is the repository's bounded_tasks.construct with explicitly
frozen parameters. This adapter never looks up historical plans or scores.
It verifies Git blob identities of the official and fallback Python files.
Online official E0 call budget: ZERO. E0 remains an external acceptance test.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from p1_phase_cut import FROZEN_COMMIT,atomic_json,integrate_construct

def git_blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def verify_checkout(root):
    paths=['data/raw/a/official/code','src/q1']
    output=subprocess.check_output(['git','-C',str(root),'ls-tree','-r',FROZEN_COMMIT,'--',*paths],text=True)
    matched=[]
    for row in output.splitlines():
        meta,path=row.split('\t',1);mode,kind,oid=meta.split()
        if kind=='blob' and path.endswith('.py'):
            file=root/path
            if not file.is_file() or git_blob(file.read_bytes())!=oid:raise ValueError('Frozen file identity mismatch: '+path)
            matched.append(path)
    if not matched:raise ValueError('Frozen commit missing from local Git object database')
    # Match the configuration read in this study, not an arbitrary current file.
    config=root/'data/raw/a/official/data/config.txt'
    if git_blob(config.read_bytes())!='94e7b0cd981d709e676c6b1a8dd5ae66bd3abc5c':raise ValueError('Fixed config identity mismatch')
    return matched

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path);p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--cores',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--diagnostics',type=Path,required=True)
    a=p.parse_args();root=a.repo.resolve();verified=verify_checkout(root)
    # Keep this source directory importable; add only the verified repository.
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'data/raw/a/official/code'))
    from src.q1.bounded_tasks import construct as bounded
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order,validate_graph
    graph=json.loads(a.graph.read_text());validate_graph(graph)
    fallback=lambda g,k:bounded(g,k,packet_factor=4,trigger_ops=4096,chunk_ops=1024)
    plan,info=integrate_construct(graph,a.cores,60,{'L1':524288,'UB':131072},fallback,gate=100)
    validate_task_order(derive_multicore_plan(graph,plan))
    info['frozen_commit']=FROZEN_COMMIT;info['verified_python_file_count']=len(verified)
    info['official_E0_calls']=0
    atomic_json(a.output,plan);atomic_json(a.diagnostics,info)
if __name__=='__main__':main()
