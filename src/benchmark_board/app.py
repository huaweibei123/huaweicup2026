"""Local read-only HTTP/Agent interface; import published data only, never run benchmarks."""
from __future__ import annotations
import argparse, fnmatch, json, html, mimetypes, re, subprocess, threading, time, traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from core import Ledger, now, packed, sha, safe_path, MAX_BLOB, digest, batch_candidates

ROOT=Path(__file__).resolve().parents[2]
WEB=Path(__file__).parent/'web'
REPO='huaweibei123/huaweicup2026'

def git(repo,*args,timeout=45):
    return subprocess.run(['git','-C',str(repo),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=timeout).stdout

def blob(repo,commit,path):
    safe_path(path)
    size=int(git(repo,'cat-file','-s',commit+':'+path))
    if size>MAX_BLOB: raise ValueError('oversized artifact')
    return git(repo,'show',commit+':'+path)

def load_feed(ledger,repo,commit,path):
    if not sha(commit,40): raise ValueError('full source commit required')
    data=blob(repo,commit,path)
    if len(data)>8*1024*1024: raise ValueError('feed too large')
    return ledger.ingest(json.loads(data),lambda p:blob(repo,commit,p),{'repo':REPO,'commit':commit,'path':path,'url':f'https://github.com/{REPO}/blob/{commit}/{path}'})

def sync_once(ledger,repo,sources,on_progress=None):
    for s in sources:
        started=now(); name=s['id']
        try:
            ref=s['ref']
            if not re.fullmatch(r'[A-Za-z0-9_./-]+',ref) or '..' in ref: raise ValueError('bad source ref')
            found=git(repo,'ls-remote','origin','refs/heads/'+ref).decode().split()
            if not found: raise ValueError('source branch not published')
            commit=found[0]
            with ledger.connect() as db: prior=db.execute('SELECT body FROM sources WHERE id=?',(name,)).fetchone()
            prior=json.loads(prior['body']) if prior else {}
            if prior.get('commit')==commit and prior.get('status') in ('ok','waiting_feed'):
                prior.update(checked_at=now());ledger.source_status(name,prior);continue
            try: git(repo,'cat-file','-e',commit+'^{commit}')
            except subprocess.CalledProcessError: git(repo,'fetch','--no-tags','origin',commit,timeout=90)
            paths=git(repo,'ls-tree','-r','--name-only',commit,'--',s['prefix']).decode().splitlines()
            paths=[p for p in paths if fnmatch.fnmatch(p,s['prefix'].rstrip('/')+'/**/board-feed*.json') or (p.startswith(s['prefix'].rstrip('/')+'/') and Path(p).name.startswith('board-feed') and p.endswith('.json'))]
            if len(paths)>300: raise ValueError('source feed count exceeds 300; scope review needed')
            results=[]
            for path in paths:
                if on_progress: on_progress()
                results.append(load_feed(ledger,repo,commit,path))
            ledger.source_status(name,{'status':'ok' if paths else 'waiting_feed','ref':ref,'commit':commit,'checked_at':now(),'started_at':started,'feeds':len(paths),'added':sum(r['added'] for r in results),'message':'已接收固定数据' if paths else '分支可读，等待发布 board-feed；不等于队友未运行'})
        except Exception as e:
            ledger.source_status(name,{'status':'error','checked_at':now(),'started_at':started,'ref':s['ref'],'message':type(e).__name__+': '+str(e)[:250]})
        finally:
            if on_progress: on_progress()

def ui_bundle(problem=None):
    files={name:(WEB/name).read_bytes() for name in ('index.html','app.js','style.css')}
    hashes={name:digest(data) for name,data in files.items()}
    asset_id=digest(packed(hashes).encode())
    rendered=files['index.html'].replace(b'</head>',f'<meta name="board-assets" content="{asset_id}"></head>'.encode(),1)
    if problem in ('P1','P2','P3'):
        rendered=rendered.replace(b'<html lang="zh-CN">',f'<html lang="zh-CN" data-problem="{problem}">'.encode(),1)
    return rendered,{'ui_asset_id':asset_id,'file_hashes':hashes,'served_html_sha256':digest(rendered)}

def sync_state(path):
    if path is None: return None
    try:
        with Path(path).open('rb') as stream: raw=stream.read(64*1024+1)
        if len(raw)>64*1024: raise ValueError('Sync status too large')
        state=json.loads(raw)
        if not isinstance(state,dict): raise ValueError('Sync status must be an object')
        return state
    except (OSError,ValueError) as error:
        return {'state':'error','error':{'stage':'status','message':type(error).__name__+': '+str(error)[:200]}}

def make_handler(ledger,sync_status=None):
    def annotate(data):
        state=sync_state(sync_status)
        if state is not None:
            data.setdefault('runtime',{'mode':getattr(ledger,'mode','local_ledger')})['sync']=state
        return data
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,data,status=200,ctype='application/json; charset=utf-8',headers=None):
            payload=packed(data).encode() if not isinstance(data,bytes) else data
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            for k,v in (headers or {}).items(): self.send_header(k,v)
            self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'): self.send({'error':'loopback host required'},403);return
            u=urlparse(self.path);q={k:v[-1] for k,v in parse_qs(u.query).items()};path=u.path
            try:
                if path=='/api/v1/health':
                    return self.send(annotate(ledger.health()))
                if path=='/api/v1/runtime':
                    _,assets=ui_bundle();state=sync_state(sync_status)
                    software=(state or {}).get('software',{})
                    return self.send(dict(assets,schema_version=1,mode=getattr(ledger,'mode','local_ledger'),
                                          software=software if isinstance(software,dict) else {},sync=state))
                if path=='/api/v1/cells':
                    data=ledger.snapshot(q.get('algorithm'),q.get('run'),q.get('include_reported')=='true')
                    for key in ('problem','case_id','cores'):
                        if q.get(key): data['cells']=[c for c in data['cells'] if str(c[key])==q[key]]
                    return self.send(annotate(data))
                if path=='/api/v1/batches':
                    cases=q['cases'].split(',') if 'cases' in q else [f'{n:03d}' for n in range(1,101)]
                    return self.send(batch_candidates(ledger.records(),q.get('problem','P1'),int(q.get('cores',5)),cases))
                if path=='/api/v1/events':
                    after=max(0,int(q.get('after',0)));deadline=time.monotonic()+min(25,max(0,int(q.get('wait',0))))
                    while True:
                        events=ledger.events(after)
                        if events or time.monotonic()>=deadline: break
                        time.sleep(.5)
                    return self.send({'events':events,'next_cursor':events[-1]['cursor'] if events else after})
                if path=='/api/v1/records':
                    rows=ledger.records({k:q.get(k) for k in ('problem','case_id','cores','algorithm_id','run_id')})
                    start=max(0,int(q.get('offset',0)));limit=min(500,max(1,int(q.get('limit',100))))
                    return self.send({'records':rows[start:start+limit],'total':len(rows),'next_offset':start+limit if start+limit<len(rows) else None})
                if path.startswith('/api/v1/records/'):
                    rows=[r for r in ledger.records() if r['id']==path.rsplit('/',1)[-1]]
                    return self.send(rows[0] if rows else {'error':'not found'},200 if rows else 404)
                if path=='/api/v1/catalog':
                    if hasattr(ledger,'catalog'): return self.send(ledger.catalog())
                    return self.send(json.loads((ROOT/'docs/benchmarks/algorithm-registry.json').read_text(encoding="utf-8")))
                if path=='/protocol':
                    body=(ROOT/'docs/benchmarks/SUBMISSION_PROTOCOL.md').read_text(encoding="utf-8")
                    page='<meta charset="utf-8"><title>统一交付协议 · 方案成绩台</title><link rel="stylesheet" href="/style.css"><body class="agent"><a href="/">← 方案成绩台</a><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+html.escape(body)+'</pre></body>'
                    return self.send(page.encode(),ctype='text/html; charset=utf-8')
                if path=='/api/v1/template': return self.send(json.loads((ROOT/'docs/benchmarks/examples/submission-v1.json').read_text(encoding="utf-8")))
                if path=='/api/v1/schema': return self.send(json.loads((ROOT/'docs/benchmarks/board-feed.schema.json').read_text(encoding="utf-8")))
                if path.startswith('/api/v1/blobs/'):
                    key=path.rsplit('/',1)[-1]
                    if hasattr(ledger,'blob_sources'):
                        links=ledger.blob_sources(key) if sha(key) else []
                        return self.send({'error':'Original bytes are not stored in the read-only mirror; use the fixed source links.','sources':links},409 if links else 404)
                    if not sha(key) or not (ledger.state/'blobs'/key).is_file(): return self.send({'error':'not found'},404)
                    return self.send((ledger.state/'blobs'/key).read_bytes(),ctype='application/octet-stream',headers={'Content-Disposition':'attachment; filename="'+key+'"'})
                files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/agent':'agent.html'}
                if path in files:
                    if path=='/': return self.send(ui_bundle(q.get('problem'))[0],ctype='text/html; charset=utf-8')
                    f=WEB/files[path];return self.send(f.read_bytes(),ctype={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[f.suffix[1:]])
                self.send({'error':'not found'},404)
            except (ValueError,KeyError) as e: self.send({'error':str(e)},400)
        def do_POST(self): self.send({'error':'Read-only HTTP. Publish immutable feed via your branch; captain imports verified commit.'},405)
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=ROOT);p.add_argument('--state',type=Path,default=ROOT/'output/benchmark-board');sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('import');i.add_argument('--commit',required=True);i.add_argument('--feed',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=52341);s.add_argument('--sync-interval',type=int,default=5);s.add_argument('--no-sync',action='store_true')
    s.add_argument('--mirror',type=Path,help='Read an accepted central snapshot current.json; never ingest it into the local ledger')
    s.add_argument('--sync-status',type=Path,help='Read-only status file owned by the separate sync process')
    s.add_argument('--sync-inbox',type=Path,help='Central mode only: receive completed local deliveries from the authenticated sync transport')
    sub.add_parser('sync');args=p.parse_args()
    manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_text(encoding="utf-8"))
    mirror=args.command=='serve' and args.mirror is not None
    if mirror and args.sync_inbox: p.error('--sync-inbox is only available in central ledger mode')
    if mirror:
        from mirror import MirrorView
        ledger=MirrorView(args.mirror,manifest,args.sync_status)
    else:
        admission=ROOT/'docs/benchmarks/board-calibrations.json';ledger=Ledger(args.state,manifest,json.loads(admission.read_text(encoding="utf-8")) if admission.exists() else {})
    sources=json.loads((ROOT/'docs/benchmarks/board-sources.json').read_text(encoding="utf-8"))
    if args.command=='import': print(packed(load_feed(ledger,args.repo,args.commit,args.feed)));return
    if args.command=='sync':sync_once(ledger,args.repo,sources);print(packed({'done':True}));return
    if not mirror and (not args.no_sync or args.sync_inbox):
        def receive():
            if args.sync_inbox:
                from inbox import drain_inbox
                for result in drain_inbox(ledger,args.sync_inbox):
                    if result['state']=='retry': print('Benchmark inbox retry: '+packed(result),flush=True)
        def worker():
            next_sources=0
            while True:
                try:
                    receive()
                    if not args.no_sync and time.monotonic()>=next_sources:
                        sync_once(ledger,args.repo,sources,on_progress=receive)
                        next_sources=time.monotonic()+max(5,args.sync_interval)
                except Exception:
                    # Keep retries visible and preserve batch idempotency if a
                    # filesystem/database interruption occurs after admission.
                    traceback.print_exc()
                # A completed request.json is already authenticated and local.
                # Keep the final receive hop below a second; remote polling and
                # artifact verification remain the sync transport's responsibility.
                time.sleep(.25 if args.sync_inbox else max(5,args.sync_interval))
        threading.Thread(target=worker,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(ledger,args.sync_status));server.daemon_threads=True
    args.state.mkdir(parents=True,exist_ok=True)
    (args.state/'service.json').write_text(packed({'url':f'http://127.0.0.1:{args.port}','started_at':now(),'mode':'central_mirror' if mirror else 'local_ledger','sources_poll_seconds':None if args.no_sync or mirror else max(5,args.sync_interval)}))
    print(f'Benchmark board: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
