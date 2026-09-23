"""Verify and package completed stage B evidence. Zero graph evaluations."""
from __future__ import annotations

import csv
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from .budget_search import ROOT, save, sha
from .stage_b import RUN, UNITS


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csv_write(path, rows):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def delivery_manifest():
    delivery={p.relative_to(RUN).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
              for p in sorted(RUN.rglob('*')) if p.is_file() and p.parts[len(RUN.parts)] not in UNITS
              and p.name!='delivery_manifest.json'}
    save(RUN/'delivery_manifest.json',delivery)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-only',action='store_true',help='refresh delivery identities after figures/receipts, without repackaging')
    args=parser.parse_args()
    if args.manifest_only:
        delivery_manifest()
        print('Refreshed final delivery manifest; zero E0 calls')
        return
    started=time.monotonic()
    stage=read(RUN/'stage.json')
    assert set(stage['units'])==set(UNITS)
    frozen=read(ROOT/'docs/a/source-manifest.json')
    checked={}
    for entry in frozen['files']:
        if entry['path'].startswith('code/') or entry['path'] in {
                'data/config.txt','data/case_002.json','data/case_008.json','data/case_044.json'}:
            original=ROOT/'data/raw/a/official'/entry['path']
            assert sha(original)==entry['sha256'] and original.stat().st_size==entry['bytes']
            checked[entry['path']]=entry
    save(RUN/'official-source-check.json',{'phase':'post-run verification, not backdated preflight',
        'source_manifest_sha256':sha(ROOT/'docs/a/source-manifest.json'),
        'official_code_hash':frozen['official_code_hash'],'checked_files':checked})
    outer={}
    for path in (RUN/'controller-output.jsonl',RUN/'controller-e503e61-output.jsonl'):
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            row=json.loads(line)
            if 'unit' in row and 'wall_through_stage_ledger' in row:
                outer[row['unit']]=row
    metrics,candidates,archives=[],[],{}
    code_versions={}
    (RUN/'plans').mkdir(exist_ok=True)
    for name in UNITS:
        folder=RUN/name
        summary=read(folder/'summary.json')
        ledger=read(folder/'calls.json')
        control=read(folder/'controller.json')
        assert summary['status']=='confirmed' and summary['full_repeat_equal']
        assert control['status']=='completed' and not control.get('remaining_job_pids')
        assert not control.get('worker_exit_with_descendants')
        assert ledger['charged']==len(ledger['calls'])==summary['calls_charged']<=32
        assert all(r['status']=='ok' and r['launched'] for r in ledger['calls'])
        assert ledger['calls'][0]['phase']=='initial' and ledger['calls'][-1]['phase']=='final'
        assert ledger['calls'][-1]['slot']==32
        assert outer[name]['wall_through_stage_ledger']<=600
        source=summary['head']
        if source not in code_versions:
            for path,identity in summary['source_hashes'].items():
                data=subprocess.check_output(['git','show',f'{source}:{path}'],cwd=ROOT)
                assert hashlib.sha256(data).hexdigest()==identity,path
            code_versions[source]=summary['source_hashes']
        assert code_versions[source]==summary['source_hashes']
        assert sha(ROOT/summary['graph'])==summary['graph_sha256']
        assert sha(ROOT/'data/raw/a/official/data/config.txt')==summary['config_sha256']
        for path,identity in read(folder/'artifacts.json').items():
            assert sha(folder/path)==identity['sha256'] and (folder/path).stat().st_size==identity['bytes']
        best=summary['incumbent']
        assert read(ROOT/best['output']/'result.json')==read(ROOT/summary['final']['output']/'result.json')
        assert all(sha(ROOT/r['plan'])==r['plan_sha256'] for r in ledger['calls'])
        baseline_plan=read(folder/'baseline/plan.json')
        def placement(plan):
            cores={sg:c for c,schedule in enumerate(plan['core_schedules']) for sg in schedule}
            return {op:cores[sg] for op,sg in plan['node_to_subgraph'].items()}
        if summary['method']=='M2':
            original=placement(baseline_plan)
            for plan in folder.glob('proposal-*/plan.json'):
                assert placement(read(plan))==original,plan
        duplicate=sum(p.get('outcome')=='duplicate_exact_plan' for p in summary['proposals'])
        generation_failures=sum(p.get('outcome')=='generation_failed' for p in summary['proposals'])
        initial=ledger['calls'][0]['makespan']
        chosen=next((p.get('specification','D') for p in summary['proposals']
                     if p['name']==Path(best['plan']).parent.name),'D')
        metric={'case':summary['case'],'method':summary['method'],'cores':4,'seed':0,
                'initial_cycles':initial,'best_cycles':best['makespan'],
                'reduction_percent':100*(initial-best['makespan'])/initial,
                'added_copy_bytes':best['movement']['added_copy_bytes'],
                'spill_bytes':best['movement']['spill_added_copy_bytes'],
                'calls':ledger['charged'],'unused_call_allowance':32-ledger['charged'],
                'duplicates':duplicate,'generation_failures':generation_failures,
                'worse_than_initial':sum(r['phase']=='explore' and r['makespan']>initial for r in ledger['calls']),
                'worst_cycles':max(r['makespan'] for r in ledger['calls']),
                'proposal_seconds':sum(p.get('wall_seconds',0) for p in summary['proposals']),
                'evaluation_seconds':sum(r['wall_seconds'] for r in ledger['calls']),
                'unit_seconds':outer[name]['wall_through_stage_ledger'],
                'controller_receipt_unit_seconds':stage['units'][name]['wall_through_controller_receipt'],
                'worker_tail_seconds':read(folder/'worker-completion.json')['worker_tail_seconds'],
                'cleanup_seconds':control['cleanup_seconds'],
                'receipt_seconds':outer[name]['controller_receipt_write_seconds'],
                'deadline_overshoot_seconds':outer[name]['all_bookkeeping_overshoot'],
                'peak_working_set_bytes':control['peak_working_set_bytes'],
                'status':summary['status'],'best_specification':json.dumps(chosen,separators=(',',':')),
                'evaluated_head':source}
        metrics.append(metric)
        best_so_far=initial
        for r in ledger['calls']:
            best_so_far=min(best_so_far,r['makespan'])
            candidates.append({'unit':name,'slot':r['slot'],'charged_index':r['charged_index'],
                'phase':r['phase'],'status':r['status'],'makespan':r['makespan'],
                'best_so_far':best_so_far,'added_copy_bytes':r['movement']['added_copy_bytes'],
                'spill_bytes':r['movement']['spill_added_copy_bytes'],'wall_seconds':r['wall_seconds'],
                'timeout_seconds':r['timeout_seconds'],'completed_elapsed':r['completed_elapsed'],
                'plan':r['plan'],'plan_sha256':r['plan_sha256'],'output':r['output']})
        shutil.copyfile(ROOT/best['plan'],RUN/'plans'/f'{name}.json')
        members={p.relative_to(folder).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
                 for p in sorted(folder.rglob('*')) if p.is_file()}
        archive=RUN/f'{name}.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for path in members:
                info=zipfile.ZipInfo(f'{name}/{path}',date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o644<<16
                z.writestr(info,(folder/path).read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist())==len(members)
            for path,identity in members.items():
                raw=z.read(f'{name}/{path}')
                assert len(raw)==identity['bytes'] and hashlib.sha256(raw).hexdigest()==identity['sha256']
        archives[name]={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'members':members}
        print(json.dumps({'unit':name,'verified_files':len(members),'archive_bytes':archive.stat().st_size}),flush=True)
    assert len(candidates)==sum(r['calls'] for r in metrics)<=288
    active=sum(r['unit_seconds'] for r in metrics)
    receipts=sum(r['controller_receipt_unit_seconds'] for r in metrics)
    final_name=UNITS[-1]
    envelope=stage['units'][final_name]['started_monotonic']+outer[final_name]['wall_through_stage_ledger']-stage['started_monotonic']
    assert envelope<=5400
    # All methods regenerated the exact same initial plan independently per case.
    for case in ('002','008','044'):
        hashes={sha(RUN/f'{case}-{method}'/'baseline/plan.json') for method in ('D','M1','M2')}
        assert len(hashes)==1
    csv_write(RUN/'metrics.csv',metrics)
    csv_write(RUN/'candidates.csv',candidates)
    save(RUN/'evidence_manifest.json',archives)
    summary={'units':metrics,'calls':len(candidates),'maximum_calls':288,'active_unit_seconds':active,
             'controller_receipt_unit_seconds':receipts,
             'stage_envelope_seconds':envelope,'coordination_and_between_unit_seconds':envelope-active,
             'maximum_stage_seconds':5400,'code_versions':code_versions,
             'all_full_repeats_equal':True,'all_initial_plan_bytes_match_within_case':True,
             'M2_assignment_verified_for_all_saved_proposals':True,
             'archive_raw_bytes':sum(v['bytes'] for a in archives.values() for v in a['members'].values()),
             'archive_bytes':sum(a['bytes'] for a in archives.values()),
             'original_evidence_files':sum(len(a['members']) for a in archives.values())}
    save(RUN/'summary.json',summary)
    lines=['# Q2/B stage B: completed finite comparison','',
        'All values below are generated from saved official Q2 outputs. No additional evaluations were used for verification or packaging.','',
        '## Task and scope','',
        '- Goal: compare D, packet/core proposals M1, and fixed-D-core priority/granularity proposals M2 under identical ceilings.',
        '- Inputs: public case002/008/044, frozen config/E0, four cores, deterministic seed0 tie rules; no sealed test set.',
        '- Outputs: metrics.csv, candidates.csv, nine lossless evidence ZIPs, readable final plans and source method/limitations.',
        '- Constraints: each unit ≤32 calls/600 seconds; total ≤288/5400 seconds; serial, independently regenerated and evaluated D.',
        '- Checks: all source/input/plan/output identities, full final repetitions, initial plan parity, M2 assignment parity, controller states and whole archive member bytes.',
        '- Checkpoint: development T0 2026-09-24 04:29:06 Asia/Taipei; experiment first started '+stage['started_utc']+'; no claim of captain final acceptance.','',
        '## Quality and cost','',
        '| Case | Method | Final cycles | Reduction vs D | Added COPY (B) | Spill (B) | Calls /32 | Unit wall (s) |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in metrics:
        lines.append(f"| {r['case']} | {r['method']} | {r['best_cycles']} | {r['reduction_percent']:.2f}% | {r['added_copy_bytes']} | {r['spill_bytes']} | {r['calls']} | {r['unit_seconds']:.3f} |")
    lines += ['',
        'M1 improves case002; M2 does not. Neither family improves case008. Both improve case044, with M2 better in this small pool. Equal ceilings do not mean equal consumption: D stops after initial/final calls; finite search families stop after duplicates and all declared parameters are exhausted. No unused budget was spent on new, post-result families.','',
        'The selected case002 M1 plan increases partition COPY bytes while reducing time; lower movement is not a sufficient timing proxy. M2 preserves the D core map; its case044 improvement demonstrates an ordering/granularity opportunity for that assignment only. These are public development observations, not strong-solver superiority or generalization.','',
        '![Confirmed quality and measured cost](figures/quality_cost.png)',
        'Figure 1. Generated from metrics.csv; zero-based bars, four cores, seed0. Cost labels show wall seconds and [official calls]. No error bars: one deterministic run per unit. Vector PDF/SVG and provenance are in figures/.','',
        '## Retained regressions','',
        '| Unit | Duplicate proposals | Explored plans worse than D | Worst cycles | Best specification |',
        '|---|---:|---:|---:|---|']
    for r in metrics:
        lines.append(f"| {r['case']}-{r['method']} | {r['duplicates']} | {r['worse_than_initial']} | {r['worst_cycles']} | `{r['best_specification']}` |")
    lines += ['',
        f"Official calls: **{len(candidates)}/288**, all successful; no official rejection, timeout or resource failure in this measured run. Construction failures: {sum(r['generation_failures'] for r in metrics)}. All nine final results exactly repeat their selected result objects. The favorable status count does not prove the families always generate executable plans.",
        '![Every evaluated exploration candidate, including regressions](figures/candidate_regressions.png)',
        'Figure 2. Generated from candidates.csv; each point is an official exploration call, normalized by that unit’s own D. Diamonds include fallback to D. No rejected or missing values are drawn as zero. Style adapted from ChenLiu-1996/figures4papers, CC BY-NC 4.0; see figures/provenance.json and the plotting source.',
        f"Unit wall through controller receipts sums to **{receipts:.3f} s**; including the measured stage-ledger writes, **{active:.3f} s**. Original-stage envelope including the coordination pause: **{envelope:.3f} s**; between-unit/pause portion **{envelope-active:.3f} s**. Each unit remains below 600 s, envelope below 5400 s. Unit timing includes source/graph/config reads, generation, all E0 output, hashing and process cleanup. The last printed measurement records the explicit stage-ledger boundary; printing that timestamp itself is not claimed free.",
        f"Largest sampled controller+job-tree working set: **{max(r['peak_working_set_bytes'] for r in metrics)/1024**2:.3f} MiB**. Interval 250 ms, 4 GiB stopping threshold. Sampling can miss spikes/double count shared pages; no OS hard-memory guarantee. Per-call timing, proposal/evaluation totals, worker hash tail, cleanup/receipt and deadline overshoot are in CSV/archives.",'',
        '## Two control versions and the review pause','',
        'case002/008 used `9b544ad28b9515f9ab53070d457774b1d8f65a58` (78 calls). Coordinator review identified continuation after worker failure and missing-summary accounting gaps. After case008-M2 completed, a marked empty case044 directory stopped the original controller before reservation. The resulting FileExistsError is preserved as a coordination interruption, not a candidate rejection.',
        'After 4 controller and 10 process/ledger zero-E0 tests, coordinator explicitly approved `e503e61daed67c97cb09629a6f315b14cae2cca1` for case044 only (44 calls). Faults now stop subsequent units even if summary says confirmed, and charges come from persistent calls.json. Candidate generator and D algorithms did not change; failure classification/control did. Previous units were neither rewritten nor rerun. Stage start/deadline were inherited through the pause; both code identities are retained.',
        'No real official-graph failure exercised the corrected stop path; dummy processes/mock controller checks cover that path. These checks are not cross-machine or cross-platform evaluation.','',
        '## Later forced-stop check and delivery-only fix','',
        'A later developer rerun at `2422225` passed 4/4 controller checks but only 9/10 process checks: the injected memory-stop test hit Windows WinError32 when immediately deleting inherited stderr. Earlier passing runs and this later failure are both retained. The traceback alone does not prove the exact cause of the file lock.',
        'Delivery-only commit `e2b4c5ad76f2b8f3021f2442c03111ba3d3b2db2` retains process synchronization handles, waits under a single shared cleanup deadline, closes owned handles and reports wait failures as monitor_error. Final developer validation passed 4 controller and 12 process/ledger tests, including 12 bounded forced-stop/immediate-log-cleanup iterations and an injected wait failure. The two suite invocation times were 3.656 s and 11.687 s; see control-validation/handle-wait-fixed-e2b4c5a/run.json. An intermediate 11-test pass with a ResourceWarning is also retained.',
        'These tests use dummy processes or mock workers and consume zero E0 calls. No official graph was evaluated with this third control version. Bounded success does not prove that all future Windows file-lock conditions are eliminated.','',
        '## Evidence and reproduction','',
        f"The nine ZIPs contain **{summary['original_evidence_files']} files**, **{summary['archive_raw_bytes']} original bytes**, compressed to **{summary['archive_bytes']} bytes**. Each ZIP was reopened and every member size/SHA-256 compared to its original file. evidence_manifest.json contains both archive and member identities; original expanded folders remain on the development machine but are ignored in Git to avoid duplicating large traces. Archive storage is lossless, not sampled evidence.",
        'plans/<case>-<method>.json is the exact selected plan copied for convenient reuse. Official graph files come from the unchanged source-manifest/restoration workflow; source commits are available in Git. Unit archives contain complete result/trace/log, raw stdout/stderr, all plans/specifications, call ledger, identities and monitor samples.',
        'Private path prefixes in shared root/controller and developer-test tracebacks are explicitly redacted. Exact raw logs are retained outside all Git worktrees; redaction_manifest.json binds raw and shared hashes and explains substitutions. Shared redacted logs are not byte-identical originals. The nine unit ZIPs are unaffected. official-source-check.json is explicitly post-run verification, not a backdated per-call preflight.',
        'Post-run verification/compression/report/PR work is separate delivery labor, not solver throughput. Its duration is recorded in packaging.json and did not produce any new E0 label.',
        'Run `python -X utf8 -B -m src.q2.report_b` against the existing expanded evidence to regenerate this report and packages without E0. The search stage has a single nonresettable approval ledger; reproducing nine units requires a new explicitly assigned budget, not a new directory or deleting the ledger.','',
        '## Limits and next decision','',
        'Only three selected public graphs, four cores and deterministic seed0; no many-seed uncertainty estimate, 100-case/2–5-core matrix, average single-core speedup curve, proof of optimality, strong candidate-pool benchmark or independent final acceptance. The 32-ready lookahead, coarse M1 virtual load model and no-spill frontier preference can miss good schedules; case008 is a clear no-improvement outcome. Research-reported better values use other plans/implementations and remain author reports, not paired baselines here.',
        'Recommend reviewing the preserved regressions and stronger reentrant-stage ordering proposals before authorizing another experiment. Do not extend this finite pool retrospectively or call the entire Q2 task done. Atlas and further budget decisions remain with coordination.','']
    (RUN/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    (RUN/'.gitignore').write_text('# Expanded evidence is retained locally and losslessly published in the unit ZIPs.\n'+''.join(f'/{name}/\n' for name in UNITS),encoding='utf-8',newline='\n')
    save(RUN/'packaging.json',{'generator':'src/q2/report_b.py','generator_sha256':sha(Path(__file__)),
        'q2_calls':0,'elapsed_through_report_seconds':time.monotonic()-started,
        'boundary':'final delivery-manifest hashing follows; separate from solver budgets'})
    delivery_manifest()
    print(json.dumps({'verified_units':len(metrics),'calls':len(candidates),'packaging_seconds':time.monotonic()-started}),flush=True)


if __name__ == '__main__':
    main()
