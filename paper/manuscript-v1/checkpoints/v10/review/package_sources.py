"""Export pinned source bytes for the v10 attachment; never execute a solver."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

P = Path(__file__).resolve().parents[2]
ROOT = P.parents[1]
OUT = P / 'attachments/v10'
PACKAGE = OUT / 'source-code-v10'
COMMITS = {
    'P1': '834d8c957538ee069c66aadac9509552a4cc69d7',
    'P2': 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f',
    'P3': '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1',
}
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
items = []

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def put(name, raw, **metadata):
    path = PACKAGE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    items.append(dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), **metadata))

def export(commit, name, target):
    raw = git('show', f'{commit}:{name}')
    put(target, raw, commit=commit, source=name, original_bytes_preserved=True)
    return raw

PACKAGE.mkdir(parents=True, exist_ok=False)
for problem, commit in COMMITS.items():
    paths = git('ls-tree', '-r', '--name-only', commit, '--',
                'src', 'pyproject.toml', 'uv.lock', '.python-version',
                'data/raw/a/official/code', 'data/raw/a/official/data/config.txt').decode().splitlines()
    for name in paths:
        export(commit, name, f'snapshots/{problem}/{name}')
    put(f'snapshots/{problem}/SOURCE_COMMIT.txt', (commit+'\n').encode())

manifest_path = 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'
manifest = json.loads(export(COMMITS['P2'], manifest_path, f'snapshots/P2/{manifest_path}'))
assert manifest['e2_commit'] == E2
for name, expected in manifest['e2_sources'].items():
    raw = export(E2, name, f'dependencies/E2-source/{name}')
    assert hashlib.sha256(raw).hexdigest() == expected, name

listings = json.loads((P/'appendix-code/manifest.json').read_text())
for record in listings['files']:
    original = (P/'appendix-code'/record['file']).read_bytes()
    declared = (P/'appendix-code'/record['listing_file']).read_bytes()
    assert hashlib.sha256(original).hexdigest() == record['sha256']
    assert hashlib.sha256(declared).hexdigest() == record['listing_sha256']
    assert original == git('show', f"{record['commit']}:{record['source']}")
    assert declared[record['declaration_bytes']:] == original
    assert ast.dump(ast.parse(original)) == ast.dump(ast.parse(declared))
    for file in ('file', 'listing_file'):
        put('paper-listings/'+record[file], (P/'appendix-code'/record[file]).read_bytes(),
            commit=record['commit'], source=record['source'])
put('paper-listings/manifest.json', (P/'appendix-code/manifest.json').read_bytes())
for file in ('code-header.txt', 'model-metadata.json'):
    put('ai-disclosure/'+file, (P/'ai-disclosure'/file).read_bytes())

readme = '''# 论文 v10 源码附件（审阅版）

本附件替代论文附录中连续展示的七份代码。正文仅保留六段说明算法决策的简短伪代码；本包保留对应的完整模块及三个固定版本的 src/ 源文件。没有修改求解逻辑，没有重新运行求解器或评价器。

## 内容

- `paper-listings/`：原附录的七份原始模块（1464 行）、带既有 AI 使用声明的七份版本（1520 行），以及逐文件来源和哈希。声明版本只增加注释，原始字节与 Python AST 保持不变。
- `snapshots/P1/`、`P2/`、`P3/`：各题固定提交的完整 src/、Python 版本、依赖锁、官方评价 Python 源码和配置。每个文件均按原 Git 对象逐字节导出。源码可能含该版本保留的历史候选；论文入口见下表。
- `dependencies/E2-source/`：P2 原生评价依赖的固定源文件，与原运行清单逐文件核同。包括 C++ 源码和构建脚本，不包含本机原生二进制。
- `MANIFEST.json`：本包文件清单、来源、SHA-256 和验证范围。

| 题目 | 论文求解入口 | 固定提交 |
| --- | --- | --- |
| P1 | `src.q1.branch_refine` | `834d8c957538ee069c66aadac9509552a4cc69d7` |
| P2 | `src.q2_nikolastarx.adaptive_hypergap_guarded` | `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` |
| P3 | `src.q3.forest_solve` | `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1` |

## 运行环境与范围

Python 版本和依赖以各快照中的 `.python-version`、`pyproject.toml`、`uv.lock` 为准。官方题目输入图沿用原附件，本包不重复收录数据和实验结果。

这是完整源模块的审阅附件，不宣称解压后即可跨平台运行。P2 原入口会读取 Git 提交并通过 `git archive` 核验 E2 来源，因此正式复现应在组织仓库相应固定提交的独立工作树中进行，不应伪造 Git 元数据或移除验证。固定 E2 提交为 `603b0741e21c449d3db652ebd67c94f2dc014cc9`；既有认证二进制仅适用 macOS arm64，SHA-256 为 `0f765b7b1229ea221881ff8e017ba7d37b64461eded6afb7f48e9cf61bfd4e94`。源码编译得到的新二进制不能自动视为该认证版本。最终运行交付包仍须由程序责任人按实际环境补齐并验证，此次没有新增实验授权。

原模块与带声明版本分别保存；已核实的七模块声明为 GPT-6 系列辅助，主要使用 OpenAI GPT-6 Astra（gpt-6-astra，发布日期2026-09-03）。原声明依据见 `ai-disclosure/` 和 `paper-listings/manifest.json`。其他作者的源文件保留原样，不推定全队都使用同一模型；正式提交前由各作者据实际工具历史补全。

## 完整性检查

解压后逐项计算 `MANIFEST.json` 中 files[].path 的 SHA-256 并与 files[].sha256 对照即可。清单本身的哈希和整个 ZIP 的哈希记录在包外 `attachment-receipt.json`。本次只核原始字节、七组声明前后 AST 和 ZIP 回读；不把打包成功当作跨平台运行验收。
'''
put('README.md', readme.encode())
doc = dict(version='v10', kind='source-review-attachment', commits=COMMITS,
           e2_commit=E2, files=items, original_listing_lines=1464,
           declared_listing_lines=1520, solver_calls=0, evaluator_calls=0,
           limitations=['No native E2 binary', 'P2 requires original Git objects for source verification',
                        'No new runtime or cross-platform validation', 'Author-specific final AI disclosures pending'])
(PACKAGE/'MANIFEST.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n')
zip_path = OUT/'source-code-v10.zip'
with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for path in sorted(PACKAGE.rglob('*')):
        if path.is_file():
            info = zipfile.ZipInfo('source-code-v10/'+path.relative_to(PACKAGE).as_posix(), (2026,9,27,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes())
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    for item in items:
        assert hashlib.sha256(z.read('source-code-v10/'+item['path'])).hexdigest() == item['sha256']
receipt = dict(version='v10', zip=zip_path.name, bytes=zip_path.stat().st_size,
               sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),
               manifest_sha256=hashlib.sha256((PACKAGE/'MANIFEST.json').read_bytes()).hexdigest(),
               files=len(items)+1, seven_original_modules_verified=True,
               seven_declarations_ast_identical=True, zip_readback_verified=True,
               solver_calls=0, evaluator_calls=0, standalone_runtime_verified=False)
(OUT/'attachment-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
