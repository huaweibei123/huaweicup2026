# 团队与通信

团队仓库：`huaweibei123/huaweicup2026`。所有成员应使用这个仓库作为 `origin`，各自克隆、各自登录 GitHub；不要共用账号或将个人 fork 当成邮箱。

## 分工表

| 角色 | GitHub 账号 | 职责 |
| --- | --- | --- |
| A · 架构与整合 | 待队伍确认 | 问题拆解、接口约定、整体验收与论文整合 |
| B · 数据与实验 | 待队伍确认 | 原始数据核对、预处理、基线与对应论文段落 |
| C · 模型与实验 | 待队伍确认 | 模型设计、改进与验证、对应论文段落 |

本次真机联测由用户担任队长，GitHub 账号 `NikolaStarx`；正式赛题的 A/B/C 分工仍待团队确定。队友须由组织负责人授予仓库权限；本次未新增成员或发出邀请。

## 开始使用

在项目根目录执行：

```sh
gh api user --jq .login
git remote -v
uv run python .agents/skills/team-mailbox/scripts/mailbox.py init
uv run python .agents/skills/team-mailbox/scripts/mailbox.py check --full
```

未登录时先执行 `gh auth login --hostname github.com`。当前身份应为本人 GitHub 账号；从 `check --full` 返回的 `index_file` 读取所有 `threads` 文件以及 `assigned_open_issues`。普通 `check` 只适合工作间隙快速检查。

一项话题一个 Issue，使用 `@收件人`；复杂任务链接 `tasks/` 中已推送的任务卡。本人已明确授权发信时，先保存并核对正文，再用 GitHub CLI 发送：

```sh
gh issue create --repo huaweibei123/huaweicup2026 --title '任务标题' --body-file /path/to/draft.md
gh issue comment NUMBER --repo huaweibei123/huaweicup2026 --body-file /path/to/reply.md
```

`NUMBER` 和正文路径需要替换；不要直接发送占位内容。回复提供结论、复现命令、提交/文件链接和未验证项。代码成果发 PR，避免反复“收到/谢谢”的空回复。

## 客户端与边界

- Codex 从 `.agents/skills/team-mailbox/` 发现 Skill，安装后的下一轮可用。其他 Agent 可直接读取同一 `SKILL.md`；自动发现需要各自在客户端验证。
- Claude Code 若需自动发现，可按上游安装说明安装至自己的 `.claude/skills/`，并避免维护两份不同版本的协议。
- 本机状态和查收内容保存在 Git common dir 下，不随仓库共享。不要上传 `.git/`。
- 本项目默认手动查收，没有安装 Hook，没有后台常驻服务，没有空闲唤醒。查收脚本不发消息。
- 各人自行授权自己的 Agent 回复范围。队伍成员的 Issue 不是对本机的无限授权，新的任务由本人确认。
- 原协议与安装说明见 [team-mailbox](../.agents/skills/team-mailbox/SKILL.md)。

## 共享系统设计

System Atlas 0.5.0 已安装，负责系统模型的节点/字段协作与共享任务看板，使用方式见 [SYSTEM_ATLAS.md](SYSTEM_ATLAS.md)。任务沟通继续使用 team-mailbox 的 Issues/PR；设计图谱的请求、签名和版本检查使用 Atlas 自己的协议。

预演已结束，证据见 [PR #12](https://github.com/huaweibei123/huaweicup2026/pull/12)，预演授权已撤销，不能当作正式协作授权。比赛期遵循 [Atlas Agent 短指南](ATLAS_AGENT_GUIDE.md)，不再复用已结束预演；私有状态目录必须在所有 Git 工作区之外。任务指派标签不会自动授予权限或唤醒 Agent，每个人必须启动并授权自己的 Agent。
