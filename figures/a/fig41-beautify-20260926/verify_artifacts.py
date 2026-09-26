"""Read-only image inspection and provenance manifest; never edits pixels."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import PIL
from PIL import Image

root = Path(__file__).resolve().parent
source_commit = 'b3b5ed8ec112a0f87baba184937ff7fe9e1dcd6e'
source_dir = 'figures/a/jia-fig4-1-20260926'
source_names = ['fig4-1-p1-two-layer-flow.png', 'fig4-1-p1-two-layer-flow.svg',
                'fig4-1-p1-two-layer-flow.drawio', 'nodes.csv', 'edges.csv', 'caption.md', 'audit.json']
sources = []
for name in source_names:
    path = source_dir + '/' + name
    raw = subprocess.check_output(['git', 'show', source_commit + ':' + path], cwd=root)
    sources.append(dict(commit=source_commit, path=path, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
refs = []
style_commit = 'e509c998ea5a3a0a8ceeb0ec59153c0b297ca133'
for name in ['fig-framework-zh.png', 'fig-hypercut-paper.png']:
    path = 'paper/manuscript-v1/figures/' + name
    raw = subprocess.check_output(['git', 'show', style_commit + ':' + path], cwd=root)
    refs.append(dict(commit=style_commit, path=path, sha256=hashlib.sha256(raw).hexdigest()))
file = root / 'fig4-1-language-review.png'
with Image.open(file) as im:
    assert im.mode == 'RGBA', 'Final PNG must contain an alpha channel'
    alpha = im.getchannel('A')
    counts = alpha.histogram()
    assert counts[0] > 0, 'No fully transparent pixels'
    info = dict(mode=im.mode, width_px=im.width, height_px=im.height,
                alpha_min=min(i for i,n in enumerate(counts) if n),
                alpha_max=max(i for i,n in enumerate(counts) if n),
                fully_transparent_pixels=counts[0],
                paper_width_mm=165, paper_height_mm=165*im.height/im.width,
                pixels_per_inch_at_165mm=im.width/(165/25.4),
                actual_paper_layout_verified=False)
files = [dict(path=p.name, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
         for p in sorted(root.iterdir()) if p.is_file() and p.name != 'manifest.json']
result = dict(status='user_confirmed_submitted_for_captain_review', source=sources, style_references=refs,
              user_confirmation=dict(date='2026-09-26', scope='Current image confirmed in conversation; submit with teammate delivery criteria', image_sha256='6fb51556d5ba6481e6415db757d42a06f90dc93a7e6093eddd46a870077d4508'),
              submission_standard_commit='a58a7d4dccdd90bfca25a8eb2c4384a7d258d3f4',
              submission_standard_version='2026-09-26.5',
              language_standard_commit='2d5fbdc66d9fbd5b6ac5988706546e4d60a6ab42',
              language_standard_version='2026-09-26.3',
              tool='built-in image_gen', generation_calls=8,
              python=sys.version.split()[0], pillow=PIL.__version__, image=info, files=files,
              limitations=['Old v4 algorithm; not 834d8c95.', 'No independent language acceptance.',
                           'No current manuscript PDF insertion QA.',
                           'Submission arrow enters evaluation group, not individual read card.',
                           'Some light edge fringe on dark backgrounds.'])
(root/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(info, ensure_ascii=False))
print('Source hashes:', len(sources), 'Style references:', len(refs), 'Output files:', len(files))
