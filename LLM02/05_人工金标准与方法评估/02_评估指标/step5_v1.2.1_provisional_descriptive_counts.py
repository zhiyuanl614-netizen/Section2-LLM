#!/usr/bin/env python3
"""Non-destructive v1.2.1 descriptive counts with D03 excluded from outcomes.

Consumes either the existing provisional ledger or a fresh ledger compiled
from a real v1.2 local Step 4 run. It reports only the nine active analytic
dimensions in primary_label_counts; D03 status is kept in a separate metadata
field and is never treated as a finding or performance metric.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "04_LLM抽取与Critic审查/06_v1.2文本范围预分类/B001_v1.2_scope_aligned_50record_provisional_ledger.json"
ACTIVE_DIMS = ["D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]
D03_STATUS_LABEL = "Not_Analyzed_Out_Of_Scope"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--run-id", default=None, help="Unique output suffix; existing outputs are refused")
    args = parser.parse_args()

    ledger_path = args.ledger.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not ledger_path.is_file():
        raise FileNotFoundError(ledger_path)
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Ledger must contain a non-empty records array")

    doc_ids = data.get("document_ids") or sorted({r.get("doc_id") for r in records if r.get("doc_id")})
    if not doc_ids or len(doc_ids) != len(set(doc_ids)):
        raise ValueError("Ledger has missing or duplicate document IDs")
    if data.get("active_analysis_dimensions") != ACTIVE_DIMS:
        raise ValueError("Ledger active_analysis_dimensions do not match the v1.2 text-scope set")

    per_dim: dict[str, collections.Counter] = {d: collections.Counter() for d in ACTIVE_DIMS}
    d03_status = collections.Counter()
    seen: set[tuple[str, str]] = set()
    for record in records:
        doc_id = record.get("doc_id")
        dim_id = record.get("dimension_id")
        key = (doc_id, dim_id)
        if doc_id not in doc_ids or key in seen:
            raise ValueError(f"Unexpected/duplicate record key: {key}")
        seen.add(key)
        if record.get("equation_detail") not in (None, {}, []):
            raise ValueError(f"Equation details are prohibited in v1.2 Step 5: {key}")
        if dim_id == "D03":
            if record.get("primary_label") != D03_STATUS_LABEL:
                raise ValueError(f"D03 must be a scope-status record only: {key}")
            d03_status[record["primary_label"]] += 1
        elif dim_id in per_dim:
            per_dim[dim_id][record.get("primary_label", "<missing>")] += 1
        else:
            raise ValueError(f"Unexpected dimension in ledger: {dim_id!r}")

    expected_keys = {(doc, dim) for doc in doc_ids for dim in ACTIVE_DIMS + ["D03"]}
    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        raise ValueError(f"Ledger is not a complete 9-active+1-scope-status set; missing={missing}, extra={extra}")

    d02_by_doc = {
        r["doc_id"]: r.get("primary_label")
        for r in records if r.get("dimension_id") == "D02"
    }
    sensitivity = None
    pdf03_label = d02_by_doc.get("B001-PDF-03")
    if pdf03_label == "Mentioned_Only_Not_Modeled":
        sensitivity = dict(per_dim["D02"])
        sensitivity["Mentioned_Only_Not_Modeled"] -= 1
        sensitivity["Generic_Water_Network_Only"] += 1
        if sensitivity["Mentioned_Only_Not_Modeled"] == 0:
            sensitivity.pop("Mentioned_Only_Not_Modeled")

    run_id = args.run_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise ValueError("run-id may contain only letters, digits, dot, underscore and hyphen (1-80 chars)")
    prefix = f"evaluation_metrics_v1.2.1_scope_aligned_provisional_{run_id}"
    out_json = output_dir / f"{prefix}.json"
    out_md = output_dir / f"{prefix}.md"
    if out_json.exists() or out_md.exists():
        raise FileExistsError("Refusing to overwrite a previous v1.2.1 Step 5 output")

    output = {
        "report_id": f"Step5-v1.2.1-scope-aligned-provisional-{run_id}",
        "status": "provisional_descriptive_counts_not_formal_model_evaluation",
        "run_id": run_id,
        "corpus_size": len(doc_ids),
        "document_ids": doc_ids,
        "record_count_including_scope_status": len(records),
        "active_analytic_record_count": len(doc_ids) * len(ACTIVE_DIMS),
        "overall_research_objective_unchanged": True,
        "research_objective": data.get("research_objective"),
        "candidate_gap_directions_preserved": data.get("candidate_gap_directions_preserved", []),
        "ledger_status": data.get("status"),
        "ledger_provenance": data.get("source_sha256", {}),
        "primary_label_counts": {d: dict(sorted(per_dim[d].items())) for d in ACTIVE_DIMS},
        "D03_scope_status_metadata_only": dict(d03_status),
        "D03_included_in_findings_or_metrics": False,
        "D02_PDF03_boundary_status": "unresolved_no_label_is_treated_as_user_approved",
        "D02_PDF03_boundary_sensitivity_if_reclassified_as_Generic_Water_Network_Only": sensitivity,
        "not_computed": ["accuracy", "precision", "recall", "F1", "Cohen_kappa", "Krippendorff_alpha", "model_effectiveness"],
        "reason_not_computed": "No independent human gold standard or independent reviewer output is available.",
        "formula_policy": "No equation transcription, derivation, or equation-type analysis enters these outcomes. Formula-risk metadata remains in the source evidence/ledger only.",
        "limitations": [
            "Counts describe only the selected pilot ledger; five PDFs are not a representative field-wide sample.",
            "Zero labels are sample observations and do not establish field-wide absence or justify deleting a research question.",
            "D04-D10 provenance must be read from the ledger; a local-run ledger and the earlier mixed-provenance ledger are not interchangeable.",
            "The PDF-03/D02 alternative is a sensitivity scenario only, not a user/domain-expert adjudication.",
        ],
        "source_sha256": {"ledger": sha256_file(ledger_path)},
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    if out_json.exists() or out_md.exists():
        raise FileExistsError("Output appeared during Step 5; refusing to overwrite")
    out_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Step 5 v1.2.1 先导语料描述性统计（预备版）",
        "",
        f"- **状态：**{output['status']}；无模型性能或人工标注者一致性结论。",
        f"- **语料：**{len(doc_ids)} 篇；当前数字只描述输入 ledger，不外推至领域总体。",
        f"- **ledger 状态：**`{data.get('status')}`；ledger SHA-256：`{output['source_sha256']['ledger']}`",
        "- **公式范围：**D03 只作范围状态 metadata，不进入主标签频数；不报告方程类型、公式转录或推导。",
        "- **D02 PDF-03：**边界仍未决；当前 ledger 标签不是用户批准的裁定。备选标签只作敏感性情景。",
        "",
        "## 主标签描述频数（仅9个 active analytic dimensions）",
        "",
        "| 维度 | 先导样本主标签频数 |",
        "|---|---|",
    ]
    for dim in ACTIVE_DIMS:
        counts = "; ".join(f"`{label}` {count}/{len(doc_ids)}" for label, count in sorted(per_dim[dim].items()))
        lines.append(f"| {dim} | {counts} |")
    lines += [
        "",
        "## 单独的范围状态 metadata（不计入主标签频数）",
        "",
        f"- D03：{dict(d03_status)}。该记录只说明此版本未做方程类型分析，不表示论文没有方程。",
        "",
        "## PDF-03/D02 敏感性（非裁定）",
        "",
    ]
    if sensitivity is None:
        lines.append("- 输入 ledger 中未出现可按预设备选标签计算的 PDF-03/D02 记录；未生成敏感性频数。")
    else:
        lines.append(f"- 当前输入标签频数：{dict(per_dim['D02'])}")
        lines.append(f"- 假设 PDF-03 改列 `Generic_Water_Network_Only` 的情景：{dict(sensitivity)}")
        lines.append("- 该情景不是用户或领域专家裁定；两种边界解释均保留为未决。")
    lines += [
        "",
        "## 未计算的指标",
        "",
        "未计算 accuracy、precision、recall、F1、Cohen's κ、Krippendorff's α 或 model effectiveness，因为没有独立人工金标准/独立审核输出。",
        "",
        "## 版本化输出",
        "",
        f"- JSON：`{out_json.name}`",
        f"- Markdown：`{out_md.name}`",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
