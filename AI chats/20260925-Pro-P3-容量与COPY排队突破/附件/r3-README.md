# P3 R3 只读证明与算术审计

输入是用户附件 q3-theoretical-bound-r3.zip，11,309,176字节，SHA256:
9d50a4260ff72981ea902c115cd39aa109f6fc8f88ee69ae0c0e9f759295ea4f。

## 复现

仅需Python标准库。不要使用python -O（脚本使用assert校验）。

```sh
python audit_readonly.py --archive /path/q3-theoretical-bound-r3.zip --out ./reproduced
python mechanism_readonly.py --archive /path/q3-theoretical-bound-r3.zip --out ./reproduced
python check_small_proofs.py --archive /path/q3-theoretical-bound-r3.zip --out ./reproduced
```

脚本不会导入官方或solver模块，不会调用构造、Task、Step1/2/3、E0/E1/E2，不生成候选方案。第三脚本仅导入本包audit_readonly的纯解析/整数证书函数。原图始终从原ZIP只读取得。

## 文件

- cells_500.csv：全部100图×1–5核B/U/L0/L1、三个间隙、比值与对均值贡献、extra/spill/hit/wall、来源身份。
- all_100_cases.md：100行易读表，每格U/L1。
- proofs_100.json：原图CP路径、工作量、每核窗口见证及原子计数见证。窗口成员用阈值定义，可从原图重新枚举核验。
- audit_summary.json：核验身份、1–5核均值、各核top10及top5/10/20乐观贡献、作者CacheGain摘要与缺件说明。
- mechanism_audit.json：044四份保存P2/P3的6712个操作、两份计划、所有Cache事件和同计划比较；P2/P3关键编译函数AST比较。
- small_proofs.json：20个小DAG/核数窗口实现交叉核验、森林交换微例、预加载反例、067完整作业界及下界下降但真实传输增大的解析反例。
- PROPOSITIONS.md：15组命题、证明、条件与须撤回的陈述。
- READ_SCOPE.md：本轮实际阅读/解析/缺件。

## 证据和计时边界

所有U、B及原始E0轨迹均来自作者既有记录；本轮没有产生任何新的E0成绩。L1及500行空间算术是本轮只读计算。
十个feed包含M3、指标、图/配置/official/plan身份，但没有500个P2周期，也未附500组原始计划和结果；所以完整mean(G)和pooled字节命中率明确标为作者汇总。逐格G除四个作者明确报告的负例外留空，不推造值。
044机制单格单列，不替换统一311322b/19bebf的500格。其原件包含完整操作时间线，未附独立Perfetto Trace和全部prepare原图。
三次成功只读脚本计时分别约19.9095、0.1388、0.1734秒，依机器不同会变化。读取讨论与脚本编写不包含，不能当成solver时延。mechanism脚本首次静态AST查找函数名写错、StopIteration，改为源码实际名称后成功；没有发生任何官方或solver调用。失败静态检查未独立计时。
数值比值先用整数/Fraction聚合；旧文末位浮点差约1e-15，非数据变化。

## 重要限制

L1只用原计算DAG的必要因果与整数服务工作，刻意不加入未完成官方浮点误差证明的共享服务公式。比旧L0强不代表精确全局最优；500格没有U=L1。
“成功E0 feed”是作者已保存证据的归属，不是本轮独立复评认证。SHA连通验证的是提供字节/元数据一致性，不能由哈希凭空补出缺失原件。
