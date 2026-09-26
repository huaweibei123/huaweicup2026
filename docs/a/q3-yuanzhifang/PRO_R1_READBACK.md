# P3 Pro首轮答复复核与下一实验

来源为 `AI chats/20260925-Pro-P3-容量与COPY排队突破/` 的完整一问一答，固定归档 `2a0d34620c92added6b71d4e009e9c73b2e6c99c`。用户指定项目最高Pro，第5项/共5项；页面显示思考33m25s后生成，root在最终控件出现后读完，暂停临时监听。没有重复在途提问或覆盖P1/P2咨询。两份附件下载未取得字节，不能称其脚本已本地复现。

本机独立复核两份保存P3 Cache事件。067有50份共同输入，每份71个eligible consumer；按 `(core_id, logical_tensor_id)` 首次/重复划分，首次3,721,600B、重复202,303,488B，其他首次5,452,800B、重复0。044旧cold-setup共享首次930,400B、重复1,622,016B，其他首次77,440B、重复0。逐事件分账加总与官方hit+miss完全一致，共同输入重复量均与官方spill字段相同。原始只读分析0.234s；将驱动整理为相对路径CLI后再次复核0.128s。两个回执分别为 `pro-r1-read-classification.json`、`pro-r1-read-classification-repro.json`，均0构造/derive/Step/E0。

复现入口：`python -B src/q3_yuanzhifang/read_classification.py --graph-dir <原图目录> --output <新JSON文件>`。图/压缩与解压result SHA、消费者计数、事件条数和驱动SHA在回执中。这里只复核这两份事件，不代签Pro的八组33,142操作核对，也不单靠字节相等证明所有隐藏spill分配或反事实收益。

Pro指出的DDR守卫过严已在 `2df4a5fa` 修复，随后044/k4容量DP实测37581；其输入只含旧代码和旧40927，所以新37581不是Pro得出的实验数字。静态 `shared + max(single-op incident)` 确实不覆盖长残差活跃区间；本次实际峰值也略大于代理。保留其一例改善，不扩大成全域可行性/零spill/最优证书。

新主线采用完整作业归核，消除跨核激活COPY，核内 `(wave, position, job)` 让同位置权重连续使用。F/A计算包含长残差，wave宽度按容量直接求整数上限，不扫参；同分核的 full-wave 是必要对照。共享读量上界仅在严格输入、COPY端点和单操作容量条件下讨论，最终还要用P3事件直接检查；它不是Makespan保证，也不能排除私有激活spill。默认不做安全合并、不在线调用Step/E0。保序合并另需完整Step2输入序列及核内图身份一致，尚未实现。

已实际读队长Issue51评论5821001337与固定 `08d2060d8d524729b335d6aecc1f30220d324626:results/a/q3-nikolastarx/shared-pipeline-probe-20260925/README.md`：6bae固定候选集合的均值上限不覆盖新切点或wave；最新报告的067 calendar对照为12,237,901，Pro输入的13,422,709是旧V2。下一实验会分别注明版本，不选择更弱对照宣称领先，不重复队长044/046k5或Attention witness任务。
