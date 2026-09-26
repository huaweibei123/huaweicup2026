"""Loopback-only HTTP view. All files are registered and hash checked."""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from .core import Board, ROOT, Conflict
from .language import import_author_report
from .semantic import validate_workflow


class Documents:
    def __init__(self, board):
        self.board = board
        p = board.state / 'documents.json'
        self.locations = json.loads(p.read_text()) if p.exists() else {}
        self.cache = board.state / 'pages'
        self.cache.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.hashes = {}

    def locate(self, doc_id):
        doc = next((d for d in self.board.cat['documents'] if d['id'] == doc_id), None)
        if not doc:
            raise FileNotFoundError('未知文档')
        path = Path(self.locations.get(doc_id, ROOT / doc['path'])).resolve()
        if not path.is_file():
            # The current checkpoint is a fixed Git object even before merge.
            if doc.get('commit'):
                path = self.cache / (doc['sha256'] + '.pdf')
                if not path.exists():
                    p = subprocess.run(['git', '-C', str(ROOT), 'show', f"{doc['commit']}:{doc['path']}"], capture_output=True, timeout=30)
                    if p.returncode:
                        raise FileNotFoundError('本机缺固定论文Git对象；请按文档取回或注册PDF路径')
                    temp = path.with_suffix('.tmp')
                    temp.write_bytes(p.stdout)
                    if hashlib.sha256(p.stdout).hexdigest() != doc['sha256']:
                        temp.unlink(); raise ValueError('Git论文对象哈希不匹配')
                    temp.replace(path)
            else:
                raise FileNotFoundError('本机未注册参考PDF；文字对照可用，请按文档注册本人已有文件')
        stat = path.stat()
        fingerprint = (str(path), stat.st_mtime_ns, stat.st_size)
        if fingerprint not in self.hashes:
            self.hashes[fingerprint] = hashlib.sha256(path.read_bytes()).hexdigest()
        if self.hashes[fingerprint] != doc['sha256']:
            raise ValueError('文档字节已变化，拒绝将旧页码/验收绑定到新文件')
        return path, doc

    def page(self, doc_id, page):
        with self.lock:
            pdf, doc = self.locate(doc_id)
            if not 1 <= page <= doc['pages']:
                raise ValueError('页码越界')
            target = self.cache / f"{doc['sha256']}-{page}.png"
            if not target.exists():
                try:
                    subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1450', '-png', str(pdf), str(target.with_suffix(''))], check=True, capture_output=True, timeout=35)
                except FileNotFoundError:
                    raise FileNotFoundError('缺少pdftoppm，仍可用“打开PDF原件”审阅') from None
            return target


class CheckpointDocuments:
    """Serve a registered frozen PDF only when its bytes match the checkpoint ledger."""
    def __init__(self, board):
        self.board = board
        self.locations_file = board.state / 'checkpoint-locations.json'
        self.cache = board.state / 'checkpoint-pages'
        self.cache.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.fetch_lock = threading.Lock()

    @staticmethod
    def record(checkpoint_id):
        records = json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text())['checkpoints']
        result = next((item for item in records if item['id'] == checkpoint_id), None)
        if result is None:
            raise FileNotFoundError('未知论文检查点')
        return result

    def locate(self, checkpoint_id):
        record = self.record(checkpoint_id)
        locations = json.loads(self.locations_file.read_text()) if self.locations_file.exists() else {}
        path = Path(locations.get(checkpoint_id, ROOT / record['pdf_path'])).resolve()
        if not path.is_file():
            if not record.get('git_commit'):
                raise FileNotFoundError('本机尚未登记此检查点PDF；公开链接可在检查点记录中查看')
            with self.fetch_lock:
                path = self.cache / f"{record['pdf_sha256']}.pdf"
                if not path.exists():
                    result = subprocess.run(['git', '-C', str(ROOT), 'show',
                                             f"{record['git_commit']}:{record['pdf_path']}"],
                                            capture_output=True, timeout=30)
                    if result.returncode:
                        raise FileNotFoundError('本机缺固定论文Git对象；请使用公开PDF链接')
                    if hashlib.sha256(result.stdout).hexdigest() != record['pdf_sha256']:
                        raise ValueError('Git论文对象哈希与检查点不一致')
                    temp = path.with_suffix('.tmp')
                    temp.write_bytes(result.stdout)
                    temp.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['pdf_sha256']:
            raise ValueError('PDF字节与检查点哈希不一致，拒绝展示旧页码')
        return path, record

    def page(self, checkpoint_id, page):
        with self.lock:
            pdf, record = self.locate(checkpoint_id)
            if not 1 <= page <= record['pages']:
                raise ValueError('页码越界')
            target = self.cache / f"{record['pdf_sha256']}-{page}.png"
            if not target.exists():
                try:
                    subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-singlefile',
                                    '-scale-to', '1450', '-png', str(pdf), str(target.with_suffix(''))],
                                   check=True, capture_output=True, timeout=35)
                except FileNotFoundError:
                    raise FileNotFoundError('缺少pdftoppm，仍可打开PDF原件审阅') from None
            return target


