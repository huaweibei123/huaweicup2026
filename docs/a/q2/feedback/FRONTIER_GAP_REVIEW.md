# Frontier gap 首轮独立审阅（2026-09-25）

审阅范围：`src/q2/feedback/frontier_gap.py`、`physical_frontier.py` 与 `construct.py` 的新 CLI 分支，只读前两份源码；仅在 `tests/q2/test_physical_frontier.py` 增加两条小图官方**前缀**差分测试。未运行全局 `evaluate_scene_b`、官方大图、solver 或 E0；未修改冻结的五份算法文件或既有测量结果。

## 路由与证书

- `frontier_gap.build` 先拦截 `logical_tid` alias 并走原 gap 路线，明确标记未认证（`frontier_gap.py:92-96`）。随后仅在 `word_descriptor()` 成功时构造 `resource_word`，而且仅当 `physical_frontier.certificate` 全核通过才早退（`:98-109`）。word 构造本身仍由 `Index.build` 和官方 `derive_multicore_plan` 校验合法性。
- 其余走原 `gap_build`。原方案全核获证则不改顺序（`:111-118`）。否则只尝试未获证的核；弱分量不完整地分到该核便跳过（`:26-47`）。共享输入签名按首次作业顺序分组；组内宽度为既有 `memory_window`，每核每组最多一个 `pipe_window` 候选。拼接后完整 `footprint` 超容量即回退该核（`:48-80`）。最终再以含原 tensor、异核 direct UB token 的物理证书核对已改核；未改且未获证的核保持诚实未认证（`:120-128`）。没有按图号或历史分数择优，也没有在线 E0。
- `physical_frontier` 保留每核 token 首末桶、峰值桶及当桶 live token。原 tensor 每核物理副本只计一次；原 DDR 本地副本归 UB；异核 direct 边在两端各建独立 UB token（`physical_frontier.py:37-65,85-95`）。`base_copy_bytes/count` 按消费核、最终输出核及 producer/destination 核对累计，源 tensor 扇出不会少计 COPY 工作（`:69-83`）。逐桶先加后减是 Step2 闭区间**充分**包络；它不声称最终全局驻留或 Makespan 上界（`:97-130`）。

这一修复支路对完整弱分量同核使用旧 `capacity_window.footprint` 作候选筛选，是安全的：跨核原 tensor/direct 边会连接 eligible 弱分量，故若该分量完全在一核，不存在遗漏的异核 direct 本地 token；最终仍用独立物理证书复验。当前未找到一个会让已标记 `capacity_certified=True` 却发生 Step2 spill 的源码反例。拆分分量与 alias 继续保留原计划或未认证，不把局部证书扩张到这些分支。

## 有限差分验证

新增两条 tiny fixture 测试均只调用未改的 `_build_scene_b_tasks`，截至本审阅共 **4 次前缀调用**（两次交互预检、两次正式测试），0 次全局 E0：

1. 一份 L1 输入、一份原 DDR 输入、一个源 tensor 发往两个核且其中一核有双消费者，并含 0 B/3 B 异核 direct 边。证书峰值为核0 `L1=9, UB=16`，`base_copy_bytes=43`、`base_copy_count=11`；官方前缀 `spill_added_copy_bytes=0`，实际基础 COPY 字节/条数也是 43/11。
2. 将同一四操作图放到一核并加一个空核：同核 direct 边不建 UB token，空核 token 与峰值均为空/零；证书与前缀均给出基础 COPY 17 B、3 条，spill 为 0。

命令：`.venv/Scripts/python.exe -X utf8 -B -m unittest tests.q2.test_physical_frontier -v`，含原测试共 **5 项通过**，运行约 0.006 秒。这是极小结构对照，不等于官方 100 图覆盖，也不检验实际 Makespan、DDR 公平竞争、较大图时延或最终方案优劣。

结论：当前结构守卫、保守回退和物理容量证书的实现范围相符，可以进入事先固定的小批量官方证伪；任何 `capacity_certified=False` 都不能被解读为计划非法或必然 spill。下一阶段须单独报告 Step2 spill、官方 Makespan、额外 DDR 字节与从进程启动到计划落盘的墙钟。
