# 团队与通信

团队仓库：`huaweibei123/huaweicup2026`。所有成员应使用这个仓库作为 `origin`，各自克隆、各自登录 GitHub；不要共用账号或将个人 fork 当成邮箱。

## 分工表

**2026-09-24 最新优先级：** 总调度继续跨任务协调与科学复核路由；成绩台的研发对接、benchmark 分配和数据接收由 `s-7c98…` 汇总，本机生产会话 `s-59ee…` 执行已经明确的批次。分配、执行、交成绩与网站维护统一先读 [方案成绩台](benchmarks/BENCHMARK_BOARD.md)，具体边界见 [团队工作流](TEAM_WORKFLOW.md#方案成绩台与研究调度分工)。NikolaStarx、Fang 的算法专项负责后续算法与 Coherent 研究；LYX、farmer 保全既有已授权批次，并承接独立成绩数据任务。旧算法范围仍是历史及交接责任，不因新分工默认释放单写权。

| 角色 | GitHub 账号 | 职责 |
| --- | --- | --- |
| 队长 | NikolaStarx | A 题首轮：冻结输入、公共接口/E0、独立验收与团队协调 |
| 成绩台研发对接与接收 | NikolaStarx 的 `s-7c98…` 会话 | 对接研发、分配明确 benchmark、协调 LYX/farmer 数据；网站、协议和中央账本单写维护 |
| 本机 benchmark 生产 | NikolaStarx 的 `s-59ee…` 会话 | 调度/执行已明确批次；独立 runner、原件、结果、导出和预检，向成绩台交固定产物 |
| 形式化与对抗样本 | farmeruncle123 | A 题首轮：规则来源、语义探针、对抗生成与反例缩减；Issue #14 |
| 评估器工程化与测试 | lyx0217 | E1/原生精确核工程化；E2 开发交付后的独立测试；Issue #15 |
| E2 核心开发专项 | NikolaStarx 的 `s-55b6…` 会话 | 2026-09-24 用户调整：E2 核心方案、实现和开发验证；[任务卡](../tasks/a/E2-CORE-DEVELOPMENT.md)，Issue #15 |
| 情况 A / P1 | NikolaStarx 的 `s-6607…` 原专项 | 已接受 P1 回交，固定基线 `4dff90ef699fd51845cf482951e8477066f5f566`；`src/q1/` 单写，PR34阶段成果待验 |
| 情况 B / P2 独立协作 | NikolaStarx 的 `s-8ee33…` 第二专项 | `src/q2_nikolastarx/` 与对应独立目录；与Fang交换固定成果，PR59，不再负责P1 |
| 情况 C / P3 | NikolaStarx 的 `s-3172…` 第三专项 | 只读Cache构造、P3官方对照；独立 `src/q3/`，PR53阶段成果待验 |
| 情况 B 核心算法 | yuanzhifang30-sudo | 2026-09-24 新增：Q2 构造、子图优先级与有预算搜索；Issue #33 |

形式化与评估器工作起于 A 题第一轮，表中已叠加最新 E2 开发/测试分工；2026-09-24 队长确认 yuanzhifang30-sudo 上线、有 Codex，新增 [Q2 任务](../tasks/a/Q2-CORE-SEARCH.md)，覆盖此前对他的“暂不分配”。情况 A 已由原专项实际接回，第二专项转 P2 与 Fang 分目录协作，第三专项负责 P3；这覆盖此前“第二专项负责 P1、原专项仅维护架构”的旧路由。P1/P2/P3 各自按原任务确认新预算，交接不重置封存预算；[分工与交接包](a/Q2_HANDOFF.md) 规定共享接口和独立范围。指派不代表成员已读、接手或正在执行；仓库权限以本人实际授权为准。

LYX 早期自报 Codex / Windows；其路由成本静态审计和 farmer 四反例资料交接均已有独立文档验收，不能继续视为待接手，也不等于 E1/E2/FORM 整体终验。用户最新按两位 CodeBuddy 队员参与成绩台安排工作，具体客户端能力与在途 benchmark 以各 session 实质回执核对，不仅按品牌推断能力。原数据与失败记录保留；队长统一管理公共信息、归档与 Atlas，网站专责维护成绩台，双方不争写共享范围。

## 团队可用资源（2026-09-24 更新）

已有资源描述见 [选题讨论原文](../AI%20chats/选择建模题目策略.md) 中的“五、你的资源，应该按任务价值与验证成本分配”。此处维护当前增补，原始讨论保留原样。资源可用不代表已经安排实验或证明算法收益；按具体任务价值选择。

**资源归属不等于全员权限**：标注“队长”的设备、软件许可、OAuth、额度、ChatGPT 连接和 Vioano 镜像管理权限，仅供队长及其授权本地会话使用。Vioano 镜像于2026-09-24按用户要求公开，任何人可读取其公开内容。队友可以读组织主库，不因此获得这些账户或工具权限；需要代跑时通过任务 Issue 交接。成员自己的资源另记本人授权。[详细边界与实测记录](a/CAPTAIN_RESOURCES.md)。

| 资源 | 来源与当前确认程度 | 可承担的工作 |
| --- | --- | --- |
| 队长 MacBook Pro | 队长自报，当前协调与有限复核已在本机执行；具体 CPU/GPU/内存以每次运行记录为准 | 开发、协调、原型与本机实验 |
| 队友的游戏笔记本 | 原讨论自报有几台；各机 GPU/显存/可用时段尚未汇总，不据此假定可运行 CUDA | 独立样本、随机种子和实验分片，按实际配置选择 |
| Codex 20x、CodeBuddy 积分 | 原讨论自报；不将历史套餐说明当成当前剩余额度 | 实现、分析、候选扩展与复核 |
| 队长 ChatGPT Pro | 本轮已用于网页研究探索；回答与实验仍须核材料及证据 | 数学/算法研究、资料综合 |
| 队长本机 Python、MATLAB、Wolfram/Mathematica | 2026-09-24 已查到 Python/uv、MATLAB R2026a、Wolfram 应用和 wolframscript 入口；本次未启动 MATLAB/Wolfram 核验许可或工具箱 | Python 复现；按需做小规模优化、符号计算、反例与猜想检查；数学输出仍需对照官方语义 |
| **队长 Google AI Pro → Colab 200 Compute Units（CU/CCU）** | **队长报告 200 CU、A100 备选；官方权益说明支持 200 CCUs 按月发放。2026-09-24 CLI 0.7.2 的 OAuth 会话查询成功、当前无活动会话；此前网页 CPU 探针通过并释放，CLI 分配曾超时。余额、费率和 A100 分配未实测** | 有实际收益时可安排 CUDA 原型、训练、批量实验；已验证的工具范围见详细记录，不能当作完整工程已在 Colab 跑通 |
| 额外租赁算力 | 原讨论中的备选，没有本次新采购或消耗授权 | 本地资源成为明确瓶颈后，再按收益和预算决定 |

队长明确：新增 Colab 额度只是扩充可选资源，**不要求必须使用，不因登记而启动运行时、训练或采购，也不改变 E1/E2 验收标准**。此前 CPU 连通性探针有单独授权，不构成队友或其他实验的无限授权。不预设某项算法必须用 GPU；Apple 硬件与 CUDA 路线均以实际整条流程收益判断。

### 200 CU 大致能用多久

CU 不是 GPU 小时。若全部用于同一种运行时，预算时长为 `剩余 CU / 当前 usage rate（CU/小时）`。本次公开官方页面没有给出固定的 A100 扣费表；不能把网上某个时点的费率写成当前账户保证。

| 假设当前面板显示的费率 | 200 CU 对应累计运行时长 |
| --- | ---: |
| 5 CU/小时 | 40 小时 |
| 10 CU/小时 | 20 小时 |
| 15 CU/小时 | 约 13.3 小时 |

这些是条件换算，不是本账户实测费率。作为量级参考，2025-09-13 的 [modded-nanogpt 作者使用指南](https://github.com/KellerJordan/modded-nanogpt/discussions/126) 报告 100 CU 约可用 16 小时 A100，线性换算 200 CU 约 32 小时；另一份 [autoresearch-colab 项目说明](https://github.com/aigorahub/autoresearch-colab#recommended-a100-40gb--best-balance-of-cost-and-capability) 写约 10.6 CU/小时，换算约 18.9 小时。两者均非 Google 定价承诺，也未在本账户复测，**约 19–32 小时只作公开资料的预算参考区间，不是上下界或连续运行保证**。

需要实际安排时，由队长记录账户资源面板的剩余 CU、扣费速率、分配到的 GPU/显存、内存档位和日期，再按余额重算；部署、数据传输等占用运行时的开销也应留预算。GPU 类型与资源供给会变化；累计可用小时不能直接当成一段不中断的作业时长。本次没有启动运行时来测费率。

来源核对日期：2026-09-23。

- [Google One：Google AI Pro 权益](https://support.google.com/googleone/answer/14534406?hl=en#zippy=%2Cuse-google-colab)：明确 200 CCUs，具体账户资格与余额另核。
- [Google Colab FAQ：Google AI plans / Resource Limits](https://research.google.com/colaboratory/faq.html)：额度按月发放；高级 GPU 受供应情况影响，运行时寿命与可用性有限。公开规则不等于本账户已成功分配 A100。

## 开始使用

同一账号的多个 Agent Session 按 [轻量会话协议](SESSION_PROTOCOL.md) 登记和寻址；完整抓取后按角色读取，不能用账号共享缓存代替本会话已读。

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
- Skill 默认手动查收；队长已明确授权本轮持续查收与范围内回复，并设置周期跟进。该授权不会自动唤醒队友的 Agent；队友仍按本人授权查收与回复。查收脚本本身不发消息。
- 各人自行授权自己的 Agent 回复范围。队伍成员的 Issue 不是对本机的无限授权，新的任务由本人确认。
- 原协议与安装说明见 [team-mailbox](../.agents/skills/team-mailbox/SKILL.md)。

## 共享系统设计

System Atlas 0.5.0 已安装，负责系统模型的节点/字段协作与共享任务看板，使用方式见 [SYSTEM_ATLAS.md](SYSTEM_ATLAS.md)。任务沟通继续使用 team-mailbox 的 Issues/PR；设计图谱的请求、签名和版本检查使用 Atlas 自己的协议。

正式业务空间已初始化为 `huaweicup2026-a`，同步分支 `atlas/a-2026`；当前接入与身份锚点见 [A 题 Atlas 接入](a/ATLAS.md)，不要恢复已结束预演。私有状态目录必须在所有 Git 工作区之外。任务指派标签不会自动授予权限或唤醒 Agent，每个人必须启动并授权自己的 Agent。

队长本人已明确：**公钥核对和公开身份交换直接走已建立的 team-mailbox / GitHub Issue 通道，不默认再转微信。** 核对实际 GitHub 作者、固定邀请、project/epoch 和 PEM 指纹后，在本人既有授权内继续；详细流程及真正需要暂停的例外见 [通道约定](a/ATLAS.md#已确认的核对通道2026-09-23)。
