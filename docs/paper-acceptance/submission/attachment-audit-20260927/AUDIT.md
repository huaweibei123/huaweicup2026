# A 题提交附件有限核查（2026-09-27）

## 结论与交付状态

[附件候选 ZIP](../../../../output/paper-submission-20260927/attachment-a-source-candidate.zip) 是**来源可追溯的离线源码与输入候选**，不是已证明跨机即用、可复现论文全量成绩的最终程序附件。v13 继承的 `source-code-v10.zip` 是完整源码模块审阅包：含七份论文展示模块及三套固定提交的 `src/` 快照、官方评价源码和配置；它并非只有伪代码。P1、P2、P3 均可静态找到算法入口，但 P2 依赖固定 Git 对象与缺席的认证原生二进制，P1 源码中的旧研究性注释已由500份实际生产记录补证：固定入口确为 `src/q1/branch_refine.py`，不能仅据旧注释判定不存在全量证据。本轮不改程序，也不运行求解器或评价器。

P1/P2 是原题明列的提交脚本核对重点；P3 的成对 Cache 复现代码列为配套完整性。原题正文、附录与 1500 个官方结果数值由主代理独立核对，本报告不覆盖其结论。

## 固定来源

| 项目 | 已核身份 | 静态判断 |
| --- | --- | --- |
| v13 沿用的源码 ZIP | `paper/manuscript-v1/checkpoints/v13/attachments/v10/source-code-v10.zip`；SHA-256 `1bd41bc1beaefb97b9b2cc9fac72c71103b9933cf497e1841eacf0c95bf219d1` | 与 v12-anonymous、组织固定 v12 提交 `6389c68f4c5e7e3003ad79c09253076156b89b36` 的同路径 ZIP 字节哈希一致。v13/v12 README 均标为审阅附件。 |
| P1 | `834d8c957538ee069c66aadac9509552a4cc69d7`；`src/q1/branch_refine.py` SHA-256 `aca4939eed36b953c94eeac9981aea35e40216adf0007eb1aac0d5e96db83f71` | ZIP 与固定 Git 对象逐字节相同。CLI 有 graph/cores/output/diagnostics；父求解器 `structural_refine`，至多加一次 E1。文件自身写明研究性、没有全矩阵验收。 |
| P2 | `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`；`src/q2_nikolastarx/adaptive_hypergap_guarded.py` SHA-256 `ce888dc91b7f29a42622ca699d553aca9716f56b0afeb9c54af5331ca0d0a01e` | ZIP 与固定 Git 对象逐字节相同。`build` 构造 baseline/gap/hypergap，主入口转到 `adaptive_guarded.main`，三次 E2 上限；缺 E2 认证原生库，不能解压即运行。 |
| P3 | `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`；`src/q3/forest_solve.py` SHA-256 `f11ffd5bf04f7e5aa113d584ed7f147ac20b8d01c8f5ce7ce521aa8a71aa6c5c` | ZIP 与固定 Git 对象逐字节相同。入口转到 `safe_solve`，包含候选池与 E0 调用；本轮只做静态核查。 |
| 官方输入 | 固定 v12 提交中的 `data/raw/a/official-cases.zip`；SHA-256 `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528` | 与当前只读原件哈希一致；含 `case_001` 至 `case_100` 100 个 JSON，压缩 CRC 通过。源码 ZIP 原来没有这些图。 |
| P2 E2 清单 | P2 固定提交的 `results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json` | 清单中 50 个 `e2_sources` 与源码 ZIP 的 `dependencies/E2-source/` 逐文件 SHA-256 相同；认证二进制未提供。 |

v13 论文正文 `main.tex` 的附录 C/E、`attachments/appendix-supplement-20260927/source-details.md`、源码 ZIP `README.md` 都把这三项列为固定入口；论文 v13 README 虽称“外置完整代码”，其附录 E 和源码包 README 同时限定为源码审阅附件。静态状态须按后者的运行限制解读。

## 完整性与接口边界

