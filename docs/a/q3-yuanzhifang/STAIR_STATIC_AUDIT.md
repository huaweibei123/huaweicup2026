# 067/k5 首波阶梯：一次静态证伪预算

本批只回答 Pro R2 的 compute/FIFO 必要界能否由本地独立实现复现。`tail_stair_model`、索引、结构/容量代理、两遍 DP 与 FIFO 最长路固定为 `68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9` 的原字节；CLI `stair_audit.py` 和本文另行提交固定后才执行。输出 `results/a/q3-yuanzhifang/stair-static-20260925/`，一次新进程、067/k5、超时 10 秒、零重试；只调用 `analyze`，不调用官方计划 builder/derive、Step、E0/E1/E2，不产生可提交计划。它与尚未启动的 cold+E0 批次分账，不占用或复用旧封存实验窗口。

静态分析使用一个进程；预期内存量级取自旧 FIFO 审计，不声称硬 RSS 上限。启动前可用物理内存须至少 1 GiB，输出磁盘至少 256 MiB；不足则保存停止收据、不轮询重试。这是轻量静态模型的独立预算，**没有放宽冷 solver/E0 批次的 2 GiB 门槛**。外部 supervisor 记录解释器启动至退出的墙钟、退出码、原始 stdout/stderr、命令、资源检查及原始/压缩 SHA。body 时间另列，不冒充冷 solver 时间。

```powershell
.venv/Scripts/python.exe -X utf8 -B -m src.q3_yuanzhifang.stair_audit ../huaweicup2026/data/raw/a/official-cases/data/case_067.json --cores 5 --config data/raw/a/official/data/config.txt --incumbent 12237901
```

固定图 SHA 为 `f49b5087689e18c6bf231843f8f3bbaca238a547ea5309b2492c76d5f170b542`，config SHA 为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。比较值来自队长固定 forest solver `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`、feed `19bebf35205d23fdd832781540f8879da52eeb62` 的 067/k5/P3 记录，计划 SHA 为 `d992fc2017995d226cee7ee2229f3e9e43878f2d0e3200ceb6cf56b587ce6dcd`。比较不影响次序生成，也不是新增 E0。

核对重点：`cuts=[0,20,44,66,94,124]`、`U=[6,6,5,5,6]`、`h=2`、首波 `[2,3,4,5,6]` 与 Pro 报告的必要界 `11856672` 是否一致；把不一致原样报告，不改参数。独立读回关键路径的正整数周期和及 original/FIFO 边类型，不能把同管线端点检查升级为完整 FIFO 投影证明。结果低于 12237901 只表示这条必要界尚未排除候选；不证明可达或官方收益。未来冷构造必须重新完成所有索引、DP 与次序分析，不能复用本批预计算隐藏求解成本。
