# 当前选中方案上的 R05 单次静态构造

固定003/K2、当前c665选中方案为seed，使用 `ready_exchange_candidate.build_from_plan(..., final_proxy_guard=False)` 一次构造。执行源码 `effa60585bfa86b7efeded841efedde4e0b86dd2`；图、配置、种子与全源码指纹见 evidence.zip 内 manifest。原始含本机路径收据留 output/，共享副本只替换路径前缀并记录前后SHA。

- 本机实际完成1次构造、0E0/E1/E2、0重试、0云；2.0497s，观察器+子进程RSS峰值207,192,064B，exit0、无遗留进程。30s/512MiB限制内完成。
- spill前COPY字节4,262,874→4,216,154 B，减少46,720B（1.096%）。改变89/13,455个单例包归属。
- 静态lag代理235,640→243,341；这不是官方周期界，不据此拒绝官方可能收益。
- 新方案固定计算FIFO必要下界240,663，当前官方M245,150。因此该固定候选最多有1.8303%的M降幅；不证明这个余量可达。新方案官方M和spill均未测。
- 当前seed官方spill为0；候选仅保证pre-Step2字节不增加，不能把它换成最终额外DDR不增加。

基于当前seed的小幅字节收益和受限时序余量，本轮不为它追加云评分。不是证明R05在其他图上无效，也不是宣称到达全局最优。接下来优先保持每核每Pipe计算顺序与归属，仅调整跨Pipe优先级穿插以缩短生命周期；该方向仍需官方验证。

运行入口（需先冻结本机输入路径与manifest，不得重用已消费尝试）：
```sh
python -B scripts/q2_selected_plan_static_probe.py freeze --graph <official/case_003.json> --config <official/config.txt> --output output/<fresh-run>
python -B scripts/q2_selected_plan_static_probe.py run --manifest output/<fresh-run>/manifest.json
```

`evidence.zip`保存完整构造plan、meta、mandatory计数、FIFO证书、运行及资源收据。`verification.json`逐项记录原始和公开副本SHA/大小，ZIP CRC及全部成员复核通过。
