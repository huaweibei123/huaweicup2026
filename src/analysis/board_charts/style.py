"""全局图表样式：配色、字体、主题。论文级统一观感。"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 三批次主色（论文同图复用）
BATCH_COLORS = {
    "A-farmer-q1-v3": "#2E86AB",       # 蓝
    "B-lyx-p123-multicore": "#A23B72",  # 品红
    "C-official-singlecore": "#4C9F70",  # 绿
}
PROBLEM_COLORS = {"P1": "#2E86AB", "P2": "#A23B72", "P3": "#F18F01"}
NA_COLOR = "#D8D8D8"
MISSING_COLOR = "#F2F2F2"

CMAP_SPEEDUP = "magma"


def setup_style():
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update({
        "axes.unicode_minus": False,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "legend.frameon": False,
        "legend.fontsize": 9,
    })
    return plt
