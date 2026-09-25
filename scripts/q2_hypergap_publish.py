"""One-shot hypergap case-group publisher; dry-run unless --publish is explicit."""
from __future__ import annotations

import argparse
import fcntl
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from q2_hypergap_export import ROOT, accepted_by_coordinate, export, read, sha

BRANCH = 'codex/q2-hypergraph-s8ee'
FIRST = '2442bf5bf7d3587ac0d53b80e43f53c0743c5aab'
DELIVERY = '9115855c7f3bf71db5da67be69fdc5881c7ea11b81d359eec68717fdbeb8394c'


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def cmd(argv, cwd=ROOT):
    return subprocess.check_output(argv, cwd=cwd, text=True, timeout=120).strip()


def write_journal(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def committed_source():
    if cmd(['git', 'branch', '--show-current']) != BRANCH:
        raise ValueError('Wrong archive branch')
    if cmd(['git', 'diff', '--cached', '--name-only']):
        raise ValueError('Git index is not empty')
    for name in ('scripts/q2_hypergap_export.py', 'scripts/q2_hypergap_publish.py'):
        if (ROOT/name).read_bytes() != subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=ROOT):
            raise ValueError('Uncommitted publisher/exporter source: '+name)


def group_commit(folder):
    return cmd(['git', 'log', '-1', '--format=%H', '--', folder.relative_to(ROOT).as_posix()])


def first_committed_bytes(folder):
    relative = folder.relative_to(ROOT).as_posix()
    if group_commit(folder) != FIRST:
        raise ValueError('Existing first group commit differs')
    paths = cmd(['git', 'ls-tree', '-r', '--name-only', FIRST, '--', relative]).splitlines()
    disk = sorted(p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file())
    if sorted(paths) != disk:
        raise ValueError('Existing first group file set differs')
    for name in paths:
        if (ROOT/name).read_bytes() != subprocess.check_output(['git', 'show', FIRST+':'+name], cwd=ROOT):
            raise ValueError('Existing first group bytes differ: '+name)
    remote = cmd(['git', 'ls-remote', 'origin', 'refs/heads/'+BRANCH]).split()[0]
    subprocess.check_call(['git', 'merge-base', '--is-ancestor', FIRST, remote], cwd=ROOT)


