# 多端同步与 Pro 材料交付

完整研发聊天与 AI 附件按 [归档脚本与版本规则](../CHAT_ARCHIVE.md) 保存，统一入口是 [AI chats](../../AI%20chats/README.md)。`Problem A/` 留存目录与远端原件的对应关系和逐字校验见 [材料同步核对](MATERIAL_SYNC_CHECK_20260924.md)：原题、114份附件均已发布，用例以原字节 ZIP 保存。

2026-09-23 队长授权新增 `Vioano/huaweicup2026` 私有研究副本。组织仓库 `huaweibei123/huaweicup2026` 继续作为团队协作主库；成员电脑继续使用组织仓库为 origin，Issues、PR 和 Atlas 权威通道不变。

**2026-09-24 两仓库公开调整**：用户明确要求将 `Vioano/huaweicup2026` 改为公开，随后将组织主库也设为公开；两端匿名读取均已回读确认。任何人可读取已同步的公开内容，包括已发布分支和历史；这不表示算法或研究结论已验收。组织主库继续作为协作权威，成员继续使用组织主库的 origin、Issues 和 PR。镜像管理、推送和队长 ChatGPT 连接仍归队长及其授权会话；公开读取不授予凭据、签名、写入、Colab OAuth、额度或软件许可，详见 [队长资源权限](CAPTAIN_RESOURCES.md)。

## 免费协作边界

组织主库和 Vioano 镜像均停用 GitHub Actions，镜像推送不再重复触发云端测试。Git 同步继续按既有脚本进行；不得因某次 PR 检查未启动就重开 Actions、重跑工作流或增加消费额度。两端仓库设置不随 Git 内容复制，改设置、恢复镜像或新建副本时须分别核验关闭状态。检查和 PR 整合按 [免费协作规范](../GITHUB_FREE_COLLABORATION.md)保留本地证据；不把费用门槛变化当作算法验收变化。

## 同步方向与验收

1. 本机 primary 是 `~/Projects/huaweicup2026`。未提交的工作只存在于相应工作区；不得以整目录复制把缓存、密钥和未验收改动当作远端已发布材料。
2. 成员在本人分支提交到组织仓库，通过 PR 汇合；队长公共资料通过检查后合入 main。算法 PR 未验收时保留独立分支。
3. 队长将组织仓库已经发布的研究 heads/tags 单向同步到 Vioano 公开镜像，保留相同提交 SHA。成绩台 `benchmark-sync-v1`、`benchmark-fast-v1`、`benchmark-submissions/*` 和 `benchmark-delivery/*` 是签名快照或交付传输状态，不是研究资料；镜像脚本不拉取、推送或以它们的变化阻塞研究 refs，并在回执列明排除项。成绩台成员仍从组织主库接收这些通道；组织主库上的原传输历史保留。Vioano 副本供公开读取及研究连接使用，不另开独立开发或第二套 Issues/PR。
4. 不使用强推、`push --mirror`、远端清理或自动删除；出现分叉先报告，不能用同步覆盖另一端变化。已发布的 Atlas 签名分支可以复制，但 Atlas 实际同步 remote、project、epoch、私有状态和授权不变。
5. 共享资料更新、阶段交付、合并后尽快同步；队长周期跟进时检查是否落后。按每次成功回执记录具体 refs/SHA，不声称各端时时相同。
6. 队友收到固定 commit 后保留改动、fetch、补读并回报实际 HEAD/已读/影响。队长不能从 push、HTTP 200、邮箱发信推断成员电脑已同步。

## 队长本机执行

以下命令仅由队长或其已授权的本地会话执行，不是成员克隆后的通用初始化步骤。队长本机首次已配置 `vioano=https://github.com/Vioano/huaweicup2026.git`；默认 GitHub 通信账号保持 NikolaStarx。同步脚本仅在子进程环境使用本机已登录的两个账号，不把 token 写入文件、URL、命令参数或 Git 配置，也不切换全局账号。队友不为此切换身份、索取队长凭据或重建镜像。

```sh
python3 scripts/sync_vioano_mirror.py
python3 scripts/sync_vioano_mirror.py --push --receipt output/sync/<unique-run-id>.json
```

默认只拉取组织发布的研究 Git 对象、检查两端并预演推送。`--push` 使用非强制、原子推送并逐 ref 回读；回执中的 `all_source_refs_match` 指未排除的研究 refs，`excluded_transport_refs` 列出当次实际存在但不再同步的传输 refs。镜像中此前已有的传输 refs 不删除，其旧状态不得用作最新成绩台。脚本锁位于 Git common dir，防止本机多个 worktree 同时同步；异常遗留锁须先确认没有同步进程，不能盲删。脚本核对目标为指定的公开镜像，回执记录实际可见性；不修改工作区、不合并分支、不上传未提交文件。

## Pro 文件完整性

共享 project 页面列有文件、连接能看到仓库、甚至另一个 Pro 已读到，都不证明当前 Pro 能读取相同内容。每轮先给简短材料索引、固定提交/原件哈希；对当前会话实际缺少的文件直接附加字节，并要求在自己的工具环境回报读取清单与残余缺口。两仓库均可匿名读取。优先使用组织主库的固定提交链接；当前 Pro 的连接或访问工具确有读取限制时，再提供已核同步的 Vioano 固定链接或直接附件。公开访问不等于连接授权已改变；链接可达与当前 Pro 实际读到文件分开核对。

历史缺件记录（2026-09-23）：第一路缺少旧 ZIP 引用的 295 份历史完整结果；第二路未取得冻结源码/ZIP 字节；第三路未取得题面和源码。当时用户先停第四路，要求补齐前三路二轮、汇总后再续第四路。此为当时的执行顺序，不是要求后续会话继续停在该状态。

后续三路二轮回答见 [已发布研究索引](research/20260923-round2/README.md)；2026-09-24 的后续 Pro 归档与读取范围已在 [固定提交的归档说明](https://github.com/huaweibei123/huaweicup2026/blob/3a4505d4101e23d54580d15560da3820e02d05da/docs/a/research/20260924-pro-archive/README.md) 交付（PR31，待验收）。队长向 ChatGPT 提供同一内容时优先使用公开主库固定提交入口；受连接限制时使用已同步的 Vioano 固定入口。归档、Pro 报告、本机复现和算法验收分开记录；每个新专项 Pro 仍须核实际可读材料。

现有本机/仓库中没有找到的历史完整结果保持 missing，不能从摘要补造。新运行保存新的输入、命令、版本、完整结果与运行身份，不能冒充旧产物。代码集合哈希配方见 `docs/a/source-manifest.json`，可由 `scripts/a_materials.py` 复核。附件 ZIP、PDF 和单个源码的哈希不等于代码集合哈希。
