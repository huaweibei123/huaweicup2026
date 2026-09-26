# 华为杯 A 题 · 第三路第二轮研究交付

**入口：** [研究报告](REPORT.md) · [研究卡](RESEARCH_CARDS.md) · [机器可读汇总](evidence/SUMMARY.json) · [未完成/探索性运行](evidence/INCOMPLETE_RUNS.md)。

这是可执行研究原型与证据，不是全100例正式参赛结果或 E1/E2 发布验收。

## 标识

- 官方代码集合：`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- `S`：保留事件与浮点运算序列的热点改写，源码在 `fast_code/`；部分历史文件名写 `R2`，意为研究第二轮，**不是问题2，也不是团队 E2**。
- `W`：Q2/Q3 固定算子到核心映射下的完整增广操作词等价缓存。
- `W_E0`：W 未命中时使用冻结官方局部过程；`W_S`：未命中时使用 S。
- `solve.py`：少量构造候选的官方确认器，所有实际更新 incumbent 的候选调用未改动 E0；不是依赖代理分数直接提交。

## 环境

本次实际：Python 3.13.5，Linux x86_64，AMD EPYC 9V74 宿主，容器暴露5逻辑CPU；性能实验单Python线程/一次一个进程。没有GPU测试。原型只用Python标准库。Mac/Windows的运行兼容性尚未实测；`spawn` 选择不等于跨平台验收。

## 首次使用

在交付目录运行：

```bash
python verify_delivery.py
cd input_bundle
python VERIFY_BUNDLE.py
python scripts/a_materials.py --extract
cd ..
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/build_accelerator.py
```

ZIP不重复保存约240MB的已解压 case JSON，而是保存完整的原始 `official-cases.zip`；`a_materials.py --extract` 恢复100份原始JSON，并按114文件清单逐字节验证。不是用摘要代替输入。交付包内已有正式源码、两份说明、配置、题面、FORM/FAST和64份给定真值。

## 生成方案：只调用官方确认

请用**新证据目录**，不覆盖现有成功输出：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/solve.py \
  input_bundle/data/raw/a/official/data/case_080.json \
  --config input_bundle/data/raw/a/official/data/config.txt \
  --problem 2 --cores 4 --budget 300 --max-candidates 10 \
  --output runs/repro_080_q2_multicore_res.json \
  --evidence runs/repro_080_q2
```

问题3将 `--problem` 改为3，并使用不同输出路径。命令的 `--output` 只有官方两字段；其他资料都在 `--evidence`。如果预算内没有官方确认的方案，程序明确失败，不生成伪成功。

预算说明：总计时包括父进程准备、候选构造、词检查、子进程启动、官方评估与落盘；官方评估子进程有硬终止。父进程的一次图准备或候选生成不是可抢占步骤，极大图可能在该步骤越过预算；本原型不是严格最坏时间保证。当前实测60秒预算/最多5候选的case080两问分别用4.66秒、4.53秒完成。

## 单个方案用 S 的官方风格 CLI

```bash
python fast_code/multicore_cut_evaluate_problem_2.py \
  input_bundle/data/raw/a/official/data/case_080.json \
  results/solver080_q2.plan.json \
  --config input_bundle/data/raw/a/official/data/config.txt \
  -o runs/s080_result.json \
  --trace-output runs/s080_trace.json \
  --log-output runs/s080_log.txt
```

运行前创建 `runs/`。用于正式确认时将 `fast_code/` 换为 `input_bundle/data/raw/a/official/code/`。原件永不覆盖。

## 复跑研究证据

请保留原ZIP只读，另解压一份工作副本。以下脚本默认写固定的 `results/` 子目录，复跑会更新该副本的对应记录；原ZIP及其哈希是本次实验身份。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/fork_probe.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/hol_probe.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/fifo_hit_probe.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/float_counterexample_strict.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/random_regression.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/regress64.py --start 0 --end 64
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/epoch_check.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/canonical_plan.py --case 097 --q 3
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python src/benchmark.py --case 003 --q 1 --kind intervals --repeats 3
```

`word_ablation.py` 要求输出目录尚不存在；先在复跑副本中将 `results/word_ablation/080_q3` 改名，再运行 `python src/word_ablation.py --case 080 --q 3 --repeats 5`。该脚本读取已有 `results/word/` 的八个不同方案。

`runtime.strict_equal` 比较完整字典键、值类型、列表顺序，float比较binary64字节；不使用`isclose`。给定gzip真值比较仅做JSON自身的整数对象键字符串化，不删字段。CLI对照另外检查result、trace和log三件字节一致。

## 尚未工程化的边界

W上下文固定图、配置、问题、核数、逐算子核心映射、mapping插入顺序和源码版本。改变任一条件必须重建上下文；返回对象按只读使用。其cache当前没有LRU/内存上限，多唯一词搜索应加字节预算。模块隔离加载与AST截取是冻结源码研究适配层，不是线程安全公共服务。对原图直接Op→Op输入明确不支持该W特化，因为题面不允许该输入；E0自身接受域不扩大为竞赛域。

原型不声称通用图同构等价，不重新编号原始op/tensor，不让核内操作任意越过FIFO，也不添加题外的等待、预取或重算。
