# 实际阅读与未取得范围

## 全文或完整内容读取
START_HERE.md；原题problem.pdf全部文本（14页，另查看5/13/14页渲染）；官方README.md、docs/a/OFFICIAL_OBJECTIVES.md；paper/sections/a-q3.md全部613行。
新机制的partial-preload公开REPORT、INDEPENDENT_AUDIT及run-public记录；query-flow-static-repair REPORT、query-flow-one-shot README、pro-r08-independent REVIEW。
solver-311中的forest_solve.py、shared_pipeline.py、forest_memory_order.py；research-65的query_flow.py。

## 按相关函数/段落实际审读，不称整套源码通读
官方P3重建、稳定分桶、Cache/共享池/事件/结果路径；P2对应Task函数与差分（另AST精确比较）；P1 Task边界构造/Task激活路径；Step1确定性排序；Step2生命周期/spill/扩展图；Step3物理存储、VIRGIN信用、Pipe队列、内存补边；方案parser和全局合法性检查；singlecore基线入口全文。
固定算法construct、pipe_bound等相关代码；partial_preload_prepare/probe相关守卫。未逐行通读所有solver-311其他模块，不把源码哈希核对算作语义审读。
paper/notes/a-q3-evidence.md关键证据表/更新段及3个draft审计JSON相关字段。
全局bounds的README/REPORT、原证书结构与基线摘要。

## 完整程序化解析与哈希验证
外层ZIP104项、MANIFEST登记103项；内层全部100张原图及source-manifest图哈希；10份官方源码/配置身份。
10份统一feed的全部500格；旧bounds.csv、新current-gap.csv全部500行；snapshot structures.json和baselines.json。
044两份计划、基线结果、四份P2/P3结果全部解压解析，核对6712条操作记录、全部Cache事件/跨核释放。公开SHA256SUMS在包内存在的9项均复核，缺失引用另外列入mechanism_audit.json。
原题PDF文本抽取及局部渲染不等同逐图视觉审读全部图示。

## 未取得/未执行/只保留来源声明
统一500格的完整原始计划/结果/trace以及其500份配对P2原件；100个基线原件中仅044附带，其余为作者基线数值/哈希摘要。
071/069 query-flow候选正式计划、完整准备Task原件不在本包；数字采用作者静态报告，不重建候选。全部query-flow源码/运行原件是否等于此前Pro附件，不能以该附件不可取而冒充逐字复现。
044本次prepare完整快照、stdout/worker/preflight等SHA256SUMS提及但未提供的文件；重复raw-evidence路径的结果gzip虽未以该路径提供，同字节artifacts副本已核。
R8既往回答原文文件完成包哈希核验，本轮结论主要逐条依据独立REVIEW/新源码/静态报告，不称重新执行其作者测试；paper所链接而包外的P1/P2新答案未访问，不杜撰三问共识。
没有调用solver、候选construct、Task、Step1/2/3、E0/E1/E2，没有搜索新候选。所有静态程序和其边界见README。
