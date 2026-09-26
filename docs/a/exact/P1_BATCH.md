# P1 精确批量 evaluator：首个工程版本

用于情况 A / Q1 搜索。同一划分只编译局部 Task 一次，每个候选重新校验方案并完整模拟全局 FIFO、事件、核间等待和共享 DDR。划分、容量或带宽改变时重编译；图在实例创建时快照，换图创建新实例。只支持 P1，不把该复用边界外推到 P2/P3。

E0 保持原件作为最终核查基准；此实现属于 E1 的精确批量能力，不另造 E3/E4 公开格式。E2 近似研究代码保留在原 FAST 分支，本 PR 不导入或更改 E2。这里的有限自测不等于独立验收或通用 3 倍门槛通过。

## 最小接口

```python
from src.eval_exact import P1Evaluator, P1BatchEvaluator, read_config

config = read_config("data/raw/a/official/data/config.txt")
engine = P1Evaluator(graph, cache_bytes=16 << 20)
result = engine.evaluate(plan, **config)  # 官方完整 P1 对象；原异常类型/消息
assert isinstance(result["makespan"], int)
print(engine.cache_stats())
```

`graph` 和 `plan` 直接使用官方 JSON 加载后的对象；不增加方案字段。配置由官方 reader 读取，调用参数为 `bandwidth/capacity/cross_core_wait/same_core_wait`，可另传 `max_iter`。现有 `python -m src.eval_exact.cli` 保留 FAST 的完整 CLI/Trace 行为，仍走原 E1 单次入口；新能力由以下队内 API 提供，不声称批量搜索记录就是官方结果文件。

```python
import json
from pathlib import Path
from src.eval_exact import P1BatchEvaluator, read_config

def main():
    graph = json.loads(Path("data/raw/a/official/data/case_003.json").read_text())
    config = read_config("data/raw/a/official/data/config.txt")
    # plans 是官方方案对象的 iterable，也可以逐个读取不同方案文件。
    plans = [json.loads(Path("my_plan.json").read_text())]
    with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20,
                          timeout_seconds=60, max_tasks_per_worker=256) as pool:
        for row in pool.evaluate_batch(plans, full=False, **config):
            if row["status"] == "ok":
                print(row["index"], row["makespan"], row["data_movement_bytes"])
            else:
                print(row["index"], row["status"], row["error_type"], row["message"])

if __name__ == "__main__":  # spawn 必需；不要在导入模块时启动进程
    main()
```

同一 `pool` 可用于多批；同一实例禁止同时提交两个批次。`P1Evaluator.evaluate_batch` 是同进程流式接口，没有墙钟超时；有硬截止需要使用隔离进程池。`full=False` 仍完整计算官方结果，仅减少父子传输与调用方保留量；`full=True` 在记录的 `result` 内返回整份官方对象。不是省略语义核查的 metrics-only 模拟。

记录的 `status`：

| 状态 | 含义 |
| --- | --- |
| `ok` | 官方完整模拟成功；含 makespan、data_movement_bytes、cross_task_traffic |
| `invalid` | 官方明确的图/参数/方案校验拒绝；含原异常类型/消息 |
| `timeout` | 工作进程超过候选墙钟预算，被终止；不产生合法性结论 |
| `error` | 模拟限制、deadlock、未知错误或进程崩溃；不假装 invalid |

成功和运行异常记录含累计 `cache`、引擎版本、冻结源码哈希和调用耗时；进程池另含 worker PID、CPU 秒、RSS 高水位（不支持的系统为 null）和派发墙钟。超时/崩溃的 cache 为 null，不能编造未返回统计。初始化/读取配置失败直接抛出设置错误，尚未派发任何候选，不生成虚假的候选成绩。底层 `evaluate` 不包装异常；调用方需要捕获或改用 `evaluate_record`。

## 复用及资源约束

