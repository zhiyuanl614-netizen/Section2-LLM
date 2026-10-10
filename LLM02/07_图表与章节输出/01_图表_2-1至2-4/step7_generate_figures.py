#!/usr/bin/env python3
"""Step 7（图表部分）— 生成图2.1-2.4（2026-10-06）。

输入：
  - 04_LLM抽取与Critic审查/05_核验通过结果/*_verified_10d.json （50条已核验记录）
  - 06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.json （研究范式簇、候选方向）
  - 06_跨文献综合与FRDI/02_FRDI计算/frdi_results_v1.json （FRDI计算结果）
  - 02_PDF清洗与分块/01_Zones/step1_sliced_pdf_corpus.json （出版年份）

输出：figure_2_1_label_matrix.png ... figure_2_4_timeline.png（本目录）

**强制声明：** 本图表只可视化已核验/已计算的结果，不引入任何新的语义判断；
所有图表必须与 05/06 阶段的书面报告（尤其是强制披露与稳健性分析）一并引用，
不得脱离文字说明单独使用，以免被误读为已验证的跨领域结论。
"""
import os
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

matplotlib.use("Agg")

# --- Portable CJK font resolution ------------------------------------------------
# The original authoring sandbox had Noto Sans CJK preinstalled at a fixed Linux
# path. Offline/end-user machines (Windows/macOS/other Linux) will not have that
# exact path, so we: (1) honor an explicit override via CJK_FONT_PATH env var,
# (2) fall back to the copy bundled with this package under ../../fonts/, and
# (3) fall back further to common per-OS system font locations.
ROOT = Path(__file__).resolve().parents[2]  # package root (mirrors Section2-LLM/)
_CJK_FONT_CANDIDATES = [
    os.environ.get("CJK_FONT_PATH", ""),
    str(ROOT / "fonts" / "NotoSansCJK-Regular.ttc"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # common Linux (original sandbox)
    "C:/Windows/Fonts/msyh.ttc",       # Windows: Microsoft YaHei
    "C:/Windows/Fonts/simsun.ttc",     # Windows: SimSun
    "/System/Library/Fonts/PingFang.ttc",  # macOS: PingFang SC
    "/System/Library/Fonts/STHeiti Light.ttc",  # macOS fallback
]
CJK_FONT_PATH = next((p for p in _CJK_FONT_CANDIDATES if p and Path(p).exists()), None)
if CJK_FONT_PATH is None:
    raise SystemExit(
        "No CJK-capable font found. Set the CJK_FONT_PATH environment variable to "
        "point at a .ttf/.ttc/.otf font that covers Chinese characters (e.g. Noto "
        "Sans CJK, Microsoft YaHei, PingFang SC), or restore fonts/NotoSansCJK-Regular.ttc "
        "which ships with this offline package."
    )
fm.fontManager.addfont(CJK_FONT_PATH)
plt.rcParams["font.family"] = fm.FontProperties(fname=CJK_FONT_PATH).get_name()
plt.rcParams["axes.unicode_minus"] = False

VERIFIED_DIR = ROOT / "04_LLM抽取与Critic审查/05_核验通过结果"
SYNTHESIS_FP = ROOT / "06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.json"
FRDI_FP = ROOT / "06_跨文献综合与FRDI/02_FRDI计算/frdi_results_v1.json"
STEP1_FP = ROOT / "02_PDF清洗与分块/01_Zones/step1_sliced_pdf_corpus.json"
OUT_DIR = Path(__file__).resolve().parent

DOCS = ["B001-PDF-01", "B001-PDF-02", "B001-PDF-03", "B001-PDF-04", "B001-PDF-05"]
DOC_SHORT = {d: d.replace("B001-PDF-", "PDF-") for d in DOCS}
DIMS = [f"D{str(i).zfill(2)}" for i in range(1, 11)]

EXEMPT_LABELS = {"Not_Addressed", "None_Reported", "Not_Stated_In_Text", "Explicitly_Not_Considered",
                  "Insufficient_Evidence", "Evidence_Unavailable"}


def load_records():
    all_recs = {}
    for doc in DOCS:
        recs = json.loads((VERIFIED_DIR / f"{doc}_verified_10d.json").read_text(encoding="utf-8"))
        for r in recs:
            all_recs[(doc, r["dimension_id"])] = r
    return all_recs


def figure_2_1(records):
    """图2.1：D01-D10 标签覆盖矩阵（豁免 vs 非豁免 + confidence 作为色深）。"""
    fig, ax = plt.subplots(figsize=(11, 5.5))
    mat = np.zeros((len(DOCS), len(DIMS)))
    annot = np.empty((len(DOCS), len(DIMS)), dtype=object)
    for i, doc in enumerate(DOCS):
        for j, dim in enumerate(DIMS):
            r = records[(doc, dim)]
            exempt = r["primary_label"] in EXEMPT_LABELS
            mat[i, j] = (0.3 if exempt else 1.0) * r["confidence"]
            label_short = r["primary_label"].replace("_", "\n")
            annot[i, j] = label_short

    im = ax.imshow(mat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(DIMS)))
    ax.set_xticklabels(DIMS)
    ax.set_yticks(range(len(DOCS)))
    ax.set_yticklabels([DOC_SHORT[d] for d in DOCS])
    for i in range(len(DOCS)):
        for j in range(len(DIMS)):
            ax.text(j, i, annot[i, j], ha="center", va="center", fontsize=5.3,
                     color="black" if mat[i, j] < 0.6 else "white")
    ax.set_title("图2.1　五篇文献 D01–D10 标签覆盖矩阵\n（色深=置信度×[非豁免1.0/豁免0.3]；豁免=Not_Addressed/None_Reported等）", fontsize=11)
    fig.colorbar(im, ax=ax, label="置信度加权强度（豁免标签已降权显示，非实际置信度差异）", fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure_2_1_label_matrix.png", dpi=160)
    plt.close(fig)


def figure_2_2(synthesis):
    """图2.2：研究范式簇示意图（N=5下的方法论家族归类，非统计聚类）。"""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    ax.set_title("图2.2　研究范式簇示意图（N=5语料内的方法论家族归类，非统计聚类算法产出）", fontsize=11)

    colors = {"A": "#a6cee3", "B": "#fdbf6f", "C": "#b2df8a"}
    boxes = {
        "A": {"xy": (0.03, 0.15), "w": 0.28, "h": 0.6, "title": "簇A：纯经济调度范式\n（无扰动/韧性框架）",
              "docs": ["PDF-01", "PDF-02"], "note": "D01=Bidirectional_Coupled\nD07=Not_Stated_In_Text"},
        "B": {"xy": (0.36, 0.15), "w": 0.28, "h": 0.6, "title": "簇B：拓扑图论韧性范式\n（单篇个案，非统计簇）",
              "docs": ["PDF-03"], "note": "D03=受控词表缺口\n(No_Explicit_Equation)"},
        "C": {"xy": (0.69, 0.15), "w": 0.28, "h": 0.6, "title": "簇C：运行韧性指标/\n级联失效范式",
              "docs": ["PDF-04", "PDF-05"], "note": "D07=Critical_Facility_Impact\nD09横跨Hybrid→Real_World"},
    }
    for cid, b in boxes.items():
        rect = plt.Rectangle(b["xy"], b["w"], b["h"], facecolor=colors[cid], edgecolor="black", alpha=0.85)
        ax.add_patch(rect)
        cx = b["xy"][0] + b["w"] / 2
        ax.text(cx, b["xy"][1] + b["h"] - 0.08, b["title"], ha="center", va="top", fontsize=9.5, fontweight="bold")
        ax.text(cx, b["xy"][1] + b["h"] / 2 + 0.03, "、".join(b["docs"]), ha="center", va="center", fontsize=10)
        ax.text(cx, b["xy"][1] + 0.08, b["note"], ha="center", va="bottom", fontsize=7.5, color="#333333")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure_2_2_paradigm_clusters.png", dpi=160)
    plt.close(fig)


def figure_2_3(frdi):
    """图2.3：FRDI跨6场景稳健性柱状图。"""
    direction_ids = ["3-1", "4-1", "5-1"]
    direction_names = {
        "3-1": "3-1 第3章\n冷却热-水力建模空白",
        "4-1": "4-1 第4章\ncyber快感知空白",
        "5-1": "5-1 第5章\n人口/社会脆弱性空白",
    }
    scenarios = []
    for scheme in ["primary_equal", "sensitivity_ESI_dominant", "sensitivity_TGM_excluded"]:
        for yb in ["frdi_printed_year_basis", "frdi_doi_year_basis"]:
            label = f"{scheme}\n({'印刷年' if 'printed' in yb else 'DOI年'})"
            scenarios.append((scheme, yb, label))

    fig, ax = plt.subplots(figsize=(12, 5.5))
    n_dir = len(direction_ids)
    n_scen = len(scenarios)
    width = 0.12
    x = np.arange(n_scen)
    for k, did in enumerate(direction_ids):
        vals = [frdi["directions"][did]["FRDI_by_weight_scheme"][sc][yb] for sc, yb, _ in scenarios]
        ax.bar(x + (k - 1) * width, vals, width=width, label=direction_names[did])
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, _, lab in scenarios], fontsize=8)
    ax.set_ylabel("FRDI（探索性指数，非验证指标）")
    ax.set_title("图2.3　候选方向FRDI跨6种权重/年份假设场景的稳健性比较\n（3-1在全部场景均最低；4-1与5-1排序对假设敏感，见frdi_v1.md第4节）", fontsize=10.5)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure_2_3_frdi_robustness.png", dpi=160)
    plt.close(fig)


