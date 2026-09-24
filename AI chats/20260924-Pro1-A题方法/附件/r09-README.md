# Q1 释放边界理想集：研究备忘与小验证

入口：`RESEARCH_MEMO.md`。

`src/ideal_split.py` 提供成员拆分、真实 COPY 收缩、精确 spill 前增量 net、冻结释放标签、阈值区间扫描、理想闭包与整数最小割。它不是 evaluator，也不是完整生产搜索器。参考最大流采用 Edmonds–Karp，面向小 Task 验证；不要把其性能当作原生最大流实现的性能。

官方源码从本会话原附件按字节提取在 `official/`，代码集合哈希和每文件哈希见 `evidence/official_identity.json`。本轮 GitHub 授权读取记录见 `evidence/source_reads.json`。

## 读取证据

- `evidence/new_checks/summary.json`：第一组结构、字节、流和合成 E0 检查。第一输入布局的入口候选只打平父计划，保留中性结果。
- `evidence/nonprefix_variant/summary.json`：随后手工构造的非前缀布局。所有同图父/子方案保持原图字节不变。
- `evidence/ledger.json`：18 次 E0 函数结果身份和指标，另有 3 次 CLI 复核。不把重复成员的重复调用当独立样本。
- 每个实验目录有 graph、plan、完整 result。CLI 复核目录还有 trace、log、command 与 CLI JSON。
- 数学检查使用 48 张 2–6 计算节点合成图，964 次是计划 validator，不是 964 次完整 E0。

## 复跑

脚本拒绝覆盖已有实验目录。在副本中先移动旧结果，再运行：

```sh
mv evidence/new_checks evidence/new_checks_saved
mv evidence/nonprefix_variant evidence/nonprefix_variant_saved
python -B src/verify.py
python -B src/verify_nonprefix.py
```

只需 Python 标准库。原始 `verify.py` 第一组入口实验的源码注释中“after late input”是构造时的目标，不是实际观察；实际 Step1 被写入结果，为 a,b,c。随后 `verify_nonprefix.py` 的变体才实际给出 b,c,a，且前缀都退化、非前缀改善。研究备忘明确保留此开发顺序，不能将第二例声称为首次/盲测结果。

前瞻集成应由现有搜索器控制父计划身份、流调用数、成员多样性、E1 批预算与最终 E0 确认。当前没有把该生成器接进本队 E1/E2 默认路径，没有正式 case 的新成绩。
