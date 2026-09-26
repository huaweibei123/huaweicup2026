# 并发评估控制面模型检查（非性能实验）

2026-09-24，macOS ARM64、Python3.12.13、项目已有锁定环境；标准库，无新增依赖。
确定性手工事件，无随机数；**E0/E1/E2调用均0，真实worker/服务均0**。
仅运行`model_checks.py`，不是导入/调用评估器，不是Windows/三客户端接入验证。

两次命令分别退出0，结果不覆盖：

```sh
python research/a/evaluation_service/model_checks.py --output results/a/review/evaluation-concurrency-model-20260924/summary.json
python research/a/evaluation_service/model_checks.py --output results/a/review/evaluation-concurrency-model-20260924/summary-v2.json
```

第一次8项通过，源码`model_checks-r01.py` SHA与原输出记录一致；它在测试开始前只知道
固定同分规则，使用了字典序ID示例。收到Fang反馈后第二版改为**原proposal序号**，增加首失败
投机窗口模型，10项通过。最新源码在`research/a/evaluation_service/model_checks.py`，
两次源码哈希均独立校验。`run.json`记录版本、锁文件和检查产物哈希；脚本耗时仅为这些模型
断言和环境记录的本地执行时间，不是评价耗时。

检查覆盖：慢项不阻塞其他完成交付/补发；三个租户获得dispatch机会；模拟内存和每租户在途
上限；幂等提交/冲突；queued取消退款；started超时保留未知费用不重投；native成功证据退款
而官方拒绝仍耗一次；零真值额度阻止自动fallback；队列满拒收不预留；按原序号同分；
过期epoch只留证、缺半配对；完成在前但前缀未确认仍占投机窗口；首失败保留started状态。

## 模型数据的正确读法

| 手工构造情形 | 原模型 | 拟议模型 | 仅支持的结论 |
| --- | --- | --- | --- |
| 2槽，一个100 tick慢项后8个1 tick快项 | 块派发批完成104；首个快项100才交付 | 滚动派发批完成100；首个快项1交付 | 有限例中块屏障导致可避免等待 |
| 3槽、9长项+3短项+1单项、三个租户同时入队 | FIFO全批27；第三租户27交付 | 轮转全批28；第三租户1交付 | 公平/小请求延迟改善可能牺牲一点总批时间 |
| 内存权重4、3槽、每租户最多1 | 不作为实机基线 | 峰值权重≤4、执行数≤3 | 模型admission守住声明值，不证明RSS硬上限 |

tick和memory_unit均为虚构单位，不能换算真实秒、字节、倍率或正式吞吐。
全部模型任务在时刻0入队；不证明动态到达负载的饥饿边界或按CPU时间公平。
额度模型在内存中运行，没有事务、落盘、崩溃恢复、IPC和真实进程清理。
投机窗口模型只规定顺序与停止；OS终止费用、结果持久化仍未实现。
模型每个proposal只有一个评价操作；审阅后文档补充的多problem/score/full操作分组、
圈存费用求和与前缀确认尚未在该模型实现/检查，不沿用这10项给新增契约背书。

完整设计、使用方及固定源码依据见`docs/a/e2/`。Actions按免费协作策略停用，
没有发起云端工作流；停用状态不是测试通过。
