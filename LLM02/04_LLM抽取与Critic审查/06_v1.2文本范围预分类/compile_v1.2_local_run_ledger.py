#!/usr/bin/env python3
"""Compile one completed, real local Step 4 run into a fresh v1.2 ledger.

Unlike compile_v1.2_provisional_pilot_ledger.py, this compiler consumes the
run_id-isolated local Step 4 outputs and does not carry D04-D10 forward from
legacy v1.0. D03 is retained only as a separate scope-status record; it is not
an analytic label or metric. No source records are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DEFAULT = ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json"
ACTIVE_DIMS = ["D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]
FALLBACKS = {"Not_Stated_In_Text", "Explicitly_Not_Considered", "Insufficient_Evidence", "Evidence_Unavailable"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_quote(value: str) -> str:
    value = value.replace(chr(0x00AD), "")
    value = re.sub(r"-\s*\n\s*", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite ledger: {path}")
    tmp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if path.exists():
            raise FileExistsError(f"Target appeared during compilation; refusing to overwrite: {path}")
        os.rename(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="One Step 4 local run_id directory")
    parser.add_argument("--evidence-blocks", type=Path, required=True, help="Exact versioned evidence_blocks.jsonl used by Step 4")
    parser.add_argument("--output", type=Path, required=True, help="New ledger JSON path; existing files are never replaced")
    parser.add_argument("--schema-path", type=Path, default=SCHEMA_DEFAULT)
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    evidence_path = args.evidence_blocks.expanduser().resolve()
    out_path = args.output.expanduser().resolve()
    schema_path = args.schema_path.expanduser().resolve()
    config_path = run_dir / "run_config_redacted.json"
    summary_path = run_dir / "run_summary.json"
    manifest_path = run_dir / "02_模型调用日志" / "model_call_manifest.jsonl"
    for required in (config_path, summary_path, manifest_path, evidence_path, schema_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    if out_path.exists():
        raise FileExistsError(f"Refusing to overwrite ledger: {out_path}")

    config = load_json(config_path)
    summary = load_json(summary_path)
    schema = load_json(schema_path)
    run_id = config.get("run_id")
    if not isinstance(run_id, str) or not run_id or summary.get("run_id") != run_id:
        raise ValueError("run_config and run_summary run_id values do not match")
    if config.get("execution_mode") != "local_api_only" or summary.get("execution_mode") != "local_api_only":
        raise ValueError("Only a real local_api_only Step 4 run can be compiled; dry-run/mock outputs are not data")
    if schema.get("schema_version") != "v1.2" or schema.get("active_analysis_dimensions") != ACTIVE_DIMS:
        raise ValueError("Unexpected v1.2 schema or active dimension set")
    if config.get("schema_sha256") != sha256_file(schema_path):
        raise ValueError("Schema hash differs from the source schema recorded by Step 4")
    if config.get("evidence_blocks_sha256") != sha256_file(evidence_path):
        raise ValueError("Evidence-block hash differs from the Step 4 run configuration")
    if config.get("model_schema_policy", {}).get("D02_boundary_rule_sent_to_model") is not False:
        raise ValueError("Run configuration does not confirm that the unapproved D02 boundary rule was withheld")

    requested = summary.get("documents_requested")
    completed = summary.get("documents_completed")
    failed = summary.get("documents_failed")
    results = summary.get("results") or []
    if failed != 0 or requested != completed or len(results) != requested:
        raise ValueError("Step 4 run is incomplete or contains failures; compile only a complete run")
    doc_ids = [r.get("doc_id") for r in results]
    if not doc_ids or any(not isinstance(d, str) for d in doc_ids) or len(set(doc_ids)) != len(doc_ids):
        raise ValueError("Invalid or duplicate doc_id values in run_summary")
    if sorted(doc_ids) != sorted(config.get("doc_ids") or []):
        raise ValueError("Completed doc_ids do not match the run configuration")

    evidence_by_id: dict[str, dict] = {}
    with evidence_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            eid = row.get("evidence_id")
            if not isinstance(eid, str) or eid in evidence_by_id:
                raise ValueError(f"Invalid or duplicate evidence_id at line {line_no}")
            evidence_by_id[eid] = row

    manifest_entries = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not manifest_entries or any(entry.get("execution_channel") != "local_api_call" for entry in manifest_entries):
        raise ValueError("A real local API call manifest is required; mock/dry-run entries are not compilable")
    if any(entry.get("run_id") != run_id for entry in manifest_entries):
        raise ValueError("Model call manifest contains an entry from another run_id")

    records: list[dict] = []
    per_doc_sources: dict[str, dict[str, str]] = {}
    for doc_id in doc_ids:
        verified_path = run_dir / "05_核验通过结果" / f"{doc_id}_verified_v1.2_text_scope.json"
        scope_path = run_dir / "06_范围状态_D03" / f"{doc_id}_D03_scope_status_v1.2.json"
        if not verified_path.is_file() or not scope_path.is_file():
            raise FileNotFoundError(f"Missing verified/scope output for {doc_id}")
        verified = load_json(verified_path)
        scope = load_json(scope_path)
        if not isinstance(verified, list) or len(verified) != len(ACTIVE_DIMS):
            raise ValueError(f"{doc_id} must have exactly nine active v1.2 records")
        by_dim = {r.get("dimension_id"): r for r in verified}
        if set(by_dim) != set(ACTIVE_DIMS):
            raise ValueError(f"{doc_id} active dimensions are missing, duplicated, or unexpected")
        for dim_id in ACTIVE_DIMS:
            rec = dict(by_dim[dim_id])
            if rec.get("doc_id") != doc_id or rec.get("schema_version") != "v1.2" or rec.get("run_id") != run_id:
                raise ValueError(f"Record provenance mismatch for {doc_id}/{dim_id}")
            if rec.get("equation_detail") not in (None, {}, []):
                raise ValueError(f"Non-null equation_detail found for {doc_id}/{dim_id}")
            if dim_id == "D02" and doc_id == "B001-PDF-03" and rec.get("verification_status") != "adjudication_required":
                raise ValueError("B001-PDF-03/D02 must remain adjudication_required")

            eids = rec.get("evidence_ids") or []
            if not isinstance(eids, list) or len(eids) != len(set(eids)):
                raise ValueError(f"Invalid evidence_ids for {doc_id}/{dim_id}")
            cited_blocks = []
            risk_meta = []
            for eid in eids:
                block = evidence_by_id.get(eid)
                if block is None or block.get("doc_id") != doc_id:
                    raise ValueError(f"Evidence ID {eid!r} is missing or belongs to another document")
                cited_blocks.append(block.get("text", ""))
                risk_meta.append({
                    "evidence_id": eid,
                    "formula_layout_risk": bool(block.get("formula_layout_risk", False)),
                    "formula_layout_risk_score": block.get("formula_layout_risk_score"),
                    "contains_unmapped_glyph_marker": bool(block.get("contains_unmapped_glyph_marker", False)),
                })
            quote = rec.get("verbatim_quote") or ""
            if quote and not any(normalize_quote(quote) in normalize_quote(text) for text in cited_blocks):
                raise ValueError(f"Quote does not exactly match a cited block for {doc_id}/{dim_id}")
            label = rec.get("primary_label")
            if label not in FALLBACKS and (not eids or not quote):
                raise ValueError(f"Text-supported record lacks evidence/quote for {doc_id}/{dim_id}")
            rec["evidence_risk_metadata"] = risk_meta
            rec["record_origin"] = "v1.2_local_api_model_run"
            rec["source_schema_version"] = "v1.2"
            rec["carried_forward_from_v1_0"] = False
            rec["result_scope_version"] = "v1.2_local_text_scope_provisional"
            records.append(rec)

        if (scope.get("doc_id") != doc_id or scope.get("dimension_id") != "D03"
                or scope.get("primary_label") != "Not_Analyzed_Out_Of_Scope"
                or scope.get("run_id") != run_id
                or scope.get("verification_status") != "scope_status_not_a_paper_finding"
                or scope.get("agent_a_model_call_id") is not None
                or scope.get("agent_b_review") is not None
                or scope.get("evidence_ids") not in ([], None)
                or scope.get("equation_detail") not in (None, {}, [])):
            raise ValueError(f"Invalid D03 status-only record for {doc_id}")
        scope = dict(scope)
        scope["record_origin"] = "v1.2_local_pipeline_generated_status_no_model_call"
        scope["carried_forward_from_v1_0"] = False
        scope["evidence_risk_metadata"] = []
        records.append(scope)
        per_doc_sources[doc_id] = {
            "verified_records_sha256": sha256_file(verified_path),
            "d03_scope_status_sha256": sha256_file(scope_path),
        }

    order = {dim: i for i, dim in enumerate(["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"])}
    records.sort(key=lambda r: (doc_ids.index(r["doc_id"]), order[r["dimension_id"]]))
    counts = {d: sum(r["dimension_id"] == d for r in records) for d in ["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]}
    expected = {d: len(doc_ids) for d in counts}
    if counts != expected:
        raise ValueError(f"Unexpected records per dimension: {counts}")

    output = {
        "batch_id": f"{run_id}-v1.2-local-ledger",
        "status": "provisional_local_model_run_not_final_human_adjudication",
        "overall_research_objective_unchanged": True,
        "research_objective": schema["research_program"]["overall_objective"],
        "candidate_gap_directions_preserved": schema["research_program"]["candidate_gap_hypotheses_preserved"],
        "corpus_note": "This ledger covers only the documents in the selected local run; it is not a field-wide sample.",
        "scope_note": "D01/D02/D04-D10 are local-model candidate records; D03 is a separate scope-status record only. No equation details are included.",
        "adjudication_note": "Any record marked adjudication_required, including B001-PDF-03/D02, remains unresolved and must not be treated as a user-approved label.",
        "run_id": run_id,
        "record_count": len(records),
        "records_per_dimension": counts,
        "active_analysis_dimensions": ACTIVE_DIMS,
        "document_ids": doc_ids,
        "source_sha256": {
            "run_config_redacted": sha256_file(config_path),
            "run_summary": sha256_file(summary_path),
            "model_call_manifest": sha256_file(manifest_path),
            "evidence_blocks": sha256_file(evidence_path),
            "schema_v1_2": sha256_file(schema_path),
            "records_by_doc": per_doc_sources,
        },
        "records": records,
    }
    write_new_json(out_path, output)
    print(f"Wrote provisional local-run ledger: {out_path}")
    print(f"Documents={len(doc_ids)}; records={len(records)}; D03 statuses={counts['D03']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
