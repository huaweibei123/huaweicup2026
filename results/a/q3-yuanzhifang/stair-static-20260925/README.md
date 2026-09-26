# 067/k5 首波阶梯静态审计

固定 CLI fc2adb027c2e3bfbb1f03b88a38b12ab6eed9238、模型 68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9。一次纯计算次序分析，0 plan builder / derive / Step / E0；完整进程 0.801024 秒，分析 body 0.345912 秒。它是当前用例的研发成本，未来冷调用必须重新计算。

必要界 11856672；cuts=[0,20,44,66,94,124]、U=[6,6,5,5,6]、h=2、首波[2,3,4,5,6]与 Pro R2 一致。旧次序必要界12218400，新界降低361728；距固定队长成绩12237901仍有381229周期。这不是官方 Makespan 或可达收益。容量足迹仅为代理，没有证明零spill或实际Cache行为。

关键路径854个正整数周期操作、139条original边、714条FIFO边，原图依赖和FIFO同管线端点已读回；没有独立重证整个FIFO投影。run.json 中 first_wave_match_pro=false 来自读回字段拼写 first_wave，实际字段为 first_wave_sizes；root-readback.json 保留更正，原run/stdout未改。

initial-supervisor-stop.json 保留第一次0分析的预检误判：监督脚本额外要求整个分支HEAD不变，而所有固定文件字节本就匹配；根并行提交了独立runner。后续仅修正这个预检条件，实际分析共1次、无分析重试。资源门实际可用RAM1592995840 B、盘8941617152 B，满足本静态预算；没有放宽cold/E0的2GiB门。

stdout/stderr 原始压缩字节、SHA、调用命令、环境与费用保存在run.json；root再次核对压缩/原始SHA和路径周期和。共享supervisor脚本是执行后的可移植副本，去掉个人路径、修正读回键名并禁止覆盖已有收据；未重跑该副本，原执行后脚本的私存副本SHA见root-readback.json。
