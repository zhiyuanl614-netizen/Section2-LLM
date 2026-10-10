#!/usr/bin/env python3
"""Run a local-only, evidence-grounded challenge of the three manuscript RQs.

This is a second-stage challenge tool, not a candidate-direction discovery
step. It consumes a complete real v1.2 local Step 4 ledger, compares the
three directions supplied by the project schema, and requires every cited
supporting/counterevidence passage to resolve to an input evidence block.
No web search, cloud provider, formula analysis, or legacy v1.0 carry-forward
records are used. The output is preliminary and is not human adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "04_LLM抽取与Critic审查" / "API批量管线"
sys.path.insert(0, str(API_DIR))
from llm_api_client_v1_2_local import LocalEndpointConfig, LLMCallError, call_llm  # noqa: E402

SCHEMA_DEFAULT = ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "产出_v1.2_local_evidence_challenge"
ACTIVE_DIMS = {
    "3-1": ["D01", "D02", "D10"],
    "4-1": ["D04", "D05", "D06", "D10"],
    "5-1": ["D07", "D08", "D09", "D10"],
}
EXPECTED_PILOT_DOC_IDS = tuple(f"B001-PDF-{i:02d}" for i in range(1, 6))
ASSESSMENTS = {"pilot_support", "mixed_evidence", "counterevidence_dominates", "unresolved"}


def validate_complete_pilot_doc_ids(doc_ids: Any) -> None:
    if (not isinstance(doc_ids, list)
            or len(doc_ids) != len(EXPECTED_PILOT_DOC_IDS)
            or any(not isinstance(doc_id, str) for doc_id in doc_ids)
            or set(doc_ids) != set(EXPECTED_PILOT_DOC_IDS)):
        raise ValueError("Step 6 cross-paper challenge requires exactly B001-PDF-01 through B001-PDF-05")
SYSTEM_PROMPT = """Role: local cross-paper evidence challenger.

Task: Assess ONLY the supplied candidate direction and the supplied v1.2
text-scope records/evidence for the five-paper pilot. Do not invent, add,
remove, rename, or rank research directions. The candidate directions were
proposed in the manuscript's Introduction; this call tests them, it does not
re-discover them. Report a pilot-limited assessment with direct support,
counterevidence, and unresolved issues.

Evidence rules:
1. Use only clear natural-language evidence in the supplied evidence blocks.
   Do not read, transcribe, explain, compare, or infer equations, variables,
   symbols, formula structure, or equation types. A formula-layout-risk block
   may be used only when the quoted narrative sentence stands alone.
2. Every support/counterevidence item must cite an input evidence_id, doc_id,
   dimension_id, and an exact verbatim quote from that evidence block. Do not
   cite a record label alone as proof of absence. A Not_Stated/Not_Addressed
   label is only a five-paper text observation, not field-wide negative proof.
3. Preserve provenance. If a record has verification_status
   "adjudication_required" or an unresolved-boundary notice, describe it as
   unresolved; never convert its candidate label into an approved decision.
4. Distinguish current model/method evidence from background mention and from
   author-stated future work. A future-work statement is not an implemented
   method. Explicitly retain material counterexamples.
5. N=5 is a pilot only. Do not claim field-wide prevalence, confirmed gaps,
   independent review, or causal conclusions. Do not use D03; it is a local
   scope-status record and is not part of the input.

