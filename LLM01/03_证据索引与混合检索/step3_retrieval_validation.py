#!/usr/bin/env python3
"""Step 3 retrieval validation: sanity-check the hybrid (dense+BM25+RRF) index
against D01-D10 / RQ1-4 style queries before trusting it for Step 4.

IMPORTANT METHODOLOGY CAVEAT (must be repeated in any report using this
script's output): the "reference_ids" below are NOT a double-annotated,
independent human gold-evidence set. They were hand-identified by the same
agent building the pipeline, via targeted keyword search + manual reading of
candidate blocks. This is an *engineering sanity check* (does the index even
retrieve plausible evidence for each construct, and do we find corpus
coverage gaps worth flagging before Step 4), not a confirmatory IR evaluation
and not a substitute for the Step 5 gold-standard audit.
"""
from __future__ import annotations

import json
from pathlib import Path

from step3_hybrid_retrieval import HybridIndex, FUSED_TOP_K

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "03_检索运行清单" / "retrieval_validation_report.md"
OUT_JSON = ROOT / "03_检索运行清单" / "retrieval_validation_results.json"

# Each entry: dimension id, RQ, natural-language query text (as Step 4's
# dimension-retrieval-pass would issue), and a hand-identified reference set
# of evidence_ids that clearly instantiate the construct (see caveat above).
TEST_QUERIES = [
    {
        "dimension": "D01", "rq": "RQ1",
        "query": "coupling direction between power grid and water supply system, bidirectional or one-way dependency",
        "reference_ids": ["B001-PDF-01-ZB-S05-2-1-C001", "B001-PDF-02-ZB-S04-II-C001",
                           "B001-PDF-03-ZB-S04-2-2-C001", "B001-PDF-01-ZA-ABSTRACT-C001"],
        "note": "Corpus has strong, explicit coupling-direction content (water-electric nexus is the core topic of 4/5 papers).",
    },
    {
        "dimension": "D02", "rq": "RQ1",
        "query": "power plant cooling water thermal hydraulic model condenser versus generic water distribution network",
        "reference_ids": ["B001-PDF-01-ZB-S05-2-1-C001", "B001-PDF-02-ZB-S04-II-C001"],
        "note": "No paper in this 5-paper corpus models in-plant power-plant cooling water explicitly; reference set "
                "intentionally points to the best generic-water-network evidence to check the index can still "
                "surface discriminating context for a Generic_Water_Network_Only verdict.",
    },
    {
        "dimension": "D03", "rq": "RQ1",
        "query": "hydraulic pressure flow equation pump curve linking water network variables to power system variables",
        "reference_ids": ["B001-PDF-02-ZB-S05-A-C003", "B001-PDF-02-ZB-S07-A-C002", "B001-PDF-01-ZB-S05-2-1-C002"],
        "note": None,
    },
    {
        "dimension": "D04", "rq": "RQ2",
        "query": "fast cyber information sensing real-time monitoring communication layer for power or water system state",
        "reference_ids": ["B001-PDF-04-ZB-S04-II-C004", "B001-PDF-04-ZB-S04-II-C001"],
        "note": "Weak corpus coverage expected: only PDF-04 ('Cyber-Enabled...') has tangential content "
                "(co-simulation topology update), not an explicit fast-sensing/communication architecture.",
    },
    {
        "dimension": "D05", "rq": "RQ2",
        "query": "two-stage day-ahead real-time dispatch multiple time scales fast and slow dynamics",
        "reference_ids": ["B001-PDF-01-ZB-S06-2-2-C001", "B001-PDF-01-ZB-S06-2-2-C002", "B001-PDF-01-ZA-S03-1-2-C002"],
        "note": None,
    },
    {
        "dimension": "D06", "rq": "RQ2",
        "query": "early warning proactive anticipatory control rolling horizon predictive scheduling versus reactive control",
        "reference_ids": ["B001-PDF-01-ZB-S06-2-2-C001", "B001-PDF-03-ZB-S09-3-2-1-C001"],
        "note": None,
    },
    {
        "dimension": "D07", "rq": "RQ3",
        "query": "cascading failure propagation across infrastructure layers beyond physical network service loss",
        "reference_ids": ["B001-PDF-03-ZB-S04-2-2-C006", "B001-PDF-05-ZC-S15-3-4-C003", "B001-PDF-05-ZA-ABSTRACT-C001"],
        "note": None,
    },
    {
        "dimension": "D08", "rq": "RQ3",
        "query": "population affected social vulnerability critical facility human impact of infrastructure failure",
        "reference_ids": ["B001-PDF-05-ZD-S11-3-C001", "B001-PDF-05-ZC-S12-3-1-C002", "B001-PDF-04-ZC-S13-H-C002"],
        "note": "Corpus has a named-region case (Shelby County) but no explicit population-count / social-vulnerability-"
                "index metric found by keyword search; recall of the named-region evidence is the realistic bar here.",
    },
    {
        "dimension": "D09", "rq": "RQ3",
        "query": "case study validation system IEEE test feeder or real named city region such as Shelby County",
        "reference_ids": ["B001-PDF-04-ZD-S47-A-C001", "B001-PDF-05-ZD-S11-3-C001", "B001-PDF-05-ZC-S14-3-3-C002"],
        "note": None,
    },
    {
        "dimension": "D10", "rq": "RQ4",
        "query": "author acknowledged limitations model simplification scalability data availability future research directions",
        "reference_ids": ["B001-PDF-04-ZD-S52-X-C002", "B001-PDF-03-ZD-S31-7-C003", "B001-PDF-02-ZD-S15-VI-C002"],
        "note": None,
    },
]


