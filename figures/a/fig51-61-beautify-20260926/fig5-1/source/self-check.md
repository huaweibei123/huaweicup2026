# 图 5-1 自查记录（甲，v5，2026-09-26）

## 实际执行结果（本机制图环境）

- 导出：draw.io CLI（--disable-gpu --no-sandbox）rc=0，SVG viewBox 711×1032、PNG 1422×2064（scale=2）。
- validate.py：0 error；2 处纯线交叉（s1×s2、e12×s1），无文字/标签压盖。
- 页面预览：XeLaTeX rc=0，main.pdf 1 页（pdfinfo Pages=1）；pdftotext 实测图号「图 5.1」、无 U+FFFF；编译日志 0 处 "Float too large"。
- 尺寸与字号（fontSize×W/711×72/25.4）：最小 10px → 6.58pt@165mm、5.66pt@144mm；主标签 11–13px → 7.24–8.55pt@165mm。（v2 的 5.90pt 系 732/711 旧宽混用误算，按审阅公式更正。）

## 二轮剩余项逐条自查（对应 5844497669）

1. R02 残项：score/plan/hyper 三处 module 改为固定 c665 真实符号（guarded_component._score；adaptive_hypergap_guarded 输出/adaptive_guarded.main 写 plan；gap_hyperrefine.refine）。已完成。
2. R03：route 编号大框按 :43–84 顺序（①resource_word ②tree_paired_leaves ③general+波次 ④条件向量修复），①②成功即返回不流经③；恢复 resource_word；br_shared/cores 移除并入③文字。SVG/PNG/nodes/edges/caption 一致。已完成。
3. R04：note53 覆盖构造意外异常（:34–38/50–54/68–72）、字节证据非法（:57–61）、评分异常（:85–100）→ 一律记录 unknown 退回 Π₀；UnsupportedStructure 区别保留。已完成。
4. R05：e13 间距充足不压 select；e13b 短标签「异常」+note53 释义；TeX 数学模式无缺字；图注实际 4 行如实记录。已完成。
5. R06：命令含真实工作目录与改名步骤、模板锁定 e82c2009 完整 commit；字号算术更正（6.58/5.66pt）。已完成。

## 历史稿

v1=3992a4e96；v2=e3e8d3627；v3=b17bb0e48；v4=cc7887a08。均保留于 git 历史。

未完成项：无。

## v4 增补（F51-R06 收尾，5844708118；146mm 结论已被 v5 更正）

- 命令块：audit.command 页面预览段改为 Git Bash 可复制版本（repo_root 自解析、mkdir -p、tar --force-local、无中文混入可执行行），本机实际执行全链退出码 0。
- ~~插入宽 148→146mm……~~（v5 更正：146mm 编译产物当时未落盘到交付目录，交付 PDF 实际仍是 148mm 版面；该警告结论不作实测记录。）

## v5 增补（F51-R06 残项：源文件与实际导出一致性，5845188141；采用方案 B）

- **不一致确认**：v4 tex 声明 146mm，但交付 PDF（705202a2…）主图 bbox 实测宽 148.000mm（审阅方 PyMuPDF 独立测量；本方哈希指纹 705202a2…/cc9ce47e… 与审阅方完全一致）、PNG 与 v3 字节相同——146mm 产物未真正落盘。
- **方案 B 执行**：① page-preview-main.tex 实际 width 改回 148mm（注释同步统一）；交付 PDF/PNG 不变（保留已核验的 148mm 合格页面）。② 说明消除"146mm 后 0 警告"不实测断言，如实记录为"交付页面=148mm 编译版（v3 已通过口径），当前有效宽度=148mm"。③ 字号统一：10px ≈ 5.90pt@148mm、6.58pt@165mm（v4 的 5.83pt@146mm 作废）。
- 一致性终态：当前有效 TeX width（148mm）= 实际 PDF 图像 bbox 换算（148.000mm）= 页面 PNG（v3 已核字节）= 最新说明（本文件与 DELIVERY v5 段）；audit 绑定最终字节（本文件为最后编辑项之一，哈希在全部定稿后统一重算）。
- 图仍为单页、图注完整；未新增最小字号/零警告/新实验门槛（146/148 均可，选定 148）。
