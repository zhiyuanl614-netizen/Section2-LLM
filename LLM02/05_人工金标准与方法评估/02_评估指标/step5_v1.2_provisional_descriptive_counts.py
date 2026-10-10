#!/usr/bin/env python3
"""DEPRECATED: retained to reproduce the first v1.2 provisional Step 5 output.

Its historical primary_label_counts still contains D03, despite a separate
scope-status note. Do not use it for new reports; use
step5_v1.2.1_provisional_descriptive_counts.py, which excludes D03 from the
analytic label counts. No accuracy/agreement metrics are computed without an
independent human gold set.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # Section2-LLM/
LEDGER = ROOT / "04_LLM抽取与Critic审查/06_v1.2文本范围预分类/B001_v1.2_scope_aligned_50record_provisional_ledger.json"
OUT_DIR = Path(__file__).resolve().parent
OUT_JSON = OUT_DIR / "evaluation_metrics_v1.2_scope_aligned_provisional.json"
OUT_MD = OUT_DIR / "evaluation_metrics_v1.2_scope_aligned_provisional.md"
EXPECTED_DIMS = [f"D{i:02d}" for i in range(1, 11)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("Refusing to overwrite prior v1.2 provisional Step 5 output")
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    records = data["records"]
    per_dim: dict[str, collections.Counter] = {d: collections.Counter() for d in EXPECTED_DIMS}
    origins = collections.Counter()
    for r in records:
        per_dim[r["dimension_id"]][r["primary_label"]] += 1
        origins[r.get("record_origin", "unknown")] += 1

    if len(records) != 50 or any(sum(per_dim[d].values()) != 5 for d in EXPECTED_DIMS):
        raise ValueError("Unexpected record counts")
    if any(r.get("equation_detail") not in (None, {}, []) for r in records):
        raise ValueError("Equation details must not enter new Step 5 output")

    d02 = dict(per_dim["D02"])
    sensitivity = None
    if d02.get("Mentioned_Only_Not_Modeled", 0) >= 1:
        sensitivity = dict(d02)
        sensitivity["Mentioned_Only_Not_Modeled"] = sensitivity.get("Mentioned_Only_Not_Modeled", 0) - 1
        sensitivity["Generic_Water_Network_Only"] = sensitivity.get("Generic_Water_Network_Only", 0) + 1
        if sensitivity["Mentioned_Only_Not_Modeled"] == 0:
            sensitivity.pop("Mentioned_Only_Not_Modeled")

    output = {
        "report_id": "Step5-v1.2-scope-aligned-provisional-descriptive-counts-20261008",
        "status": "provisional_descriptive_counts_not_formal_model_evaluation",
        "corpus_size": 5,
        "record_count": len(records),
        "overall_research_objective_unchanged": True,
        "research_objective": data["research_objective"],
        "candidate_gap_directions_preserved": data["candidate_gap_directions_preserved"],
        "provenance": {
            "D01_D02_D03": "v1.2 same-session text-only candidate records; D02 PDF-03 boundary unresolved",
            "D04_D10": "v1.0 verified records carried forward unchanged; not re-reviewed in v1.2",
        },
        "primary_label_counts": {d: dict(per_dim[d]) for d in EXPECTED_DIMS},
        "D03_scope_status_count": dict(per_dim["D03"]),
        "D03_included_in_findings_or_metrics": False,
        "D02_PDF03_boundary_sensitivity_if_reclassified_as_Generic_Water_Network_Only": sensitivity,
        "record_origin_counts": dict(origins),
        "not_computed": [
            "accuracy", "precision", "recall", "F1", "Cohen_kappa", "Krippendorff_alpha", "model_effectiveness"
        ],
        "reason_not_computed": "No independent human gold standard or independent reviewer output is available; current labels are same-session Agent-assisted and partly carried forward from v1.0.",
        "formula_policy": "No equation transcription, derivation, or equation-type field is included in this report. D03 is only a scope-status register and excluded from outcome distributions.",
        "limitations": [
            "The five PDFs are a pilot corpus; counts are descriptive of these five documents only.",
            "Zero labels in D01-D10 are normal sample observations and do not establish field-wide absence or justify deleting a research question.",
            "D04-D10 use v1.0 records with unchanged definitions, not fresh v1.2 content review.",
            "PDF-03 D02 has unresolved construct-threshold ambiguity; only one specified alternative is shown in the sensitivity table.",
        ],
        "source_sha256": {"provisional_ledger": sha(LEDGER)},
    }
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Step 5 v1.2 先导语料描述性统计（预备版）",
        "",
        "- **状态：**版本化预备计数；不是正式 Step 5 模型性能评估，不覆盖 v1.0/v1.1 文件。",
        "- **总目标：**保持不变——文献学习提出三项候选研究差距/前沿方向，形成 RQ/假设，再由 LLM 基于证据检验支持、反例和不确定性。",
        "- **样本：**5篇先导 PDF；D01–D10某些标签在此样本为零属于正常观察，不推断领域总体缺失，也不因此删除任何候选方向。",
        "- **结果来源：**D01/D02/D03为v1.2同会话Agent文本候选；D04–D10沿用原v1.0记录（定义未变），没有在本版重审。PDF-03 D02仍待领域 adjudication。",
        "- **不能声称：**无独立人类金标准，未计算准确率、精确率、召回率、F1、Cohen's κ、Krippendorff's α或模型效果。",
        "- **公式范围：**不报告公式转录、推导或方程类型；D03只记范围状态，不进入发现/分布。",
        "",
        f"- 输入 ledger SHA-256: `{output['source_sha256']['provisional_ledger']}`",
        "",
        "## 1. 主标签描述频数",
        "",
        "| 维度 | 版本/状态 | 5篇先导语料中的 primary-label 频数 |",
        "|---|---|---|",
    ]
    for dim in EXPECTED_DIMS:
        if dim == "D03":
            status = "v1.2范围状态，不作研究发现"
        elif dim in {"D01", "D02"}:
            status = "v1.2文本候选"
        else:
            status = "v1.0沿用，定义未变"
        counts = "; ".join(f"`{label}` {n}/5" for label, n in sorted(per_dim[dim].items()))
        lines.append(f"| {dim} | {status} | {counts} |")

    lines += [
        "",
        "### D01/D02 当前候选标签分布",
        "",
        f"- D01：{dict(per_dim['D01'])}",
        f"- D02：{dict(per_dim['D02'])}",
        "- D03：5/5 `Not_Analyzed_Out_Of_Scope`；不计为“无方程”或缺失发现。",
        "",
        "## 2. PDF-03 D02 敏感性",
        "",
        "按当前冷却专属过程阈值，PDF-03暂列 `Mentioned_Only_Not_Modeled`，但原文中的通用“供水设施为电厂供水”依赖确实进入模型。若专家裁定该项应改列 `Generic_Water_Network_Only`，D02频数将变为：",
        "",
        "| 假设 | `Generic_Water_Network_Only` | `Mentioned_Only_Not_Modeled` | `Both_Present` |",
        "|---|---:|---:|---:|",
        f"| 当前暂行判定 | {d02.get('Generic_Water_Network_Only',0)}/5 | {d02.get('Mentioned_Only_Not_Modeled',0)}/5 | {d02.get('Both_Present',0)}/5 |",
        f"| PDF-03改列通用水网（敏感性） | {sensitivity.get('Generic_Water_Network_Only',0)}/5 | {sensitivity.get('Mentioned_Only_Not_Modeled',0)}/5 | {sensitivity.get('Both_Present',0)}/5 |",
        "",
        "敏感性只示范这一种备选标签，不代表专家已裁定；PDF-03的通用依赖模型与冷却专属过程模型必须分别表述。原文复核见 `04_LLM抽取与Critic审查/06_v1.2文本范围预分类/D02_v1.2_original_pdf_targeted_review_same_session_2026-10-08.md`。",
        "",
        "## 3. 方法限制与后续门槛",
        "",
        "1. 本表是5篇文献上的描述性频数；没有独立金标准，不能度量LLM性能或审核者一致性。",
        "2. D04–D10只是因定义未变而沿用旧记录；D03方程类型信息完全不带入新指标。",
        "3. PDF-03 D02须由用户/领域专家确认构念阈值后，才能生成定稿Step 4及正式Step 5–7。",
        "4. Step 6/7应把三项 gap/frontier 作为可被样本证据支持、反驳或保留不确定性的假设；不能用零频标签把研究目标改写为领域总体结论。",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
