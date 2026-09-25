# accel-100 v3：官方单核分母纠正版

## 为什么要 v3

v2 的 c1 分母用 `stub_multicore_cut_and_schedule.generate_multicore_plan`（随机切图）在 1 核上执行，
队长在 #14 comment 5811875496 指出：**官方 README 第 93 行明确 `singlecore_evaluate.py` 才是单核基线**，
stub 只演示方案格式，不能当分母。v2 的 `speedupN` 列因此不作正式发布。

## v3 口径

| 项 | 入口 | 说明 |
|---|---|---|
| c1（分母） | `data/raw/a/official/code/singlecore_evaluate.py` | 原图全部非 COPY op 合一个子图放 core 0，直接调官方 CLI |
| c2..c5（分子） | `multicore_cut_evaluate_problem_1.py`（冻结官方 E0） | 候选生成与 v2 逐字一致：进程内复用 `src/q1/search.py propose`（取件自 `4dff90ef`），≤32 候选 / 60s 预算（含内部 E0）/ 单次 E0 30s 超时 |
| 加速比 | `c1 / cN` | 全部由官方程序产出，不是自写 evaluator |

## 对照验证（参考图 vs 两种分母）

| case | 参考图 2/3/4/5 核 | v3 官方分母 | max\|diff\| | v2 stub 分母 | max\|diff\| |
|---|---|---|---|---|
| 001 | 1.99 / 2.97 / 3.95 / 4.91 | **1.981 / 2.952 / 3.894 / 4.907** | **0.056** | 2.137 / 3.186 / 4.202 / 5.296 | 0.385 |
| 008 | 2.00 / 3.03 / 3.92 / 4.32 | 1.987 / 2.967 / 3.949 / 4.815 | 0.495 | 1.790 / 2.674 / 3.559 / 4.340 | 0.361 |

001 用官方分母后与参考图偏差从 0.385 降到 0.056。

## 产物布局

- `caseXXX/c1official/`：官方单核 result / trace / log / summary.json / `.cmd.txt`（实际命令行）
- `caseXXX/cN/`（N=2..5）：每个候选 `NNN_<kind>-{plan,result,trace,log}` + `best-plan.json` + `summary.json`
- `caseXXX/c1/`（仅主工作区）：v2 的 stub 分母原件，保留作对照，**不用于正式表**
- `caseXXX-summary-v3.json`、日志中的 `ROWV3:` 行

## 运行

```sh
python -B results/a/review/accel-100-20260924/v3/accel100_v3.py all 017 018 ...   # 分母+分子
python -B results/a/review/accel-100-20260924/v3/accel100_v3.py single 001        # 只跑分母
python -B results/a/review/accel-100-20260924/v3/accel100_v3.py sweep 038 039 ... # 只跑分子
```

断点续跑：`c1official/summary.json` 或 `cN/summary.json` 存在即跳过。