- 原源码 ZIP 326 个成员：清单登记 325 个普通文件，逐项大小及 SHA-256 均通过；其中 289 份 Python 源以本机 Python 3.14.5 的 `ast.parse` 均通过。三个快照的 `.python-version` 均为 3.12；各有同一锁文件及 `pyproject.toml`，要求 `>=3.12,<3.13`，声明 numpy、pandas、scipy、matplotlib。未用 Python 3.12 安装或执行，故不能以语法静查证明目标环境可运行。
- 257 个快照条目中，254 个有 `commit:path` 的源文件与本地固定 Git 对象逐字节匹配；其余三个是 `SOURCE_COMMIT.txt` 元数据，分别记录 P1/P2/P3 的完整提交号，不是原 Git 文件映射。七个展示模块在 `paper-listings/`，正文六段伪代码用于解释算法决策；不能单独作为运行程序。
- P1/P2 实现含顶层 `node_to_subgraph`、`core_schedules` 两键的静态检查；P3 构造可见两键，外部结果尚未生成。官方配置 `config.txt` 在各源码快照内。各入口接受图文件和核数，指定新输出与诊断/证据路径；没有抽取实际输出，也没有逐格格式验证。
- P2 的 `adaptive_guarded.check_e2_source` 要求 macOS arm64、固定 Git 对象 `603b0741e21c449d3db652ebd67c94f2dc014cc9`，通过 `git archive` 校验 50 个源文件，还要求 `research/a/e2_search/native/libreplay_bc.so` **36,784 字节**、SHA-256 `0f765b7b1229ea221881ff8e017ba7d37b64461eded6afb7f48e9cf61bfd4e94`。该库不在源码 ZIP、E2/P2 固定 Git 提交或本工作树对应目录。已有 C++ 源与构建脚本可供审查，不等于得到同一认证二进制。不要移除校验、补假 Git 或把新构建库称为旧认证库。
- 主验收者补读固定提交 `a1bb4451cd85c46b32bb928d57c81e22cfeca1a6` 的500份真实运行记录，逐项核对压缩原件哈希、实际 argv、成功状态、固定求解器提交与方案哈希，均指向 `src/q1/branch_refine.py`。见 `p1-entry-evidence.json`。旧研究注释不再作为“缺生产证据”的依据；新打包目录的独立执行仍未验证。
- 主验收者已核500份P3无L2配对结果、500份Cache结果、固定配置与对应方案身份，见 `data-verification.json`。这解决已有数值来源核对，不代表新打包目录已独立复现。

## 附件候选结构

外层 `attachment-a-source-candidate.zip` 包含未改字节的 `source-code-v10.zip`、`official-cases.zip`、P2 原清单 `p2-e2-manifest.json`、`README.md`、`MISSING.md`、`SHA256SUMS`、`FILE-SHA256.tsv`。`FILE-SHA256.tsv` 有 426 个内层成员 SHA（源码 326、输入图 100）及 7 个顶层原件/说明的 SHA；外层 ZIP SHA 在 `output/paper-submission-20260927/SHA256SUMS.txt`。这是可移植的**来源运输与离线核验包**，不声称 P2 可移植运行。解压与使用说明在 [BUNDLE-README.md](BUNDLE-README.md)，待补原件在 [MISSING.md](MISSING.md)。

## 验收与停止点

已做：固定提交与 ZIP 身份核对、325 项原清单 SHA/大小、254 项 Git 源字节核对、50 项 E2 源清单核对、100 图计数与 ZIP CRC、289 份源码静态语法、入口/路径/依赖静读、外层 ZIP CRC 与哈希。未做：安装依赖、Python 3.12 运行、`--help` 导入测试、任何求解或官方 E0/E1/E2、全量成绩复核、跨平台/作者生产环境验证。新 benchmark 和评价调用数为 **0**。实验验证需算法作者按原预算与固定版本回交，本轮不会自行启动。

责任人下一步：P2 作者补认证二进制与真实Git依赖，或给不可分发结论并提出合法新版本；三题程序均需完成独立附件运行验证。P1生产入口与P3成对数值的既有证据已由主验收者补核。详见缺件清单。模型/推理按派工 Sol/medium；软 token 上限 12,000，实际用量不可用；无递归派工。工具调用未超过 40 次，未超过 15 分钟停止线。

## 主验收者合并复核

Sol只读附件来源，主验收者读取正式结果与运行原件，二者覆盖不同。最终候选额外收录 `p1-entry-evidence.json` 与 `data-verification.json`；README及缺件清单采用合并后的事实。旧候选哈希59d08025开头不再作为当前下载身份；当前SHA见同目录附件收据。无求解器或评价器新增调用。
