# 原生精确重放：有限正式接入探针

这是情况 A / Q1 的研究原型，不是生产 evaluator。源自已归档的专项 Pro 首轮答复与证据包，来源见 `PROVENANCE.json`。`src/replay.cpp` 保持 Pro 原字节；`replay_api.py` 修复一个本机正式图发现的 uint8 累加溢出。没有修改 `src/eval_exact/`、冻结原件、配置、依赖或官方接口。

## 已接通的边界

1. 由既有 `P1Evaluator` 验证图/计划并调用官方局部编译，得到包含 spill、COPY、incarnation 和内存依赖的真实 Task。
2. `pack_tasks` 将这个固定划分编成不可变数值数组。图、划分、带宽、容量固定；不同核归属和顺序不缓存答案，每次调用原生重放。
3. `score` 的私有输入是已准备划分加核内顺序。每个新顺序检查 Task 覆盖、重复和 Task 依赖加核顺序的联合环，再分配私有状态并重放所有事件。保留全部 DDR 更新时间点；只允许合并发射阶段的最终投影。

返回的是密集操作/Task 时刻数组和 Makespan，不是完整官方 JSON。元数据与完整轨迹输出仍应由正式实现处理；不能把这里的速度说成完整 JSON API 的速度。浮点等待、超过原型数字/核数边界或原生错误须交回 E1；当前原型抛 `Unsupported`，生产回退和准确异常分类尚未实现。

## 复现

从本仓库根目录执行，输出目录必须不存在。当前编译驱动针对已实测的 macOS arm64 / Apple Clang；没有测试 Windows/Linux。

```sh
uv sync --locked
uv run --locked python -B scripts/a_materials.py --extract
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  uv run --locked python -B research/a/native-replay-20260924/probe.py \
  --output results/a/my-native-probe --cases 002 003 008 --candidates 3 --repeats 3
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  uv run --locked python -B research/a/native-replay-20260924/batch_probe.py \
  --output results/a/my-native-batch64
```

第一个驱动从已审查源码编译 `src/libreplay.so`，禁用 fast-math 和 FMA contraction；生成的本机二进制不提交。第二个驱动使用同一二进制、记录其哈希，单个新 Python 进程包含首次动态库加载。输入来自只读官方图；每个计划、完整 E0 输出、原生核对记录、原始计时与源文件哈希都落盘。64 候选驱动流式写 16 候选一份的 gzip，不保留全部完整 trace 在内存中。

## 本机发现的修正

图 002 的一个固定划分有 3,779 次 DDR 发射。Pro 的 `sum(np.uint8_mask)` 在本机锁定 NumPy 环境会以 uint8 累加并溢出，造成审计日志分配不足，原生核安全返回 status=4。本机改为 `np.count_nonzero`，保持事件算法不变。失败运行单独保存在 `results/a/native-replay-probe-20260924/`，修复后的运行在 `results/a/native-replay-probe-20260924-v2/`，没有覆盖原记录或 Pro 附件。

## 交接边界

精确性证据限于已运行输入，不是全输入域证明。图/划分/config 身份与不可变生命周期、官方错误回退、进程池与硬超时、独立 worker RSS、多平台和长跑仍待工程化。原有 E1 继续作为可用回退与比较基线。频繁改变划分会再次付出局部编译成本，不能把高复用批次的收益外推为所有算法实验的统一倍数。

实现者要保留每次 DDR 的浮点更新顺序及同刻退休/激活/发射次序。不能把“纯计算节点不访问 DDR”当作删除其完成事件的充分依据；删除时间点可能改变共享 DDR 的浮点累计与整数取整。
