#!/usr/bin/env python3
"""Compile a non-final v1.2 5x10 working ledger without changing legacy outputs.

D01/D02 and D03 scope records come from the v1.2 text-only candidate batch.
D04-D10 are carried forward unchanged from v1.0 verified records because their
operational definitions were not revised. This file is explicitly provisional,
not a replacement for any *_verified_10d.json file or an independent review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # /home/user/Section2-LLM
OUT_DIR = Path(__file__).resolve().parent
CANDIDATE = OUT_DIR / "B001_RQ1_D01-D03_v1.2_text_only_preclassification.json"
OLD_VERIFIED_DIR = ROOT / "04_LLM抽取与Critic审查" / "05_核验通过结果"
BLOCKS = ROOT / "02_PDF清洗与分块" / "02_Chunks" / "evidence_blocks.jsonl"
SCHEMA = ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json"
OUT = OUT_DIR / "B001_v1.2_scope_aligned_50record_provisional_ledger.json"
DOCS = [f"B001-PDF-{i:02d}" for i in range(1, 6)]
DIMS = [f"D{i:02d}" for i in range(1, 11)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUT}")
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    candidate_by_key = {(r["doc_id"], r["dimension_id"]): r for r in candidate["records"]}
    blocks_by_id = {}
    for line in BLOCKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            b = json.loads(line)
            blocks_by_id[b["evidence_id"]] = b

    records = []
    source_hashes = {}
    for doc_id in DOCS:
        old_path = OLD_VERIFIED_DIR / f"{doc_id}_verified_10d.json"
        old_records = json.loads(old_path.read_text(encoding="utf-8"))
        old_by_dim = {r["dimension_id"]: r for r in old_records}
        source_hashes[doc_id] = sha(old_path)
        for dim in DIMS:
            if dim in {"D01", "D02", "D03"}:
                rec = dict(candidate_by_key[(doc_id, dim)])
                rec["record_origin"] = "v1.2_text_scope_candidate_same_session"
                rec["source_schema_version"] = "v1.2"
                rec["verification_status"] = "preliminary_agent_assisted_not_final"
                rec["carried_forward_from_v1_0"] = False
            else:
                rec = dict(old_by_dim[dim])
                rec["record_origin"] = "v1.0_verified_record_carried_forward_unchanged"
                rec["source_schema_version"] = rec.get("schema_version", "v1.0")
                rec["verification_status"] = "legacy_v1.0_pass1_to_pass4_carried_forward_not_reverified_in_v1_2"
                rec["carried_forward_from_v1_0"] = True

            # The new ledger never carries equation transcriptions/derivations.
            equation_detail = rec.pop("equation_detail", None)
            if equation_detail not in (None, {}, []):
                raise ValueError(f"Unexpected equation_detail in {doc_id} {dim}; stop rather than propagate it")

            eids = list(rec.get("evidence_ids", []))
            if not eids and rec.get("evidence"):
                eids = [e["evidence_id"] for e in rec["evidence"]]
            risk_meta = []
            for eid in eids:
                if eid not in blocks_by_id:
                    raise ValueError(f"Missing evidence ID {eid} in current blocks")
                b = blocks_by_id[eid]
                risk_meta.append({
                    "evidence_id": eid,
                    "formula_layout_risk": bool(b.get("formula_layout_risk", False)),
                    "formula_layout_risk_score": b.get("formula_layout_risk_score"),
                    "contains_unmapped_glyph_marker": bool(b.get("contains_unmapped_glyph_marker", False)),
                })
            rec["evidence_risk_metadata"] = risk_meta
            rec["result_scope_version"] = "v1.2_text_only_RQ1_and_formula_scope_alignment"
            if dim == "D03":
                if rec.get("primary_label") != "Not_Analyzed_Out_Of_Scope":
                    raise ValueError(f"D03 must be a scope status, got {rec.get('primary_label')}")
                rec["evidence_ids"] = []
                rec["evidence"] = []
                rec["mechanism_judgment"] = (
                    "Equation-type analysis was not performed under the current scope. This does not mean the paper lacks equations, "
                    "and no equation-type findings are used in Step 5-7."
                )
            records.append(rec)

    if len(records) != 50:
        raise ValueError(f"Expected 50 records, got {len(records)}")
    counts = {dim: sum(r["dimension_id"] == dim for r in records) for dim in DIMS}
    if any(v != 5 for v in counts.values()):
        raise ValueError(f"Expected five records per dimension: {counts}")
    if any(r.get("equation_detail") is not None for r in records):
        raise ValueError("Equation details must not enter the v1.2 provisional ledger")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    output = {
        "batch_id": "B001-v1.2-scope-aligned-50-record-provisional-20261008",
        "status": "preliminary_compilation_not_final_step4_and_not_independent_human_expert_validation",
        "overall_research_objective_unchanged": True,
        "research_objective": schema["research_program"]["overall_objective"],
        "candidate_gap_directions_preserved": schema["research_program"]["candidate_gap_hypotheses_preserved"],
        "corpus_note": "Five-PDF pilot corpus only; absent D01-D10 labels are normal sample observations, not field-wide absence.",
        "scope_note": "D01/D02 are v1.2 text-only candidates; D03 is an out-of-scope status only; D04-D10 are copied unchanged from v1.0 verified records because their definitions were not revised. No equation details are carried into this ledger.",
        "adjudication_note": "PDF-03 D02 remains a boundary case. Its generic water-supply dependency to power plants is modeled; whether that meets the D02 cooling-specific threshold remains pending user/domain-expert adjudication.",
        "record_count": len(records),
        "records_per_dimension": counts,
        "active_analysis_dimensions": schema["active_analysis_dimensions"],
        "source_sha256": {
            "candidate_v1_2": sha(CANDIDATE),
            "schema_v1_2": sha(SCHEMA),
            "evidence_blocks": sha(BLOCKS),
            "legacy_verified_records": source_hashes,
        },
        "records": records,
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print("records per dimension:", counts)
    print("D03 formula detail: excluded from all 5 new scope-status records")


if __name__ == "__main__":
    main()
