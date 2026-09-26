# Join 候选跨平台测量包（尚未执行）

负责人/接收入口：方案成绩台 owner `nikolastarx/s-7c98eab1093e485291eacb04fd7c59ff`；[原任务 Issue 51](https://github.com/huaweibei123/huaweicup2026/issues/51)。这份交付是候选测量包，先由 owner 核对其本机容量、原件齐备及评分窗口后排队，不直接向 LYX/farmer 派发，也不在本成员 Windows 机器启动新测量。

1. **任务目标与机制**

   固定 `071d538ddae05ceda519d3b1b0844e987da908d5:src/q3_yuanzhifang/join_list.py`，只测 069/071/005/086、请求 5 核、各一个 `dag_join_list` 方案及同方案 P2/P3。069/071用于另一平台重现；005/086分别有 4,113/5,274 个计算操作，用于较大一般 DAG 的首次泛化检查。

   构造沿用真实 eligible 依赖守卫、串行链凝聚和逐 Pipe 时钟；当前链将释放唯一的多前驱 join 时，直接计算至多 k² 对核分配并一起追加。这个局部模型忽略共享 COPY、Cache、容量，不是官方最优或全局定理。没有在线 E0 或参数搜索。机制与两例合成边界见固定 [JOIN_LIST.md](https://github.com/huaweibei123/huaweicup2026/blob/071d538ddae05ceda519d3b1b0844e987da908d5/docs/a/q3-yuanzhifang/JOIN_LIST.md)。

2. **输入文件与既有控制**

   使用 `docs/a/source-manifest.json` 冻结的四图、`data/raw/a/official/code/` 全部官方源码和 `data/raw/a/official/data/config.txt`。图目录默认 `data/raw/a/official/data`，可用项目相对 `--graph-dir` 指向只读原件。预检只读取目标四图、代码/配置、固定算法及依赖、导出模板和四个现存官方单核基准；不构造方案、不调用 E0。未目标化的其他 96 图无需为此包新增测量。

   单核分母直接读取 `results/benchmark-board/official-singlecore-20260924/{case}/run.json` 引用的实际 `result.json.gz`，核对 graph/config/official 身份及存储字节 hash，要求 scene A、1 核、成功。不从发布 ratio×T 取整推导分母。缺失或 hash 不符则在评分前停止，向 owner 补取已有原件，绝不为缺上传重跑。

   | 图/k5 | 既有 P3 控制 | 固定来源 |
   |---|---:|---|
   | 069 | 15,221 | `ef80a88ed04b26e70465d56a54c373b0dcc5d00f` 的 join-list 批 |
   | 071 | 11,613 | 同上 |
   | 005 | 90,450 | 15:11 中央快照所接收的 `fd0a78b3f3e62357a3c04ebb77c1e7796b93dad9` feed |
   | 086 | 112,029 | 15:11 中央快照所接收的 `ba99b74b523f93a4002cd88970ec7164076d8008` 全500格 feed |

   069/071 控制原件及同计划 P2 见 [本成员既有4条 feed](https://github.com/huaweibei123/huaweicup2026/blob/ef80a88ed04b26e70465d56a54c373b0dcc5d00f/results/a/q3-yuanzhifang/join-list-20260924/board-feed-20260924T160841Z-join-list.json)。005 的固定 [中央已接收 feed](https://github.com/huaweibei123/huaweicup2026/blob/fd0a78b3f3e62357a3c04ebb77c1e7796b93dad9/results/a/p123-multicore-20260924/submissions/20260924-cases001-010/board-feed-20260924T133700.533615Z-cf4c0ea0d79a-001.json) 与086的 [全量 feed](https://github.com/huaweibei123/huaweicup2026/blob/ba99b74b523f93a4002cd88970ec7164076d8008/results/a/local-p3-20260924/20260924T1331Z-s59ee/board-feed-full500.json) 是冻结时点来源，不声称它们仍为最新最优。owner 在排队前核对这两图同核控制原件与当前接收状态；中央页面比值不能代替 result 原件。运行器不重跑控制，也不按控制分数选择新候选。

3. **输出要求与复现入口**

   新文件：`src/q3_yuanzhifang/portable_join_benchmark.py` 与 `portable_join_export.py`。`--producer-session`、`--run-label`、独立 `--output` 都必填；session 必须是实际执行人的小写 `login/s-ID`，run-label 每批唯一。输出路径须在本仓库 `results/` 下且尚不存在；拒绝覆盖、续跑和旧尝试重用。不要复制本成员 session/runtime 标识。

   接收方先在自己的环境运行 `uv sync --locked`。以下单行命令适用于激活相同项目环境的 Mac/Linux/Windows；须先替换示例 session、label 与目录。`--check-only` 不创建输出目录，不采集一份冒充实际执行时段的环境，也不启动 solver/E0：

   ```text
   uv run --no-sync python -B src/q3_yuanzhifang/portable_join_benchmark.py --producer-session actual-login/s-actual-session --run-label actual-host-utc-unique --output results/a/q3-portable-join/actual-host-utc-unique --graph-dir data/raw/a/official/data --check-only
   ```

   owner 确认容量与预约窗口后，用同样实参去掉 `--check-only` 才是实际批次。无需为了生成预检回执先调用任何构造函数。结束后执行：

   ```text
   uv run --no-sync python -B src/q3_yuanzhifang/portable_join_export.py results/a/q3-portable-join/actual-host-utc-unique
   ```

   每图保存原两字段 plan、完整 result/trace/log、stdout/stderr、真实调用账、manifest 与 run 收据。gzip 保全原字节并保存压缩/解压 SHA；目录自带 `* -text` 防 Git 换行转换。清理未确认的子进程可能仍持有文件时，保留未封存原件并明确标记，不能伪造稳定 hash 或成功结果。

   出口为 `board-submission-v1`：最多 8 条实际 P2/P3 记录，每图共享一次真实构造；原始总数以调用账为准。导出 producer session/runtime/时间/环境来自本批，算法作者仍按实际代码来源标注。另有逐记录 CSV。保存 Git 提交后运行 `protocol.py FEED --submission --commit FULL_SHA`，查看 `eligible` 与失败原因；预检不写成绩台。将固定提交、feed 和预检回执交 owner，不直接导入中央服务。

4. **限制条件与资源**

   建议上限已在新 runner 固定：4 cold solver、8 E0、1 worker；solver≤30 s/调用，E0≤60 s/调用；整批600 s，540 s后不派新调用，并在接近总上限时缩短调用超时，预留清理时间。首个失败、超时、守卫拒绝、身份不符或子进程清理异常即停，零重试/E1/E2/GPU/云。保全收尾计入批墙钟；若收尾异常或超出总时限，状态标 stopped，不能继续派发。069/071若成功后005失败，也不得用剩余额度试其他图。

   实时采集实际平台、CPU、总 RAM、Python/依赖 hash、线程/worker。Windows 用注册表和系统内存接口，Mac 用 `sysctl`，Linux 用平台/`/proc`/`sysconf`；不可用字段为 null 并给出 missing_reasons，不填0。GPU未使用，未枚举安装型号；峰值RSS未测。OS文件缓存不清空。运行窗口及其他进程争用由owner协调；实时环境文本不等于整机独占证明。

   Mac/Linux 每个子进程拥有独立 POSIX process group，超时只杀该组；Windows只对本次 PID 执行 `taskkill /T /F`。清理错误记录并停止，不影响其他任务。solver墙钟从进程启动至输入读取、在线全部构造/验证、写盘及退出；外部官方 E0 墙钟另列。Python冷启动、不同硬件与单次噪声使跨平台时延不能直接充当算法优劣证明。

5. **验收标准**

   本轮包准备只做静态语法/配置与 `--check-only`，零solver/E0；Mac/Linux实际运行、超时树清理、环境探测以及四图新输出尚未实测，不能把“代码包含分支”称为跨平台验证通过。包由根会话审阅后，交 owner 容量核对、排队。

   实际批次验收：冻结字节预检通过；所有实际调用记账，无补跑；官方容量、依赖、spill/额外DDR/按字节Cache原样保留；069/071与固定Windows质量原件逐项比较，差异调查不覆盖。跨平台原计划的换行可能不同，保留各自真实字节hash，另外比较解析后的两字段内容，不能改写原件去凑相同hash；本批每图的P2/P3必须引用同一个实际plan。005/086保留正负收益和与现有中央原件的比较。冷solver与外部E0分别报告。标准feed固定提交预检通过只表明格式和可用字节，不代表独立复跑、盲审或算法最终验收。

6. **截止时间**

   未另设运行日程；由 owner 在可用容量与评分窗口确认后安排，并记录实际UTC T0/T1。此交接不自动启动任务或扩大预算，也不替代全100图/1–5核研究。

## 包准备验证记录

代码冻结提交 `60477a382514cb6e97bfd8ea1bb560fda1594c06`。本成员在 Windows/Python 3.12 环境执行静态 AST 语法与 preflight 调用检查，并仅运行以下只读命令：

```text
.venv/Scripts/python.exe -X utf8 -B src/q3_yuanzhifang/portable_join_benchmark.py --producer-session yuanzhifang30-sudo/s-3d9c78db26714786b88b987ca6f58e2b --run-label portable-check-only-20260925 --output results/a/q3-yuanzhifang/portable-preflight-only-20260925 --graph-dir ../huaweicup2026/data/raw/a/official-cases/data --check-only
```

返回 `verified_files=15`（四图、配置、10份官方代码），四个既有单核基准及固定实现/依赖/模板核验通过，`calls_executed=0`。核实上述输出目录没有被创建；没有新plan、result、feed或测量时间。环境采集延后至真正执行host，Mac/Linux运行和树清理分支未实测。本记录中的成员session只描述已完成的只读检查，接收方实际运行必须使用自己的session与新label。
