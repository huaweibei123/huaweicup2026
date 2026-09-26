# 本机 P2 2–5 核 benchmark

执行会话：`nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`，分工及首包见[Issue #26](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814790103)。

1. **任务目标**：对固定 P2 连续分块算法运行 001–100 全部图、模拟核数2–5的400个真实求解格；每格一次构造、一次冻结官方P2 E0评价。允许与队友既有格重复，以独立原件复核。
2. **输入文件**：固定求解器 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 `src/q2/construct.py`；冻结100图、配置与官方代码，身份见 `docs/a/source-manifest.json`。分母复用PR #89，不重跑。
3. **输出要求**：`results/a/local-p2-multicore-20260924/20260924T1325Z-s59ee/` 中每格plan、完整官方result/Trace无损gzip、log、run及批次清单；`board-feed-full400.json`按`board-submission-v1`交成绩台。首12格另有不可覆盖的快照feed。
4. **限制条件**：先3图×4核以4 worker验证；随后其余97图×4核以8 worker执行。每格构造≤120秒、E0≤180秒，批次自T0起≤120分钟，0 E1/E2、0自动重试、0搜索。资源阈值与实际采样见run；模拟核数不等于外层worker。
5. **验收标准**：400格各有状态和原件；成功格冻结图/config/官方身份、P2 scene B与核数吻合。固定提交严格协议预检`eligible=400`；仅代表格式和原件一致，不代替科学终验。
6. **截止时间**：实际T0 `2026-09-24T13:25:27.866Z`，最后格 `13:27:02.591Z`。该批已结束；后续P1/P3另立批次。
