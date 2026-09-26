# P2 5C 并行批中断记录

按 `round5c-parallel-spec.json` 唯一启动一次。runner 因 Windows `PermissionError [WinError 5]` 中断，依照零重试、首个意外失败停止的协议，没有续跑或重评。后续本 lane 的 7A/B/C 与 9A/B/C 未启动。

- T0：`2026-09-24T17:08:26.297280Z`；T1：`2026-09-24T17:08:34.117251Z`；批墙钟 `7.8205676` 秒，批前来源校验另计。
- 账本状态 `stopped`；实际收费调用为 solver 2、独立官方 E0 1、E1/E2 0。`070` 的 solver 与 E0 完成，官方 Makespan 为 36800，固定单核基线 117300，对应逐图比值 3.1875。
- `071` 的 solver 进程和计划输出已完成，reservation 标记 `ok`、墙钟 `1.183122` 秒；异常发生在把更新的 `ledger.json.tmp` 替换为 `ledger.json` 时，其 `run.json` 仍为 `running`，E0 未调用。余下 28 图未启动。因此本批没有30图均值，也不能据此宣称四核全100完成。
- 失败路径是 `src/q2/feedback/measure.py` 的 `save_json` 中 `os.replace`，错误为 `PermissionError: [WinError 5] 拒绝访问`。本代理曾在批次运行中只读打开 `ledger.json` 查看进度，可能造成 Windows 短暂共享锁；目前没有证据确认唯一原因。错误发生后未修改 runner、spec 或成果原件。
- `audit_saved.py` 独立只读核查了 spec 哈希、账本计数、两个 run 状态、已保存工件哈希、070 的 gzip 原始字节与官方结果、单核基线身份以及 071 计划存在性。命令：`.venv/Scripts/python.exe -X utf8 -B results/a/q2-yuanzhifang/feedback-20260924/round5c/audit_saved.py`，退出码 0；审计不运行 solver/E0。

由于 071 的持久运行记录未完成，本批未调用 `export_board` 或 `analyze`，也未生成可能被误认为完整批次的 feed/summary。墙钟发生于其他 P2 lane 和系统任务可共享 CPU、内存及文件缓存的环境，不可解释为独占冷缓存效率。批前可用物理内存约 2373 MB。所有原始文件留存供父任务判定后续协议；本代理没有重试或擅自用替代 spec 补洞。
