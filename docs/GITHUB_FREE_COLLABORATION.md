# GitHub 免费协作

2026-09-24，用户明确要求本项目的 GitHub 协作只使用免费功能。队长负责维护该边界；成员不为继续协作而升级付费服务。

## 保留与停用

| 用途 | 当前方式 |
| --- | --- |
| 共享源码、材料与历史 | 公开组织仓库（2026-09-24用户调整）、Git 分支/worktree、正常 fetch/push；不使用 LFS 计费存储 |
| 任务、通信与审查 | Issues、team-mailbox、PR 和普通代码审查；PR 不按数量收费 |
| 权威图谱 | 本机 Atlas 与既有签名 Git 同步，无需 Actions |
| Pro 材料镜像 | 既有本机脚本同步 Vioano 公开副本（2026-09-24用户要求），两仓库都关闭 Actions |
| 自动测试 | 按范围在已经授权的本机或队友电脑运行，提交真实证据；不启动云端 runner |
| 上线调度 | 当前 Codex 会话 heartbeat，默认 30 分钟；使用既有 Codex 额度，不是 GitHub 免费计算资源 |

不得开启/dispatch/rerun GitHub Actions、购买云端 runner、提高账单限额或升级计划。不得自行为本项目启用会计费的 Codespaces、Copilot 云端任务/自动审查、LFS/Packages 超额服务或第三方付费 CI。免费额度也可能用尽或变更，不能把“可能有赠送额度”当作持续免费保证。遇到文件大小、API 速率或额度限制，先采用现有本机工具、调整节奏或报告具体缺口，不能静默转为付费。

原 `.github/workflows/` 保留作为历史复现清单，远端仓库级 Actions 权限关闭是当前执行控制。不会删除历史工作流、日志和产物；历史 artifact/cache 仍须与账户其他存储合并计算，本次未修改历史账单或账户级其他项目设置。

## PR 的验证与整合

- 固定提交、输入和环境，按修改范围运行必要检查。资料修改检查内容、链接、来源/哈希、diff 与文件卫生；无需为每次文档 PR 运行三平台示例。
- 实现修改保存真实命令、退出码、依赖/平台、结果与局限，独立复核和任务卡验收继续有效。需要 Windows 证据的任务交给实际 Windows 环境；macOS 本机成功不能代替其他平台实测。
- PR 清楚写“Actions 按免费策略停用；本地已验证……；尚未验证……”。历史因付款/限额未启动的检查不算代码失败，也不算通过。不得伪造绿色状态或把未知结果记为通过。
- 队长仅在实质证据满足本次范围时整合；文档和算法分开判断。若远端必需状态检查阻止合入，先报告具体规则，不自动强行绕过或削弱算法门槛。
- E0 冻结、E1 零差分与速度要求、E2 误差与速度要求、构造算法的方案质量及端到端计时均保持原标准。

## 已实施的控制与范围

2026-09-24，队长分别以 NikolaStarx、Vioano 身份将 `huaweibei123/huaweicup2026` 和 `Vioano/huaweicup2026` 的 Actions 权限设为 `enabled: false` 并重新读取确认。该设置属于仓库服务端，不在 Git 内容里；任何新镜像也应单独检查，不能只复制本文件就声称已停用。

这是本项目未来协作操作的免费边界，不是对账户全部历史账单或其他仓库费用的审计。未充值、未加卡、未提高预算；既有 Codex/ChatGPT/Google 等订阅和实验额度仍按各自授权，不能由这份 GitHub 规范自动新增消费。

依据：[GitHub 免费方案](https://github.com/pricing)、[Actions 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[仓库 Actions 权限 API](https://docs.github.com/en/rest/actions/permissions#set-github-actions-permissions-for-a-repository)。规则核对日期：2026-09-24。
