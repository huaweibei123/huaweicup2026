# 044 A/B 共同机制输入：零 E0 字节核验

全部原件固定在 `13d6b0298f944d3c0bfdf3172191f1ac25a50379`。本次未生成新计划，未启动实验，E0/E1/E2 新调用均为 0。

原图、配置、计划与完整结果的 SHA、大小和固定链接见 [inputs.json](inputs.json)。

| 对象 | SHA-256 |
|---|---|
| case_044.json | `9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e` |
| config.txt | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` |
| parent plan | `ed987c6abf0764f9f64d0f99fd9eec52fbd3729f13d82f2404a9fad8a4e3dbd7` |
| child plan | `a5fd82ce49f2e6bc96b4bbefe2cc1c9f219412997c831decb04c6cd968c04a08` |

父计划→仅合并 Task 8/10；逐操作核归属、mapping 键顺序均保持。配置4核，实际仅core0有工作。
既有 A 完整 E0 为116227→126094 cycles，两份 trace/result 已逐成员校验，可直接复用；不是本次新测成绩。
B 的同核合并不等于 A 的 Task 边界消失；其 COPY 分桶、spill/FIFO 和结果须由匹配 B E0 验证，失败也保留。

Fang协调汇总固定输入、T0/分工及收尾预留后启动新调用；本清单不是已启动回执。008由Q2核查，未在此补造。

本次六字段：目标=固定可交换044原件；输入=上述13d6提交；输出=本清单与inputs.json；
限制=零新评价/单活跃核；验收=来源、归属、原始字节和已有结果绑定检查通过；节点=准备完成，待协调落实执行。

重做本项只读核验（输出须是新目录）：

```sh
uv run python -B src/q1/mechanism_inputs.py --output results/a/new-mechanism-input-check
```