Return exactly one JSON object with these keys:
{
  "direction_id": "3-1|4-1|5-1",
  "pilot_assessment": "pilot_support|mixed_evidence|counterevidence_dominates|unresolved",
  "pilot_limited_conclusion": "string",
  "supporting_evidence": [{"doc_id":"...","dimension_id":"D...","evidence_id":"...","quote":"exact text","why_relevant":"..."}],
  "counterevidence": [{"doc_id":"...","dimension_id":"D...","evidence_id":"...","quote":"exact text","why_it_qualifies_or_limits":"..."}],
  "unresolved_issues": ["..."],
  "scope_limitations": ["..."]
}
Use empty arrays when no qualifying text is supplied. Do not output equation_detail or other keys. Return JSON only."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_simple_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def extract_json(text: str) -> Any:
    text = re.sub(r"<think>.*?</think>", "", text.strip(), flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def normalize_quote(value: str) -> str:
    value = value.replace(chr(0x00AD), "")
    value = re.sub(r"-\s*\n\s*", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def build_direction_payload(direction: dict, rq: str, dims: list[str], records: list[dict],
                            evidence_by_id: dict[str, dict]) -> dict:
    doc_ids = sorted({r.get("doc_id") for r in records if r.get("dimension_id") in dims})
    packed_records = []
    included_eids: set[str] = set()
    for doc_id in doc_ids:
        for record in sorted(
            (r for r in records if r.get("doc_id") == doc_id and r.get("dimension_id") in dims),
            key=lambda r: r["dimension_id"],
        ):
            evidence = []
            for eid in record.get("evidence_ids") or []:
                block = evidence_by_id.get(eid)
                if block is None or block.get("doc_id") != doc_id:
                    raise ValueError(f"Missing/wrong-document evidence_id {eid!r} in record {doc_id}/{record.get('dimension_id')}")
                included_eids.add(eid)
                evidence.append({
                    "evidence_id": eid,
                    "section_id": block.get("section_id"),
                    "page_numbers": block.get("page_numbers"),
                    "formula_layout_risk": bool(block.get("formula_layout_risk", False)),
                    "text": block.get("text", ""),
                    "step4_verbatim_quote": record.get("verbatim_quote") or "",
                })
            packed_records.append({
                "doc_id": doc_id,
                "dimension_id": record["dimension_id"],
                "primary_label": record.get("primary_label"),
                "verification_status": record.get("verification_status"),
                "record_origin": record.get("record_origin"),
                "own_method_vs_cited": record.get("own_method_vs_cited"),
                "mechanism_judgment": record.get("mechanism_judgment"),
                "uncertainty_note": record.get("uncertainty_note"),
                "evidence": evidence,
            })
    return {
        "task": "challenge_one_existing_candidate_direction_against_v1.2_pilot_records",
        "direction": {"id": direction["id"], "summary": direction["summary"], "rq": rq},
        "pilot_corpus": {"document_count": len(doc_ids), "doc_ids": doc_ids, "not_representative_of_field": True},
        "dimension_ids_used": dims,
        "formula_scope": "D03 and equation-type analysis excluded; use clear narrative only.",
        "records": packed_records,
        "input_evidence_ids": sorted(included_eids),
    }


def validate_result(value: Any, *, direction_id: str, input_payload: dict,
                    evidence_by_id: dict[str, dict]) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return None, ["top-level result must be a JSON object"]
    required = {
        "direction_id", "pilot_assessment", "pilot_limited_conclusion",
        "supporting_evidence", "counterevidence", "unresolved_issues", "scope_limitations",
    }
    extras, missing = set(value) - required, required - set(value)
    if extras:
        errors.append(f"unexpected keys: {sorted(extras)}")
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    if value.get("direction_id") != direction_id:
        errors.append("direction_id does not match the requested candidate")
    if value.get("pilot_assessment") not in ASSESSMENTS:
        errors.append("pilot_assessment is not an allowed value")
    for field in ("pilot_limited_conclusion",):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"{field} must be a non-empty string")
    input_ids = set(input_payload.get("input_evidence_ids", []))
    input_records = {
        (r["doc_id"], r["dimension_id"], e["evidence_id"])
        for r in input_payload.get("records", []) for e in r.get("evidence", [])
    }
    for field in ("supporting_evidence", "counterevidence"):
        items = value.get(field)
        if not isinstance(items, list):
            errors.append(f"{field} must be an array")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{field}[{i}] must be an object")
                continue
            allowed_item_keys = {"doc_id", "dimension_id", "evidence_id", "quote", "why_relevant"} if field == "supporting_evidence" else {"doc_id", "dimension_id", "evidence_id", "quote", "why_it_qualifies_or_limits"}
            if set(item) != allowed_item_keys:
                errors.append(f"{field}[{i}] has unexpected/missing keys")
                continue
            key = (item.get("doc_id"), item.get("dimension_id"), item.get("evidence_id"))
            eid = item.get("evidence_id")
            if key not in input_records or eid not in input_ids:
                errors.append(f"{field}[{i}] cites evidence not included for this direction: {key}")
                continue
            block = evidence_by_id.get(eid, {})
            quote = item.get("quote")
            if not isinstance(quote, str) or not quote.strip() or normalize_quote(quote) not in normalize_quote(block.get("text", "")):
                errors.append(f"{field}[{i}] quote is not an exact normalized substring of evidence block {eid}")
            why_key = "why_relevant" if field == "supporting_evidence" else "why_it_qualifies_or_limits"
            if not isinstance(item.get(why_key), str) or not item[why_key].strip():
                errors.append(f"{field}[{i}] missing rationale")
    for field in ("unresolved_issues", "scope_limitations"):
        if not isinstance(value.get(field), list) or any(not isinstance(x, str) or not x.strip() for x in value.get(field, [])):
            errors.append(f"{field} must be an array of non-empty strings")
    if not errors:
        return value, []
    return None, errors


def atomic_new_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    tmp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if path.exists():
            raise FileExistsError(f"Target appeared during write: {path}")
        os.rename(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True, help="Fresh ledger from compile_v1.2_local_run_ledger.py")
    parser.add_argument("--evidence-blocks", type=Path, required=True)
    parser.add_argument("--schema-path", type=Path, default=SCHEMA_DEFAULT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--env-file", type=Path, default=API_DIR / ".env.local")
    parser.add_argument("--dry-run", action="store_true", help="Write explicit non-data placeholders; no model call")
    parser.add_argument("--allow-private-network", action="store_true")
    parser.add_argument("--tokenizer-path", type=Path, default=None)
    parser.add_argument("--context-limit", type=int, default=None)
    parser.add_argument("--require-token-preflight", action="store_true")
    args = parser.parse_args()

    ledger_path = args.ledger.expanduser().resolve()
    evidence_path = args.evidence_blocks.expanduser().resolve()
    schema_path = args.schema_path.expanduser().resolve()
    if not all(p.is_file() for p in (ledger_path, evidence_path, schema_path)):
        raise FileNotFoundError("Ledger, evidence blocks, and schema must all exist")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("schema_version") != "v1.2":
        raise ValueError("Step 6 requires schema v1.2")
    if ledger.get("status") != "provisional_local_model_run_not_final_human_adjudication":
        raise ValueError("Step 6 accepts only a fresh ledger compiled from a real local Step 4 run")
    if ledger.get("source_sha256", {}).get("evidence_blocks") != sha256_file(evidence_path):
        raise ValueError("Evidence blocks hash does not match the compiled ledger")
    records = ledger.get("records") or []
    scope_records = [r for r in records if r.get("dimension_id") == "D03"]
    if any(r.get("primary_label") != "Not_Analyzed_Out_Of_Scope" for r in scope_records):
        raise ValueError("D03 may only be present as a Not_Analyzed_Out_Of_Scope status record")
    active_records = [r for r in records if r.get("dimension_id") != "D03"]
    validate_complete_pilot_doc_ids(ledger.get("document_ids"))
    if not active_records or any(r.get("record_origin") != "v1.2_local_api_model_run" for r in active_records):
        raise ValueError("Legacy-carried or same-session static records are not accepted as a local-run Step 6 input")
    # D03 may be present in the ledger solely as metadata, but is filtered out
    # before any model prompt is assembled.

    directions = schema.get("research_program", {}).get("candidate_gap_hypotheses_preserved") or []
    directions_by_id = {d.get("id"): d for d in directions}
    if set(directions_by_id) != {"3-1", "4-1", "5-1"}:
        raise ValueError("Schema must contain exactly the three preserved candidate directions")
    rq_by_direction = {"3-1": "RQ1", "4-1": "RQ2", "5-1": "RQ3"}
    selected = ["3-1", "4-1", "5-1"]

    evidence_by_id: dict[str, dict] = {}
    with evidence_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            eid = row.get("evidence_id")
            if not isinstance(eid, str) or eid in evidence_by_id:
                raise ValueError(f"Invalid/duplicate evidence_id at line {line_no}")
            evidence_by_id[eid] = row

    # Exclude D03 from all model input; it is a project scope status only.
    run_id = args.run_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise ValueError("run-id may contain only letters, digits, dot, underscore and hyphen")
    output_root = args.output_root.expanduser().resolve()
    run_dir = output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing Step 6 run directory: {run_dir}")

    load_simple_env(args.env_file.expanduser().resolve())
    if args.dry_run:
        cfg = LocalEndpointConfig("AgentA", "dry_run", "N/A", "dry-run-stub")
    else:
        cfg = LocalEndpointConfig.from_env("AgentA", allow_private_network=args.allow_private_network)
        if cfg.provider == "dry_run":
            raise SystemExit("No model call configured. Use --dry-run for explicit non-data placeholders or configure AGENT_A_PROVIDER= openai_compatible.")
    cfg.validate()

    tokenizer = None
    if args.tokenizer_path:
        try:
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers is required for --tokenizer-path") from exc
        tokenizer_path = args.tokenizer_path.expanduser().resolve()
        if not tokenizer_path.exists():
            raise FileNotFoundError(tokenizer_path)
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True, trust_remote_code=False)
    if args.require_token_preflight and not args.dry_run and (tokenizer is None or not args.context_limit):
        raise SystemExit("--require-token-preflight requires a local tokenizer path and positive --context-limit")
    if tokenizer is not None and (not args.context_limit or args.context_limit <= 0):
        raise ValueError("A positive --context-limit is required with --tokenizer-path")

    if cfg.provider == "dry_run" and not args.dry_run:
        raise SystemExit("Dry-run provider requires --dry-run; placeholder outputs must be explicit")

    output_root.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=False, exist_ok=False)
    manifest_path = run_dir / "model_call_manifest.jsonl"
    manifest_path.touch(exist_ok=False)
    config_record = {
        "run_id": run_id,
        "pipeline_version": "Step6-v1.2-local-evidence-challenge",
        "execution_mode": "dry_run_no_network" if args.dry_run else "local_api_only",
        "local_only": True,
        "endpoint": {"provider": cfg.provider, "base_url": cfg.base_url, "model": cfg.model,
                     "api_key": "[REDACTED]" if cfg.api_key else None,
                     "temperature": cfg.temperature, "max_tokens": cfg.max_tokens,
                     "request_timeout_s": cfg.request_timeout_s, "max_retries": cfg.max_retries},
        "ledger_path": str(ledger_path), "ledger_sha256": sha256_file(ledger_path),
        "evidence_blocks_path": str(evidence_path), "evidence_blocks_sha256": sha256_file(evidence_path),
        "schema_path": str(schema_path), "schema_sha256": sha256_file(schema_path),
        "system_prompt_sha256": sha256_bytes(SYSTEM_PROMPT.encode("utf-8")),
        "step6_script_sha256": sha256_file(Path(__file__).resolve()),
        "token_preflight": {"configured": tokenizer is not None and args.context_limit is not None,
                            "tokenizer_path": str(args.tokenizer_path.expanduser().resolve()) if args.tokenizer_path else None,
                            "context_limit": args.context_limit, "required": args.require_token_preflight},
        "formula_scope": "D03 and equation-type analysis excluded; source formula-risk metadata retained but formula interpretation prohibited",
        "candidate_direction_dimension_map": ACTIVE_DIMS,
        "adjudication_boundary": "All source records marked adjudication_required remain unresolved; no label is promoted by this synthesis.",
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_new_json(run_dir / "run_config_redacted.json", config_record)

    results = []
    errors = []
    for direction_id in selected:
        direction = directions_by_id[direction_id]
        dims = ACTIVE_DIMS[direction_id]
        payload = build_direction_payload(direction, rq_by_direction[direction_id], dims, active_records, evidence_by_id)
        user_prompt = json.dumps(payload, ensure_ascii=False)
        token_estimate = None
        if tokenizer is not None:
            token_estimate = len(tokenizer.encode(SYSTEM_PROMPT + "\n" + user_prompt, add_special_tokens=True)) + 256
            if token_estimate + cfg.max_tokens > args.context_limit:
                errors.append({"direction_id": direction_id, "error": f"token budget exceeded: input={token_estimate}, output={cfg.max_tokens}, limit={args.context_limit}"})
                continue
        elif not args.dry_run:
            print(f"[warning] {direction_id}: no tokenizer preflight; no input truncation is performed", file=sys.stderr)

        if args.dry_run:
            results.append({
                "direction_id": direction_id,
                "pilot_assessment": "unresolved",
                "pilot_limited_conclusion": "DRY RUN placeholder only; no model inference or evidence assessment was performed.",
                "supporting_evidence": [], "counterevidence": [],
                "unresolved_issues": ["Synthetic dry-run output; not a paper-level judgment."],
                "scope_limitations": ["No model call was made."],
                "status": "dry_run_placeholder_non_data",
            })
            continue

        last_errors: list[str] = []
        parsed_result = None
        for repair_index in range(2):
            request_prompt = user_prompt
            if last_errors:
                request_prompt += "\n\n[JSON/SCHEMA REPAIR] Correct these validation errors and return only the required JSON object: " + "; ".join(last_errors)
            try:
                response = call_llm(cfg, SYSTEM_PROMPT, request_prompt)
                try:
                    raw = extract_json(response.text)
                    parsed_result, validation_errors = validate_result(
                        raw, direction_id=direction_id, input_payload=payload, evidence_by_id=evidence_by_id,
                    )
                except Exception as exc:
                    parsed_result, validation_errors = None, [f"JSON parse/validation error: {type(exc).__name__}: {exc}"]
                entry = {
                    "run_id": run_id,
                    "call_id": f"MC-{run_id}-Step6-{direction_id}-{repair_index}-{uuid.uuid4().hex[:8]}",
                    "direction_id": direction_id,
                    "execution_channel": response.execution_channel,
                    "local_only_mode": True,
                    "provider": response.provider,
                    "model_name": response.model_name,
                    "model_version": response.model_version,
                    "endpoint": response.endpoint,
                    "system_prompt_sha256": sha256_bytes(SYSTEM_PROMPT.encode("utf-8")),
                    "user_prompt_sha256": sha256_bytes(request_prompt.encode("utf-8")),
                    "input_evidence_ids": payload["input_evidence_ids"],
                    "input_sha256": sha256_bytes(stable_json(payload).encode("utf-8")),
                    "output_sha256": sha256_bytes(response.text.encode("utf-8")),
                    "temperature": response.temperature,
                    "input_tokens_reported": response.input_tokens,
                    "output_tokens_reported": response.output_tokens,
                    "input_tokens_local_estimate": token_estimate,
                    "latency_s": round(response.latency_s, 3),
                    "retry_count": response.retry_count,
                    "finish_reason": response.finish_reason,
                    "repair_index": repair_index,
                    "validation_errors": validation_errors,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "review_status": "local_llm_preliminary_not_independent_human_adjudication",
                }
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                if response.finish_reason in ("length", "max_tokens"):
                    validation_errors = ["model response ended with finish_reason=length"]
                    parsed_result = None
                if parsed_result is not None:
                    parsed_result["status"] = "preliminary_local_model_evidence_challenge_not_final"
                    parsed_result["source_record_provenance"] = sorted({
                        r.get("record_origin", "unknown") for r in payload["records"]
                    })
                    parsed_result["unresolved_record_keys"] = [
                        f"{r['doc_id']}:{r['dimension_id']}" for r in payload["records"]
                        if r.get("verification_status") == "adjudication_required"
                    ]
                    results.append(parsed_result)
                    break
                last_errors = validation_errors
            except LLMCallError as exc:
                last_errors = [f"local API call failed: {exc}"]
                break
        if parsed_result is None:
            errors.append({"direction_id": direction_id, "errors": last_errors})

    summary = {
        "run_id": run_id,
        "pipeline_version": config_record["pipeline_version"],
        "execution_mode": config_record["execution_mode"],
        "directions_requested": len(selected),
        "directions_completed": len(results),
        "directions_failed": len(errors),
        "results": results,
        "errors": errors,
        "output_dir": str(run_dir),
        "scope_notice": "The three manuscript-introduction candidates are tested, not re-generated. N=5 pilot only; no field-wide conclusion or independent human adjudication.",
    }
    atomic_new_json(run_dir / "run_summary.json", summary)
    for result in results:
        safe_id = result["direction_id"].replace("-", "_")
        atomic_new_json(run_dir / f"direction_{safe_id}.json", result)
    print(f"Step 6 run directory: {run_dir}")
    print(f"Completed {len(results)}/{len(selected)} direction(s); failed={len(errors)}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
