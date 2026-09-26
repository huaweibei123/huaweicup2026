# 流程图图内文字规范改写回执（Read Receipt v2）

- **工作日期**：2026-09-27
- **执行会话**：Antigravity (v9 阶段)
- **交付目标**：`gemini-mapping.json` (共 91 个文字节点改写映射第二版终稿)
- **对应改动记录**：`changes-v2.md`

---

## 1. 实际查看与阅读清单

### 1.1 实看图像文件
1. `review/incoming-figures/fig53-7b65452/fig53_p2_speedup.png`
2. `review/v9-requests/flow-language/p1-complete-flow/current.png`
3. `review/v9-requests/flow-language/p2-local-cut/current.png`
4. `review/v9-requests/flow-language/p2-three-plans/current.png`
5. `review/v9-requests/flow-language/p2-three-plans/current-b.png`
6. `review/v9-requests/flow-language/p3-forest-decision/current.png`

### 1.2 实际阅读文档与数据资产
1. `review/v9-requests/flow-language/language-standard-20260927.1.md`（尤其严格核对 V03 与五项科学纠正要求）
2. `review/incoming-figures/fig53-7b65452/`：`caption.md`, `README.md`, `paper-data-check.json`, `method_core_summary.csv`
3. 正文对应章节：`chapters/04-p1.md`, `chapters/05-p2.md`, `chapters/06-p3.md`
4. 冻结标签资产：`review/v9-requests/flow-language/fixed-labels.json`, `owner-inventory.json`, `additional-edge-labels.json`
5. 对应源码实现：
   - `src/q1_fang/structural_refine.py`, `src/q1_fang/branch_aid.py`, `src/q1_fang/branch_refine.py`
   - `src/q2_nikolastarx/binary_hypercut.py`（第 198–259 行 `load_guarded_cut`）
   - `src/q2_nikolastarx/adaptive_hypergap_guarded.py`
   - `src/q3_nikolastarx/forest_memory_order.py`, `src/q3_nikolastarx/witness_solve.py`

---

## 2. 映射覆盖与决策统计（v2 终稿）

全部 91 个文字节点已完全覆盖，6 条边的容量标签保持原样不变。长注释、适用范围及局限性说明统一移入图注（`move_to_caption`），图内文本置空（`proposed_figure_text: ""`）：

| 流程图 ID (`figure_id`) | 固定提交 (`source_commit`) | 源码文件 (`source_file`) | 节点数 | `keep_short` | `split` | `move_to_caption` |
|---|---|---|---:|---:|---:|---:|
| `p1-complete-flow` | `83e03c093af991ec7414f80787984726ebdea329` | `p1-834-flow-clean.drawio` | 25 | 19 | 3 | 3 |
| `p2-local-cut` | `4eb1dd426b25bde8871a31835416676314a50519` | `p2-local-cut.drawio` | 22 | 14 | 7 | 1 |
| `p2-three-plans` | `4eb1dd426b25bde8871a31835416676314a50519` | `a-construction.drawio` (15) / `b-scoring.drawio` (9) | 24 | 21 | 3 | 0 |
| `p3-forest-decision` | `4eb1dd426b25bde8871a31835416676314a50519` | `p3-forest-decision.drawio` | 20 | 16 | 3 | 1 |
| **总计** | — | — | **91** | **70** | **16** | **5** |

---

## 3. 核心科学事实与规范核验

1. **P1 科学边界**：
   - `base1` 明确仅切分“过大”的独立计算部分；
   - `base4` 明确按共享输入选核心数，或按分叉分配子树；
   - 模式名严格命名为 `root-heavy-fused`；
   - 三分支长说明（`base_note`, `intact_note`, `branch_note`）置空移至图注与正文，准确说明回退已有合法最优解，不宣称哈希去重或无条件回退单核；
   - 明确分支援助不保证单步消除所有环。
2. **P2 科学边界**：
   - 明确原 P1 即使与 P0 拓扑同构，仍保留并作为局部调整基准，仅在进候选列表时去重；
   - 去重机制为 Python 方案对象值比对，非哈希/序列化；
   - 无改善时保留已有候选，不预设候选集恰为 2 个；
   - 明确指标相同时保留先构造方案，删除“平局决胜”等黑话；
   - `guard_cap` 忠实 `binary_hypercut.py:198-259`：按传入上限检查、取首个超额核心与流水线、选流入其在该超限流水线上工作量最大的可移动链（同工作量按单元编号升序破平），退回原核心；图内句精确为“检查各核流水线工作量：超限则将该超限流水线工作量最大的迁入链退回原核心并重算”，杜绝误解为整链全量耗时；
   - 严格区分内层 `Cost <= Cost_0`（非增）与外层 `after < before`（严格降）；
   - `guard_bound` 置空移入图注与正文，明确至多 $r+1$ 次最大流（$r \le 16$），与全局至多 3 次在线评测预算完全解耦。
3. **P3 科学边界**：
   - 归约森林适用范围忠实 `forest_memory_order.py`（至少两个树组件且含多子汇聚；各操作为已知大小单输出，非根输出有唯一父操作，根操作输出为外部依赖）；
   - 排序按 $h_i - r_i$ 降序（同值按算子编号升序破平）；
   - 去重为直接比对当前最优方案 `winner[0]` 的编码字节；
   - `guarantee` 置空移入图注与正文，明确属于非交错树模型推导，非真实芯片物理 L1/UB 占用峰值。
4. **全稿语言规范**：
   - 彻底清除“严格、精准、底层微架构实测、物理墙钟、护栏、裁决”等夸大词；
   - 图 5-3 正文清除“未独立复审非主算法原始 E0 记录”、“数据源于固定提交 7b65452 校验的冻结结果表”等验收台黑话；
   - 消除“拓扑保形”、“优选链方案”等用词，转换为直观科学事实；
   - 动作主语明确，由具体施动者（算法/调度器）执行动作。
