# 图6-3、6-4已验收Python原稿交接

负责人：@yuanzhifang30-sudo；session=yuanzhifang30-sudo/s-f42fb47d93984f22a151b0a09f678c84；沟通Issue217。

1. **任务目标**：按用户授权，将已通过工作台逐图验收的Python原稿直接交队长。
2. **输入文件**：farmer固定来源babdd74c2c2358516de61d1d9bef0ec9ef90e965；6-4是工作台local-format-v1，6-3是工作台local-complete-v1；两图都基于forest311322b revision2的同一500对同计划对照。全部来源链接和实际审查见acceptance.json。
3. **输出要求**：完整原图、矢量图、代码、CSV、图注、来源与审查证据；本次交接不改图、不重新绘图。
4. **限制条件**：保持原件字节及科学口径。Makespan方案质量与完整solver墙钟分开；本图展示模拟质量，不新增真机或求解器速度结论。5～10分钟是题面效率建议，本次不扩充实验预算。
5. **验收标准**：转交下列工作台完整criteria；本会话验证当前submission/review绑定和全部43原文件SHA，查看插入宽原图。未重跑1000结果/计划审计、未执行上传代码或solver/E0/E1/E2。
6. **截止时间**：2026-09-27（Asia/Shanghai）本次交接。

## 版本与证据边界

43原文件逐字节保存；.gitattributes禁用换行转换，package-manifest.json覆盖所有交付文件（清单自身除外）。两图pairs.csv SHA均为a8be50e8689b9c75fc871224734d693294319645597a5cc21a15efbd69f370f5。验收记录与转交分开；18图当前候选通过不等于全套最终版本统一、用户总验收、队长审核或论文入稿。834新版4-4/4-5仍需独立审查。

图6-3按逐例共同单核基线/M再求算术平均，单核真实值保留；图6-4按同核心数同计划无L2/只读Cache比较。Cache命中率按字节，平均比率与汇总字节比率区分。负收益样本、局限和计时边界按原图注保留。

语言标准2026-09-27.1（1be28c77b911ef00781e0c23413b68b62823a566）已读；本包按用户授权原件送审，不代签新一轮语言验收。复现方式按各目录README/代码记录，代码未在本次执行。以下是工作台验收原文，不冒充本会话重新独立完成科学审查。

## fig-6-3

版本：forest311322b revision2 / local-complete-v1 / babdd74c pairs。submission `0b467c05beae4893b359b109a9cb91af`；review `497a1e1401af4cc2949167d89b2e70cd`。

- **criterion-1**（passed=True）：已独立读取固定Git对象的1000份压缩result引用和1000份plan引用，校验SHA256及Git blob SHA；500对plan实际字节相等，逐对case/core/graph/official/config身份一致，共享带宽60 B/cycle、L1 524288 B、UB 131072 B。实际两端周期和hit/miss与交付500行全相等。476已有P2+24已完成delta，未执行solver/E0或队友脚本。原件审查证据source-verification.json、raw-pair-verification.json；规范表由本机prepare_cache_tables.py复算并字节复现。 每核100对；pairs.csv SHA a8be50e8689b9c75fc871224734d693294319645597a5cc21a15efbd69f370f5，与6-4字节完全同一份，旧F63-R01/R03关闭。

- **criterion-2**（passed=True）：无L2直接取同计划原始P2结果周期，Cache直接取revision2 P3原始周期；逐例fixed baseline/M后取每核100例算术均值，未由汇总Gain反推或替换独立优化P2主线。固定共同基线已逐case连接，002基线261945 cycles原件重核，其余复用同哈希已有核验。

- **criterion-3**（passed=True）：单核无L2=1.1971433351520684、Cache=1.1997595678587545均保留真实值，不强制1；图底注与caption准确写B/M再平均，明确共同官方单核基线。F63-R02倒置表述关闭。

- **visual**（passed=True）：已实际查看本机受控代码生成的完整PNG及160mm PDF预览：双曲线实/虚线、圆/方标记可区分，五核表格与完整精度summary舍入一致，字体/图例/底注无裁切。5核两值4.476283/4.757617，未掩盖真实单核。

## fig-6-4

版本：babdd74c / forest311322b revision2 / local-format-v1。submission `b149f8ee6a0c450f9f0c19182a8e09d2`；review `7a2274bee538410682b83dd0e07c7a72`。

- **criterion-1**（passed=True）：已独立读取固定Git对象的1000份压缩result引用和1000份plan引用，校验SHA256及Git blob SHA；500对plan实际字节相等，逐对case/core/graph/official/config身份一致，共享带宽60 B/cycle、L1 524288 B、UB 131072 B。实际两端周期和hit/miss与交付500行全相等。476已有P2+24已完成delta，未执行solver/E0或队友脚本。原件审查证据source-verification.json、raw-pair-verification.json；规范表由本机prepare_cache_tables.py复算并字节复现。 CacheGain逐对无L2/Cache，五核均值1.0023396456/1.0079236455/1.0313799263/1.0512016361/1.0829171727；图面参考线1，负收益红三角保留。

- **criterion-2**（passed=True）：原始cache_stats的hit_bytes、miss_bytes逐格核；按字节计算率。每核逐例均值与汇总字节率分列，汇总率9.955%/36.416%/41.239%/42.440%/47.446%；全500无访问样本为0，代码对零分母留空。图注明确两种统计口径。

- **criterion-3**（passed=True）：由当前forest311322 revision2真实周期计算的负例仅021/k3、038/k2、079/k3、092/k4；与negative.csv、图面红三角一致，非按数量拼造。

- **criterion-4**（passed=True）：实际第三面板标题与caption均明确散点仅展示分布，不构成命中率决定总体加速的证据；限定模拟同计划单机制对照，不外推真机。

- **visual**（passed=True）：已实际查看原PNG和165mm插入宽度预览，三面板标题/坐标/图例/参考线可读且无裁切；负例红三角兼有形状区分。原SVG/PNG字节未改，独立副本只补交付规范及P2/P2图注笔误；不得声称所有18图主版本统一已由用户确认。
