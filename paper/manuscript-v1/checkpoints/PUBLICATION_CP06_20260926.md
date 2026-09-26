# CP06 固定预览发布

本次发布从论文 PR #216 的固定父提交 `e34ded176ae7e84914f53ffa81839a053df2df42` 提取冻结检查点，不读取或提交作者仍在修改的 Markdown 正文。该检查点是 `preview_not_accepted`，供团队审阅与用户批注；不是科学、语言或排版终验。

| 检查点 | PDF SHA-256 | 用途 |
| --- | --- | --- |
| `checkpoint-04-live` | `834e85fffa78423b522c13a2f3698532952ab3ffe711009d57f679e8cb997929` | 用户原始三处列表批注的坐标锚点 |
| `checkpoint-05-lists` | `b0f319a0120280199caf02726ac3933aa20461d692a901b800a065f67f417b7c` | 列表换行检查点，后续三处强调/公式批注的坐标锚点 |
| `checkpoint-06-numbered` | `22e19a17af7d068fe1b4eef18e27f506c18103d61f060f1fc87ba707251e4b55` | 37 页排版预览：按章编号 32 个陈列公式，加粗三个定义术语 |

每个目录保留 `anonymous-paper-v1.pdf`、`main.tex`、`result-tables.tex/pdf`、`figure-manifest.json` 与 `annotation-lock.json`；CP06 另有 `formatting-receipt.json`。这些 TeX 文件是该检查点的实际排版源，后续作者正在修改的分章 Markdown 不是 CP06 的字节来源。CP06 图件清单的 16 项都按 SHA-256 核对；父提交已有 15 项，新增的 `figures/fig-progression-v3.png` SHA-256 为 `d4a75c65f85de8c7b83beecf9b46d05fa3295061e666bad3849c6eed8fbf1d43`。

用户批注事件保存在 `review/checkpoint-04-live/user-annotations.json` 和 `review/checkpoint-05-lists/user-annotations.json`，分别由 CP04、CP05 的 PDF 哈希绑定。发布时只把 CP05 事件里的本机绝对 `pdf_path` 改成等价的仓库相对路径，批注原话、事件 ID、页码和坐标不变；本机原文件 SHA-256 为 `40d126d4afda3c2b6cf661ff37c0ae0bbe8b2694868cd908d3c2d0d3ece82138`，发布副本为 `b1ca63314f79aeacfa8f83ae6568b90859d98ece63ada54aee4f973b94b8062e`。旧 PDF 的坐标不能移用于 CP06。

提取时逐字核对三个 `annotation-lock.json` 的 PDF/TeX 哈希、16 项图件清单哈希，并复读来源文件确认提取期间未变化。`pdfinfo` 显示 CP06 为 A4、37 页。此次发布不包含后续 Gemini 正文修订，也不改变 PR #216 作者分支。
