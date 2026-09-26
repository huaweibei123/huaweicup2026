# 044原tensor切点静态盘点

固定原图SHA `9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e`，实际只读取一次；旧singleton计划固定 `e6b5500dcbf3818034804168ee79d0f65c16706b`。由旧28/58/91阶段内作业片段还原11个124位置作业，并按原op/tensor边检查真实计算依赖：所有作业拓扑合法、相邻位置存在计算依赖、没有跨作业计算依赖。位置模式同构：True。

frontier仅计原计算producer在左、原计算consumer在右的tensor，逐tensor去重。原终端COPY_OUT另列，不能把终端DDR写回混作跨阶段tensor。全部123切点、每作业tensor ID集合/字节/逐tensor ceil(bytes/60)、累计compute和来源SHA保存在JSON。

|切点h|每作业tensor数|每作业字节|每作业逐tensor ceil之和|每作业累计compute|11作业总字节|
|---|---:|---:|---:|---:|---:|
|28|4|4096|71|1928|45056|
|58|6|4096|73|3875|45056|
|91|4|4096|71|5758|45056|

各指标最小切点（累计compute均为每作业）：
- `total_tensor_count`最小值11，达到者：h=1（compute=150）, h=2（compute=172）, h=7（compute=538）, h=12（compute=904）, h=113（compute=6918）, h=114（compute=6940）, h=119（compute=7306）。
- `total_bytes`最小值22528，达到者：h=1（compute=150）, h=2（compute=172）, h=7（compute=538）, h=12（compute=904）, h=113（compute=6918）, h=114（compute=6940）, h=119（compute=7306）。
- `total_sum_ceil_bytes_over_60`最小值385，达到者：h=1（compute=150）, h=2（compute=172）, h=7（compute=538）, h=12（compute=904）, h=113（compute=6918）, h=114（compute=6940）, h=119（compute=7306）。

原终端COPY_OUT输入tensor共11个，总22528 B；全部没有计算consumer：True。

这里的ceil(bytes/60)只是名义带宽下单次COPY的算术服务量，未乘双向复制、跨核500延迟或模拟争用/Cache/容量；不能解释为官方Makespan或官方界。前缀compute采用max(1,cycles)求和，也不是实际求解墙钟。没有生成候选或选择正式切点。

分析UTC 2026-09-24T18:11:29.660001Z–2026-09-24T18:11:30.412793Z，Python CPU 0.421875s、分析wall 0.752980s；0 solver/build/derive/Step/E0/E1/E2。父watchdog限制60秒、单worker低于普通优先级，实际外层计时由JSON回执记录。没有自动重试。
