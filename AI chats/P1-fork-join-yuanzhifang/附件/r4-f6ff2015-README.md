# P1 R4 全域界与500格差距：只读作者报告

**不是新Benchmark。** 本包未运行solver、Task compiler、响应模拟、E0/E1/E2。新增证明是作者报告，等待本地独立审计。源材料500格的可行性来自归档成功记录，本轮只核身份与算术；没有500份原始执行记录。

输入ZIP `p1-pro-r4-fixed-evidence.zip`：9654760 bytes，SHA-256
`ac92bfd0c6a2ad389c0bdb7ced43a9e13033d76fc96b385f9f9c3affc0326084`。
64个成员，MANIFEST列出的62项全部通过长度/哈希；嵌套原始100图全部解析。

固定v4 solver：`a0537aeb72dc702af86d67d3194587d581ac207c`；归档：`9c5f87548cc7588465a638e032993969b5cac891`；feed SHA-256：`4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764`。

## 首先阅读

- `theory_draft_zh.md`：中文论文草稿，含域定义、旧界审计、数值边界、两个新整数定理及完整证明、差距与迭代性质。
- `proof_audit.md`：逐命题状态、代码/论文修订点、传递依赖缺失与补证优先级。
- `summary.csv`：K1–K5汇总。正式比较看K2–K5的 `safe_C` 等字段；K1正式曲线点1，不能把重分区单核结果当基线。
- `paired_500_audited.csv` / `audit_tables.json`：逐格身份、B/U/L、所有空间指标、主导分量、spill与归档墙钟。
- `closest_widest.csv`：每K最接近、最宽及对均值包络贡献最大的各5格。宽松不是必可改善。
- `window_certificates.json` / `separator_certificates.json` / `independent_verification.json`：整数计算窗口和通用分隔gate证书及第二个实现的验证结果。
- `signature_static_audit.json`：008保存的8+20个Task签名的纯DAG/窗口复算。101836/106071仍是固定签名精确服务模型界，不混入E0全域表。
- `complete_input_inventory.json`：64个外层成员（62MANIFEST项+2根文件）与100个内层图的完整清单、SHA/Git与读取层级。`read_inventory.json`保留62项扁平清单。

## 表格字段

`L_safe_global=max(L_safe_compute_window,L_safe_separator)` 是本轮正式整数全域界。`L_conditional_archived` 是复算一致但缺E0数值桥的旧DDR增强静态值。`L_conditional_combined` 在理想服务域取两者max，仍为条件表，不能当E0全域认证。

`safe_global_max_makespan_reduction = 1-L_safe_global/U`；
`safe_global_max_relative_speed_gain = U/L_safe_global-1`。
这两个CSV字段是比例，不是已经乘100的百分数，均表示“最多可能”的上限。`C_cell_safe`为仅窗口的辅助列，**最终全域表请用 `C_cell_safe_global`**。

均值用Fraction逐图求比值后取算术平均；`mean(U/L-1)`不等于均值加速比的相对空间。`official_curve_point`在K1固定为1；K1的U仍作为候选审计数据保存。

归档 `solver_wall_seconds` 与 `external_E0_wall_seconds` 原样分列，不代表本轮运行。`analysis_wall_seconds`只是静态脚本分析耗时，不是solver时间。

## 独立复核（标准库，无官方导入）

解压用户原证据包到 `EVIDENCE`，本报告脚本置于同一目录REPORT下，可在新的OUTPUT目录生成数据：

```sh
python REPORT/recompute.py --root EVIDENCE --out OUTPUT
python REPORT/enrich_report.py --root EVIDENCE --out OUTPUT
python REPORT/verify_certificates.py --root EVIDENCE --report OUTPUT
python REPORT/signature_static_audit.py --root EVIDENCE --out OUTPUT/signature_static_audit.json
python REPORT/finalize_artifacts.py --root EVIDENCE --out OUTPUT
```

`recompute.py`只构建静态DAG、计算整数/有理数，不运行原 `lower_bounds.py` 的入口，也不启动官方校验/调度。`verify_certificates.py`不导入生成代码，并用另一种分段可达性检查验证分隔证书；它证明所给见证有效，不要求证明生成器已选出最强窗口。

`signature_static_audit.py`只调用本报告自己的纯窗口函数。其对称组前提必须另审；保存的模型上界没有重放，原图到签名的编译来源没有在本轮重新验证。原 `causal_certificates.json` 不在包中，本轮生成了新的有效窗口见证而非假称读到了原选中job文件。

脚本的输入、输出路径可传参；未使用图编号作构造规则。仅报告按case_id索引。摘要记录的静态调用计数不等于官方成绩调用。

## 关键结论

K2–K5的当前均值为1.947513173/2.739046557/3.453039755/4.025907474；本轮整数全域理论包络为2.475951486/3.691400439/4.898841162/6.068017159。没有任何格上下界完全闭合。此结果不证明剩余收益可达，更不证明截图来源同身份。

缺少E1实现与capacity_return的动态导入依赖，因此“附包包含v4源文件”不等于完整可运行依赖树；不可据此认证E1≡E0。更多缺件见proof_audit。
