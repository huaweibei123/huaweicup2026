# F1 固定算法的 5 核 100 图结果

本表仅汇总已经结束的 round16b、round17a、round17b、round17c，未再运行求解器或 E0。014 复用 round16b，另外 99 格来自三个 33 格批次，没有重复取优。源码固定 `4a501d7f4a8b780263e097a963e12dcb66178e69`，variant=`frontier_gap`，args=[]。coverage.json 核对七份源码、官方源码/配置、输入图、单核基线与保存结果哈希，100 个唯一 case/k5 全部有效。

| 指标 | 结果 |
|---|---:|
| 5 核覆盖 | 100/100 |
| 逐图固定单核基线 M / F1 M 的算术平均 | 3.8882093912295597 |
| 同口径旧 tensor 平均 | 3.89603690404328 |
| 同口径 gap 平均 | 3.6765753297355195 |
| F1 对旧 tensor：改善/相同/退化 | 42/17/41 |
| F1 对 gap：改善/相同/退化 | 3/96/1 |
| 额外 DDR 总字节 | 1823304488 |
| spill 总字节 | 652269884 |
| 这 100 格实际 solver / 外部 E0 | 100/100 |
| solver 阶段墙钟合计（秒） | 438.65676699998585 |
| 外部 E0 阶段墙钟合计（秒） | 475.5181540999547 |

差值比较按每格 Makespan，原件为相邻 all500、gap-full500 的 coverage.json；不按保存成绩拼接赢家。F1 相比 gap 的 007/5 退化 68 周期仍保留。新方法恢复了部分结构上的损失，但这批均值略低于旧 tensor，不能宣布全面替代。墙钟来自共享主机上的不同测量窗口，不是独占硬件效率比较，也不能将阶段总和冒充每次求解端到端时延。

此目录只含 5 核。加上 round16a 的 5 个 3 核试验，F1 总成本为 105 solver / 105 E0；1/2/4 核没有 F1 数据，3 核只有 5 格，仍不是完整 500 格算法。首次 17c 入口 RAM 不足的 0 派发记录保留于 `../frontier-17c-preflight-stop.json`。

## 状态更正与收尾

本次 `get_goal` 核对发现原长期竞速目标实际为 PAUSED（updatedAt=1790286743）。17c 新窗口在未核对该状态的情况下启动，是执行控制错误；既有预算及队友释放资源不构成恢复暂停目标的授权。发出停机指令、核对可用中断机制期间，measure 已自然完成，未再追加批次、重试或候选。随后仅允许已启动的审计/发布助手完整保全结果，以及本目录的无评分汇总；目标继续暂停。

round17c 实际 T0 `2026-09-24T22:12:45.359152Z`、T1 `2026-09-24T22:19:39.469979Z`，墙钟 414.1110138 秒，33 solver / 33 E0。原件提交 `749fb7f8e55a4dd1b11ae90040c8ed9f57c4d9af`。发布助手核对 66 个压缩原件、198 个 feed 引用、499839 个 trace 操作，并成功完成一次提交/推送，未新增 solver/E0。精确时间及 feed 哈希见 `publisher-receipt.json`。推送成功不等于成绩台已验收，也不等于队长已采纳。

后续任何新测量先核对用户授权与当前目标状态；摘要、剩余预算、旧任务卡和其他会话的消息不能代替状态核对。本次交付只关闭已经发生的成本和证据链。

## 无评分复现

从仓库根目录运行，输出目录须尚不存在：

```sh
python -X utf8 -B -m src.q2.feedback.coverage --batch results/a/q2-yuanzhifang/feedback-20260924/round16b --batch results/a/q2-yuanzhifang/feedback-20260924/round17a --batch results/a/q2-yuanzhifang/feedback-20260924/round17b --batch results/a/q2-yuanzhifang/feedback-20260924/round17c --solver-commit 4a501d7f4a8b780263e097a963e12dcb66178e69 --variant frontier_gap --output <new-output-directory>
```

该命令只读取封闭账本和保存结果，新增 solver/E0 调用均为 0。
