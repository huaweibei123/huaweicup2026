# 834新版图4-4、4-5已验收Python原稿交接

负责人：@yuanzhifang30-sudo；session=yuanzhifang30-sudo/s-f42fb47d93984f22a151b0a09f678c84；沟通Issue217。

1. **任务目标**：将工作台独立验收通过的834新版Python数字图交给队长，替代同图旧v4候选；不将旧版approval转移给新版。
2. **输入文件**：算法834d8c957538ee069c66aadac9509552a4cc69d7，结果a1bb4451cd85c46b32bb928d57c81e22cfeca1a6，论文6b1fdf25649b2b5bfc8d267896428187c3469291；当前local-format-v1包以两份acceptance.json中的submission/review及逐文件SHA绑定。
3. **输出要求**：原PNG/PDF/SVG、metrics、汇总、来源固定副本、代码、图注、独立审查及交付原文。图4-5(a)标题与图例重叠修复已在此次通过图内，原图字节不再变动。
4. **限制条件**：数字按原文件保存，图4-4注释保留四位小数；图4-5 summary采用线性P95，同时保留论文原最近秩P95，不混写。Makespan是模拟周期，solver wall是完整求解程序墙钟；5～10分钟是效率建议，本次未扩大实验预算。
5. **验收标准**：下文逐项转交工作台原审查。交接方核对当前approved submission及全部48个上传文件SHA，查看原图；未重做500格原始合法性审计、未运行solver/E0/E1/E2或上传代码。
6. **截止时间**：2026-09-27（Asia/Shanghai）本次交接。

## 口径与验证范围

48个工作台原文件逐字节保留；包内.gitattributes禁止换行转换，package-manifest.json覆盖所有交付文件（清单自身除外）。工作台完成500格固定feed/正文对齐，以及001/k1、003/k2、014/k5、067/k1四组原始run/result/plan分层抽核；这是已有证据核验，没有新实验。

4-4逐例共同基线B/M再取算术平均，图中单核锚点为1，实际单核均值1.0020968223600535另列；2～5核均值1.9515526413、2.7513994579、3.4785940989、4.0552669858。分布包含全部离群值，箱线须不是重复测量置信区间。

4-5全体墙钟线性P95=13.1690867506s，最近秩P95=13.1638878340s分别保留；差异来自算法口径，不是源数据错误。新summary由工作台自编normalize_summary.py生成，original-summary.csv保留原口径。本次不执行该脚本。CPU型号未记录，macOS arm64/Python3.12.13、workers=4；在线E1计入求解墙钟；48新E0与452身份复用分开，后者evaluation_wall为空而非0。未清空OS缓存，不称严格冷启动。

本session已读语言标准2026-09-27.1 / 1be28c77b911ef00781e0c23413b68b62823a566。本包是数字图通过版原稿送审；最终图注/正文适用性仍须队长核对。新版数字图通过不使旧P1方法图自动适用834；图4-1语言美化候选仍待用户确认。本次不代表用户全套总验收或论文最终入稿。

以下为工作台验收证据原文：

## fig-4-4

版本：P1 solver834 / result a1bb445 / paper6b1fdf / local-format-v1。submission `b6b1a56382c64ee0852f10d17a19adc7`；review `4a839bb0d63342e6943d29452287280f`。

- **criterion-1**（passed=True）：实际Git blobs取得a1bb445固定feed及QUALITY_SUMMARY、6b1fdf整稿CSV/来源收据，逐字节匹配；500唯一case/core格、每核100、solver834/status ok/graph/plan身份及逐格M全部一致。四个分层样本001/k1、003/k2、014/k5、067/k1原run/result/plan字节SHA匹配且实际周期一致，非全500合法性重跑。2至5核均值1.9515526413/2.7513994579/3.4785940989/4.0552669858与v8相应精度一致。

- **criterion-2**（passed=True）：500行逐例B/M复算；旧分母与工作台旧已验收metrics SHA 5c18283ccae6966493a23603808cf6537f56c76c129e884448d9d52fdc5ab8b0实际字节核对一致，沿用既有基线核验。图中k1=1，实际单核均值1.0020968223600535独立保留；不使用总周期之比。

- **criterion-3**（passed=True）：已静态读完整绘图源和plot-input，2至5核各100个值生成散点/箱线，无删除离群。实际图面保留红色离群点，箱体IQR和1.5IQR须不是重复观测置信区间；灰色y=k仅参考，图注限定模拟周期而非真机/程序墙钟。

- **visual**（passed=True）：已查看实际PNG并从PDF渲染165mm插图预览，标题/数值标注/图例/双面板无重叠裁切，黑白用实/虚线与点区分。本次数字图与v8 solver834对齐；P1旧v4方法图与新版834的整稿适用性仍须单独核，未把18图整稿一致性冒记已由用户终验。

## fig-4-5

版本：P1 solver834 / result a1bb445 / paper6b1fdf / local-format-v1。submission `f821d9c9b2ec443e96a32b2d12dbe45a`；review `6e6ecc5c05e24c1a9bd16b46c844b53a`。

- **criterion-1**（passed=True）：同一a1bb445固定feed完整500格的周期、墙钟、scheduled COPY、额外DDR、spill及外部E0逐项对齐；与6b1fdf正文结果graph/plan身份一致。4组原run/result/plan抽核确认solver.wall_seconds同源、cycle/搬运一致、调用数真实，包含最长25.551509s和新增E0样本。实际fresh child时间包括在线E1；48新E0/452身份复用分开，后者evaluation_wall留空，未把缺失当0。CPU型号未记录。

- **criterion-2**（passed=True）：500行均为macOS arm64 Python3.12.13、批次workers=4、相同计时scope，规范summary按核/平台/worker/scope分组。各100例median/linearP95/max独立复算，与工作台自编normalize_summary.py实跑字节一致；全体P95线性13.1690867506，最近秩次13.1638878340另列解释。散点不连成跨实例Pareto。

- **criterion-3**（passed=True）：已读caption及图底注：箱线代表单次跨用例分布、保留离群，不称重复测量置信区间；OS cache not flushed，不称严格冷启动。scheduled COPY总搬运与added_copy_bytes分别核原result，不把COPY量外推全部物理总线流量。

- **visual**（passed=True）：实际165mm PNG中三个面板、图例和底注清楚，(a)图例与标题已错开；不同核兼有形状区分，DDR两条曲线有实/虚线区分。只在独立副本规范P95图注/summary/audit，图像与500行metrics均未修改；不代表最终整稿语言和18图联合总验收。
