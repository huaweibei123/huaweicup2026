P3 专项突破咨询：容量约束、共享权重复用与 COPY 输出队列
负责人 session=yuanzhifang30-sudo/s-3d9c78db26714786b88b987ca6f58e2b；请独立于本项目 P1/P2 咨询。使用当前最高 Pro 档深入研究。

请解压附件 q3-capacity-copy-queue-evidence.zip（2901468 bytes，SHA256 bb91c542e94abdba7aef3e87a85841308744aec1720189b2ff1dd4636b5e02e5），先读 START_HERE.md、原题、冻结 config 和官方 evaluator，再核对已有算法、实测结果与完整 trace。MANIFEST.json 给出60文件的来源/哈希；固定资料 HEAD c514edf0a8ef95861fc5cfbcc6719ffd5fdd4e07。请在回答开头报告实际读到和未读到的关键文件，不能把链接存在当作已读。

瓶颈是明确的：044/k4 singleton流水40927 cycles；加入冷setup的精确抽象DP实际退到41738并发生1622016 B spill；同核归属、M/V/MTE2执行序保持但把1364个singleton合成4个阶段，实际退到97641，MTE3次序发生阻塞。更大的067/073共同权重3721600 B超出总L1与只读cache，命中0、spill很大，现流水还不如队长固定V2。我们不能继续靠小图切点成功推广。

请只优先提出1—2条能突破这个瓶颈的具体路线，尤其审查“容量感知分段 + wave/microbatch跨作业复用 + 可由合法subgraph/schedule编码的COPY优先序”。若不可行，请给反例并改换更可靠构造。不能直接提交MTE队列或时间戳，输出只能 node_to_subgraph 与 core_schedules；不得修改官方语义或配置。请说明E0真正提供的控制自由度、容量代理为何失效、能证明的保证范围、复杂度和完整伪代码。现有 pipeline_capacity 是静态shared+max单op非shared足迹约束，仅合成测试，没有官方实测，不应预设有效。

目标同时压低官方Makespan和求解端到端墙钟，额外DDR/按字节hit另报；在线E0必须计入求解时间。需要结构性方法而非按图号特判或大量盲扫。最后给一个最小证伪实验设计，建议预算最多6次冷构造/12次外部E0、具体比较对象/预期signature/停止条件；请不要自行宣称本机结果或最优性。区分抽象定理、已测事实、推测和待验证点。