def figure_2_4(pub_years, achievement_scores):
    """图2.4：候选方向"成就等级"随出版年份的分布（印刷卷期年），
    直观展示D04(4-1)在全部5篇均为0的情形，以及3-1/5-1仅各有1-2个非零点。
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    direction_ids = ["3-1", "4-1", "5-1"]
    markers = {"3-1": "o", "4-1": "s", "5-1": "^"}
    jitter = {"3-1": -0.12, "4-1": 0.0, "5-1": 0.12}
    for did in direction_ids:
        years = [pub_years[d] for d in DOCS]
        scores = [achievement_scores[did][d] for d in DOCS]
        jittered_years = [y + jitter[did] for y in years]
        ax.scatter(jittered_years, scores, label=f"方向{did}", marker=markers[did], s=90)
    # stagger labels that share the same pub_year so they don't overlap
    from collections import defaultdict
    year_groups = defaultdict(list)
    for d in DOCS:
        year_groups[pub_years[d]].append(d)
    for year, ds in year_groups.items():
        for k, d in enumerate(sorted(ds)):
            offset = (k - (len(ds) - 1) / 2) * 0.55
            ax.annotate(DOC_SHORT[d], (year + offset, -0.25), fontsize=7, ha="center", rotation=0, color="gray")
    ax.set_xlabel("印刷卷期年份（B001-PDF-05=2027为期刊提前分配的未来卷期号，见frdi_v1.md 1.2节说明）")
    ax.set_ylabel("成就等级（0=未涉及，1=部分进展，2=完整实现[本语料未出现]）")
    ax.set_yticks([0, 1, 2])
    ax.set_ylim(-0.5, 2.5)
    ax.set_title("图2.4　候选方向成就等级 vs 出版年份（TGM计算的可视化依据）\n方向4-1在全部5篇均为0，是本语料中唯一无法计算时间动量趋势的方向", fontsize=10.5)
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure_2_4_achievement_timeline.png", dpi=160)
    plt.close(fig)


def main():
    records = load_records()
    synthesis = json.loads(SYNTHESIS_FP.read_text(encoding="utf-8"))
    frdi = json.loads(FRDI_FP.read_text(encoding="utf-8"))
    step1 = json.loads(STEP1_FP.read_text(encoding="utf-8"))
    pub_years = {d["doc_id"]: d["pub_year"] for d in step1}
    achievement_scores = {did: frdi["directions"][did]["ESI_achievement_scores"] for did in ["3-1", "4-1", "5-1"]}

    figure_2_1(records)
    figure_2_2(synthesis)
    figure_2_3(frdi)
    figure_2_4(pub_years, achievement_scores)
    print("Wrote figure_2_1 .. figure_2_4 to", OUT_DIR)


if __name__ == "__main__":
    main()
