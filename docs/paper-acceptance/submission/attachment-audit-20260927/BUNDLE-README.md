# A题 Python 附件候选：来源完整、运行待补证

本包是可复制的离线来源与校验包，**不是已验收的即用求解器交付**。它保留 v13 沿用的 v10 原源码 ZIP、100 个官方输入图 ZIP，以及 P2 固定版本所需的 E2 来源认证清单。没有修改算法、官方评价器或既有 ZIP 的字节。P1/P2/P3 分别位于源码 ZIP 的 `source-code-v10/snapshots/P1`、`P2`、`P3`。

## 离线核验

1. 用 `shasum -a 256 attachment-a-source-candidate.zip` 核对外层 ZIP 哈希（见同目录外部收据）。解压后执行 `shasum -a 256 -c SHA256SUMS`。
2. `FILE-SHA256.tsv` 列出两个内层 ZIP 每个普通文件的 SHA-256；路径中 `!/` 表示 ZIP 成员。源码 ZIP 自带 `source-code-v10/MANIFEST.json`，含逐文件来源、大小和哈希。
3. `unzip -t source-code-v10.zip` 与 `unzip -t official-cases.zip` 只检压缩完整性；本轮已用 Python `ast.parse` 静态解析 289 份 `.py`。这些步骤不启动求解/评测。
4. 原始图 ZIP 内的 `data/case_001.json` 至 `data/case_100.json` 是只读赛题输入。需要运行时，应各自在固定版本独立工作树中解压为 `data/raw/a/official/data/case_XXX.json`，保留 ZIP 与哈希；不要覆盖原件。三个快照已有官方 `config.txt` 和源码。

## 固定入口和环境

源码快照保留 `.python-version`、`pyproject.toml`、`uv.lock`。要求 Python 3.12（`>=3.12,<3.13`），声明依赖 numpy、pandas、scipy、matplotlib，实际安装可按固定工作树中的 `uv sync --locked` 离线使用已可信缓存或受控获取。未在本轮安装、导入或运行程序。

- P1 `834d8c957538ee069c66aadac9509552a4cc69d7`：`python -m src.q1.branch_refine GRAPH --cores K --output NEW_PLAN --diagnostics NEW_JSON`。源码明确该入口为 one-shot R6 refinement，含 E1；主验收者已核500份真实运行记录，其实际命令均使用该固定入口；见 `p1-entry-evidence.json`。新附件目录尚未独立执行。
- P2 `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`：`python -m src.q2_nikolastarx.adaptive_hypergap_guarded GRAPH --cores K --output NEW_PLAN --evidence NEW_DIR --e2-root VERIFIED_E2_DIR`。入口调用 `adaptive_guarded.py`，在固定 Git 工作树用 `git archive` 核对 E2 对象，并认证 macOS arm64 原生库。仅源码 ZIP 无法满足此条件。**不得**移除认证或伪造 `.git`。
- P3 `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`：`python -m src.q3.forest_solve GRAPH --cores K -o NEW_PLAN --evidence NEW_DIR`；它经 `safe_solve` 调用官方 E0。P3 是研究与论文配套完整性，原题 P1/P2 的脚本要求由主代理核对。

`GRAPH`、`NEW_PLAN`、`NEW_JSON`、`NEW_DIR` 必须显式替换，输出使用新路径。上述只是源码中解析到的接口，**不是本轮实测命令**。若安装依赖、运行求解器或官方评估器，需要另行执行授权和验证。求解方案应仅有 `node_to_subgraph`、`core_schedules` 两个顶层键；P1/P2 有静态检查，P3 构造可见这两键；本轮未生成方案，不能声称运行结果合规。

## P2 合法重建边界

`p2-e2-manifest.json` 来自 P2 固定提交的 `results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json`。其 50 个 `e2_sources` 与源码包 `dependencies/E2-source/` 逐字节哈希一致。要复现原 P2 执行，P2 作者需在包含原 Git 对象 `603b0741e21c449d3db652ebd67c94f2dc014cc9` 的固定提交工作树提供独立 E2 根目录，包含清单中恰好 50 个源文件及认证库 `research/a/e2_search/native/libreplay_bc.so`（36,784 字节，SHA-256 `0f765b7b1229ea221881ff8e017ba7d37b64461eded6afb7f48e9cf61bfd4e94`）。库未随本包提供，也未在两个固定 Git 提交中找到。原始构建证据索引是 `results/a/proxy/e2-p3-20260924/run.json`（E2 提交中）。若重新编译，生成的是新二进制，不能自动冒充此认证字节；需作者建立新身份、验证与运行证据。macOS arm64 以外平台需另行移植和验证，不能声称已有同版本可运行。

缺件和责任人见本包 `MISSING.md`；核查报告在工作树 `docs/paper-acceptance/submission/attachment-audit-20260927/AUDIT.md`。

## 已有实验原件核对

`data-verification.json`记录三题1500份官方结果、500份无L2对照、100份单核基准与2000行附表数值的一致性。`p1-entry-evidence.json`记录P1的500份实际生产命令来源。两者是已有固定数据的核查结果，不是重新运行求解器或新环境复现；本包尚未通过运行验收。