class TeamImages:
    """Serve only pinned teammate PNGs, after checking their Git blob identity."""
    def __init__(self, board):
        self.manifest_path = ROOT / 'docs/paper-acceptance/team-figures.json'
        self.registry_lock = threading.Lock()
        self.manifest = {}
        self.by_id = {}
        self.locks = {}
        self.cache = board.state / 'team-figures'
        self.cache.mkdir(exist_ok=True)
        self.refresh()

    def refresh(self):
        """Read the fixed registry on request so new teammate deliveries appear without a restart."""
        manifest = json.loads(self.manifest_path.read_text())
        by_id = {item['id']: item for item in manifest['items']}
        if len(by_id) != len(manifest['items']):
            raise ValueError('队友图件编号重复')
        with self.registry_lock:
            self.manifest = manifest
            self.by_id = by_id
            for item_id in by_id:
                self.locks.setdefault(item_id, threading.Lock())
        return manifest

    @staticmethod
    def checked(raw, item):
        if len(raw) != item['size_bytes'] or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('图像字节数或PNG格式与来源登记不符')
        git_hash = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if git_hash != item['git_blob_sha1']:
            raise ValueError('图像Git对象哈希与固定来源不符')
        if item.get('sha256') and hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('图像SHA-256与交接登记不符')
        return raw

    def image(self, item_id):
        self.refresh()
        with self.registry_lock:
            item = self.by_id.get(item_id)
            lock = self.locks.get(item_id)
            source_repo = self.manifest['source_repo']
        if not item:
            raise FileNotFoundError('未登记的队友图件')
        with lock:
            target = self.cache / (item_id + '.png')
            if target.exists():
                try:
                    return self.checked(target.read_bytes(), item)
                except ValueError:
                    target.unlink()
            url = f"https://raw.githubusercontent.com/{source_repo}/{item['source_commit']}/{item['source_path']}"
            request = Request(url, headers={'User-Agent': 'paper-acceptance-board/1'})
            with urlopen(request, timeout=20) as response:
                raw = response.read(min(item['size_bytes'] + 1, 12_000_001))
            self.checked(raw, item)
            temp = target.with_suffix('.tmp')
            temp.write_bytes(raw)
            temp.replace(target)
            return raw


