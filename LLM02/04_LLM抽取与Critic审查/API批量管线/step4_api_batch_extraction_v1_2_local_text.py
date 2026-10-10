#!/usr/bin/env python3
"""Versioned, local-only Step 4 runner for v1.2 text-scope extraction.

- D01/D02 and D04-D10 are model-extracted; D03 is emitted locally as a scope
  status and is never included in prompts.
- Uses only loopback/private OpenAI-compatible endpoints or explicit dry-run.
- Requires an explicit evidence-block file and versioned Step 3 index directory.
- Every run writes to a fresh run_id directory and refuses overwrite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parents[1]
SCHEMA_DEFAULT = PIPELINE_DIR.parent / "01_Prompt与Schema注册" / "schema_v1.2.json"
PROMPT_DEFAULT = PIPELINE_DIR / "agent_prompts_v1.2_local_text_scope.json"
DEFAULT_OUTPUT_ROOT = PIPELINE_DIR / "产出_v1.2_local_text_scope"
STEP3_DIR = PROJECT_ROOT / "03_证据索引与混合检索"
sys.path.insert(0, str(STEP3_DIR))

from llm_api_client_v1_2_local import (  # noqa: E402
    LLMCallError,
    LocalEndpointConfig,
    call_llm,
    list_models,
)
from step3_hybrid_retrieval_v1_2_local import LocalHybridIndex  # noqa: E402

ACTIVE_FALLBACKS = {"Not_Stated_In_Text", "Explicitly_Not_Considered", "Insufficient_Evidence", "Evidence_Unavailable"}
FORMULA_ONLY_LABEL = "Out_Of_Scope_Formula_Only"
UNRESOLVED_HUMAN_BOUNDARIES = {("B001-PDF-03", "D02"): "v1.2 D02 boundary has not been user-finalized"}
VALID_DECISIONS = {"accept", "revise", "reject", "insufficient_evidence"}
MAX_JSON_REPAIR_ATTEMPTS = 2


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_simple_env(path: Path) -> bool:
    """Load KEY=VALUE lines without overriding explicit shell environment."""
    if not path.exists():
        print(f"[env] no local env file at {path}; using shell variables/dry-run defaults")
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)
    print(f"[env] loaded simple local configuration from {path} (shell environment takes precedence)")
    return True


def load_schema(path: Path) -> dict:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if schema.get("schema_version") != "v1.2":
        raise ValueError(f"Expected schema_version v1.2, got {schema.get('schema_version')!r}")
    active = schema.get("active_analysis_dimensions") or []
    if "D03" in active or not active:
        raise ValueError("v1.2 schema must keep D03 outside active_analysis_dimensions")
    d03 = schema.get("dimensions", {}).get("D03", {})
    if d03.get("labels") != ["Not_Analyzed_Out_Of_Scope"]:
        raise ValueError("D03 must be a status-only Not_Analyzed_Out_Of_Scope dimension")
    if schema.get("formula_policy", {}).get("transcription_or_derivation_in_scope") is not False:
        raise ValueError("Schema formula policy does not exclude transcription/derivation")
    missing = [d for d in active if d not in schema.get("dimensions", {})]
    if missing:
        raise ValueError(f"Active dimensions missing from schema: {missing}")
    expected = {"D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09", "D10"}
    if set(active) != expected:
        raise ValueError(f"Unexpected v1.2 active dimension set: {active}")
    # Formula-only fallback metadata is retained in the source schema, but it is
    # deliberately withheld from the active model task and result labels.
    schema["model_fallback_states"] = [
        label for label in schema.get("fallback_states", []) if label != FORMULA_ONLY_LABEL
    ]
    if FORMULA_ONLY_LABEL in schema["model_fallback_states"]:
        raise ValueError("Formula-only fallback must not enter the v1.2 text-only model schema")
    return schema


def load_prompts(path: Path) -> dict:
    prompts = json.loads(path.read_text(encoding="utf-8"))
    if prompts.get("schema_version") != "v1.2":
        raise ValueError("Prompt file must explicitly target schema v1.2")
    for k in ("agent_a_system_prompt", "agent_b_system_prompt", "prompt_version"):
        if not prompts.get(k):
            raise ValueError(f"Prompt file missing {k}")
    for k in ("agent_a_system_prompt", "agent_b_system_prompt"):
        text = prompts[k]
        if "D03" in text or "PDF-03" in text or FORMULA_ONLY_LABEL in text:
            raise ValueError(f"{k} contains a forbidden scope ID or formula-only label")
    # Scope metadata is local configuration and is never passed to call_json.
    scope = prompts.get("scope", "")
    if "D03" in scope and "never sent" not in scope:
        raise ValueError("Prompt scope metadata must affirm D03 is not sent")
    return prompts


def extract_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def dimension_query(dim_id: str, dim: dict) -> str:
    labels = " ".join(str(x).replace("_", " ").lower() for x in dim.get("labels", []))
    return f"{dim.get('name', dim_id)} {labels}"


def prompt_blocks(blocks: list[dict]) -> list[dict]:
    """Expose only text/provenance and the risk flag; never expose equation_detail."""
    return [
        {
            "evidence_id": b["evidence_id"],
            "zone": b.get("zone"),
            "section_id": b.get("section_id"),
            "page_numbers": b.get("page_numbers"),
            "formula_layout_risk": bool(b.get("formula_layout_risk", False)),
            "text": b.get("text", ""),
        }
        for b in blocks
    ]


def build_context(index: LocalHybridIndex, doc_id: str, schema: dict) -> dict:
    ids = index.coverage_pass_ids(doc_id)
    if not ids:
        raise ValueError(f"No evidence blocks found for doc_id={doc_id!r}")
    blocks = [index.by_id[eid] for eid in ids]
    active = schema["active_analysis_dimensions"]
    hits = {}
    for dim_id in active:
        dim = schema["dimensions"][dim_id]
        result = index.hybrid_search(dimension_query(dim_id, dim))["fused_top"]
        hits[dim_id] = [eid for eid, _score in result if eid in index.by_id and index.by_id[eid]["doc_id"] == doc_id]
    return {"evidence_blocks": blocks, "dimension_retrieval_hits": hits}


def normalize_quote(s: str) -> str:
    s = s.replace(chr(0x00AD), "")
    s = re.sub(r"-\s*\n\s*", "", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def derive_source_locations(eids: list[str], by_id: dict) -> tuple[Any, list[int]]:
    sections = []
    pages = set()
    for eid in eids:
        row = by_id[eid]
        section = row.get("section_id")
        if section is not None and section not in sections:
            sections.append(section)
        pages.update(p for p in (row.get("page_numbers") or []) if isinstance(p, int))
    section_value = sections[0] if len(sections) == 1 else sections or None
    return section_value, sorted(pages)


def validate_agent_a_records(raw: Any, *, expected_dims: list[str], schema: dict,
                             by_id: dict, doc_id: str, dry_run: bool = False) -> tuple[dict[str, dict], dict[str, list[str]]]:
    warnings: dict[str, list[str]] = {}
    cleaned: dict[str, dict] = {}
    if not isinstance(raw, list):
        return {}, {"_document": ["Agent A response must be a JSON array"]}
    seen = []
    for pos, item in enumerate(raw):
        if not isinstance(item, dict):
            warnings.setdefault("_document", []).append(f"record[{pos}] is not an object")
            continue
        rec = dict(item)
        dim_id = rec.get("dimension_id")
        if dim_id not in expected_dims:
            warnings.setdefault("_document", []).append(f"unexpected/forbidden dimension_id {dim_id!r}; record ignored")
            continue
        if dim_id in cleaned:
            warnings.setdefault(dim_id, []).append("duplicate dimension record")
            continue
        seen.append(dim_id)
        dim = schema["dimensions"][dim_id]
        allowed = set(dim.get("labels", [])) | set(schema.get("model_fallback_states", schema.get("fallback_states", [])))
        label = rec.get("primary_label")
        if not isinstance(label, str) or label not in allowed:
            warnings.setdefault(dim_id, []).append(f"primary_label is not in schema: {label!r}; sanitized to Insufficient_Evidence")
            label = "Insufficient_Evidence"
        second = rec.get("secondary_labels") or []
        if isinstance(second, str):
            second = [second]
            warnings.setdefault(dim_id, []).append("secondary_labels returned as string; normalized to one-item list")
        if not isinstance(second, list) or any(not isinstance(x, str) or x not in dim.get("labels", []) for x in second):
            warnings.setdefault(dim_id, []).append("secondary_labels contain invalid values")
            second = [x for x in second if isinstance(x, str) and x in dim.get("labels", [])] if isinstance(second, list) else []
        eids = rec.get("evidence_ids") or []
        if isinstance(eids, str):
            eids = [eids]
            warnings.setdefault(dim_id, []).append("evidence_ids returned as string; normalized to one-item list")
        if not isinstance(eids, list) or any(not isinstance(x, str) for x in eids):
            warnings.setdefault(dim_id, []).append("evidence_ids must be a list of strings")
            eids = [x for x in eids if isinstance(x, str)] if isinstance(eids, list) else []
        eids = list(dict.fromkeys(eids))
        quote = rec.get("verbatim_quote") or ""
        if not isinstance(quote, str):
            warnings.setdefault(dim_id, []).append("verbatim_quote must be a string")
            quote = ""
        if not dry_run:
            valid_eids = []
            for eid in eids:
                if eid not in by_id:
                    warnings.setdefault(dim_id, []).append(f"unknown evidence_id {eid!r}")
                elif by_id[eid].get("doc_id") != doc_id:
                    warnings.setdefault(dim_id, []).append(f"evidence_id {eid!r} belongs to another doc_id")
                else:
                    valid_eids.append(eid)
            eids = valid_eids
            no_quote_states = ACTIVE_FALLBACKS
            if label not in no_quote_states and not eids:
                warnings.setdefault(dim_id, []).append("evidence_ids required for this label")
            if label not in no_quote_states and not quote:
                warnings.setdefault(dim_id, []).append("verbatim_quote required for this label")
            if quote and eids:
                cited_text = " ".join(by_id[eid].get("text", "") for eid in eids if eid in by_id and by_id[eid].get("doc_id") == doc_id)
                if normalize_quote(quote) not in normalize_quote(cited_text):
                    warnings.setdefault(dim_id, []).append("verbatim_quote was not found in the cited block text after whitespace/hyphen normalization")
        confidence = rec.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            warnings.setdefault(dim_id, []).append(f"confidence outside [0,1]: {confidence!r}")
            confidence = 0.0
        own = rec.get("own_method_vs_cited")
        if own not in schema.get("own_method_vs_cited_values", []):
            if label not in ACTIVE_FALLBACKS:
                warnings.setdefault(dim_id, []).append(f"own_method_vs_cited invalid: {own!r}")
        mechanism = rec.get("mechanism_judgment")
        if not isinstance(mechanism, str) or not mechanism.strip():
            warnings.setdefault(dim_id, []).append("mechanism_judgment missing")
            mechanism = ""
        # Do not persist any non-null equation_detail value if a model violates scope.
        eq_value = rec.get("equation_detail")
        if eq_value not in (None, {}, []):
            warnings.setdefault(dim_id, []).append("non-null equation_detail discarded under v1.2 scope policy")
        rec.pop("equation_detail", None)
        section_id, page_numbers = derive_source_locations([e for e in eids if e in by_id and by_id[e].get("doc_id") == doc_id], by_id)
        cleaned[dim_id] = {
            "dimension_id": dim_id,
            "primary_label": label,
            "secondary_labels": second,
            "own_method_vs_cited": own,
            "mechanism_judgment": mechanism,
            "uncertainty_note": str(rec.get("uncertainty_note") or ""),
            "evidence_ids": eids,
            "verbatim_quote": quote,
            "equation_detail": None,
            "confidence": confidence,
            "section_id": section_id,
            "page_numbers": page_numbers,
        }
    for dim_id in expected_dims:
        if dim_id not in cleaned:
            warnings.setdefault(dim_id, []).append("missing dimension record")
    if len(raw) != len(expected_dims):
        warnings.setdefault("_document", []).append(f"expected {len(expected_dims)} records, received {len(raw)}")
    return cleaned, warnings


def validate_agent_b(raw: Any, *, expected_dims: list[str], schema: dict, by_id: dict,
                     doc_id: str, dry_run: bool = False) -> tuple[dict[str, dict], dict[str, list[str]]]:
    warnings: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return {}, {"_document": ["Agent B response must be a JSON object"]}
    out = {}
    labels = {d: set(schema["dimensions"][d].get("labels", [])) for d in expected_dims}
    for dim_id in expected_dims:
        dec = raw.get(dim_id)
        if not isinstance(dec, dict):
            warnings.setdefault(dim_id, []).append("Agent B decision missing/invalid")
            out[dim_id] = {
                "decision": "insufficient_evidence", "corrected_label": None,
                "critic_comment": "No valid Agent B decision returned; human adjudication required.",
                "supporting_evidence_ids": [], "contradicting_evidence_ids": [],
                "confidence": 0.0, "checks_failed": ["missing_decision"],
            }
            continue
        decision = dec.get("decision")
        if decision not in VALID_DECISIONS:
            warnings.setdefault(dim_id, []).append(f"invalid decision {decision!r}")
            decision = "insufficient_evidence"
        corrected = dec.get("corrected_label")
        if decision == "revise" and corrected not in (labels[dim_id] | set(schema.get("model_fallback_states", schema.get("fallback_states", [])))):
            warnings.setdefault(dim_id, []).append(f"invalid corrected_label {corrected!r}")
            decision = "insufficient_evidence"
            corrected = None
        ids = []
        for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
            vals = dec.get(field) or []
            if isinstance(vals, str):
                vals = [vals]
            if not isinstance(vals, list):
                warnings.setdefault(dim_id, []).append(f"{field} must be an array")
                vals = []
            valid = []
            if not dry_run:
                for eid in vals:
                    if not isinstance(eid, str) or eid not in by_id or by_id[eid].get("doc_id") != doc_id:
                        warnings.setdefault(dim_id, []).append(f"invalid {field} item {eid!r}")
                    else:
                        valid.append(eid)
            else:
                valid = [e for e in vals if isinstance(e, str)]
            ids.append(valid)
        conf = dec.get("confidence", 0.0)
        if not isinstance(conf, (int, float)) or not 0 <= float(conf) <= 1:
            warnings.setdefault(dim_id, []).append("critic confidence outside [0,1]")
            conf = 0.0
        out[dim_id] = {
            "decision": decision,
            "corrected_label": corrected if decision == "revise" else None,
            "critic_comment": str(dec.get("critic_comment") or ""),
            "supporting_evidence_ids": ids[0],
            "contradicting_evidence_ids": ids[1],
            "confidence": float(conf),
            "checks_failed": dec.get("checks_failed") if isinstance(dec.get("checks_failed"), list) else [],
        }
    extras = sorted(set(raw) - set(expected_dims))
    missing = sorted(set(expected_dims) - set(raw))
    if extras:
        warnings.setdefault("_document", []).append(f"unexpected Agent B dimension keys: {extras}")
    if missing:
        warnings.setdefault("_document", []).append(f"missing Agent B dimension keys: {missing}")
    return out, warnings


def load_tokenizer(path: str | None):
    if not path:
        return None
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Tokenizer path not found: {p}")
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("transformers is needed only when --tokenizer-path is used") from exc
    return AutoTokenizer.from_pretrained(str(p), local_files_only=True, trust_remote_code=False)


def prompt_token_count(tokenizer, system_prompt: str, user_prompt: str) -> int:
    text = system_prompt + "\n" + user_prompt
    # Reserve a conservative allowance for role/chat-template tokens not included here.
    return len(tokenizer.encode(text, add_special_tokens=True)) + 256


def check_prompt_budget(tokenizer, context_limit: int | None, cfg: LocalEndpointConfig,
                        system_prompt: str, user_prompt: str, *, strict: bool) -> int | None:
    if tokenizer is None:
        if strict and cfg.provider != "dry_run":
            raise RuntimeError(f"{cfg.agent_name}: --require-token-preflight needs a local tokenizer path")
        return None
    if context_limit is None or context_limit <= 0:
        raise ValueError(f"{cfg.agent_name}: tokenizer supplied without a valid context limit")
    n = prompt_token_count(tokenizer, system_prompt, user_prompt)
    if n + cfg.max_tokens > context_limit:
        raise ValueError(
            f"{cfg.agent_name} prompt budget exceeded: input={n}, max_output={cfg.max_tokens}, "
            f"context_limit={context_limit}; no truncation is performed"
        )
    return n


def write_new_json(path: Path, obj: Any) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite output: {path}")
    temp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex[:8]}")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def append_manifest(path: Path, entry: dict) -> None:
    # The manifest is scoped to a unique, non-reusable run_id directory.
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def safe_json_hash(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def build_call_entry(*, run_id: str, doc_id: str, agent: str, pass_name: str,
                     prompt_version: str, schema_version: str, prompt: str,
                     user_prompt: str, evidence_ids: list[str], resp, repair_index: int,
                     token_estimate: int | None) -> dict:
    return {
        "run_id": run_id,
        "call_id": f"MC-{run_id}-{doc_id}-{agent}-{pass_name}-{uuid.uuid4().hex[:8]}",
        "doc_id": doc_id,
        "agent_name": agent,
        "pass": pass_name,
        "execution_channel": resp.execution_channel,
        "local_only_mode": True,
        "provider": resp.provider,
        "model_name": resp.model_name,
        "model_version": resp.model_version,
        "endpoint": resp.endpoint,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "system_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "user_prompt_sha256": sha256_bytes(user_prompt.encode("utf-8")),
        "input_sha256": safe_json_hash(evidence_ids),
        "input_evidence_ids": evidence_ids,
        "output_sha256": sha256_bytes(resp.text.encode("utf-8")),
        "temperature": resp.temperature,
        "input_tokens_reported": resp.input_tokens,
        "output_tokens_reported": resp.output_tokens,
        "input_tokens_local_estimate": token_estimate,
        "latency_s": round(resp.latency_s, 3),
        "http_retry_count": resp.retry_count,
        "json_repair_index": repair_index,
        "finish_reason": resp.finish_reason,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "human_or_agent_reviewed": "local_api_agent_only_not_human_adjudication",
    }


def call_json(cfg: LocalEndpointConfig, system_prompt: str, payload: dict, *, expect: str,
              run_id: str, doc_id: str, agent: str, pass_name: str,
              prompt_version: str, schema_version: str, evidence_ids: list[str],
              manifest_path: Path, tokenizer=None, context_limit: int | None = None,
              require_token_preflight: bool = False) -> tuple[Any, Any]:
    user_prompt = json.dumps(payload, ensure_ascii=False)
    last_error = None
    for repair_index in range(MAX_JSON_REPAIR_ATTEMPTS + 1):
        if last_error:
            request_text = user_prompt + (
                f"\n\n[JSON REPAIR] Previous response was invalid ({last_error}). "
                f"Return only a valid JSON {expect}; do not add prose or markdown."
            )
        else:
            request_text = user_prompt
        token_estimate = check_prompt_budget(
            tokenizer, context_limit, cfg, system_prompt, request_text,
            strict=require_token_preflight,
        )
        resp = call_llm(cfg, system_prompt, request_text)
        entry = build_call_entry(
            run_id=run_id, doc_id=doc_id, agent=agent, pass_name=pass_name,
            prompt_version=prompt_version, schema_version=schema_version,
            prompt=system_prompt, user_prompt=request_text, evidence_ids=evidence_ids,
            resp=resp, repair_index=repair_index, token_estimate=token_estimate,
        )
        append_manifest(manifest_path, entry)
        resp.call_id = entry["call_id"]
        if resp.finish_reason in ("length", "max_tokens"):
            last_error = "model response ended with finish_reason=length"
            continue
        try:
            parsed = extract_json(resp.text)
            if expect == "array" and not isinstance(parsed, list):
                raise ValueError("top-level JSON value must be an array")
            if expect == "object" and not isinstance(parsed, dict):
                raise ValueError("top-level JSON value must be an object")
            return parsed, resp
        except Exception as exc:
            last_error = str(exc)
    raise LLMCallError(f"{agent} {pass_name}: valid JSON {expect} not returned after repairs: {last_error}")


def build_scope_status_record(doc_id: str, schema_version: str, run_id: str) -> dict:
    return {
        "doc_id": doc_id,
        "dimension_id": "D03",
        "schema_version": schema_version,
        "primary_label": "Not_Analyzed_Out_Of_Scope",
        "secondary_labels": [],
        "own_method_vs_cited": None,
        "mechanism_judgment": "D03 is excluded by project scope; this status is not a finding about the paper.",
        "uncertainty_note": "No equation-type analysis was performed; this does not imply that equations are absent.",
        "evidence_ids": [],
        "verbatim_quote": "",
        "section_id": None,
        "page_numbers": [],
        "equation_detail": None,
        "confidence": None,
        "agent_a_model_call_id": None,
        "agent_b_review": None,
        "verification_status": "scope_status_not_a_paper_finding",
        "record_status": "scope_status_not_a_paper_finding",
        "record_origin": "v1.2_local_pipeline_generated_status_no_model_call",
        "execution_channel": "local_scope_status_no_model_call",
        "result_scope_version": "v1.2_local_text_scope_preliminary",
        "run_id": run_id,
    }


def build_model_dimensions_schema(schema: dict, dimension_ids: list[str], doc_id: str) -> dict:
    """Create the model-facing schema without exposing an unapproved D02 boundary rule.

    The source schema remains unchanged and its hash is recorded. For the known
    PDF-03/D02 boundary, even the general interpretation note is withheld and
    replaced with a neutral adjudication notice; the pipeline still records a
    candidate label, but it can never be promoted to a final decision.
    """
    dimensions = {d: dict(schema["dimensions"][d]) for d in dimension_ids}
    d02 = dimensions.get("D02")
    if d02 is not None:
        d02.pop("boundary_rule", None)
        if (doc_id, "D02") in UNRESOLVED_HUMAN_BOUNDARIES:
            d02.pop("interpretation_note", None)
            d02["adjudication_note"] = (
                "This document's D02 construct boundary has not been finalized by the user. "
                "Do not infer or treat any candidate label as approved; state uncertainty and require human adjudication."
            )
    return dimensions


def make_agent_payload(doc_id: str, schema: dict, blocks: list[dict], hits: dict,
                       *, mode: str, records: dict | None = None,
                       feedback: dict | None = None) -> dict:
    payload = {
        "doc_id": doc_id,
        "mode": mode,
        "dimensions_schema": schema["dimensions"],
        "fallback_states": schema.get("model_fallback_states", [x for x in schema["fallback_states"] if x != FORMULA_ONLY_LABEL]),
        "own_method_vs_cited_values": schema["own_method_vs_cited_values"],
        "evidence_blocks_coverage_pass": prompt_blocks(blocks),
        "dimension_retrieval_hits_top10": hits,
    }
    if records is not None:
        payload["original_records"] = records
        payload["critic_feedback"] = feedback or {}
    return payload


def add_common_fields(rec: dict, *, doc_id: str, schema_version: str,
                      call_id: str, by_id: dict, execution_channel: str,
                      run_id: str) -> dict:
    out = dict(rec)
    out["doc_id"] = doc_id
    out["schema_version"] = schema_version
    out["agent_a_model_call_id"] = call_id
    out["execution_channel"] = execution_channel
    out["result_scope_version"] = "v1.2_local_text_scope_preliminary"
    eids = [e for e in out.get("evidence_ids", []) if e in by_id and by_id[e].get("doc_id") == doc_id]
    out["section_id"], out["page_numbers"] = derive_source_locations(eids, by_id)
    out["equation_detail"] = None
    out["run_id"] = run_id
    return out


def save_warnings(path: Path, warnings: dict) -> None:
    if warnings:
        write_new_json(path, warnings)


def process_document(*, doc_id: str, index: LocalHybridIndex, schema: dict, prompts: dict,
                     cfg_a: LocalEndpointConfig, cfg_b: LocalEndpointConfig,
                     run_id: str, run_dir: Path, tokenizer_a=None, tokenizer_b=None,
                     context_limit_a: int | None = None, context_limit_b: int | None = None,
                     require_token_preflight: bool = False) -> dict:
    ctx = build_context(index, doc_id, schema)
    blocks = ctx["evidence_blocks"]
    hits = ctx["dimension_retrieval_hits"]
    by_id = index.by_id
    active = schema["active_analysis_dimensions"]
    dry = cfg_a.provider == "dry_run" and cfg_b.provider == "dry_run"
    evidence_ids = [b["evidence_id"] for b in blocks]
    out_a = run_dir / "03_AgentA原始抽取"
    out_b = run_dir / "04_AgentB_Critic审查"
    out_v = run_dir / "05_核验通过结果"
    out_scope = run_dir / "06_范围状态_D03"
    manifest_path = run_dir / "02_模型调用日志" / "model_call_manifest.jsonl"
    for p in (out_a, out_b, out_v, out_scope, manifest_path.parent):
        p.mkdir(parents=True, exist_ok=True)

    dim_schema = build_model_dimensions_schema(schema, active, doc_id)
    a_prompt = prompts["agent_a_system_prompt"]
    b_prompt = prompts["agent_b_system_prompt"]
    call_id_a1 = f"MC-{run_id}-{doc_id}-AgentA-pass1"
    a_payload = make_agent_payload(
        doc_id, {**schema, "dimensions": dim_schema}, blocks, hits,
        mode="pass1_initial_extraction",
    )
    raw_a, resp_a1 = call_json(
        cfg_a, a_prompt, a_payload, expect="array", run_id=run_id, doc_id=doc_id,
        agent="AgentA", pass_name="pass1_initial_extraction",
        prompt_version=prompts["prompt_version"], schema_version=schema["schema_version"],
        evidence_ids=evidence_ids, manifest_path=manifest_path,
        tokenizer=tokenizer_a, context_limit=context_limit_a,
        require_token_preflight=require_token_preflight,
    )
    call_id_a1 = resp_a1.call_id or call_id_a1
    a_records, a_warnings = validate_agent_a_records(
        raw_a, expected_dims=active, schema=schema, by_id=by_id, doc_id=doc_id, dry_run=dry,
    )
    enriched_a = {
        d: add_common_fields(r, doc_id=doc_id, schema_version=schema["schema_version"],
                             call_id=call_id_a1, by_id=by_id,
                             execution_channel=resp_a1.execution_channel, run_id=run_id)
        for d, r in a_records.items()
    }
    save_warnings(out_a / f"{doc_id}_pass1_VALIDATION_WARNINGS.json", a_warnings)
    write_new_json(out_a / f"{doc_id}_pass1.json", list(enriched_a.values()))

    b2_payload = make_agent_payload(
        doc_id, {**schema, "dimensions": dim_schema}, blocks, hits,
        mode="pass2_initial_critic",
    )
    b2_payload["agent_a_structured_output"] = list(enriched_a.values())
    raw_b2, resp_b2 = call_json(
        cfg_b, b_prompt, b2_payload, expect="object", run_id=run_id, doc_id=doc_id,
        agent="AgentB", pass_name="pass2_initial_critic",
        prompt_version=prompts["prompt_version"], schema_version=schema["schema_version"],
        evidence_ids=evidence_ids, manifest_path=manifest_path,
        tokenizer=tokenizer_b, context_limit=context_limit_b,
        require_token_preflight=require_token_preflight,
    )
    b2, b2_warnings = validate_agent_b(
        raw_b2, expected_dims=active, schema=schema, by_id=by_id, doc_id=doc_id, dry_run=dry,
    )
    save_warnings(out_b / f"{doc_id}_pass2_VALIDATION_WARNINGS.json", b2_warnings)
    write_new_json(out_b / f"{doc_id}_pass2.json", b2)

    revise_dims = [d for d in active if b2.get(d, {}).get("decision") in ("revise", "reject")]
    revised: dict[str, dict] = {}
    b4: dict[str, dict] = {}
    b4_warnings: dict = {}
    if revise_dims:
        revision_schema = {d: dim_schema[d] for d in revise_dims}
        originals = {d: enriched_a[d] for d in revise_dims if d in enriched_a}
        feedback = {d: b2[d].get("critic_comment", "") for d in revise_dims}
        call_id_a3 = f"MC-{run_id}-{doc_id}-AgentA-pass3"
        p3_payload = make_agent_payload(
            doc_id, {**schema, "dimensions": revision_schema}, blocks, hits,
            mode="pass3_revision_only", records=originals, feedback=feedback,
        )
        raw_a3, resp_a3 = call_json(
            cfg_a, a_prompt, p3_payload, expect="array", run_id=run_id, doc_id=doc_id,
            agent="AgentA", pass_name="pass3_revision_only",
            prompt_version=prompts["prompt_version"], schema_version=schema["schema_version"],
            evidence_ids=evidence_ids, manifest_path=manifest_path,
            tokenizer=tokenizer_a, context_limit=context_limit_a,
            require_token_preflight=require_token_preflight,
        )
        call_id_a3 = resp_a3.call_id or call_id_a3
        revised, a3_warnings = validate_agent_a_records(
            raw_a3, expected_dims=revise_dims, schema=schema, by_id=by_id, doc_id=doc_id, dry_run=dry,
        )
        revised = {
            d: add_common_fields(r, doc_id=doc_id, schema_version=schema["schema_version"],
                                 call_id=call_id_a3, by_id=by_id,
                                 execution_channel=resp_a3.execution_channel, run_id=run_id)
            for d, r in revised.items()
        }
        save_warnings(out_a / f"{doc_id}_pass3_VALIDATION_WARNINGS.json", a3_warnings)
        write_new_json(out_a / f"{doc_id}_pass3_revisions.json", list(revised.values()))

        if revised:
            final_schema = {d: dim_schema[d] for d in revised}
            p4_payload = make_agent_payload(
                doc_id, {**schema, "dimensions": final_schema}, blocks, hits,
                mode="pass4_final_review",
            )
            p4_payload["agent_a_structured_output"] = list(revised.values())
            raw_b4, resp_b4 = call_json(
                cfg_b, b_prompt, p4_payload, expect="object", run_id=run_id, doc_id=doc_id,
                agent="AgentB", pass_name="pass4_final_review",
                prompt_version=prompts["prompt_version"], schema_version=schema["schema_version"],
                evidence_ids=evidence_ids, manifest_path=manifest_path,
                tokenizer=tokenizer_b, context_limit=context_limit_b,
                require_token_preflight=require_token_preflight,
            )
            b4, b4_warnings = validate_agent_b(
                raw_b4, expected_dims=list(revised), schema=schema, by_id=by_id, doc_id=doc_id, dry_run=dry,
            )
            save_warnings(out_b / f"{doc_id}_pass4_VALIDATION_WARNINGS.json", b4_warnings)
            write_new_json(out_b / f"{doc_id}_pass4_final.json", b4)

    verified = []
    for dim_id in active:
        rec = dict(revised.get(dim_id) or enriched_a.get(dim_id) or {})
        if not rec:
            rec = {
                "dimension_id": dim_id,
                "primary_label": "Insufficient_Evidence",
                "secondary_labels": [],
                "own_method_vs_cited": None,
                "mechanism_judgment": "No valid Agent A record was returned; human review required.",
                "uncertainty_note": "Missing/invalid model output; no paper-level conclusion assigned.",
                "evidence_ids": [],
                "verbatim_quote": "",
                "equation_detail": None,
                "confidence": 0.0,
                "section_id": None,
                "page_numbers": [],
                "doc_id": doc_id,
                "schema_version": schema["schema_version"],
                "run_id": run_id,
                "result_scope_version": "v1.2_local_text_scope_preliminary",
            }
        initial_decision = b2.get(dim_id, {}).get("decision", "insufficient_evidence")
        final_decision = b4.get(dim_id, {}).get("decision") if dim_id in revised else None
        structural = (
            bool(a_warnings.get(dim_id)) or bool(a_warnings.get("_document"))
            or bool(b2_warnings.get(dim_id)) or bool(b2_warnings.get("_document"))
            or bool(b4_warnings.get(dim_id)) or bool(b4_warnings.get("_document"))
        )
        if dry:
            status = "dry_run_placeholder_non_data"
        elif initial_decision == "accept" and not structural:
            status = "accepted_pass1"
        elif initial_decision in ("revise", "reject") and final_decision == "accept" and not structural:
            status = "accepted_after_revision"
        else:
            status = "adjudication_required"
        unresolved_boundary = UNRESOLVED_HUMAN_BOUNDARIES.get((doc_id, dim_id))
        if unresolved_boundary and not dry:
            status = "adjudication_required"
        rec["agent_b_review"] = {
            "pass2_decision": initial_decision,
            "pass2_comment": b2.get(dim_id, {}).get("critic_comment", ""),
            "pass4_decision": final_decision,
            "pass4_comment": b4.get(dim_id, {}).get("critic_comment", "") if dim_id in b4 else None,
            "configured_model_pair_distinct": (cfg_a.provider, cfg_a.model) != (cfg_b.provider, cfg_b.model),
            "cross_model_independence": "not_established_from_configuration_alone",
            "review_note": "Agent-assisted review; not independent human adjudication.",
            "forced_human_adjudication_reason": unresolved_boundary,
        }
        rec["verification_status"] = status
        verified.append(rec)
    verified.sort(key=lambda r: r["dimension_id"])
    if len(verified) != len(active) or {r["dimension_id"] for r in verified} != set(active) or any(r["dimension_id"] == "D03" for r in verified):
        raise RuntimeError("Internal output invariant failed: active result must contain D01/D02/D04-D10 only")
    verified_path = out_v / f"{doc_id}_verified_v1.2_text_scope.json"
    scope_path = out_scope / f"{doc_id}_D03_scope_status_v1.2.json"
    write_new_json(verified_path, verified)
    write_new_json(scope_path, build_scope_status_record(doc_id, schema["schema_version"], run_id))
    return {
        "doc_id": doc_id,
        "status": "dry_run_placeholder_non_data" if dry else "completed_with_review_statuses",
        "active_dimensions": len(active),
        "scope_status_dimensions": ["D03"],
        "warnings": sum(len(v) for v in a_warnings.values()) + sum(len(v) for v in b2_warnings.values()) + sum(len(v) for v in b4_warnings.values()),
        "output": str(verified_path),
        "scope_status_output": str(scope_path),
    }


def run_id_default() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-blocks", default=None, help="Versioned Step 2 evidence_blocks.jsonl")
    p.add_argument("--index-dir", default=None, help="Versioned Step 3 index directory; never modified")
    grp = p.add_mutually_exclusive_group(required=False)
    grp.add_argument("--doc-ids", help="Comma-separated exact doc_ids")
    grp.add_argument("--all", action="store_true", help="Process every doc_id in the selected evidence file")
    p.add_argument("--schema-path", default=str(SCHEMA_DEFAULT))
    p.add_argument("--prompt-path", default=str(PROMPT_DEFAULT))
    p.add_argument("--env-file", default=str(PIPELINE_DIR / ".env.local"))
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--run-id", default=None, help="Must be unique; existing run directories are refused")
    p.add_argument("--dry-run", action="store_true", help="Force both agents to no-network placeholders")
    p.add_argument("--list-models", action="store_true", help="Query /models on the configured local endpoint(s)")
    p.add_argument("--allow-private-network", action="store_true", help="Allow private numeric IPs; loopback is preferred")
    p.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    p.add_argument("--embedding-cache-dir", default=None)
    p.add_argument("--tokenizer-path-agent-a", default=None, help="Local HF tokenizer directory for input-token preflight")
    p.add_argument("--tokenizer-path-agent-b", default=None)
    p.add_argument("--context-limit-agent-a", type=int, default=None)
    p.add_argument("--context-limit-agent-b", type=int, default=None)
    p.add_argument("--require-token-preflight", action="store_true", help="Fail real calls unless both local tokenizers/limits are supplied")
    args = p.parse_args()

    if not args.dry_run:
        load_simple_env(Path(args.env_file).expanduser().resolve())
    cfg_a = LocalEndpointConfig.from_env("AgentA", allow_private_network=args.allow_private_network)
    cfg_b = LocalEndpointConfig.from_env("AgentB", allow_private_network=args.allow_private_network)
    if args.dry_run:
        cfg_a = LocalEndpointConfig("AgentA", "dry_run", "N/A", "dry-run-stub")
        cfg_b = LocalEndpointConfig("AgentB", "dry_run", "N/A", "dry-run-stub")
    cfg_a.validate()
    cfg_b.validate()
    if (cfg_a.provider == "dry_run") != (cfg_b.provider == "dry_run"):
        raise SystemExit("Mixed dry_run/real agents are prohibited; configure both agents as local APIs or both as dry_run")
    effective_dry_run = cfg_a.provider == "dry_run" and cfg_b.provider == "dry_run"

    if args.list_models:
        for cfg in (cfg_a, cfg_b):
            print(f"--- {cfg.agent_name}: {cfg.provider} {cfg.base_url} model={cfg.model} ---")
            print(list_models(cfg))
        return 0
    if not args.evidence_blocks or not args.index_dir:
        p.error("--evidence-blocks and --index-dir are required unless --list-models is used")
    if not args.all and not args.doc_ids:
        p.error("one of --doc-ids or --all is required unless --list-models is used")

    schema_path = Path(args.schema_path).expanduser().resolve()
    prompt_path = Path(args.prompt_path).expanduser().resolve()
    evidence_path = Path(args.evidence_blocks).expanduser().resolve()
    index_dir = Path(args.index_dir).expanduser().resolve()
    schema = load_schema(schema_path)
    prompts = load_prompts(prompt_path)
    tokenizer_a = load_tokenizer(args.tokenizer_path_agent_a)
    tokenizer_b = load_tokenizer(args.tokenizer_path_agent_b)
    if args.require_token_preflight and not args.dry_run:
        for name, cfg, tok, lim in (
            ("AgentA", cfg_a, tokenizer_a, args.context_limit_agent_a),
            ("AgentB", cfg_b, tokenizer_b, args.context_limit_agent_b),
        ):
            if cfg.provider != "dry_run" and (tok is None or lim is None):
                raise SystemExit(f"--require-token-preflight needs tokenizer path and context limit for {name}")
    elif not args.dry_run and (tokenizer_a is None or tokenizer_b is None):
        print("[warning] tokenizer-level context preflight is not fully configured; no automatic truncation is performed")

    embedding_cache_dir = args.embedding_cache_dir or os.environ.get("FASTEMBED_CACHE_DIR") or None
    index = LocalHybridIndex(
        evidence_path, index_dir,
        embedding_model=args.embedding_model,
        embedding_cache_dir=embedding_cache_dir,
        local_files_only=True,
    )
    known = set(index.doc_ids())
    if args.all:
        doc_ids = index.doc_ids()
    else:
        doc_ids = [x.strip() for x in args.doc_ids.split(",") if x.strip()]
        if len(doc_ids) != len(set(doc_ids)):
            raise SystemExit("Duplicate doc_ids in --doc-ids")
        missing = sorted(set(doc_ids) - known)
        if missing:
            raise SystemExit(f"Unknown doc_ids for the selected versioned evidence/index inputs: {missing}")
    if not doc_ids:
        raise SystemExit("No documents to process")

    run_id = args.run_id or run_id_default()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise SystemExit("run-id may contain only letters, digits, dot, underscore and hyphen (1-80 chars)")
    output_root = Path(args.output_root).expanduser().resolve()
    run_dir = output_root / run_id
    if run_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    for sub in ("03_AgentA原始抽取", "04_AgentB_Critic审查", "05_核验通过结果", "06_范围状态_D03", "02_模型调用日志"):
        (run_dir / sub).mkdir(parents=True, exist_ok=False)

    index_artifacts = ["bm25_index.pkl", "bm25_evidence_ids.json", "dense_embeddings.npy", "dense_evidence_ids.json"]
    index_hashes = {name: sha256_file(index_dir / name) for name in index_artifacts}
    if (index_dir / "index_build_manifest.json").is_file():
        index_hashes["index_build_manifest.json"] = sha256_file(index_dir / "index_build_manifest.json")
    evidence_lineage_hashes = {
        name: sha256_file(evidence_path.parent / name)
        for name in ("step2_run_manifest.json", "chunking_manifest.json")
        if (evidence_path.parent / name).is_file()
    }
    config_record = {
        "run_id": run_id,
        "pipeline_version": "Step4-v1.2-local-text-scope",
        "pipeline_code_sha256": {
            "step4_orchestrator": sha256_file(Path(__file__).resolve()),
            "local_api_client": sha256_file(PIPELINE_DIR / "llm_api_client_v1_2_local.py"),
            "step3_local_retrieval": sha256_file(STEP3_DIR / "step3_hybrid_retrieval_v1_2_local.py"),
        },
        "schema_version": schema["schema_version"],
        "prompt_version": prompts["prompt_version"],
        "execution_mode": "dry_run_no_network" if effective_dry_run else "local_api_only",
        "local_only": True,
        "allow_private_network": args.allow_private_network,
        "endpoint_a": {
            "provider": cfg_a.provider, "base_url": cfg_a.base_url, "model": cfg_a.model,
            "api_key": "[REDACTED]" if cfg_a.api_key else None,
            "temperature": cfg_a.temperature, "max_tokens": cfg_a.max_tokens,
            "request_timeout_s": cfg_a.request_timeout_s, "max_retries": cfg_a.max_retries,
        },
        "endpoint_b": {
            "provider": cfg_b.provider, "base_url": cfg_b.base_url, "model": cfg_b.model,
            "api_key": "[REDACTED]" if cfg_b.api_key else None,
            "temperature": cfg_b.temperature, "max_tokens": cfg_b.max_tokens,
            "request_timeout_s": cfg_b.request_timeout_s, "max_retries": cfg_b.max_retries,
        },
        "evidence_blocks_path": str(evidence_path),
        "evidence_blocks_sha256": sha256_file(evidence_path),
        "evidence_lineage_manifest_sha256": evidence_lineage_hashes,
        "index_dir": str(index_dir),
        "index_artifact_sha256": index_hashes,
        "schema_path": str(schema_path),
        "schema_sha256": sha256_file(schema_path),
        "model_schema_policy": {
            "source_schema_immutable": True,
            "D02_boundary_rule_sent_to_model": False,
            "B001-PDF-03_D02_interpretation_note_sent": False,
            "B001-PDF-03_D02_adjudication_notice_sent": True,
            "note": "The source schema is preserved and hashed; the model-facing copy withholds the unapproved boundary rule, and PDF-03/D02 remains adjudication_required.",
        },
        "prompt_path": str(prompt_path),
        "prompt_sha256": sha256_file(prompt_path),
        "embedding_model": args.embedding_model,
        "embedding_cache_dir": str(Path(embedding_cache_dir).expanduser().resolve()) if embedding_cache_dir else None,
        "doc_ids": doc_ids,
        "formula_scope": "D03 not sent to models; formula-only fallback withheld from active model schema; equation details excluded",
        "forced_human_adjudication_boundaries": {
            f"{doc_id}:{dim_id}": reason
            for (doc_id, dim_id), reason in UNRESOLVED_HUMAN_BOUNDARIES.items()
            if doc_id in doc_ids
        },
        "token_preflight": {
            "agent_a": {
                "configured": tokenizer_a is not None and args.context_limit_agent_a is not None,
                "tokenizer_path": str(Path(args.tokenizer_path_agent_a).expanduser().resolve()) if args.tokenizer_path_agent_a else None,
                "context_limit": args.context_limit_agent_a,
                "max_output_tokens": cfg_a.max_tokens,
            },
            "agent_b": {
                "configured": tokenizer_b is not None and args.context_limit_agent_b is not None,
                "tokenizer_path": str(Path(args.tokenizer_path_agent_b).expanduser().resolve()) if args.tokenizer_path_agent_b else None,
                "context_limit": args.context_limit_agent_b,
                "max_output_tokens": cfg_b.max_tokens,
            },
            "required": args.require_token_preflight,
        },
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_new_json(run_dir / "run_config_redacted.json", config_record)
    manifest_path = run_dir / "02_模型调用日志" / "model_call_manifest.jsonl"
    manifest_path.touch(exist_ok=False)

    results, errors = [], []
    for doc_id in doc_ids:
        print(f"[{doc_id}] local v1.2 text-scope processing; A={cfg_a.provider}/{cfg_a.model}; B={cfg_b.provider}/{cfg_b.model}")
        try:
            result = process_document(
                doc_id=doc_id, index=index, schema=schema, prompts=prompts,
                cfg_a=cfg_a, cfg_b=cfg_b, run_id=run_id, run_dir=run_dir,
                tokenizer_a=tokenizer_a, tokenizer_b=tokenizer_b,
                context_limit_a=args.context_limit_agent_a, context_limit_b=args.context_limit_agent_b,
                require_token_preflight=args.require_token_preflight,
            )
            results.append(result)
        except Exception as exc:
            print(f"[{doc_id}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            errors.append({"doc_id": doc_id, "error_type": type(exc).__name__, "error": str(exc)})
    summary = {
        "run_id": run_id,
        "pipeline_version": "Step4-v1.2-local-text-scope",
        "execution_mode": config_record["execution_mode"],
        "documents_requested": len(doc_ids),
        "documents_completed": len(results),
        "documents_failed": len(errors),
        "results": results,
        "errors": errors,
        "output_dir": str(run_dir),
        "scope_notice": "D03 is a status-only record; not a paper finding. Agent review is not independent human adjudication.",
    }
    write_new_json(run_dir / "run_summary.json", summary)
    print(f"Run directory: {run_dir}")
    print(f"Completed {len(results)}/{len(doc_ids)} document(s); failed={len(errors)}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
