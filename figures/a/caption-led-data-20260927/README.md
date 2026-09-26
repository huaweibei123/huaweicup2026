# Fang 数据图：图内短标签与图注分工候选

从 Fang 固定提交 `f469278f76bb61050a57e4777333e035cc2522b2`（图5-5、5-6、6-6、6-7）和 `763760f7f2c8deeadd94a8e8d9456fdf5096e0d8`（图6-3、6-4）只读提取已验收工作台数据文件。`input-manifest.json` 对每份 CSV 记录固定路径和 SHA-256；两个绘图脚本运行前复核输入哈希。此处不运行求解器、官方评价器、队友数据准备或远端提取脚本。

`render_data.py` 绘制图5-5、5-6、6-3、6-4、6-7的短标签版。`render_timeline.py` 从同一份已核对的图6-6事件表导出完整与局部两张图，并用源字段 `source_core_id` 检查并呈现 Core 0–2。`output/` 中七个英文稳定文件名保留矢量 PDF 和按160 mm宽生成的纸面预览；`delivery.json` 记录全部文件的大小与 SHA-256。所有源图仍留在 Fang 固定提交，不在本包改写。长标题、说明、五核表、统计口径、事件解释和局限的去向见 `caption-transfer.md`，不可从论文完全删除。

复现：

```sh
python figures/a/caption-led-data-20260927/render_data.py
python figures/a/caption-led-data-20260927/render_timeline.py
```

在项目已安装的 Python 绘图环境中运行；仅需 Matplotlib、NumPy。本轮实际使用项目现有虚拟环境，没有安装新依赖。正式论文由监督会话按自己的 LaTeX 工程复制七份 PDF 并写图注；它负责核对实际章节、图号、图注、页面及固定 PDF 哈希。此交付是图面候选，不代表其已入稿或通过用户最终验收。