def main() -> None:
    idx = HybridIndex()
    results = []
    for item in TEST_QUERIES:
        hybrid = idx.hybrid_search(item["query"])
        fused_ids = [eid for eid, _ in hybrid["fused_top"]]
        bm25_ids = {eid for eid, _ in hybrid["bm25_top"]}
        dense_ids = {eid for eid, _ in hybrid["dense_top"]}

        ref = item["reference_ids"]
        found_fused = [r for r in ref if r in fused_ids]
        found_bm25 = [r for r in ref if r in bm25_ids]
        found_dense = [r for r in ref if r in dense_ids]
        found_any_leg = [r for r in ref if r in bm25_ids or r in dense_ids]

        docs_in_top10 = sorted({idx.by_id[eid]["doc_id"] for eid in fused_ids if eid in idx.by_id})

        results.append({
            "dimension": item["dimension"],
            "rq": item["rq"],
            "query": item["query"],
            "note": item["note"],
            "reference_ids": ref,
            "fused_top10": fused_ids,
            "recall_fused_top10": round(len(found_fused) / len(ref), 2),
            "recall_any_leg_top20": round(len(found_any_leg) / len(ref), 2),
            "found_in_fused": found_fused,
            "found_in_bm25_only": [r for r in found_bm25 if r not in found_fused and r in found_any_leg],
            "found_in_dense_only": [r for r in found_dense if r not in found_fused and r in found_any_leg],
            "missed_entirely": [r for r in ref if r not in found_any_leg],
            "distinct_docs_in_fused_top10": docs_in_top10,
        })

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    write_report(results)
    print(f"Validation complete. Report: {OUT_PATH}")


def write_report(results: list[dict]) -> None:
    lines = [
        "# Step 3 检索覆盖/召回验证报告（工程抽查，非正式金标准评估）",
        "",
        "**重要方法论声明：** 下表的 `reference_ids`（参考相关证据）由本Agent通过关键词检索+人工阅读候选块手动识别，",
        "**不是独立的人工双标注金标准**。本报告的目的是在信任该索引用于 Step 4 之前，做一次工程级的健全性检查",
        "（索引是否至少能找回明显相关的证据、是否存在系统性覆盖空白），不构成正式的检索效果confirmatory评估，",
        "也不能替代 Step 5 的金标准审核。",
        "",
        f"**融合参数：** RRF k=60，每路Top-20，融合后Top-{FUSED_TOP_K}。",
        "",
        "| 维度 | RQ | recall@fused-top10 | recall@either-leg-top20 | 命中/参考数 | 遗漏 | 说明 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for r in results:
        missed = ", ".join(r["missed_entirely"]) if r["missed_entirely"] else "无"
        note = r["note"] or ""
        lines.append(
            f"| {r['dimension']} | {r['rq']} | {r['recall_fused_top10']} | {r['recall_any_leg_top20']} | "
            f"{len(r['found_in_fused'])+len(r['found_in_bm25_only'])+len(r['found_in_dense_only'])}/{len(r['reference_ids'])} "
            f"| {missed} | {note} |"
        )

    lines += ["", "## 逐维度细节", ""]
    for r in results:
        lines.append(f"### {r['dimension']}（{r['rq']}）")
        lines.append(f"- 查询：*{r['query']}*")
        lines.append(f"- 参考相关 evidence_ids：{r['reference_ids']}")
        lines.append(f"- 融合Top-10命中：{r['found_in_fused']}")
        if r["found_in_bm25_only"]:
            lines.append(f"- 仅BM25路（Top-20）命中但未进入融合Top-10：{r['found_in_bm25_only']}")
        if r["found_in_dense_only"]:
            lines.append(f"- 仅Dense路（Top-20）命中但未进入融合Top-10：{r['found_in_dense_only']}")
        if r["missed_entirely"]:
            lines.append(f"- **两路Top-20均未召回：** {r['missed_entirely']}")
        lines.append(f"- 融合Top-10覆盖的文献：{r['distinct_docs_in_fused_top10']}")
        if r["note"]:
            lines.append(f"- 备注：{r['note']}")
        lines.append("")

    avg_recall = sum(r["recall_fused_top10"] for r in results) / len(results)
    avg_recall_any = sum(r["recall_any_leg_top20"] for r in results) / len(results)
    lines += [
        "## 汇总与建议",
        "",
        f"- 10个维度查询在融合Top-10上的平均 recall = {avg_recall:.2f}",
        f"- 10个维度查询在任一路Top-20上的平均 recall = {avg_recall_any:.2f}",
        "",
    ]
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
