# P2 完成批次的连续发布

`scripts/q2_publish_completed_batch.py` 只处理已成功结束且完整覆盖冻结 spec 的单一 F1 批次。默认模式只核对账本、格数、固定 spec 和容量元数据；`--publish` 才串接缺失的 feed 导出、分析、原件完整审计、仅本批暂存、提交及一次推送。它不调用求解器或 E0，不修改七份冻结算法源码，也不代替成绩台消费端的 enqueue 或中央验收。

在同一个 shell 中运行冻结 measure；仅其退出码为 0 时立即接本助手。不要等人工编写逐格报告：完整 raw/run/ledger、正式 feed、summary 和 audit 先提交，文字分析随后另交。调用者须保证该批已停写且本工作树没有其他 Git 写者；发现已有暂存项、失败/不完整格、原件哈希不符或获证却有 spill 时立即停止。推送失败或超时保留已提交 SHA 和外置失败收据，不自动重试。

```powershell
.venv/Scripts/python.exe -X utf8 -B scripts/q2_publish_completed_batch.py --batch results/a/q2-yuanzhifang/feedback-20260924/round17c --spec-commit aa540d3aa5ebdc1995461c58fcaa8afd033dde1d --receipt <工作树外本次唯一收据路径> --publish
```

收据保留原始最后 E0 完成 UTC、成功导出返回后的观察 UTC（写盘完成上界，非原子写的精确时刻）、feed SHA256、审计结束、commit 完成观察及 push 开始/结束 UTC。如果复用已有 feed，仅记读取观察时间，不能把它充作新导出完成时间。后续以成绩台真实 enqueue/签名回执/页面首次观察补齐链路。

验证：3 项隔离假命令测试通过，覆盖不相关暂存项拒绝、审计失败不得提交、审计→仅本批提交→单次推送的顺序、超时仍保留已提交 SHA；另曾对完成的 round17a 做默认只读校验（33 格）。截至本文件建立时尚无真实 `--publish` 完整流水线实测；round17c 是首次自然验证，不为测同步延迟重跑 E0 或重导旧 feed。默认校验不等于完整 audit，也不等于远端已接收。
