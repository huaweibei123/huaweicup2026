# 全量逐用例结果附录：57页 → 28页

本交付按用户要求整理全篇修改清单，并制作完整、可用于论文附录的表格组件，交队长统一修改整合。主稿和其他会话的格式写区没有改动。

## 交付文件

- `调整清单.md`：用户明确要求、已修附表问题、摘要参考及旧稿减页建议，分清已完成与待最新版复核。
- `case-results-appendix.pdf`：28页、A4纵向、小四宋体（12 PDF pt），按既有Word单倍校准15.6 PDF pt基线。原57页减少29页（50.9%）。
- `appendix-body.tex`：完整引导段和15个longtable，可由唯一格式写者接入主稿。此文件不改变主稿页码或全局字体。
- `case-results-appendix.tex`：独立预览包装文件，使用字体配置、页边距和连续页码。
- `build_appendix.py`：从冻结CSV生成TeX并调用XeLaTeX，至引用和列宽稳定。
- `verify_appendix.py` / `verification.json` / `pdf-extracted-records.csv`：实际PDF全量提取与逐格核对。
- `all-results.csv` / `source-receipt.json` / `summary.json`：原始冻结字节，未改数据。原收据包含实验原件提交与哈希。
- `source-identity.json`：新旧原件身份、数据匹配与验证边界。
- `abstract-05-reference.tex`：v9摘要05参考段落；仅供与新摘要比较，不能整段覆盖更新的正文。

## 为什么减少页数仍保留完整结果

|内容|配置结果数|新排法的版面数据行数|
|---|---:|---:|
|问题一，100用例 × 1—5核|500|250（左右两组）|
|问题二，100用例 × 1—5核|500|250（左右两组）|
|问题三，同方案两配置 × 100用例 × 1—5核|1000|500（横向配对）|
|合计|2000|1000|

问题一、二按每行左→右、再到下一行读取。问题三M₀、D₀表示无L2；M_C、D_C、H_C表示只读Cache；H_C按字节计算。无L2命中率不适用，并非0%。T是该方案求解时间，原有1500项全部保留。计时、舍入与配置说明见PDF首页。没有为压缩篇幅删除用例、指标，或缩小字体、行距、页边距。

## 可重复构建

依赖：Python标准库、XeLaTeX；PDF核验另需PyMuPDF。字体从项目模板现有fonts目录读取，不在此包重复分发字体。自定义路径用命令参数提供，生成的 `font-config.tex` 含本机路径，不能提交或用于跨机交换。XeLaTeX可用PATH或 `--xelatex` 指定。

在仓库根目录执行（输出目录用自己的独立目录）：

```sh
python paper/review-deliveries/20260927-appendix-handoff/build_appendix.py --fonts paper/template-2026/fonts --output /path/to/own/build
```

核验时将同字节 `all-results.csv` 复制到构建目录，再执行：

```sh
python paper/review-deliveries/20260927-appendix-handoff/verify_appendix.py --directory /path/to/own/build --graphs /path/to/official/data
```

`--graphs`可选；传入时对CSV全部1500行核对100份官方输入图的SHA-256。此次Windows实跑通过该检查。构建不调用求解器/评估器、不改变冻结数据。

## 接入主稿

1. 以队长当前固定内容稿为基础，不替换成v9。本包数据已与 `f1e63781adcb6ce7506b5e8297f0213ad57de5bb` 的v13-public CSV逐字节核同。
2. 由当前格式唯一写者在附录A位置引入 `appendix-body.tex`。若主稿已有附录A标题，移除组件第一行section以免重复编号；保留引导说明，或与作者最小文字包合并。
3. 主稿须加载longtable/booktabs/array/caption等既有依赖；表内小四宋体、单倍行距，建议在局部分组设置arraystretch=1、tabcolsep=4bp，保持主稿已校准的15.6bp基线。不要再将已有15.6bp乘一遍行距系数。
4. 组件全部表均有 `tab:full-p1-k1` 等唯一label；表号跟随主稿counter规则。合入后编译至目录、表号和引用稳定，重新核验主稿中的2000配置记录与连续页码。不得简单插入独立PDF而丢失正文连续编号。
5. 用户最新要求减页，本包将2000条配置结果合成1000个版面数据行；如果交接文案仍写“2000表格数据行”，应改成“2000条配置结果”，不能以物理行数误判覆盖。题目要求逐例列结果，没有要求每条配置独占一行。

## 已验证与未验证

最终PDF28页；1000个版面数据行提取出2000条配置结果；6000数值逐一等于冻结CSV的规定显示值；缺失、重复、额外记录、解析失败、数值不符均为0。M/D整数保留，T/H三位小数展示。行基线15.6pt；编译无overfull、缺字、待重编警告。全28页已渲染检查布局；首页、双组表、配置配对表、续页及末页放大检查。详见verification.json及visual-review.md。

本轮0新增solver/E0/E1/E2，不代表对全部原方案进行了独立合法性复评，也不代表论文正文/官方最终提交格式已经整体验收。主PDF实际附录接入由队长统一安排。
