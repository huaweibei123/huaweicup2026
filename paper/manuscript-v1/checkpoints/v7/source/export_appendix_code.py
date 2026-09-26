#!/usr/bin/env python3
"""Export pinned originals and declaration-only paper listings. Never execute them."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess

P = Path(__file__).resolve().parents[1]
REPO = P.parents[1]
DEST = P / 'appendix-code'
DISCLOSURE = P / 'ai-disclosure'
SOURCES = [
    ('P1', '834d8c957538ee069c66aadac9509552a4cc69d7', 'src/q1/branch_refine.py'),
    ('P1', '834d8c957538ee069c66aadac9509552a4cc69d7', 'src/q1/branch_aid.py'),
    ('P2', 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f', 'src/q2_nikolastarx/adaptive_hypergap_guarded.py'),
    ('P2', 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f', 'src/q2_nikolastarx/hypergraph_cost.py'),
    ('P2', 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f', 'src/q2_nikolastarx/binary_hypercut.py'),
    ('P3', '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1', 'src/q3/forest_solve.py'),
    ('P3', '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1', 'src/q3/forest_memory_order.py'),
]

def main():
    rows = []
    header = (DISCLOSURE / 'code-header.txt').read_bytes().rstrip(b'\n') + b'\n\n'
    metadata = json.loads((DISCLOSURE / 'model-metadata.json').read_text())
    previous = json.loads((DEST / 'manifest.json').read_text()) if (DEST / 'manifest.json').exists() else {'files': []}
    previous_listings = {row.get('listing_file'): row.get('listing_sha256') for row in previous['files']}
    for problem, commit, source in SOURCES:
        raw = subprocess.check_output(['git', 'show', f'{commit}:{source}'], cwd=REPO)
        target = DEST / problem.lower() / Path(source).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise SystemExit(f'Pinned copy differs; do not overwrite: {target}')
        target.write_bytes(raw)
        listing = DEST / 'declared' / target.relative_to(DEST)
        declared = header + raw
        assert ast.dump(ast.parse(declared)) == ast.dump(ast.parse(raw)), source
        assert declared[len(header):] == raw, source
        if listing.exists() and listing.read_bytes() != declared:
            old_hash = hashlib.sha256(listing.read_bytes()).hexdigest()
            if previous_listings.get(listing.relative_to(DEST).as_posix()) != old_hash:
                raise SystemExit(f'Unrecorded listing edit; do not overwrite: {listing}')
        listing.parent.mkdir(parents=True, exist_ok=True)
        listing.write_bytes(declared)
        rows.append(dict(problem=problem, commit=commit, source=source,
                         file=target.relative_to(DEST).as_posix(), bytes=len(raw),
                         lines=len(raw.splitlines()), sha256=hashlib.sha256(raw).hexdigest(),
                         listing_file=listing.relative_to(DEST).as_posix(),
                         listing_sha256=hashlib.sha256(declared).hexdigest(),
                         listing_lines=len(declared.splitlines()),
                         declaration_bytes=len(header), declaration_lines=len(header.splitlines()),
                         original_bytes_preserved=True, python_ast_identical=True))
    (DEST / 'manifest.json').write_text(json.dumps({
        'scope': 'Seven unchanged pinned original modules and seven paper listings with an AI declaration prepended. Dependencies remain at the fixed commits; these listings are not a standalone runnable bundle.',
        'disclosure_metadata': metadata,
        'header_sha256': hashlib.sha256(header).hexdigest(),
        'original_total_lines': sum(r['lines'] for r in rows),
        'listing_total_lines': sum(r['listing_lines'] for r in rows),
        'files': rows,
        'reference_style': [
            {'file': '2025A题优秀论文/A题-面向 Davinci 架构的 NPU 核内调度算法研究.pdf', 'page': 59},
            {'file': '2025A题优秀论文/A题-2-通用神经网络处理器下的核内调度问题.pdf', 'page': 38},
            {'file': '2025A题优秀论文/A题-NPU 核内调度算法设计与优化研究.pdf', 'page': 92},
        ],
    }, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(rows)} originals and declared listings; {sum(r["lines"] for r in rows)} original lines; bytes and AST verified')

if __name__ == '__main__':
    main()
