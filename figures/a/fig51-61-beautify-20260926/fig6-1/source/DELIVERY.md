# 图 6-1 交付包｜P3 结构构造与缓存评价路线（v2）

- 图号：6-1　版本：v2（2026-09-26，按首轮实质验收返工单 F61-R01～R05（#14 评论 5844880637）修订；v1=7db0a1cac 保留于 git 历史）
- 主责：甲（farmeruncle123）　输入数据约束：仅仓库固定提交（P3 初稿@1e35e3994d4792dfa2bb406669b547cb8b7e8fb0、算法源码@311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1），无外部数据；0 新实验

## 本版（v2）逐条修订

1. **F61-R01 科学公式（必须修）**：CacheGain 全部更正为 **C = M₂ / M₃**（M₂=同计划无 L2，M₃=只读 Cache；与固定初稿 1e35e399 的式 (6-4) 及 TECHNICAL_V5 图 6-4 一致）——cg 节点、nodes.csv cg.note、DELIVERY、caption 同步；显式给出分子分母；C>1 改善、C<1 退化；候选接受仍只比较 M₃。自查解释性算例：M₂=120、M₃=100 → C=1.2（改善），仅验证公式不填入论文实测。全包搜索已无倒数定义。
2. **F61-R02 流程条件与模块归属（必须修）**：route 拆为两段——「基础结构路由与基准」（仅结构守卫拒绝时依序尝试下一路；构造基准并评价 → 取得当前合法方案与已用 calls）与「后续增量候选按序、守卫及剩余预算尝试」（大框列出实际调用链 expanded→calendar→pipeline→witness→forest 与 ②③④⑤ 条件：attention_gap 仅注意力且多核；shared_pipeline 仅多核且守卫通过；attention_witness 仅放置代理严格优于就绪代理且 calls<3；forest_memory_order 仅森林守卫通过且 calls<3）。增量循环复用同一组去重/条件剪枝/E0/严格接受节点，完成一候选后进入下一适用路线或输出。**修复了 v1 在任何 E0 之前就用"当前合法方案 Makespan"剪枝的顺序错误**（基准评价先于比较）。prune 节点补 pipe_bound :78–112 适用检查五条（每子图恰一个原始非 COPY 节点、仅 PIPE_M/PIPE_V、非负整数 cycles、固定非负整数跨核 delay、COPY 收缩不引入未证依赖；循环等不支持则不用界照常评价）。forest 不再写成 witness 内部；模块归属按真实调用链。下界不证明执行合法性的边界保留。
3. **F61-R03 来源登记**：audit.sources 拆为每文件纯路径 + 完整 40 位 commit 311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1 + Git blob 字节 SHA256——witness_solve（73fd2d48…）、pipeline_solve（ac90626c…）、calendar_solve（ff1d6bf7…）、forest_memory_order（85c37641…）、pipe_bound（656865f7…）与审阅方本机读取一致（本机独立抓取核对相同），另登记 expanded_solve、attention_rows、construct 实际引用哈希；初稿与 forest 入口两项保留已核哈希；476/24 注明为初稿 6.6.1 已发布批次口径。
4. **F61-R04 表结构四格**：prune.stage→conditional_prune；e0.stage→official_p3；acc.stage→strict_improvement；nol2.stage→same_plan_no_l2（structure/candidate/deduplicate 已满足）；随 R02 节点变化同步真实 id（route→baseroute 新增 incloop，移除旧 route/cand），边端点全部存在无重复；data-flow 机检通过（validate.py 0 error）。
5. **F61-R05 实际视觉**：idx 拆两行并加高（"计算依赖、张量生产者/消费者" / "流水线类型、计算时长、张量字节"），右侧不再贴边；ext 拆短行（单尾切分与首波阶梯（6.5.2）/ 四系数响应压缩（6.5.3）），旁注标题改短「旁注｜研究拓展（不执行）」消除"次"字孤行；e6 边标签移除，"仅评未被剪枝的候选"并入 e0 节点首行——标签不再落入 e0 框顶。箭头规则维持：全部端点锚定边框，0 交叉。

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| fig6-1-p3-cache-route.svg/.png/.drawio | 主图 | viewBox 实际 711×830 |
| nodes.csv / edges.csv | 绘图输入 | 12 节点（id/stage/module/note）/ 11 边 |
| caption.md | 图注 | 与图面同步的口径 |
| preview-insert-width.png | 物理宽度预览 | 1500px |
| self-check.md / audit.json | 记录 | v2 |

## 已通过的检查（v2）

- validate.py 0 error / 20 warnings（容器与样式提示）；0 处边交叉。
- 1500px 插入宽度目检：无截字、无贴框、无压字；①–⑤ 与条件标注完整可读；箭头全部落边框。
- viewBox 711×830；165mm 宽插入高 192.6mm，最小字 ≈6.58pt、主标签 7.24–8.55pt；正文页内容纳。

## 未完成项

- 无（modern 变体不在本轮）。
