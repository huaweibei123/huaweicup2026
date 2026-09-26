# 二核容量窗口四图测量

修正后固定spec提交`8e10587e21d06b5e1b4c703e32364539c175e8ee`，spec SHA-256`c76f40f644e88af6867dcff38fa3056f32d163c2ec9bfab72eb1f7a05fc295d4`；源码`384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`。本批唯一实际运行4/4图成功，4次新进程solver、4次独立未修改官方E0，E1/E2=0，0在线E0、0自动重试。原spec`db44533f5d9f8538697ea3d3c59625fe1763a26f`因run_id含`_`在预派发校验被拒，0solver/0E0；事故原文另见`round12-13-preflight/lane-a.txt`，不计为本批solver失败。

T0`2026-09-24T18:27:07.643653Z`，T1`2026-09-24T18:28:17.451821Z`，批墙钟69.808263秒，固定字节预检另计5.852474秒；solver合计10.418935秒，独立E0合计54.461717秒。批前物理可用内存约1107.9MB，另一P2 lane与P3可能共享CPU/OS缓存，墙钟不是独占测量。

| 图 | 本轮官方cycles | 旧tensor_packet二核cycles | 本轮/旧spill B | 新分区额外B | 结构判定 |
|---|---:|---:|---:|---:|---|
| 025 | 2,351,920 | 4,251,120 | 0 / 100,832,256 | 27,648 | 两非空核各window=3、逐核容量证书成立 |
| 036 | 466,068 | 813,784 | 0 / 13,803,520 | 1,152 | 两非空核各window=3、逐核容量证书成立 |
| 072 | 11,817,077 | 11,817,077 | 81,068,032 / 81,068,032 | 10,948,952 | `selected=capacity_window`但两核window=0、顺序未变、无证书 |
| 037 | 105,906 | 105,906 | 0 / 0 | 204,800 | `capacity_window_guard_unchanged`、无证书 |

四图按同一官方单核A基线逐图B/M算术均值从旧tensor_packet的1.573454442变为本轮2.017888291。它只是事前固定四图子集，不能代替二核全100新算法均值。072的正spill和失败的容量证书是关键负例，不能因外层`capacity_window`标签宣称全图无spill。037是未覆盖通信路线的原样对照。旧连续方案若用于后续分析须单独标记，不混同旧tensor_packet。

`export_board`内置preflight为4 records/4 eligible；`analyze`成功。独立只读`audit_saved.py`核对固定spec/source、8份gzip原始/存储哈希、feed引用、71496个trace操作区间、单核基线身份、实际路由与逐核证书口径，退出码0。逐图搬运及墙钟在`measurement-audit.json`/`summary.csv`。未在运行中读取账本或结果。
