# 图 6-4 自查记录（甲，v1，2026-09-27）

## 实际执行结果（本会话为该目录唯一写者，开工回执 5848091824）

- 命令（三步，工作目录=仓库根，退出码 0）：
  1. `env -u PYTHONPATH python .workbuddy/refs/p3-64/fetch_pair_inputs.py --out .workbuddy/refs/p3-64/verified-inputs --probe`——工作台提供脚本（Issue15 评论 5847529179 v2）probe 模式：001-k1 verified、021-k2 verified、DONE 2 pairs。
  2. `env -u PYTHONPATH python .workbuddy/refs/p3-64/fetch_pair_inputs.py --out .workbuddy/refs/p3-64/verified-inputs`——**全量 500 格**：日志 500 条 "verified" + "DONE 500 pairs; completed-summary SHA verified; no experiments executed."；零失败零中断；逐格断言（plan 字节相同、两端 gzip 原字节 SHA、git blob SHA-1、核数/scene/Makespan）。脚本只读 GitHub，无 solver/E0/E1/E2、无 git push。获取耗时约 52 分钟（16:57–17:49 本地时钟）。
  3. `env -u PYTHONPATH python figures/a/jia-fig6-4-20260926/extract_pairs.py --pairs <verified-pairs.json>` → `.venv/Scripts/python.exe figures/a/jia-fig6-4-20260926/plot.py`——从收据构建三张交付 CSV 并绘图；plot.py 内置断言（500 格、cache_gain==no_l2/cache_makespan 逐格、byte_hit_rate==hit/(hit+miss) 逐格、类别与负例一致）。

## 逐项对应派发单（5848057031）

1. **数据版本**：forest311322b 完整 500 格同计划配对（revision2 feed 500 条断言 solver_commit=311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1）；非旧 witness、非汇总 CacheGain 反推。476+24 结构与 manifest/run 一致（24 jobs 全 ok；requires_new_p2_e0 仅历史身份，未启动新计算）。
2. **hit_bytes/miss_bytes 补入**：来自每格 P3 result 的 cache_stats（verified-pairs.json 逐格记录）。
3. **CacheGain/命中率/分核均值**：CacheGain=no_l2_makespan/cache_makespan 逐格复算（repr 全精度写 CSV）；命中率按字节 hit/(hit+miss)；分核均值与汇总命中率在 per_core_summary.csv **分列**（mean_cache_gain / pooled_byte_hit_rate / mean_byte_hit_rate_case_wise 三列不混用）。
4. **无访问样本**：hit+miss=0 的格本版本 **0 格**（如实报告），口径上命中率留空并在面板 3 单独列位（图例说明），不冒充 0 命中率。
5. **负收益清单**：按真实配对复算共 **4 格——038/k2、021/k3、079/k3、092/k4**，与派发单给出的当前版本负例清单一致（未强凑、未沿用历史值）；negative_cases.csv 逐格含 makespan/命中率。
6. **三面板**：均值折线（y=1 参考线，点标 5 位小数）/逐例分布（散点+箱线，红▼负例全部保留）/命中率-收益散点（y=1 线，图注声明不构成命中率决定总体加速的证据）。
7. **图面检查（165 mm 插入宽度）**：preview-insert-width.png 目检——三面板行/轴标签完整、图例位于空白区不压数据（面板 2 图例左上、面板 3 图例右下均远离散点带）、y=1 参考线与负例红▼可辨；PNG 300 dpi 局部放大复核。

## 缺口

- 无（500 格收据齐全、五项固定哈希核对通过；0 新 solver/Task/E0/E1/E2）。

## 版本

- v1：初版交付（本目录全部文件，哈希见 audit.json）。
