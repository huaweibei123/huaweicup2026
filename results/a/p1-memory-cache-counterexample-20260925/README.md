# 含 MEM 依赖时有序相对 ID 不保证响应签名相同

两条同型私有 `M,V,V,M` 链通过 `Family.verify_ordered_family`。tensor ID 块分别为 `[10,11,12]` 与 `[15,16,17]`，UB 容量80B。每链有一个40B外部输入、一个40B内部tensor和一个40B终端输出。

冻结官方 Step3 在第二个 V 退休时遍历未排序 `set(in_tids)`，同时释放两个 tensor。整数集合顺序随 ID 改变，导致 FIFO 内存信用队列的来源顺序改变。后续 M 的 need 分别为 `(1,2,0,0)` 和 `(0,2,0,0)`；实际编译的完整签名记录于 `signature-difference.json`。

差异中的第一条 M 前驱已经被第二条 V 的依赖蕴含，因此本例只推翻**扩展到 MEM 域后**“相对 ID 顺序必然保证直接签名相同”的断言，尚未证明响应或成绩不同。该 Task 总足迹120B超容量80B，也有 MEM 边，原保守编译器本就不接受；本反例不推翻旧无 MEM、总足迹可行域的证明或已复评成绩。

证据重放使用 Python3.12.13：1次官方多Task构建、2次合成 Task 编译，0真实图、0solver/E0/E1/E2。此前探索最多10次极小 Task 编译，和此次2次分开记账，累计未超12。源码与产物SHA在receipt；每个官方文件SHA在compile-certificate。原件保持不变。

重新验证须指定新的空目录，脚本仍拒绝覆盖。此参数是在证据生成后补的可复现入口，未据此新增编译：

```sh
python results/a/p1-memory-cache-counterexample-20260925/reproduce.py --output output/memory-cache-counterexample-replay
```

后续安全路径：先实际编译再比较签名；若要忽略冗余依赖，须另证其标准化保持依赖可达关系。仅核对最终被选计划不足以认证所有未展开转移的缓存。
