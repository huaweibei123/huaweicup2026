# Stage H：已完成的两项官方验证

本节更新于2026-09-24，下面的 preparation checkpoint 保留为运行前历史，不代表当前状态。冻结原件提交 `1c9b654223b663f6e624fc413913c076c843ed56` 已包含2次冷solver与2次外部未修改E0，0 E1/E2/重试；实际T0/T1为18:40:41.171005Z/18:40:44.759613Z，单worker，总3.588254秒。两个051/k5计划均合法成功。

| 变体 | Makespan / cycles | extra DDR / bytes | solver wall / s | external E0 wall / s |
| --- | ---: | ---: | ---: | ---: |
| four-core-start-v1 | 233539 | 9045396 | 0.5151505 | 1.0504761 |
| four-core-start-subtrees-v1 | 231551 | 9044736 | 0.5779331 | 1.0537121 |

两者spill均0。方案、官方result/trace/log和运行凭据在 `run/`，正式feed为 `board-feed-20260924T184059Z-stage-h.json`。中央实际accepted receipt `e3932eeb0314e31a50878f6d33a764b0dc841b8cb26b02a2bf76645cc7fdf047`，batch `df87b1170f786acb38841fbed8d9e9a135004e934e85fe7de53cd19f05feb631`，18:43:09.131063Z接收2记录/2eligible。接收不是全量成绩或最优性证明。

## 原运行前检查点（历史）

051/k5 only: `four-core-start-v1` and `four-core-start-subtrees-v1`, fixed author `4f1b9f8be4bbcc98759a19451c108e62e80abb17`. See [task card](../../../../tasks/a/q1-yuanzhifang-stage-h.md).

At this preparation checkpoint: 0 solver/E0/E1/E2, no real-plan construction, no Task compiler or full graph scan. Maximum separately authorized budget is 2 solver + 2 E0, 30/90 seconds per process, 360 seconds batch, one worker, no retries. Await parent review and explicit START. C/G originals are reused comparisons, with 0 baseline reruns.

This is an exposed single-case development comparison, not a unified all-100 result or target-achievement claim. All outcomes will be retained. Original result bytes use `-text`; Windows `dot_clean` unavailable, own output metadata scan required at delivery.

Preparation source/input/reused-evidence check passed at c197d728 in 16.269336 seconds; command/syntax checks confirm distinct fuse flags and no imported constructor/Task compiler. Receipts retain all hashes; run directory remains absent. 0 new solver/E0/E1/E2 calls. Source dependencies, test and document bytes equal author 4f1b9f8b. Waiting for parent START.