def run(args):
    summary_raw = args.summary.read_bytes()
    summary = json.loads(summary_raw)
    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    old_ref = manifest['baseline_manifest']
    old_raw = (ROOT/old_ref['path']).read_bytes()
    if (sha(old_raw) != old_ref['sha256'] or summary['manifest_sha256'] != sha(manifest_raw)):
        raise ValueError('Manifest identity differs')
    selected = accepted_by_coordinate(summary, json.loads(old_raw))
    groups = [(lo, lo+9) for lo in range(1, 101, 10)
              if all((f'{c:03d}', k) in selected for c in range(lo, lo+10) for k in range(1,6))]
    print(json.dumps({'complete_groups': [f'{a:03d}-{b:03d}' for a,b in groups],
                      'mode': 'publish' if args.publish else 'dry-run'}, ensure_ascii=False))
    if not args.publish:
        return
    if (not args.once or args.branch != BRANCH or not args.journal.is_relative_to(ROOT/'output')
            or not args.output_root.is_relative_to(ROOT/'results/a/q2-nikolastarx')):
        raise ValueError('Explicit --once, fixed branch and scoped paths required')
    committed_source()
    state = read(args.journal) if args.journal.exists() else {
        'run_id': args.run_id, 'manifest_sha256': sha(manifest_raw), 'branch': BRANCH, 'groups': {}}
    if (state['run_id'] != args.run_id or state['manifest_sha256'] != sha(manifest_raw)
            or state['branch'] != BRANCH):
        raise ValueError('Journal identity differs')
    first_folder = args.output_root/'cases-001-010'
    if args.existing_first:
        first_committed_bytes(first_folder)
        state['groups'].setdefault('001-010', {'commit': FIRST, 'delivery_id': DELIVERY,
                                               'source': 'preexisting_pushed_enqueued'})
        write_journal(args.journal, state)
    elif first_folder.exists():
        raise ValueError('First group exists; require --existing-first verification')
    for lo, hi in groups:
        key = f'{lo:03d}-{hi:03d}'
        if key == '001-010' and args.existing_first:
            continue
        folder = args.output_root/f'cases-{key}'
        step = state['groups'].setdefault(key, {})
        if 'delivery_id' in step:
            if group_commit(folder) != step['commit']:
                raise ValueError('Enqueued group commit differs')
            continue
        committed_source()
        if 'feed' not in step:
            receipt = export(args.summary,args.manifest,args.output_root,args.run_id,lo,hi,
                             args.producer_session,args.task_url,args.runtime_id,args.source_reference)
            step.update(feed=receipt['feed'],summary_sha256=receipt['summary_sha256'],export_utc=now(),
                        last_e0_utc=max(read(args.summary.parent/f'{c:03d}-k{k}/e0-process/process.json')['finished_at']
                                        for c in range(lo,hi+1) for k in range(1,6)))
            write_journal(args.journal,state)
        if 'preflight_utc' not in step:
            verdict = json.loads(cmd([sys.executable,'src/benchmark_board/protocol.py',step['feed'],'--submission']))
            if not verdict.get('valid') or verdict.get('eligible') != 50 or verdict.get('records') != 50:
                raise ValueError('Board preflight not 50/50 eligible')
            step['preflight_utc']=now();write_journal(args.journal,state)
        if sys.platform == 'darwin':
            cmd(['dot_clean',str(folder)])
        if any(p.name.startswith('._') or p.name == '.DS_Store' for p in folder.rglob('*')):
            raise ValueError('Archive metadata remains')
        committed_source()
        if 'commit' not in step:
            if folder.exists() and group_commit(folder) and not cmd(['git','status','--porcelain','--',folder.relative_to(ROOT).as_posix()]):
                step['commit']=group_commit(folder)
            else:
                cmd(['git','add','--',folder.relative_to(ROOT).as_posix()])
                staged=cmd(['git','diff','--cached','--name-only']).splitlines()
                prefix=folder.relative_to(ROOT).as_posix()+'/'
                if not staged or any(not name.startswith(prefix) for name in staged):
                    raise ValueError('Unexpected staged paths')
                cmd(['git','commit','-q','-m',f'Archive hypergap cases {key}'])
                step['commit']=cmd(['git','rev-parse','HEAD'])
            step['commit_utc']=now();write_journal(args.journal,state)
        if group_commit(folder) != step['commit']:
            raise ValueError('Group commit drift')
        if 'push_utc' not in step:
            cmd(['git','push','origin',step['commit']+':refs/heads/'+BRANCH]);step['push_utc']=now()
            write_journal(args.journal,state)
        if 'delivery_id' not in step:
            delivery=cmd([str(args.sync_python),'-m','src.benchmark_sync','--config',str(args.sync_config),
                          'enqueue','--repo',str(ROOT),'--commit',step['commit'],'--feed',step['feed']],cwd=args.sync_root)
            if len(delivery)!=64 or any(c not in '0123456789abcdef' for c in delivery):
                raise ValueError('Enqueue returned no canonical delivery ID')
            step.update(delivery_id=delivery,enqueue_utc=now());write_journal(args.journal,state)
        print(json.dumps({'group':key,'commit':step['commit'],'delivery_id':step['delivery_id']}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('summary','manifest','output-root','journal','sync-root','sync-python','sync-config'):
        p.add_argument('--'+name,required=True,type=Path)
    for name in ('run-id','producer-session','task-url','runtime-id','source-reference'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--branch',default=BRANCH)
    p.add_argument('--once',action='store_true')
    p.add_argument('--publish',action='store_true')
    p.add_argument('--existing-first',action='store_true')
    a=p.parse_args()
    for name in ('summary','manifest','output_root','journal','sync_root','sync_python','sync_config'):
        setattr(a,name,getattr(a,name).absolute() if name == 'sync_python' else getattr(a,name).resolve())
    if a.publish:
        if not a.journal.is_relative_to(ROOT/'output'):
            raise ValueError('Journal must remain under output/')
        a.journal.parent.mkdir(parents=True, exist_ok=True)
        with a.journal.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(a)
    else:
        run(a)


if __name__ == '__main__':
    main()
