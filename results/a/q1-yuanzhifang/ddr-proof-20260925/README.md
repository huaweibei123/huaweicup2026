# 051 跨轮阻塞与搬运下界：静态检查

候选证明源码固定 `6fba2f5bab01af27efcd5e4c54db77cd853196e5`。只检查一个冻结原图051，未生成新方案、未调用Task编译或solver/E0/E1/E2。十个官方源文件、图、config及已存G计划与固定Git原件逐项核同。

静态结构满足全部守卫：24轮，每轮12条4节点重链；每条重操作524周期，归约最短叶根路径每轮均为39周期；12个原始32768B输入逐轮重复，864条私有内部链边。候选公式给出理想化语义下的任意分区下界 **211076 cycles**，强于只计一个13周期归约节点的210452。固定G计划的 M=288、B=0，联合公式仍为211076。`plan_legality_checked=false`，合法性沿用其既有E0记录，不以此次静态公式检查替代。

复现（选用新的输出路径，已有产物不覆盖）：

```text
python -X utf8 -B src/q1_yuanzhifang/ddr_barrier_bound.py data/raw/a/official/data/case_051.json NEW_OUTPUT.json --config data/raw/a/official/data/config.txt --plan results/a/q1-yuanzhifang/stage-g-20260925/run/051-k5-fixed-root-four-two-v1/case_051_multicore_res.json
```

原记录在 `051-bound.json`、`metadata.json`、stdout/stderr。独立进程静态分析耗时0.930279秒，不是solver或E0时间；此前源码/输入核验耗时未并入该数。四项合成测试0.319秒通过，覆盖结构缺项和数值条件拒绝，但不是证明验收。正式证明条件见 `docs/a/q1-yuanzhifang/DDR_BARRIER_BOUND.md`。

Sol high的独立只读审查支持数学证明链；冻结E0中的浮点事件容差仍需严格误差界，本目录因此继续标记候选证明。没有最优性或可达性证书，也没有据此停止研究。
