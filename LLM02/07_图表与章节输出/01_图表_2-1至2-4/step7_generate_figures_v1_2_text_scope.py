#!/usr/bin/env python3
"""Generate versioned v1.2 text-scope pilot figures without replacing legacy PNGs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "04_LLM抽取与Critic审查/06_v1.2文本范围预分类/B001_v1.2_scope_aligned_50record_provisional_ledger.json"
DEFAULT_FRDI = ROOT / "06_跨文献综合与FRDI/02_FRDI计算/frdi_results_v1.2_text_scope_preliminary.json"
ACTIVE_DIMS = ["D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]
UNRESOLVED_BOUNDARIES = {("B001-PDF-03", "D02")}
LABEL_SHORT = {
    "Bidirectional_Coupled": "Bidirectional",
    "Power_to_Water": "Power to water",
    "Water_to_Power": "Water to power",
    "Generic_Water_Network_Only": "Generic water\nnetwork",
    "Mentioned_Only_Not_Modeled": "Mention only",
    "Both_Present": "Both",
    "Explicit_InPlant_Cooling_Model_Described": "In-plant cooling\nmodel",
    "Not_Addressed": "Not addressed",
    "Not_Stated_In_Text": "Not stated",
    "Single_Timescale_Only": "Single timescale",
    "Explicit_MultiTimescale_Model": "Multitimescale\nmodel",
    "Qualitative_Mention_No_Formal_Model": "Qualitative only",
    "Proactive_Anticipatory_Control": "Proactive control",
    "Reactive_Control_Only": "Reactive only",
    "Early_Warning_Alert_Mechanism": "Early warning",
    "Physical_Network_Service_Loss_Only": "Network loss only",
    "Critical_Facility_Impact": "Critical facility",
    "Economic_Cost_Impact": "Economic cost",
    "None_Reported": "None reported",
    "Population_Count_Affected": "Population affected",
    "Critical_Facility_Service_Disruption": "Facility disruption",
    "Social_Vulnerability_Index_Used": "Social vulnerability",
    "Named_Case_Region_Impact": "Named region impact",
    "Synthetic_Test_System_Only": "Synthetic test",
    "Hybrid_Synthetic_Calibrated_To_Real_Data": "Hybrid, real-data\ncalibrated",
    "Real_World_Named_Region": "Real region",
    "Validation_Generalizability_Limitation": "Validation/generalizability",
    "Future_Work_Direction": "Future work",
    "Model_Simplification_Limitation": "Model simplification",
    "Missing_Factor_Limitation": "Missing factor",
}
_CJK_FONT_CANDIDATES = [
    os.environ.get("CJK_FONT_PATH", ""),
    str(ROOT / "fonts" / "NotoSansCJK-Regular.ttc"),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_CJK_FONT_PATH = next((p for p in _CJK_FONT_CANDIDATES if p and Path(p).is_file()), None)
if _CJK_FONT_PATH:
    fm.fontManager.addfont(_CJK_FONT_PATH)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_CJK_FONT_PATH).get_name()
plt.rcParams["axes.unicode_minus"] = False


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def label_matrix(ledger: dict, output: Path) -> None:
    records = {(r.get("doc_id"), r.get("dimension_id")): r for r in ledger.get("records", [])}
    doc_ids = ledger.get("document_ids") or sorted({d for d, _ in records if d})
    cell_text = []
    cell_colors = []
    for doc_id in doc_ids:
        texts, colors = [], []
        for dim in ACTIVE_DIMS:
            record = records.get((doc_id, dim))
            if record is None:
                raise ValueError(f"Missing record for {doc_id}/{dim}")
            label = str(record.get("primary_label", "<missing>"))
            label = LABEL_SHORT.get(label, label.replace("_", " "))
            unresolved = record.get("verification_status") == "adjudication_required" or (doc_id, dim) in UNRESOLVED_BOUNDARIES
            if (doc_id, dim) in UNRESOLVED_BOUNDARIES:
                label = f"未裁定\n{label}"
            texts.append(label)
            if unresolved:
                colors.append("#F4C27A")
            elif record.get("record_origin") == "v1.0_verified_record_carried_forward_unchanged":
                colors.append("#DCE6F1")
            else:
                colors.append("#D9EAD3")
        cell_text.append(texts)
        cell_colors.append(colors)

    fig, ax = plt.subplots(figsize=(19, 8.5))
    ax.axis("off")
    table = ax.table(cellText=cell_text, rowLabels=doc_ids, colLabels=ACTIVE_DIMS,
                     cellColours=cell_colors, loc="center", cellLoc="center", rowLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 4.2)
    ax.set_title("v1.2 文本范围：5篇先导语料的9个分析维度\n橙色=需人工裁定；蓝色=沿用v1.0；绿色=v1.2候选记录。D03范围状态不在图中。", pad=18)
    fig.text(0.01, 0.015, "先导样本描述，不是领域总体比例；标签缺失不证明领域不存在。", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def frdi_sensitivity(frdi: dict, output: Path) -> None:
    scenarios = frdi.get("sensitivity_scenarios") or []
    if not scenarios:
        raise ValueError("v1.2 FRDI input lacks sensitivity_scenarios")
    direction_ids = ["3-1", "4-1", "5-1"]
    data = [[s["scores"][d] for s in scenarios] for d in direction_ids]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    boxes = ax.boxplot(data, tick_labels=direction_ids, patch_artist=True, showmeans=True)
    for patch, color in zip(boxes["boxes"], ["#6BAED6", "#74C476", "#FD8D3C"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    ax.set_ylabel("FRDI（探索性情景值）")
    ax.set_title("v1.2 FRDI：24种假设组合下的样本内分数范围\n不代表统计置信区间、显著差异或方向确认")
    ax.grid(axis="y", linestyle=":", alpha=0.45)
    fig.text(0.01, 0.015, "情景包含PDF-03/D02备选评分、PDF-05 LCI、年份基准和权重变化；D02仍未裁定。", fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--metrics", type=Path, required=True, help="v1.2.1 Step 5 output; used for scope validation")
    parser.add_argument("--frdi", type=Path, default=DEFAULT_FRDI)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing directory is refused")
    args = parser.parse_args()
    ledger_path = args.ledger.expanduser().resolve()
    metrics_path = args.metrics.expanduser().resolve()
    frdi_path = args.frdi.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    for path in (ledger_path, metrics_path, frdi_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    metrics = load(metrics_path)
    if metrics.get("D03_included_in_findings_or_metrics") is not False or set(metrics.get("primary_label_counts", {})) != set(ACTIVE_DIMS):
        raise ValueError("The supplied Step 5 metrics must exclude D03 and contain exactly nine active dimensions")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    label_matrix(load(ledger_path), output_dir / "figure_2_1_label_matrix_v1.2_text_scope.png")
    frdi_sensitivity(load(frdi_path), output_dir / "figure_2_3_frdi_sensitivity_v1.2_text_scope.png")
    print(f"Wrote v1.2 text-scope figures to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