def serve(board, port):
    docs = Documents(board)
    checkpoint_docs = CheckpointDocuments(board)
    team_images = TeamImages(board)
    web = Path(__file__).with_name('web')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def reply(self, body, status=200, mime='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def guard(self, write=False):
            expected = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in expected:
                raise PermissionError('拒绝非本机Host')
            if write:
                if self.headers.get('X-Paper-Review') != '1':
                    raise PermissionError('写请求需要X-Paper-Review: 1')
                origin = self.headers.get('Origin')
                if origin and origin not in {f'http://{x}' for x in expected}:
                    raise PermissionError('拒绝跨站写请求')

        def do_GET(self):
            try:
                self.guard()
                p = urlparse(self.path); q = parse_qs(p.query)
                if p.path in {'/', '/app.js', '/style.css'}:
                    path = web / ('index.html' if p.path == '/' else p.path[1:])
                    return self.reply(path.read_bytes(), mime=mimetypes.guess_type(path)[0] or 'text/plain')
                if p.path == '/api/v1/health':
                    return self.reply({'service': 'paper-acceptance', 'paper_sha256': board.cat['paper_sha256'], 'standard_hash': board.standard_hash})
                if p.path == '/api/v1/state':
                    return self.reply(board.snapshot())
                if p.path == '/api/v1/agent':
                    return self.reply(board.agent_context(q.get('item', [None])[0]))
                if p.path == '/api/v1/export':
                    return self.reply(board.snapshot())
                if p.path == '/api/v1/language':
                    report = json.loads((ROOT / 'docs/paper-acceptance/language-audit.json').read_text())
                    entries = report['entries']
                    if 'term' in q:
                        entries = [e for e in entries if q['term'][0] == e['term']]
                    if 'page' in q:
                        entries = [e for e in entries if int(q['page'][0]) == e['page']]
                    if 'id' in q:
                        entries = [e for e in entries if q['id'][0] == e['id']]
                    count = len(entries)
                    offset = max(0, int(q.get('offset', ['0'])[0]))
                    limit = min(1000, max(1, int(q.get('limit', ['1000'])[0])))
                    return self.reply({**report, 'entries': entries[offset:offset+limit],
                                       'total_matching': count, 'offset': offset, 'limit': limit})
                if p.path == '/api/v1/fulltext':
                    report = json.loads((ROOT / 'docs/paper-acceptance/fulltext-inventory.json').read_text())
                    entries = report['entries']
                    for field in ('chapter', 'kind', 'id'):
                        if field in q:
                            entries = [e for e in entries if e[field] == q[field][0]]
                    offset = max(0, int(q.get('offset', ['0'])[0]))
                    limit = min(1000, max(1, int(q.get('limit', ['1000'])[0])))
                    return self.reply({**report, 'entries': entries[offset:offset+limit], 'total_matching': len(entries), 'offset': offset, 'limit': limit})
                if p.path == '/api/v1/sentences':
                    return self.reply(json.loads((ROOT / 'docs/paper-acceptance/sentence-audit.json').read_text()))
                if p.path == '/api/v1/semantic-audit':
                    report = json.loads((ROOT / 'docs/paper-acceptance/semantic-audit.json').read_text())
                    entries = report['findings']
                    if 'id' in q:
                        entries = [e for e in entries if e['id'] == q['id'][0]]
                    offset = max(0, int(q.get('offset', ['0'])[0]))
                    limit = min(1000, max(1, int(q.get('limit', ['1000'])[0])))
                    return self.reply({**report, 'findings': entries[offset:offset+limit], 'total_matching': len(entries), 'offset': offset, 'limit': limit})
                if p.path == '/api/v1/annotation-workflow':
                    report = json.loads((ROOT / 'docs/paper-acceptance/annotation-workflow.json').read_text())
                    validate_workflow(report)
                    return self.reply(report)
                if p.path == '/api/v1/author-reports':
                    path = board.state / 'author-reports.json'
                    return self.reply(json.loads(path.read_text()) if path.exists() else [])
                if p.path == '/api/v1/handoffs':
                    path = ROOT / 'docs/paper-acceptance/handoffs.json'
                    return self.reply(json.loads(path.read_text()) if path.exists() else [])
                if p.path == '/api/v1/standards':
                    return self.reply({'hash': board.standard_hash, 'catalogue': board.cat})
                if p.path == '/api/v1/team-figures':
                    return self.reply(team_images.refresh())
                if p.path == '/api/v1/figure-requests':
                    return self.reply(json.loads((ROOT / 'docs/paper-acceptance/figure-requests.json').read_text()))
                if p.path == '/api/v1/figure-review-v7':
                    return self.reply(json.loads((ROOT / 'docs/paper-acceptance/figure-review-v7.json').read_text()))
                if p.path == '/api/v1/checkpoints':
                    return self.reply(json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text()))
                if p.path in ('/figure-review-assets/p28-crop.pdf', '/figure-review-assets/p28-crop.png'):
                    suffix = '.pdf' if p.path.endswith('.pdf') else '.png'
                    path = ROOT / 'docs/paper-acceptance/candidates' / f'p28-figure-5.1-1-crop-candidate{suffix}'
                    return self.reply(path.read_bytes(), mime='application/pdf' if suffix == '.pdf' else 'image/png')
                match = re.fullmatch(r'/checkpoints/([a-z0-9]+)(?:/(\d+)\.png|\.pdf)', p.path)
                if match:
                    path = checkpoint_docs.page(match[1], int(match[2])) if match[2] else checkpoint_docs.locate(match[1])[0]
                    return self.reply(path.read_bytes(), mime='image/png' if match[2] else 'application/pdf')
                match = re.fullmatch(r'/team-figures/([a-z0-9-]+)\.png', p.path)
                if match:
                    return self.reply(team_images.image(match[1]), mime='image/png')
                match = re.fullmatch(r'/documents/(current|ref[1-4])(?:/(\d+)\.png|\.pdf)', p.path)
                if match:
                    path = docs.page(match[1], int(match[2])) if match[2] else docs.locate(match[1])[0]
                    return self.reply(path.read_bytes(), mime='image/png' if match[2] else 'application/pdf')
                return self.reply({'error': '未知路径'}, 404)
            except FileNotFoundError as exc:
                self.reply({'error': str(exc)}, 404)
            except PermissionError as exc:
                self.reply({'error': str(exc)}, 403)
            except Exception as exc:
                self.reply({'error': str(exc)[:600]}, 400)

        def do_POST(self):
            try:
                self.guard(write=True)
                n = int(self.headers.get('Content-Length', '0'))
                if n < 0 or n > 40000:
                    raise ValueError('请求体过大')
                body = json.loads(self.rfile.read(n) or b'{}')
                if self.path == '/api/v1/identity':
                    return self.reply({'login': board.authenticate()})
                if self.path == '/api/v1/reviews':
                    return self.reply(board.draft(body), 201)
                if self.path == '/api/v1/sync':
                    return self.reply(board.sync())
                if self.path == '/api/v1/publish':
                    return self.reply(board.publish(body['id']))
                return self.reply({'error': '未知路径'}, 404)
            except Conflict as exc:
                self.reply({'error': str(exc)}, 409)
            except PermissionError as exc:
                self.reply({'error': str(exc)}, 403)
            except Exception as exc:
                self.reply({'error': str(exc)[:700]}, 400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'论文验收台 http://127.0.0.1:{port}', flush=True)
    print(f'Agent interface http://127.0.0.1:{port}/api/v1/agent', flush=True)
    server.serve_forever()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', default='output/paper-acceptance')
    p.add_argument('--catalogue')
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('serve'); s.add_argument('--port', type=int, default=8879)
    sub.add_parser('status'); sub.add_parser('sync'); sub.add_parser('identity')
    s = sub.add_parser('agent'); s.add_argument('--item')
    s = sub.add_parser('draft'); s.add_argument('file')
    s = sub.add_parser('publish'); s.add_argument('id')
    s = sub.add_parser('import-author'); s.add_argument('commit'); s.add_argument('path')
    s = sub.add_parser('check-annotations'); s.add_argument('file')
    s = sub.add_parser('register'); s.add_argument('doc_id', choices=['current','ref1','ref2','ref3','ref4']); s.add_argument('file')
    s = sub.add_parser('register-checkpoint'); s.add_argument('checkpoint_id'); s.add_argument('file')
    a = p.parse_args(); board = Board(a.state, a.catalogue)
    if a.command == 'serve':
        return serve(board, a.port)
    if a.command == 'register-checkpoint':
        checkpoint = CheckpointDocuments.record(a.checkpoint_id)
        path = Path(a.file).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != checkpoint['pdf_sha256']:
            raise ValueError('PDF哈希与登记的检查点不一致')
        f = board.state / 'checkpoint-locations.json'; data = json.loads(f.read_text()) if f.exists() else {}
        data[a.checkpoint_id] = str(path); f.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        result = {'registered_checkpoint': a.checkpoint_id, 'sha256': checkpoint['pdf_sha256']}
    elif a.command == 'register':
        doc = next(d for d in board.cat['documents'] if d['id'] == a.doc_id)
        path = Path(a.file).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != doc['sha256']:
            raise ValueError('PDF哈希与登记的检查点不一致')
        f = board.state / 'documents.json'; data = json.loads(f.read_text()) if f.exists() else {}
        data[a.doc_id] = str(path); f.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); result = {'registered': a.doc_id}
    elif a.command == 'status': result = board.snapshot()
    elif a.command == 'sync': result = board.sync()
    elif a.command == 'identity': result = {'login': board.authenticate()}
    elif a.command == 'agent': result = board.agent_context(a.item)
    elif a.command == 'draft':
        board.authenticate(); result = board.draft(json.loads(Path(a.file).read_text()))
    elif a.command == 'publish': result = board.publish(a.id)
    elif a.command == 'import-author': result = import_author_report(board, a.commit, a.path)
    elif a.command == 'check-annotations': result = validate_workflow(json.loads(Path(a.file).read_text()))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
