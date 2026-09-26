# 单尾响应核验：来源清单换行预检修正

原预算 `TAIL_RESPONSE_AUDIT.md` 的第一次supervisor在2026-09-25T03:26:37.046840Z至03:26:41.255168Z停止。响应分析、derive、Step、E0/E1/E2均0，资源门尚未执行。原runner、run.json和README完整保存在 `results/a/q3-yuanzhifang/tail-response-static-20260925/`，不覆盖、不改原记录。

根会话随后逐字节核对：工作区source-manifest有589个CRLF、19336B、SHA256 `975cefc85ecc34d529c8f3f4798e9b86a099ea65ede69595708ea40aad0da264`；固定Git blob无CRLF、18747B、SHA256 `713792d81693757a71cb29b9daea7434192d1bf14fcb8efd25165e6f68d9cffc`。两者仅CRLF/LF不同，JSON所有字段相同，`git diff`无内容修改。此前将仓库文本清单也要求原字节相同，是预检设计错误，不是官方图或脚本变更。

后续runner只对这一份JSON文本索引允许CRLF/LF规范化后与固定blob相等，并同时记录两种原SHA及 `raw_bytes_equal=false`。Python源码、官方code、图与config仍严格核原字节；未修改官方源码或manifest原件。后续目录 `tail-response-static-followup-20260925/` 独立保留回执，并先核上一份run.json固定SHA与全0调用账。

这是**一次人工修正预检后的后续执行**，整个工作流不声称零supervisor重试。原定真实图分析总上限仍为1，未增加候选/图/模型调用预算；后续最多一次分析进程、10秒、1worker、1GiB物理RAM/256MiB磁盘门，任一不足/未知直接停止、不轮询或自动重试。完整cold/E0仍0，2GiB门未变。

后续runner与本文提交固定后，执行 `.venv/Scripts/python.exe -X utf8 -B results/a/q3-yuanzhifang/tail-response-static-followup-20260925/run_response_static.py`。响应源码仍1b70dd607、阶梯依赖仍68fbe66e9，旧参考值、独立完整DAG对照与全部计量范围沿用原预算。只允许修正文本身份比较，不改分析结果或参数迎合预期。
