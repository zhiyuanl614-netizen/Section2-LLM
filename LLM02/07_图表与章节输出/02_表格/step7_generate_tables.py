#!/usr/bin/env python3
"""Step 7（表格部分）— 生成第2章配套表格（2026-10-06）。

输出：chapter2_tables_v1.xlsx（3个工作表：D01-D10标签矩阵 / Step5评估指标 / FRDI结果），
以及等价的独立 CSV 文件，便于脚本化引用。
"""
import json
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
VERIFIED_DIR = ROOT / "04_LLM抽取与Critic审查/05_核验通过结果"
METRICS_FP = ROOT / "05_人工金标准与方法评估/02_评估指标/evaluation_metrics_v1.json"
FRDI_FP = ROOT / "06_跨文献综合与FRDI/02_FRDI计算/frdi_results_v1.json"
OUT_DIR = Path(__file__).resolve().parent

DOCS = ["B001-PDF-01", "B001-PDF-02", "B001-PDF-03", "B001-PDF-04", "B001-PDF-05"]
DIMS = [f"D{str(i).zfill(2)}" for i in range(1, 11)]


def autosize(ws):
    for col in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(length + 2, 10), 48)


def sheet_label_matrix(wb):
    ws = wb.active
    ws.title = "表2.1_D01-D10标签矩阵"
    header = ["文献", "维度", "主标签", "次要标签", "置信度", "own_method_vs_cited", "evidence_id数量"]
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    for doc in DOCS:
        recs = json.loads((VERIFIED_DIR / f"{doc}_verified_10d.json").read_text(encoding="utf-8"))
        recs_by_dim = {r["dimension_id"]: r for r in recs}
        for dim in DIMS:
            r = recs_by_dim[dim]
            ws.append([
                doc, dim, r["primary_label"],
                ", ".join(r.get("secondary_labels") or []),
                r["confidence"], r["own_method_vs_cited"],
                len(r.get("evidence_ids") or []),
            ])
    autosize(ws)
    ws.freeze_panes = "A2"
    return ws


def sheet_metrics(wb):
    ws = wb.create_sheet("表2.2_Step5评估指标")
    metrics = json.loads(METRICS_FP.read_text(encoding="utf-8"))
    rows = [
        ("总记录数", metrics["total_records"]),
        ("证据豁免记录数", metrics["exempt_records"]),
        ("证据豁免率", f"{metrics['exempt_rate']:.1%}"),
        ("非豁免记录数", metrics["non_exempt_records"]),
        ("证据充分率", f"{metrics['evidence_sufficiency_rate']:.1%}"),
        ("引用精确匹配率", f"{metrics['quote_exact_match_rate']:.1%}"),
        ("章节/页码可回溯率", f"{metrics['section_page_traceability_rate']:.1%}"),
        ("Agent A/B 初次一致率(pass1→pass2 accept)", f"{metrics['pass1_pass2_initial_agreement_rate']:.1%}"),
        ("pass2修订率", f"{metrics['pass2_revision_rate']:.1%}"),
        ("主标签级修正数/率", f"{metrics['primary_label_correction_count']} / {metrics['primary_label_correction_rate']:.1%}"),
        ("证据/次要标签级修正数/率", f"{metrics['evidence_only_correction_count']} / {metrics['evidence_only_correction_rate']:.1%}"),
        ("pass4终审后未决分歧数", metrics["unresolved_adjudication_count"]),
        ("无支撑断言率", f"{metrics['unsupported_claim_rate']:.1%}"),
    ]
    ws.append(["指标", "结果"])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    for name, val in rows:
        ws.append([name, val])
    ws.append([])
    ws.append(["own_method_vs_cited 分布", json.dumps(metrics["own_method_vs_cited_distribution"], ensure_ascii=False)])
    ws.append([])
    ws.append(["强制披露", "本表指标为流程内部一致性/可回溯性度量，不满足领域专家人工评审要求；详见 05_人工金标准与方法评估/"])
    autosize(ws)
    return ws


def sheet_frdi(wb):
    ws = wb.create_sheet("表2.3_FRDI结果")
    frdi = json.loads(FRDI_FP.read_text(encoding="utf-8"))
    header = ["候选方向", "ESI", "LCI", "TGM(印刷年)", "TGM(DOI年)",
              "FRDI_等权重_印刷年", "FRDI_等权重_DOI年",
              "FRDI_ESI主导_印刷年", "FRDI_ESI主导_DOI年",
              "FRDI_剔除TGM_印刷年", "FRDI_剔除TGM_DOI年"]
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    names = {"3-1": "3-1 第3章 冷却热-水力建模空白", "4-1": "4-1 第4章 cyber快感知空白", "5-1": "5-1 第5章 人口/社会脆弱性空白"}
    for did, label in names.items():
        d = frdi["directions"][did]
        fb = d["FRDI_by_weight_scheme"]
        ws.append([
            label, d["ESI"], d["LCI"], d["TGM_printed_year_basis"], d["TGM_doi_year_basis"],
            fb["primary_equal"]["frdi_printed_year_basis"], fb["primary_equal"]["frdi_doi_year_basis"],
            fb["sensitivity_ESI_dominant"]["frdi_printed_year_basis"], fb["sensitivity_ESI_dominant"]["frdi_doi_year_basis"],
            fb["sensitivity_TGM_excluded"]["frdi_printed_year_basis"], fb["sensitivity_TGM_excluded"]["frdi_doi_year_basis"],
        ])
    ws.append([])
    rs = frdi["robustness_summary"]
    ws.append(["稳健性摘要", f"全部场景最低方向={rs['always_lowest']}；场景总数={rs['n_scenarios']}；4-1排序高于5-1的场景数={rs['n_scenarios_4-1_above_5-1']}/{rs['n_scenarios']}"])
    ws.append([])
    ws.append(["强制披露", "FRDI为本受限5篇语料内的探索性候选方向优先级指数，非已验证、可跨领域比较的前沿指数；详见 frdi_v1.md"])
    autosize(ws)
    return ws


def main():
    wb = openpyxl.Workbook()
    sheet_label_matrix(wb)
    sheet_metrics(wb)
    sheet_frdi(wb)
    out_fp = OUT_DIR / "chapter2_tables_v1.xlsx"
    wb.save(out_fp)
    print("Wrote", out_fp)


if __name__ == "__main__":
    main()
