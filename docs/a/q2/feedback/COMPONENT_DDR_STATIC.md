# k5 component / DDR 静态诊断（020、045）

只比较两组已保存的 k5 方案：A 为 `tensor_packet`，B 为固定 `gap_packet`。结果不是新评分，也不是新算法。静态脚本只载入官方原图、保存计划和收据，使用 `TensorIndex`、`derive_multicore_plan`、A 方案的 `physical_frontier.certificate` 与官方 `_op_duration`；没有调用 `_build_scene_b_tasks`、Step2、Step3 或 E0。

| 图 | A：base copy 数 / bytes / W_A cycles | B：base copy 数 / bytes / W_B cycles | A/B 跨核链接数 | A 本地证书 | U_A / L_B cycles | 诊断触发 | 已有官方 M_A → M_B cycles |
|---:|---:|---:|---:|:---:|---:|:---:|---:|
| 020 | 576 / 2,359,296 / 39,744 | 4,046 / 16,572,416 / 279,174 | 0 / 1516 | True | 146,980 / 279,174 | True | 107,650 → 477,078 |
| 045 | 136 / 557,056 / 9,384 | 1,351 / 5,533,696 / 93,219 | 0 / 510 | True | 34,996 / 93,219 | True | 26,164 → 101,085 |

归一化 multiset 按官方 P2 重建规则逐个保存在 [`static.json`](../../../../results/a/q2-yuanzhifang/feedback-20260924/component-ddr-static/static.json)：每个不同消费核各一条图输入 COPY_IN；每个生产核各一条最终 COPY_OUT；每个不同生产核→消费核对各两条 COPY；直接 eligible op-op 跨核边也各两条，含 0-byte 边（每条 COPY 仍按 `max(1, ceil(bytes / bandwidth))` 计 1 个服务周期）。本图配置带宽为 60 B/cycle。`W` 是全部 base COPY 的归一化服务周期之和；不加跨核固定 delay。逐例手算 bytes 与已存 `scheduled_copy_bytes - spill_added_copy_bytes` 一致；A 的 count/bytes 也与本地证书一致。

每核 `C_c` 是把该计划映射到的 eligible 操作按核求和 official `_op_duration`，不是 raw cycles。`U_A = max(C_c) + W_A`；`L_B = W_B`。静态诊断门定义为：A 无跨核 tensor 核对或直接 eligible 跨核边、A 本地证书通过，且 `U_A < L_B`。两例均触发；这只是有界候选诊断信号，不据此改写历史方案、承诺实际 Makespan 或称为 machine-strict 界。证书仅覆盖 singleton P2 的本地 Step2 bucket envelope（L1/UB 容量），不保证全局峰值或 Makespan；B 不运行容量证书。

表中 M_A/M_B 是保存的官方结果（020：107,650/477,078；045：26,164/101,085），仅作为既有测量展示，未被静态触发器读取。冻结索引/证书实现身份为 `4a501d7f4a8b780263e097a963e12dcb66178e69`；旧 A、gap B 与官方 E0 身份分别为 `e64723bdf99669c44f76d8e90ab0379a8578522e`、`384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`、`45f647b395b84e9569f418fd33d62c2b8eb4d190`。图、配置、plan、run、result 与源码 SHA-256 均在 JSON 中。处理仅限这两图；静态脚本耗时 3.869 s，0 solver / 0 Step2 / 0 Step3 / 0 E0。

实际使用的静态脚本现已归档入库（仅将CRLF统一为LF，原执行字节与入库字节的两个哈希均有记录）：`src/q2/feedback/component_ddr_static_probe.py`，SHA256见同目录结果的`script-identity.json`。复现命令：`python -X utf8 src/q2/feedback/component_ddr_static_probe.py . <新的输出JSON路径>`；应使用新路径，保留本次原结果。该脚本中的两个图号仅限定事后诊断范围，不是求解算法的路由规则。
