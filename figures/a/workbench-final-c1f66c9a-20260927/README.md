# 18图总验收最终归档索引

用户总验收 `c1f66c9a24a24c8db817dd1a0fa463cf`，2026-09-26T18:59:22.975411+00:00，备注“可以”。本目录封存当时通过的18图精确字节；不覆盖队长后续论文修订。

| 正文图号 | ZIP内主图 | 图注在ZIP内 | 交付版本 |
|---|---|---|---|
| 图4-1 | `fig-4-1/fig-4-1.svg` | `fig-4-1/assets/77c246c52f6d4bf887f811ba535ceeff.md` | b3b5ed8ec112a0f87baba184937ff7fe9e1dcd6e / farmer v8 |
| 图4-2 | `fig-4-2/fig-4-2.svg` | `fig-4-2/assets/19c81a1d4f4147b5b5d40de5635e73df.md` | 0a710ab1a0fcebe313c3a78d877d9c698cc27ec0 / farmer v9 |
| 图4-3 | `fig-4-3/fig-4-3.svg` | `fig-4-3/assets/3b7c72b3e7f340e2bd05694022a4ada7.md` | bc2a42c277b9d70c51f3fc6974275354df33ee26 / farmer fig4-3 v2 |
| 图4-4 | `fig-4-4/fig-4-4.svg` | `fig-4-4/assets/8c2a74d40972450ca888b73dfff454a9.md` | P1 solver834 / result a1bb445 / paper6b1fdf / local-format-v1 |
| 图4-5 | `fig-4-5/fig-4-5.svg` | `fig-4-5/assets/35489c6eca3d4854a27dc462af3c50f5.md` | P1 solver834 / result a1bb445 / paper6b1fdf / local-format-v1 |
| 图5-1 | `fig-5-1/fig-5-1.svg` | `fig-5-1/assets/189cc33897fc4358a3af8628958b3267.md` | 308039cadfcb7ef77905d08084272c6d80f4660c / farmer v5 |
| 图5-2 | `fig-5-2/fig-5-2.svg` | `fig-5-2/assets/2dec2fd3b9d24926aae2d18b576178c8.md` | 3f929ec106387c096b5b8731c67bbea47bbff31e / farmer v2 |
| 图5-3 | `fig-5-3/fig-5-3.svg` | `fig-5-3/assets/46a0d68c06834a35a8460f3dac20101d.md` | 7d1bf1e4 / captain-rework / workbench schema adapter |
| 图5-4 | `fig-5-4/fig-5-4.svg` | `fig-5-4/assets/20dedaf822d344ba91a72c2fbdf0745e.md` | ad0e5fd9cef1bf63d534a9fe0b4080c02362fa1a + user-authorized local-layout-v1 / audit a37235affe9676a8823fe24ab5ad3e42a365afb3972134f0d3c162b2279bfd73 |
| 图5-5 | `fig-5-5/fig-5-5.svg` | `fig-5-5/assets/cbaf42f92f484e43bbc17c16ae658ce5.md` | 96e819b7 / workbench local-source-v1 / c665 full500 |
| 图5-6 | `fig-5-6/fig-5-6.svg` | `fig-5-6/assets/267a87cfbf484d7eab2d97163c6eb6f9.md` | c49424c1 / workbench local-format-v1 |
| 图6-1 | `fig-6-1/fig-6-1.svg` | `fig-6-1/assets/fe2cc0ed48e947f191d4bfbcc68db03a.md` | 8e7996be6fdb41d93efc8f5d39c67c3d0284e13d / farmer v2 |
| 图6-2 | `fig-6-2/fig-6-2.svg` | `fig-6-2/assets/5567c17e0f764681b788a07404dc6fe4.md` | 2279990c6b6f51ac0d3f13c969684f77b653318c / farmer v4 |
| 图6-3 | `fig-6-3/fig-6-3.svg` | `fig-6-3/assets/d72d788adeb64ac6aa8d5ac0986c4394.md` | forest311322b revision2 / local-complete-v1 / babdd74c pairs |
| 图6-4 | `fig-6-4/fig-6-4.svg` | `fig-6-4/assets/2a02c896bf96487fa10a7c3960aa03dd.md` | babdd74c / forest311322b revision2 / local-format-v1 |
| 图6-5 | `fig-6-5/fig-6-5.svg` | `fig-6-5/assets/85094a0037314180a4fc01e632c81210.md` | 18a0d9ff / workbench local-layout-v1 |
| 图6-6 | `fig-6-6/fig-6-6.svg` | `fig-6-6/assets/34bf9e545af0434aba13c6f02b1fb6ef.md` | 68a81247 / workbench local-layout-v1 |
| 图6-7 | `fig-6-7/fig-6-7.svg` | `fig-6-7/assets/724be51571334736ad76e19d174598d0.md` | 03f445ac / workbench local-format-v1 / forest revision2 full500 |

完整原文件名、路径和SHA256见 MANIFEST.json；固定来源链接与提交/审查/release ID见 FIGURES.json；实际逐条科学、来源、数值、视觉审查及未验证范围见 REVIEWS.json。ZIP各图manifest保持工作台原件。

## 归整边界

- 4-1是用户总验收时原稿，未包含已取消发送的language-v2美化版；队长自行修改4-1，其新稿不能沿用本归档的验收。P1旧流程方法版本与834新结果须在整稿中明确区分。
- 4-4/4-5：solver 834d8c957538ee069c66aadac9509552a4cc69d7；feed a1bb4451cd85c46b32bb928d57c81e22cfeca1a6；正文数据6b1fdf25649b2b5bfc8d267896428187c3469291。500格feed全核与4格原始结果抽核，非新跑500格。
- 4-5线性P95 13.1690867506秒与原整稿最近秩次P95 13.1638878340秒分别保留，不混用；48新E0/452复用，缺外部计时不作零。
- 5-3保留队长7d1bf1e4718596f428696ed4f4b12015003f59ca已通过图件；仅归档，不重复派修或覆盖队长工作。P2图件各自固定版本见来源清单。
- 6-3/6-4使用同一forest311322 revision2同计划500格pairs；共同CSV SHA256 a8be50e8689b9c75fc871224734d693294319645597a5cc21a15efbd69f370f5。两端500对原始result/plan均实核，无新增求解。
- 队长PR232后续流程d9fad5bd051873b4d3b7990f8926018db6d8fdc2、数据d3ed092831e76e2d670ee48ec61aa04422d2a60b语言候选不在本验收中，未在这里重新看图/验收。论文源码、图注及页面整合由队长现有会话处理，不以本包覆盖更新的候选。
- 本包包含绘图源、输入、图注及审计附件，保留作者来源与原始交付说明。历史说明中的旧“候选”字样不改写原件；当前用户确认以overall.json为准。绘图成员无须再次交叉复核。

## 取用与验证

使用Git下载本目录或GitHub git/blobs API取finals.zip；大文件contents接口可能返回空content，不代表文件缺失。先比对SHA256SUMS，再解压；按FIGURES.json选择主图，按manifest的original_name还原脚本相对文件名至独立目录。不要直接执行未审查的上传/安装脚本。
