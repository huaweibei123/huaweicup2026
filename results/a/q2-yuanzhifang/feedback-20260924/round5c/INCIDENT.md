# 5C Windows 账本替换失败现场

唯一启动的 `round5c-parallel-spec.json` 批在第 2 个用例时因 `PermissionError [WinError 5] 拒绝访问` 停止。异常位置为 `src/q2/feedback/measure.py` 中 `save_json` 对 `ledger.json.tmp` 到 `ledger.json` 的 `os.replace`。runner 退出码 1；未重试、未修复账本或 run，也未重新构造/评分任何用例。

账本 T0 为 `2026-09-24T17:08:26.297280Z`，T1 为 `2026-09-24T17:08:34.117251Z`，墙钟 `7.8205676` 秒，最终 `state=stopped`。实际收费计数为 solver 2、官方 E0 1、E1 0、E2 0；两次尝试、三条 reservation。070 的 solver 和 E0 均成功，官方 Makespan 36800。071 的 solver reservation 为 `ok`，于 `2026-09-24T17:08:32.908071Z` 预留，进程 PID 22636，实际墙钟 `1.183122` 秒；071 计划、solver stdout 和空 stderr 已保存。但在持久化更新时发生异常，071 的 `run.json` 仍为 `status=running`、`stages={}`、`artifacts={}`、`calls={solver:1,E0:0,E1:0,E2:0}`，`finished_at=null`。071 没有 E0，余下 28 图未启动。

运行期间，本代理两次通过 PowerShell 只读查看变化中的 `ledger.json`；Windows 文件共享锁可能与替换失败有关，但目前不能确认唯一原因。此后不再在正在运行的批中读取 ledger/run/output。父任务将冻结本现场，并事前固定剩余 29 图的新协议；071 已消耗的一次 solver 计入总成本。标准 feed 和 summary 未生成，因为 071 的运行记录未完成。
