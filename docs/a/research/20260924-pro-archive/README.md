# 四路 Pro：实物归档与 Q1 使用边界

2026-09-24 已从四个现有 ChatGPT 会话下载实际文件。六个 ZIP 共 399,323,002 bytes，包含 17,983 个文件（跨包有重复，不是独立实验数）。全部 ZIP CRC 通过；重新封装后的每个文件与下载 payload 的 SHA-256 一致。未执行下载包里的程序。

完整文件放在 `results/a/pro-research-20260924/`，总归档约 292 MB；`manifest.json` 记录会话来源、原始 ZIP 大小/哈希和归档哈希，各包的 `*.manifest.json` 逐文件列出哈希。使用 tar.xz 仅减少重复压缩开销，不删除失败记录、源码、图、方案、结果、trace 或作者校验器。第二路大包按 48 MiB 分片，以满足 Git 单文件限制；按 `.part000`、`.part001`……顺序拼接可恢复清单中的 tar.xz。原始下载 ZIP 仍保留在本机下载目录。

常用阅读入口（相对仓库根目录）：

| 来源 | 可读报告 | 直接作用于 Q1 的部分 | 暂不能直接采用 |
|---|---|---|---|
| 第一路 R3 | `results/a/pro-research-20260924/reports/pro1-r3/RESEARCH_MEMO.md` | 非分叉链包、完整增广 DAG 的 cover 合并、出口释放风险 | 无容量 resident 集不能表示 Q1 Task 间驻留；纯计算矩阵不是含 DDR/spill 的 Task 真值 |
| 第二路 R2 | `results/a/pro-research-20260924/reports/pro2-r2-prototype/RESEARCH_MEMO_ROUND2.md` | must-link/SCC 商图闭包；共享输入按 Task 聚合；大块/小块候选组合 | Q2/Q3 阶段资源词与同核输入复用不能直接迁到 Q1 |
| 第三路 R2 | `results/a/pro-research-20260924/reports/pro3-r2/REPORT.md` | 保持事件次序的精确加速；缓存上下文守卫；浮点重排反例 | 固定 Q2/Q3 编译上下文的完整词不能作为 Q1 通用缓存键 |
| 第四路初版/追问版 | `results/a/pro-research-20260924/reports/pro4-initial/REPORT_ZH.md`、`reports/pro4-followup/RESEARCH_REPORT.md` | 内存压力候选特征、失败例、Q1 粗粒度回退 | singleton 区间无 spill 充分证书限定 Q2/Q3；不沿用初稿充要表述；未证明 Q1 适用 |

`results/a/pro-research-20260924/source/` 提取了 79 个源码文件，便于 GitHub/ChatGPT 直接读取，逐字哈希见 `readable-source-manifest.json`。它们是研究原件，不是本项目生产模块；不会自动安装依赖或导入主算法。

本目录保存前三路完整勘误回复 `PRO1_ERRATA.txt`—`PRO3_ERRATA.txt`、摘要、第四路两次回答、准确追问与接收审查。前三路自查仍是待验意见；其“已读文件”是它们的自报，不代替我们逐项验收。第四路最新下载报告与页面一样，主要是另一轮 Q2/Q3 研究，没有交付要求的逐项勘误影响矩阵。该审计仍未闭合，详见 `PRO4_FOLLOWUP_REVIEW.md`。

特别纠正阅读中容易继续传播的两点：

- 只固定**一个**共同拓扑序是受限搜索族；但“存在某个共同拓扑序，各核顺序是它的子序列”与完整 Task 数据依赖加核链无环等价，不能把所有这样的顺序一概说成必然丢失可行解。
- Q1 的局部编译输入和边界构造必须按冻结源码确定。第三路关于跨 Task backing 可能成为自由状态的研究设想尚未证明，不据此扩充当前模型或缓存键。

字节校验只证明材料完整，不证明作者实验可复现、数学结论正确或算法普遍有效。历史缺失的 295 份结果仍缺失，本次不从摘要重造。此前 `20260923-round2/` 的“尚未取得附件字节”是当时记录，本目录更新当前状态。

## 当前落实

Q1 自研代码在 `src/q1/`；读取研究建议后独立实现链/弱分量构造、官方局部编译辅助分核、完整增广 DAG 的合法合并，并对保护/不保护出口分别调用 E0。见 `docs/a/Q1_PROTOTYPE_START.md`。高速 evaluator 已由“复核队友E1和E2成果”会话独立交付于 `5bfe53a29c1ba05167239f51ea937e602f7f85b4` / Draft PR #30；本会话对 30 次真实候选调用完成全部引擎字段的 E0 集成抽查。两份代码仍各自处于独立 PR，不把提交者自测或此次抽查称为独立终验。

同步时先发布团队库分支，再运行既有 `scripts/sync_vioano_mirror.py`；不能把组织 PR 当成 ChatGPT 的读取入口。对 ChatGPT 提供 Vioano 镜像的固定提交及以上可读文件路径。
