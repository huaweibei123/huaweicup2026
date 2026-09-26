# 容量阶段 F1：冻结六格证伪结果

固定算法 `4a501d7f4a8b780263e097a963e12dcb66178e69`、variant `frontier_gap`、args=[]；预注册 spec 为 `ed32a44447a07b60fa314fc60418f5303b71577f`。run 原件在 ../round16a 和 ../round16b，官方源码/配置/基线身份及每批 trace 审计均已通过。这里只覆盖5个k3案例和1个k5案例，**任何核数都没有完整100均值**；不以部分均值代替全题成绩。

| 图/核 | 旧 tensor M | gap M | F1 官方 M | F1 spill B | F1 extra DDR B | solver / 外部E0 秒 |
|---|---:|---:|---:|---:|---:|---:|
|008/3|84,303|221,010|84,303|0|0|1.027 / 0.839|
|095/3|357,591|1,129,764|357,591|0|0|1.442 / 3.324|
|025/3|3,218,880|1,610,875|1,610,875|22,516,224|49,866,240|9.850 / 17.002|
|036/3|614,583|311,345|311,345|0|2,304|1.054 / 1.859|
|072/3|7,903,838|7,844,564|7,844,564|53,360,576|201,600,624|17.452 / 28.495|
|014/5|3,517,640|4,364,011|4,364,011|44,364,288|212,032,632|31.061 / 32.917|

比较的旧原件来自 ../full-coverage/all500/per-cell.csv（source e64723b），gap 来自 ../full-coverage/gap-full500/per-cell.csv（source384b6c2），逐 case/core 关联，未重算旧方案。相同官方单核基线作加速比分子。M 是模拟时钟周期；两个墙钟列是共享Windows机器实际单次观察值，不能推断稳定提速或与队长硬件直接比较。

008/095 走 `frontier_resource_word`，相对 gap 的M下降61.8556%/68.3482%，spill从8,073,216/45,453,312B降为0。这是恢复已有专门构造的成绩，不是这两图超越旧算法或全局最优的证据。036走 `frontier_gap_certified_unchanged`，它与008/095均取得物理容量证书且官方spill=0。025/072/014走 `frontier_gap_unresolved`，保留唯一原gap计划和正spill，不把未获证说成图无解。025/036保住原gap相对旧tensor的收益；014仍比旧tensor差，不能隐藏该负结果。普通路线额外证书开销也计入solver墙钟，025本次墙钟高于旧gap的单次记录，尚无稳定性能推断。

预注册验收均满足：008/095 M等于旧tensor且获证零spill；025/036 M等于固定gap；072如实未认证；014仅一次、未超60s求解watchdog。没有非法计划、声称获证却spill、源码漂移或监督故障。本阶段并未用到可测收益的整核容量修复分支，不能据此宣称该分支已经获得官方大图实证，也尚未实现完整容量/DDR队列联合FQ。

实际资源：6 cold solver / 6外部E0，E1/E2=0、自动重试0。第一批 T0/T1=2026-09-24T20:54:15.491892Z–20:55:43.811924Z，第二批20:58:25.193492Z–20:59:33.566269Z。更早的RAM预检停止保存在 ../frontier-six-preflight-stop.json，0派发不算算法失败；新资源窗口仍按1.5GiB门槛启动。全部预处理、证书、回退与落盘在solver墙钟中；哈希预检、离线测试/Pro咨询和本汇总另记，0追加solver/E0。

汇总命令（只读已停止的批次）：

```powershell
.venv/Scripts/python.exe -X utf8 -B -m src.q2.feedback.coverage --batch results/a/q2-yuanzhifang/feedback-20260924/round16a --batch results/a/q2-yuanzhifang/feedback-20260924/round16b --solver-commit 4a501d7f4a8b780263e097a963e12dcb66178e69 --variant frontier_gap --output results/a/q2-yuanzhifang/feedback-20260924/frontier-six
```

下一阶段只在新冻结预算中验证同一F1的完整k5，复用这次014原件；不按六格表现更改算法再沿用旧身份，不把新旧逐格赢家拼接成算法。

