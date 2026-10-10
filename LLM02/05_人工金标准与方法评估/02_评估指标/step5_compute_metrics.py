#!/usr/bin/env python3
"""Step 5 评估指标计算脚本（v1.0, 2026-10-06）。

重新计算并写出 evaluation_metrics_v1.json，口径定义见同目录
evaluation_metrics_v1.md 第1节。只做固定规则的程序化统计，不做语义判断
（语义判断已经在 Step 4 的 Agent A/B pass1-4 中完成并被此脚本读取）。

运行：python3 step5_compute_metrics.py  （从本脚本所在目录执行）
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # Section2-LLM/
SCHEMA_FP = ROOT / "04_LLM抽取与Critic审查/01_Prompt与Schema注册/schema_v2.json"
VERIFIED_DIR = ROOT / "04_LLM抽取与Critic审查/05_核验通过结果"
AGENT_A_DIR = ROOT / "04_LLM抽取与Critic审查/03_AgentA原始抽取"
AGENT_B_DIR = ROOT / "04_LLM抽取与Critic审查/04_AgentB_Critic审查"
EVIDENCE_FP = ROOT / "02_PDF清洗与分块/02_Chunks/evidence_blocks.jsonl"
OUT_FP = Path(__file__).resolve().parent / "evaluation_metrics_v1.json"

DOCS = ["B001-PDF-01", "B001-PDF-02", "B001-PDF-03", "B001-PDF-04", "B001-PDF-05"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def main():
    schema = json.loads(SCHEMA_FP.read_text(encoding="utf-8"))
    exempt_labels = set(schema["fallback_states"]) | {"Not_Addressed", "None_Reported"}

    evidence_idx = {}
    with open(EVIDENCE_FP, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                evidence_idx[rec["evidence_id"]] = rec

    all_records = []
    for doc in DOCS:
        recs = json.loads((VERIFIED_DIR / f"{doc}_verified_10d.json").read_text(encoding="utf-8"))
        for r in recs:
            r["_doc"] = doc
            all_records.append(r)

    non_exempt = [r for r in all_records if r["primary_label"] not in exempt_labels]
    exempt = [r for r in all_records if r["primary_label"] in exempt_labels]

    has_evidence = sum(1 for r in non_exempt if r.get("evidence_ids") and r.get("verbatim_quote"))
    section_page_ok = sum(1 for r in non_exempt if r.get("section_id") and r.get("page_numbers"))

    quote_match = 0
    for r in non_exempt:
        q = r.get("verbatim_quote")
        if q and any(
            eid in evidence_idx and norm(q) in norm(evidence_idx[eid]["text"])
            for eid in (r.get("evidence_ids") or [])
        ):
            quote_match += 1

    decision_counts = Counter()
    revise_detail = []
    for doc in DOCS:
        pass2 = json.loads((AGENT_B_DIR / f"{doc}_agentB_pass2.json").read_text(encoding="utf-8"))
        for dim, v in pass2.items():
            decision_counts[v["decision"]] += 1
            if v["decision"] != "accept":
                revise_detail.append((doc, dim, v.get("corrected_label")))

    primary_label_changes = 0
    evidence_only_changes = 0
    for doc, dim, corrected in revise_detail:
        pass1 = {
            r["dimension_id"]: r
            for r in json.loads((AGENT_A_DIR / f"{doc}_agentA_pass1.json").read_text(encoding="utf-8"))
        }
        if corrected and corrected != pass1[dim]["primary_label"]:
            primary_label_changes += 1
        else:
            evidence_only_changes += 1

    unresolved = 0
    for doc in DOCS:
        pass4_fp = AGENT_B_DIR / f"{doc}_agentB_pass4_final.json"
        if pass4_fp.exists():
            pass4 = json.loads(pass4_fp.read_text(encoding="utf-8"))
            unresolved += sum(1 for v in pass4.values() if v["decision"] != "accept")

    unsupported = sum(
        1
        for r in non_exempt
        if not (r.get("evidence_ids") and r.get("verbatim_quote"))
        or not any(
            eid in evidence_idx and norm(r["verbatim_quote"]) in norm(evidence_idx[eid]["text"])
            for eid in (r.get("evidence_ids") or [])
        )
    )

    n = len(all_records)
    metrics = {
        "total_records": n,
        "exempt_records": len(exempt),
        "exempt_rate": len(exempt) / n,
        "non_exempt_records": len(non_exempt),
        "evidence_sufficiency_rate": has_evidence / len(non_exempt),
        "quote_exact_match_rate": quote_match / len(non_exempt),
        "section_page_traceability_rate": section_page_ok / len(non_exempt),
        "pass1_pass2_initial_agreement_rate": decision_counts["accept"] / n,
        "pass2_revision_rate": decision_counts.get("revise", 0) / n,
        "primary_label_correction_count": primary_label_changes,
        "primary_label_correction_rate": primary_label_changes / n,
        "evidence_only_correction_count": evidence_only_changes,
        "evidence_only_correction_rate": evidence_only_changes / n,
        "unresolved_adjudication_count": unresolved,
        "unsupported_claim_rate": unsupported / len(non_exempt),
        "own_method_vs_cited_distribution": dict(Counter(r["own_method_vs_cited"] for r in all_records)),
        "revision_detail": [{"doc": d, "dimension_id": dim, "corrected_label": c} for d, dim, c in revise_detail],
    }

    OUT_FP.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_FP}")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    # Diagnostic: quote_exact_match_rate / section_page_traceability_rate depend
    # on evidence_ids referenced by the 50 frozen verified records still being
    # present, unchanged, in 02_Chunks/evidence_blocks.jsonl. If Step 1 and/or
    # Step 2 were re-run from the raw PDFs at any point (even on the same
    # platform/library versions, PDF text extraction is not guaranteed
    # byte-identical run to run), or if step4_pilot_extraction.py /
    # step4_batch2_extraction.py were re-run afterwards (which overwrites the
    # original frozen 05_核验通过结果/03_AgentA原始抽取/04_AgentB_Critic审查
    # with a freshly recomputed version against whatever evidence_blocks.jsonl
    # exists at that moment), these two metrics can legitimately drop well
    # below the documented historical baseline (1.0 / 1.0) even though nothing
    # is "broken" in the sense of a code bug -- it just means you are no longer
    # evaluating against the original frozen baseline. Surface this clearly
    # instead of leaving the user to guess why the numbers look wrong.
    missing_eid_refs = sum(
        1 for r in non_exempt for eid in (r.get("evidence_ids") or []) if eid not in evidence_idx
    )
    if metrics["quote_exact_match_rate"] < 0.99 or metrics["section_page_traceability_rate"] < 0.99:
        print(
            "\nNOTE: quote_exact_match_rate and/or section_page_traceability_rate are "
            "below the documented historical baseline (1.0 / 1.0 in the shipped "
            "evaluation_metrics_v1.json).\n"
            f"  -> {missing_eid_refs} evidence_id reference(s) in the 50 verified records "
            "were not found at all in the currently-loaded evidence_blocks.jsonl.\n"
            "This almost always means 02_PDF清洗与分块/01_Zones and/or 02_Chunks/evidence_blocks.jsonl "
            "and/or 04_LLM抽取与Critic审查/{03_AgentA原始抽取,04_AgentB_Critic审查,05_核验通过结果} "
            "were regenerated (by re-running step1_pdf_targeted_slicer.py / step2_evidence_chunker.py "
            "/ step4_pilot_extraction.py / step4_batch2_extraction.py) AFTER this package was unpacked, "
            "which overwrites the original frozen historical baseline with a freshly re-derived one "
            "(PDF text extraction is not guaranteed to be 100% byte-identical run to run). "
            "If you want Step 5 to reproduce the documented historical figures exactly, restore the "
            "original frozen files that shipped with this package instead of re-generating them."
        )


if __name__ == "__main__":
    main()
