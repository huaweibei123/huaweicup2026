# Colab 按需环境

2026-09-24 本机通过 `uv tool install google-colab-cli` 安装 Google 官方 CLI 0.7.2；`version`、`--help`、`sessions --help`、`run --help` 已验证。工具位于独立 uv 环境，不改变项目锁文件。用户已完成 OAuth，CLI 的 sessions 查询成功；MCP 未安装，未分配 GPU。

当前实际边界：CLI 创建 CPU 实例在 POST assignment 阶段遇到 120 秒 ReadTimeout，脚本尚未开始；网页 CPU Notebook 成功执行临时文件读写探针，报告 Python 3.13.15、Linux、2 个逻辑 CPU。该测试实例随后已释放，CLI 回读确认它不在活动实例中。网页执行可用不等于 CLI 分配故障已解决，也不等于项目依赖或算法已在 Colab 验收。详细记录见 `results/a/colab-preflight-20260924/receipt.json`。

官方入口：

- https://github.com/googlecolab/google-colab-cli
- https://github.com/googlecolab/colab-mcp
- https://research.google.com/colaboratory/faq.html

CLI 适合脚本、文件和实验生命周期；MCP 适合浏览器 Notebook 内交互，要求客户端支持动态工具列表通知，尚未实测当前 Codex 与内置浏览器的组合。无需同时安装两者。

只读会话查询如下；本机已授权，无需重复登录。其他环境首次使用时按打印链接登录 Google，再把授权码直接粘回终端：

```sh
colab --auth oauth2 sessions
```

CLI 首次 OAuth 会申请身份、Colab、Cloud platform 及 Drive file 等权限；用户在 Google 页面检查并决定授权，授权码不进入聊天或仓库。网页已登录不等于 CLI 已授权。

授权后可执行一轮短 CPU 验收：

```sh
colab --auth oauth2 run --timeout 30 scripts/colab_preflight.py
colab --auth oauth2 sessions
```

第一条默认申请 CPU、执行探针并释放该实例；第二条核对运行时已释放。探针只检查 Python、CPU 可见性与临时文件读写，不访问 Drive，也不是算法性能验收。CLI 路径当前在实例分配阶段超时，不能声称这条命令已跑通；暂用网页 CPU 入口即可。

正式实验再上传确定版本的项目材料，运行 `uv sync --locked --python 3.12`。项目要求 Python 3.12，Colab 原生 Notebook 内核版本应先读取，不能假定一致；可保留原生内核，用项目虚拟环境的子进程执行评估器。初始构造和 E0 验证只用 CPU；有具体批量训练任务及预算后再申请 GPU。

Notebook 保存到 Drive 只保存文档，并不保存临时 VM 的依赖和文件。准备好可重复初始化脚本、CLI 授权与结果下载流程即可按需启动；不需要为了待命保留空闲 GPU。CLI 的文件上传/下载可在正式实验时使用，结果返回本地后仍按项目规则记录来源、命令、哈希和版本。
