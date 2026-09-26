# 图4-2 A版：用户确认后交队长审核

用户确认原话：“就用A这一版比较好”。确认对象为三版比较页的 variant-A.png；送审文件改名为 fig4-2-A-confirmed.png，图片字节不变。
SHA-256：`76b1b13c073f404dc7c51e60f7ceecbcd51aaeb5cc9fdc3ea775614061592b3f`。
当前状态：用户已确认，提交队长独立审核；未合入论文。原图的Agent验收不自动覆盖美化稿。

## 六字段任务卡
1. **任务目标**：以farmer已验收图4-2为结构基准美化，保留节点、依赖、阶段和计算任务分配，按队长绘图及语言规则送审。
2. **输入文件**：farmer v9固定提交 `0a710ab1a0fcebe313c3a78d877d9c698cc27ec0` 的 `figures/a/jia-fig4-2-20260926/`。nodes.csv含id/stage/subgraph/core/order/note，edges.csv含source/target；结构示例无统计样本量、缺失样本或实测时间。原稿依据 `67c0f603960fddf86416d23ca3e85e53561c3c3a` 第4.4.2节。
3. **输出要求**：确认PNG、原始可编辑Draw.io、节点/边表、图注与邻近说明、语言映射、单页论文预览及tex、提示词、哈希和检查脚本。所有文件在本目录。
4. **限制条件**：不修改算法、数据或原图件工作台；不运行solver/E0/E1/E2/Pro/Actions。不将生成PNG冒称为可编辑矢量。用户确认图片冻结，后续图像返修另版。
5. **验收标准**：下表复用原图三条科学标准，并列论文页面、语言、格式与溯源检查；作者自查、用户选择、队长审核和入稿分别记录。
6. **截止时间**：用户未另定日期；本轮即时送审，日期2026-09-26（Asia/Shanghai）。

## 与队友同口径的逐项清单
|编号|标准|本轮证据及边界|
|---|---|---|
|F42-T01|全部示例节点在划分中恰好覆盖一次，依赖关系无遗漏或反向|两个DAG各12节点、13有向边；生图逐边目视回读，CSV自动核覆盖和无环；节点集合不变|
|F42-T02|各核心Task顺序与依赖相容，颜色与外框含义明确|Core0 Task0→1；Core1 Task2→4；Core2 Task3。合并六条Task依赖后无环。CSV core=1/2/3对应图Core0/1/2；五任务覆盖12节点一次|
|F42-T03|明确结构示例、条块宽度无时间含义，不声称实测加速或零spill|图注保留结构/时间边界；没有性能数字。灰色s/a、青绿三链、琥珀r/t，阶段括号、Core横框及线型由邻近说明逐一解释|
|F42-V01|节点、箭头、分组和文字清楚|实际查看透明PNG及浏览器白底；两DAG和任务图回读。A版阶段采用括号，端点靠近末节点中心高度，是否需外扩由审核者判断|
|F42-V02|论文单页、图号正确、插图和图注不裁切|使用固定5313ff6a的gmcm2026.cls，165mm宽，图高110mm；本轮编译page-preview.tex，并独立渲染查看。不是复用原v9页面证明|
|F42-L01|按当前学术语言规则，说明对象及条件|标准.6，固定5313ff6ab3241bb81465b3b761e97ab12700d8fe；见LANGUAGE_REVIEW.md。未代签L01–L13全部独立通过|
|F42-D01|实际原生尺寸、格式、哈希|1536×1024 RGBA；1,443,148 bytes；alpha 0–254，全透明786475像素；165mm宽约236.45ppi，不称300dpi|
|F42-D02|保留可编辑结构源与绘图输入|source中的Draw.io及CSV来自原固定提交，逐字节校验；美化PNG由生图生成，未制作与其相同的可编辑矢量|
|F42-D03|输入、提示词、结果可追溯|生成A及局部修订A2提示词保留；新图与原图的版面变化、图文分工见下文；manifest登记全部文件|

## 来源与风格
- 原交付：[farmer v9](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5843978353)；[Agent通过回执](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5844295355)。
- 风格固定 `6de5103496a40a6067ff837dcabd9e797118ef35` 的FANG_FIGURE_HANDOFF.md、FIGURE_PRODUCTION_PROTOCOL.md，以及实际查看并输入生图的fig-hypercut-v2.png、fig-progression-v2.png。
- 整体从竖排改为“上方两个DAG、下方Core分配”。保留柔和浅色、细线、统一节点、简单曲线及Draw.io式分组，用户选择A。图号、图名和长解释由LaTeX/正文承载。
- 生成3候选、2次局部修正，总5次调用；最终A由prompt-A和prompt-A2生成。本轮用户确认后零次生图。
- 未选B/C保存在本机比较记录，不作为送审候选，避免队长误用。
- 最新标准/协议已实际读取：5313ff6a的LANGUAGE_STANDARD.md(.6)、COLLABORATION_PROTOCOL.md(.3)、ANNOTATION_CONTRACT.md，以及新增USER-CP02-08至17事件和相关类别。已读Issue217评论5844653299、5844673668。仅为本session签收，不代工作台或其他会话。

## 实际验证与复现
- `python figures/a/fig42-beautify-20260926/verify_artifacts.py`：检查用户确认哈希、原源文件哈希、节点覆盖、边集合、任务依赖和无环、图片尺寸及alpha、具体目录元数据。
- 页面：在临时构建目录取固定5313ff6a的paper/template-2026/gmcm2026.cls及fonts，将本目录PNG和tex复制到该目录，运行 `xelatex -interaction=nonstopmode -halt-on-error page-preview.tex`；用 `pdftoppm -singlefile -r 120 -png page-preview.pdf page-preview` 独立渲染。
- Windows本机运行；不将源表检查称为自动验证生成PNG拓扑（后者为逐边目视检查）。
- 本机无dot_clean；对本次具体交付目录只读扫描Apple元数据，不声称执行macOS清理。
- 原v9的SVG、完整audit和历次页面可从固定来源取得，不覆盖、不将原v9预览作为新PNG纸面证据。

## 未验证及队长下一步
1. 请论文监督/审核任务审查图片及caption.md，并安排正文写作者衔接。图对应原稿第4.4.2节的构造示例，不自动适用于后续主算法全部步骤或新成绩。
2. 单页模板预览不是在最终整稿中的实际插入；最终段落位置、前置定义和字号可读性仍须整稿回读。生成字形未认证为指定字体或精确字号。
3. caption.md的第一段为短图注，其后为本图的邻近解释；执行的是子图对应的计算任务。一般阶段/链分组判据仍须引用正文准确算法，不用本例取代一般定义。
4. 用户选定图片保持原字节；若提出影响图片的返修，另生成版本并重新交用户确认。