- 每个实例持有私有、哈希校验过的官方模块，未修改官方原件或 E0 模块。普通源码维护状态计数和输出分组，不在运行时替换字符串或生成函数。
- 缓存保存不可变序列化字节，每次命中独立还原，并重建官方集合邻接顺序。核归属、前驱、plan view 每次刷新。返回结果和后续候选不共享可变状态。只有整次全局评估成功后才提交新缓存项。
- `cache_bytes=0` 关闭复用；`max_cache_entries` 默认 128。字节额度是 key+value 载荷，不包括 Python 对象、原图、编解码临时对象和官方结果，也不是 RSS 上限。过大的单条结果直接不缓存，不修改有效性结论。
- `workers` 显式设置，默认 1；最多每 worker 一个在途候选，以 worker 数为一批分块流式返回，输入和输出缓冲有界。不同图/划分尽量由调用方分组；当前不跨 worker 共享缓存，也不做任务亲和性路由。不同耗时混合时分块策略会损失部分吞吐。
- 总进程预算由搜索调用方分配，不要每个外层实验再开满内层 workers。worker 缓存预算总量至多 `workers * cache_bytes`，进程内存需单独测量。
- 默认每 256 次请求回收一个进程，降低长期累积风险；会失去该 worker 缓存。单次评估内存仍取决于图/轨迹规模，尚无跨平台硬 RSS 限制。缓存关闭、减少 worker 和缩短回收周期可以调节占用。
- `timeout_seconds` 为派发到回应的预算，`None` 关闭；启动另有默认 30 秒截止。超时和崩溃的进程被回收，下一候选用新进程。取消时关闭迭代器或退出 pool 的 `with`，不留下后台评估。管道传输/OS 调度和进程清理有少量额外耗时，不是实时系统保证。

## 复现

```sh
uv sync --locked
uv run --locked python -B scripts/a_materials.py --extract
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 uv run --locked python -m unittest discover -s tests/eval_exact -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 uv run --locked python -m src.eval_exact.batch_benchmark --output results/a/exact/my-new-run --cases 002 003 --repeats 3 --candidates 12 --resource-count 64
```

基准拒绝覆盖现存输出目录。正式图从冻结 ZIP 读取；固定 seed 和全部计划随运行落盘。计时包括首次局部编译、校验、键计算、还原、集合重建和完整结果，解析图/计划的 IO 在外，实例初始化单列。先跑原版，再按预设次序交替测量，逐候选严格比较完整对象类型和值。资源检查的 64 请求是对 12 个不同候选的重复运行，不能写成 64 个不同方案吞吐。源文件哈希、配置、依赖、环境与计划一并记录。

## 来源与验收边界

旧 E1 的 `_official.py/problem1.py/cli.py/benchmark.py` 与 11 项测试导入自 lyx0217 固定提交 `d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f`；本次仅将 indexed builder 的 runtime 依赖参数化，以供多个实例隔离。新全局模拟器 `_scene_a.py` 派生自冻结官方 P1 文件 SHA256 `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`。不改变事件计算，仅消除完成状态全量扫描和重复输出筛选。

机制来源是交接 `63353fd771b5c2e643ec25f39d61a0b1729347af`。FORM 公开定向输入来自 `65d6c0e6facee2ec8ce9694c30dd805de99abf7e` 的 `tests/adversarial/dev-samples.jsonl`；L1 backing/多 incarnation 用例来自情况 A 独立语义复核的 `tensor_graph`。复用其输入重新对照 E0，不把他人原成绩当作此实现的测试。

当前验证记录见 `results/a/exact/p1-batch-20260924/`。所有检查由实现会话执行；之后由算法会话单独做集成和抽查。未验证 P2/P3、Windows/Linux、正式大图 spill 全矩阵、数小时运行、全错误域和封存集；不声称通用 3 倍发布标准通过。

任务六字段：目标是可接入的 P1 精确批量评估；输入是上述固定 E0/E1/机制材料及官方 graph/plan/config；输出为 src/eval_exact、tests/eval_exact、本文、实验记录和 Draft PR；限制是不改原件/契约/队友分支且显式预算；验收为范围内 full/异常零差分和有限成本实测；交付节点为本轮首个可接入版本，独立验收另行记录。
