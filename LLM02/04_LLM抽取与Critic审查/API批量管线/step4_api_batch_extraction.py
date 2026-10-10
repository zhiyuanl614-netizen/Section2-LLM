#!/usr/bin/env python3
"""Step 4 batch extraction via REAL external LLM APIs, wired from Stage 03.

Why this file exists (user decision, 2026-10-06): the existing
`step4_pilot_extraction.py` records the Arena.ai Agent's own in-session
reasoning (execution_channel="arena_agent_mode_in_session"); that path
cannot scale to batch/large-corpus work and is bounded to the 5 pilot PDFs
already processed by hand. This script is the batch-scale replacement
interface: it reuses Stage 03's locked `HybridIndex` (coverage pass +
hybrid retrieval, see model_and_retrieval_config_v1_LOCKED.md) to assemble
per-document, per-dimension context, then drives the SAME frozen Agent A /
Agent B prompts and A+B+A+B protocol (agent_prompts_and_manifest_v1_LOCKED.md)
against configurable external LLM endpoints via llm_api_client.py.

SAFETY / NON-DESTRUCTION GUARANTEES
------------------------------------
- This script NEVER reads from or writes into `05_核验通过结果/` (the 50
  existing v1.0 in-session-verified records) or any other original Step 4
  output directory. All of its output goes under this folder's own
  `产出/` subtree, clearly separated, so nothing produced here can silently
  overwrite or get confused with the in-session results.
- Default provider for both agents is "dry_run" (see llm_api_client.py) --
  running this script with no environment configuration is always safe and
  produces clearly-tagged placeholder output, never fabricated "real" data.
- Every manifest entry honestly records execution_channel="external_api_call"
  (vs "arena_agent_mode_in_session" for the pilot script, or
  "dry_run_no_network" when no credentials are configured), plus the real
  provider/model/version/endpoint/temperature/seed/token-usage/latency
  reported by the API -- finally replacing the pilot script's honest
  "not_exposed_by_execution_channel" placeholders with real values, IF real
  credentials are supplied.
- If AGENT_A_* and AGENT_B_* resolve to different provider+model pairs, the
  output explicitly records `cross_model_independence: true` in each
  verified record's `agent_b_review`, documenting that -- for API-run
  batches only -- the long-disclosed "same execution channel, not a true
  independent dual-model cross-check" limitation (see
  agent_prompts_and_manifest_v1_LOCKED.md section 0) no longer applies.

USAGE
-----
    cd 04_LLM抽取与Critic审查/API批量管线
    # macOS / Linux:
    cp .env.example .env   # fill in real keys, or leave as dry_run to test
    # Windows (cmd.exe):
    copy .env.example .env
    # Windows (PowerShell):
    Copy-Item .env.example .env

    # Then on ANY platform (no "source"/"set -a" step needed -- this script
    # loads ./.env itself via python-dotenv if it's present next to it):
    python3 step4_api_batch_extraction.py --doc-ids B001-PDF-01,B001-PDF-02
    python3 step4_api_batch_extraction.py --all

Run with --all and no .env configured first: this exercises the full
pipeline in dry-run mode against every doc_id found in evidence_blocks.jsonl
and is the recommended smoke test before spending real API budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_ENV_FILE = ROOT / ".env"

# Load environment variables from a .env file sitting next to this script, if
# present. This replaces the old "set -a; source .env; set +a" bash-only
# instructions (which don't work in Windows cmd.exe/PowerShell) with something
# that works identically on every platform/shell. If python-dotenv isn't
# installed OR no .env file exists, every AGENT_*_* lookup below falls back to
# its "dry_run" default -- which looks identical to "I configured it but it
# didn't load", so we print an explicit, loud diagnostic in both cases instead
# of silently doing nothing.
try:
    from dotenv import load_dotenv  # type: ignore

    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
        print(f"[env] Loaded {_ENV_FILE}")
    else:
        print(
            f"[env] No .env file found at {_ENV_FILE} -- both agents will use "
            "the dry_run default unless AGENT_*_* variables are set some other "
            "way. See .env.example and the project-root README.md for the legacy API pipeline notes."
        )
except ImportError:
    if _ENV_FILE.exists():
        print(
            f"[env] WARNING: found {_ENV_FILE} but the 'python-dotenv' package "
            "is not installed, so its contents were NOT loaded -- both agents "
            "will silently use the dry_run default. Run: pip install python-dotenv "
            "(or pip install -r ../../requirements.txt), then re-run this script."
        )

STAGE03_DIR = ROOT.parent.parent / "03_证据索引与混合检索"


SCHEMA_DIR = ROOT.parent / "01_Prompt与Schema注册"
OUT_DIR = ROOT / "产出"
OUT_A = OUT_DIR / "03_AgentA原始抽取"
OUT_B = OUT_DIR / "04_AgentB_Critic审查"
OUT_V = OUT_DIR / "05_核验通过结果"
OUT_LOG = OUT_DIR / "02_模型调用日志"

sys.path.insert(0, str(STAGE03_DIR))
from step3_hybrid_retrieval import HybridIndex  # noqa: E402

from llm_api_client import AgentEndpointConfig, LLMCallError, call_llm, list_models  # noqa: E402

AGENT_A_PROMPT_VERSION = "AgentA_prompt_v1.0"
AGENT_B_PROMPT_VERSION = "AgentB_prompt_v1.0"
MAX_JSON_REPAIR_ATTEMPTS = 2
MAX_REVISION_ROUNDS = 1  # locked protocol: at most one Pass1->Pass4 round trip


# ---------------------------------------------------------------------------
# Frozen prompts, transcribed verbatim from
# 01_Prompt与Schema注册/agent_prompts_and_manifest_v1_LOCKED.md sections 2-3.
# Do not edit here without bumping AGENT_A_PROMPT_VERSION / AGENT_B_PROMPT_VERSION
# and updating the locked doc, per that file's own change-control rule.
# ---------------------------------------------------------------------------
AGENT_A_SYSTEM_PROMPT = """角色:Full-Text Ontology Extractor(Agent A)

任务:对给定论文,逐一完成 D01-D10 十个维度的抽取,每个维度输出一条结构化记录(多选维度可输出多条或一条含 secondary_labels 的记录)。

强制规则(违反任一条即为无效输出,须重新生成):
1. 没有正文证据支持时,primary_label 必须是四种回退状态之一
   (Not_Stated_In_Text / Explicitly_Not_Considered / Insufficient_Evidence / Evidence_Unavailable),
   不得为了"填满十维"而编造标签。
2. 不得仅凭标题、摘要、关键词推断 D02-D09 的具体子标签;必须引用 Zone B/C/D 正文证据
   (D01 允许用 Zone A 摘要中的方法性陈述作为辅助,但主要证据仍应来自 Zone B)。
3. 每条非 Not_Stated_In_Text 的记录必须包含:至少1个 evidence_id、verbatim_quote(逐字引用原文)、
   section_id、page_numbers、own_method_vs_cited、mechanism_judgment、confidence。
4. 涉及方程的维度(D03 非 No_Explicit_Equation_Qualitative_Only 标签)必须填写 equation_detail。
5. 不得把被引用文献(Cited_Other_Work)的方法误标为本文方法(Paper_Own_Method);
   如果证据文本本身就是在转述他人工作,own_method_vs_cited 必须如实标注为 Cited_Other_Work,
   且该证据不能单独支撑主标签。
6. 不得把 HLA/软件数据交换类技术细节自动等同于"真实 cyber 早期预警机制"(D04/D06);
   不得把一般水网压力方程自动等同于厂内冷却热-水力模型(D02)。
7. mechanism_judgment 必须是对证据的忠实转述式判断(1-3句话),不得引入原文没有表达的推断或外推。
8. 每条记录必须给出 confidence(0.0-1.0)的自评,且在 uncertainty_note 中说明主要不确定性来源。

输出格式:只输出一个 JSON 数组,不要输出任何解释性文字、markdown代码块标记或其他内容。
数组每个元素必须包含字段:dimension_id, primary_label, secondary_labels(数组,可为空),
own_method_vs_cited, mechanism_judgment, uncertainty_note, evidence_ids(数组), verbatim_quote,
equation_detail(仅方程维度需要,对象或null), confidence。"""

AGENT_B_SYSTEM_PROMPT = """角色:Independent Critic and Evidence Auditor(Agent B)

任务:对 Agent A 输出的每一条记录,独立执行以下七项检查,并给出裁决。你会被提供与 Agent A 相同的
原始证据文本(必须重新独立阅读,不得只看 Agent A 的结论),以及 Agent A 的最终结构化输出(不含其
中间推理过程)。

检查项:
1. Entailment check:原文是否真的支持该 primary_label 和 mechanism_judgment;
2. Direction check(仅D01相关记录):水->电/电->水/双向关系方向是否被正确识别;
3. Equation check(仅涉及方程的记录):是否真实存在所声称的方程、变量和动态过程,页码和
   equation_detail是否准确;
4. Temporal check(仅D04-D06相关记录):时间尺度、步长、触发条件描述是否准确;
5. Endpoint check(仅D07-D09相关记录):物理/经济/人类社会后果层级是否被混淆或夸大;
6. Evidence check:section_id、page_numbers、evidence_id 和 verbatim_quote 是否与源证据块精确对应;
7. Contradiction check:原始文本中是否存在反向或限制性证据,而 Agent A 未提及。

强制规则:
1. decision=accept 仅表示"原文确实支持该判断",不表示论文结论本身在工程/物理上正确。
2. insufficient_evidence 不得被改写为 Not_Considered 或其他回退状态。
3. 若分歧无法在修订轮次内收敛,不强行投票决定,输出 adjudication_required=true。

输出格式:只输出一个 JSON 对象,键为 dimension_id,值为裁决对象,不要输出任何解释性文字或markdown
代码块标记。裁决对象字段:decision("accept"|"revise"|"reject"|"insufficient_evidence"),
corrected_label(若decision=revise给出修正后的primary_label,否则null), critic_comment(字符串,
必须在末尾包含声明:若 Agent A/B 使用不同的模型/厂商则声明"本轮审查由独立配置的外部模型完成";
若相同则声明"本轮审查与 Agent A 共享同一模型配置,不构成严格独立的双模型交叉验证"),
supporting_evidence_ids(数组), contradicting_evidence_ids(数组), confidence(0.0-1.0),
checks_failed(数组,可为空)。"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_schema() -> dict:
    with open(SCHEMA_DIR / "schema_v2.json", encoding="utf-8") as f:
        return json.load(f)


def extract_json(text: str):
    """Best-effort extraction of a JSON value from model output that may be
    wrapped in markdown fences, preceded/followed by stray prose, or -- as
    confirmed by live testing against CSTCloud's `minimax-m27` on
    2026-10-06 -- contain an inline `<think>...</think>` chain-of-thought
    block directly in `message.content` (unlike `deepseek-r1:*`/
    `deepseek-v4-flash`, which expose reasoning via a separate
    `reasoning_content` field that llm_api_client.py already excludes; some
    models instead inline it as literal text, so it must be stripped here)."""
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def dimension_query(dim_id: str, dim: dict) -> str:
    """Build a retrieval query string for the per-dimension hybrid_search
    pass, from the controlled label vocabulary (English identifiers)."""
    labels = dim.get("labels", [])
    tokens = " ".join(lbl.replace("_", " ").lower() for lbl in labels)
    return f"{dim.get('name', dim_id)} {tokens}"


def build_context(index: HybridIndex, doc_id: str, schema: dict) -> dict:
    """Assemble the Stage-03-sourced context for one document: the full
    coverage pass (mandatory per model_and_retrieval_config_v1_LOCKED.md
    section 4 -- top-k retrieval alone is NOT sufficient) plus, for
    reference/traceability, the per-dimension hybrid_search Top-10 hits."""
    coverage_ids = index.coverage_pass_ids(doc_id)
    if not coverage_ids:
        raise ValueError(f"No evidence blocks found for doc_id={doc_id!r} in Stage 03 index.")
    evidence_blocks = [index.by_id[eid] for eid in coverage_ids]

    dimension_hits = {}
    for dim_id, dim in schema["dimensions"].items():
        q = dimension_query(dim_id, dim)
        fused = index.hybrid_search(q)["fused_top"]
        dimension_hits[dim_id] = [eid for eid, _ in fused if eid in index.by_id and index.by_id[eid]["doc_id"] == doc_id]

    return {"evidence_blocks": evidence_blocks, "dimension_retrieval_hits": dimension_hits}


def evidence_blocks_for_prompt(blocks: list[dict]) -> list[dict]:
    return [
        {
            "evidence_id": b["evidence_id"], "zone": b.get("zone"), "section_id": b.get("section_id"),
            "page_numbers": b.get("page_numbers"), "text": b.get("text"),
        }
        for b in blocks
    ]


def call_agent_a(cfg: AgentEndpointConfig, schema: dict, doc_id: str, blocks: list[dict],
                  dimension_hits: dict, revise_only: dict | None = None,
                  critic_feedback: dict | None = None):
    """revise_only: if given, a dict dim_id -> original record, restricts the
    call to Pass 3 (revision) for just those dimensions, per the locked
    'max 1 revision round, only reprocess flagged dims' protocol."""
    user_payload = {
        "doc_id": doc_id,
        "dimensions_schema": schema["dimensions"],
        "fallback_states": schema["fallback_states"],
        "own_method_vs_cited_values": schema["own_method_vs_cited_values"],
        "evidence_blocks_coverage_pass": evidence_blocks_for_prompt(blocks),
        "dimension_retrieval_hits_top10": dimension_hits,
    }
    if revise_only:
        user_payload["mode"] = "pass3_revision_only"
        user_payload["dimensions_to_revise"] = list(revise_only.keys())
        user_payload["original_records"] = revise_only
        user_payload["critic_feedback"] = critic_feedback
    else:
        user_payload["mode"] = "pass1_initial_extraction"

    user_prompt = json.dumps(user_payload, ensure_ascii=False)
    return _call_and_parse_json(cfg, AGENT_A_SYSTEM_PROMPT, user_prompt, expect="array" if not revise_only else "array")


def call_agent_b(cfg: AgentEndpointConfig, schema: dict, doc_id: str, blocks: list[dict],
                  agent_a_records: list[dict], mode: str):
    user_payload = {
        "doc_id": doc_id,
        "mode": mode,
        "dimensions_schema": schema["dimensions"],
        "evidence_blocks_coverage_pass": evidence_blocks_for_prompt(blocks),
        "agent_a_structured_output": agent_a_records,
    }
    user_prompt = json.dumps(user_payload, ensure_ascii=False)
    return _call_and_parse_json(cfg, AGENT_B_SYSTEM_PROMPT, user_prompt, expect="object")


def _call_and_parse_json(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str, expect: str):
    retries_total = 0
    last_error = None
    for attempt in range(MAX_JSON_REPAIR_ATTEMPTS + 1):
        prompt = user_prompt
        if last_error is not None:
            prompt = user_prompt + (
                f"\n\n[REPAIR REQUEST] Your previous response could not be parsed as valid JSON "
                f"({'array' if expect=='array' else 'object'}). Error: {last_error}. "
                f"Return ONLY the corrected JSON {expect}, no prose, no markdown fences."
            )
        resp = call_llm(cfg, system_prompt, prompt)
        retries_total += resp.retry_count
        try:
            parsed = extract_json(resp.text)
            if expect == "array" and not isinstance(parsed, list):
                raise ValueError("expected a JSON array at top level")
            if expect == "object" and not isinstance(parsed, dict):
                raise ValueError("expected a JSON object at top level")
            resp.retry_count = retries_total + attempt
            return parsed, resp
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    raise LLMCallError(f"Could not obtain valid JSON {expect} after {MAX_JSON_REPAIR_ATTEMPTS} repair attempts: {last_error}")


# ---------------------------------------------------------------------------
# Validation against schema_v2.json (structural pre-check before accepting
# any record; Agent B still does the semantic audit per its prompt).
# ---------------------------------------------------------------------------

def _coerce_to_list(value) -> list:
    """Best-effort coercion of a field that should be a JSON array but may come
    back from a real (non-dry-run) LLM as a bare string, null, or some other
    shape despite the prompt/schema instructing otherwise."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [value]


def validate_agent_a_record(rec: dict, dim: dict, by_id: dict, doc_id: str) -> list[str]:
    errors = []
    primary = rec.get("primary_label")
    allowed = set(dim.get("labels", [])) | {
        "Not_Stated_In_Text", "Explicitly_Not_Considered", "Insufficient_Evidence", "Evidence_Unavailable",
    }
    # Defensive: real LLM providers occasionally return primary_label as a
    # single-element list (or other non-string shape) despite the prompt/schema
    # requiring a bare string. `set` membership tests below require primary to
    # be hashable, so normalize/neutralize non-string values here instead of
    # letting a TypeError abort the whole batch run. A genuine mismatch (wrong
    # label, wrong type) is still recorded as a validation error either way.
    if isinstance(primary, list):
        if len(primary) == 1 and isinstance(primary[0], str):
            errors.append(
                f"primary_label was returned as a single-element list {primary!r}; "
                f"auto-normalized to {primary[0]!r}"
            )
            primary = primary[0]
            rec["primary_label"] = primary
        else:
            errors.append(f"primary_label must be a single string, got list {primary!r}")
            primary = None
    elif primary is not None and not isinstance(primary, str):
        errors.append(f"primary_label must be a string, got {type(primary).__name__}: {primary!r}")
        primary = None

    if primary not in allowed:
        errors.append(f"primary_label '{primary}' not in allowed set for {dim.get('name')}")
    is_fallback = primary in {
        "Not_Stated_In_Text", "Explicitly_Not_Considered", "Insufficient_Evidence", "Evidence_Unavailable",
    }
    eids = _coerce_to_list(rec.get("evidence_ids"))
    if eids != (rec.get("evidence_ids") or []):
        errors.append(f"evidence_ids should be a list, got {rec.get('evidence_ids')!r}; coerced to {eids!r}")
        rec["evidence_ids"] = eids
    if not is_fallback or primary == "Insufficient_Evidence" or primary == "Explicitly_Not_Considered":
        pass  # evidence optional for some fallbacks; only hard-require below for substantive labels
    if primary not in ("Not_Stated_In_Text", "Evidence_Unavailable") and not eids:
        errors.append("evidence_ids required unless primary_label is Not_Stated_In_Text/Evidence_Unavailable")
    for eid in eids:
        if not isinstance(eid, str) or eid not in by_id:
            errors.append(f"evidence_id '{eid}' not found in Stage 03 index")
        elif by_id[eid]["doc_id"] != doc_id:
            errors.append(f"evidence_id '{eid}' belongs to a different doc_id ({by_id[eid]['doc_id']})")
    if primary != "Not_Stated_In_Text" and not rec.get("verbatim_quote"):
        errors.append("verbatim_quote required unless primary_label == Not_Stated_In_Text")
    conf = rec.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
        errors.append(f"confidence must be a float in [0,1], got {conf!r}")
    omvc = rec.get("own_method_vs_cited")
    if isinstance(omvc, list) and len(omvc) == 1:
        omvc = omvc[0]
    if not is_fallback and omvc not in ("Paper_Own_Method", "Cited_Other_Work", "Mixed"):
        errors.append(f"own_method_vs_cited invalid: {omvc!r}")
    secondary = _coerce_to_list(rec.get("secondary_labels"))
    if secondary != (rec.get("secondary_labels") or []):
        errors.append(f"secondary_labels should be a list, got {rec.get('secondary_labels')!r}; coerced to {secondary!r}")
        rec["secondary_labels"] = secondary
    for s in secondary:
        if not isinstance(s, str) or s not in dim.get("labels", []):
            errors.append(f"secondary_label '{s}' not in allowed set for {dim.get('name')}")
    requires_eq_unless = dim.get("requires_equation_detail_unless")
    if requires_eq_unless is not None:
        selected = [primary] + secondary
        if any(lbl not in requires_eq_unless for lbl in selected) and not rec.get("equation_detail"):
            errors.append("equation_detail required for this D03 label selection but missing")
    return errors



def enrich_record(rec: dict, doc_id: str, schema_version: str, call_id: str, by_id: dict) -> dict:
    rec = dict(rec)
    eids = rec.get("evidence_ids") or []
    if eids:
        seen = []
        for e in eids:
            if e in by_id and by_id[e]["section_id"] not in seen:
                seen.append(by_id[e]["section_id"])
        rec["section_id"] = seen[0] if len(seen) == 1 else seen
        rec["page_numbers"] = sorted({p for e in eids if e in by_id for p in by_id[e]["page_numbers"]})
    else:
        rec["section_id"] = None
        rec["page_numbers"] = []
    rec.update(doc_id=doc_id, schema_version=schema_version, agent_a_model_call_id=call_id)
    return rec


def build_manifest_entry(call_id, agent_name, doc_id, prompt_version, pass_name, schema_version,
                          input_evidence_ids, by_id, output_obj, resp, failure_reason=None,
                          execution_channel="external_api_call"):
    input_hashes = sorted(by_id[eid]["text_sha256"] for eid in input_evidence_ids if eid in by_id)
    input_hash = sha256_text("|".join(input_hashes) + "|" + prompt_version + "|" + schema_version)
    output_text = json.dumps(output_obj, ensure_ascii=False, sort_keys=True)
    output_hash = sha256_text(output_text)
    return {
        "call_id": call_id, "agent_name": agent_name, "execution_channel": execution_channel,
        "provider": resp.provider, "model_name": resp.model_name, "model_version": resp.model_version,
        "endpoint": resp.endpoint, "prompt_version": prompt_version, "schema_version": schema_version,
        "input_hash": input_hash, "output_hash": output_hash,
        "temperature": resp.temperature, "seed": resp.seed,
        "input_evidence_ids": input_evidence_ids,
        "input_token_estimate": resp.input_tokens if resp.input_tokens is not None else "not_reported_by_provider",
        "output_token_estimate": resp.output_tokens if resp.output_tokens is not None else "not_reported_by_provider",
        "latency_s": round(resp.latency_s, 3), "retry_count": resp.retry_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "failure_reason": failure_reason,
        "human_or_agent_reviewed": "agent_only", "pass": pass_name, "doc_id": doc_id,
        "primary_model_configured": resp.primary_model,
        "used_fallback_model": resp.used_fallback_model,
    }


def process_document(doc_id: str, index: HybridIndex, schema: dict, cfg_a: AgentEndpointConfig,
                      cfg_b: AgentEndpointConfig, schema_version: str, manifest: list[dict]) -> None:
    print(f"[{doc_id}] building Stage-03 context (coverage pass + per-dimension hybrid_search)...")
    ctx = build_context(index, doc_id, schema)
    blocks = ctx["evidence_blocks"]
    by_id = index.by_id
    # cross_model_independent is computed further below, AFTER the real pass1/pass2
    # calls, using the models actually used (which may differ from cfg_a.model /
    # cfg_b.model if a backup-model fallback kicked in) -- see the recomputation
    # next to the Agent B pass2 call.

    pass1_call_id = f"MC-{doc_id}-AgentA-pass1-001"
    print(f"[{doc_id}] Agent A pass1 ({cfg_a.provider}/{cfg_a.model})...")
    raw_records, resp_a1 = call_agent_a(cfg_a, schema, doc_id, blocks, ctx["dimension_retrieval_hits"])
    if resp_a1.used_fallback_model:
        print(f"[{doc_id}] NOTE: Agent A pass1 ran on backup model "
              f"'{resp_a1.used_fallback_model}' (primary '{cfg_a.model}' was unavailable).")

    enriched = []
    all_errors = {}
    for rec in raw_records:
        dim_id = rec.get("dimension_id")
        dim = schema["dimensions"].get(dim_id)
        if dim is None:
            all_errors.setdefault("_unknown_dimension", []).append(rec)
            continue
        errs = validate_agent_a_record(rec, dim, by_id, doc_id)
        if errs:
            all_errors[dim_id] = errs
        enriched.append(enrich_record(rec, doc_id, schema_version, pass1_call_id, by_id))

    OUT_A.mkdir(parents=True, exist_ok=True)
    with open(OUT_A / f"{doc_id}_agentA_pass1.json", "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    if all_errors:
        with open(OUT_A / f"{doc_id}_agentA_pass1_VALIDATION_WARNINGS.json", "w", encoding="utf-8") as f:
            json.dump(all_errors, f, ensure_ascii=False, indent=2)
        print(f"[{doc_id}] WARNING: {len(all_errors)} dimension(s) failed structural validation; "
              f"see {doc_id}_agentA_pass1_VALIDATION_WARNINGS.json")

    all_ids_1 = sorted({eid for r in enriched for eid in (r.get("evidence_ids") or [])})
    manifest.append(build_manifest_entry(
        pass1_call_id, "AgentA", doc_id, AGENT_A_PROMPT_VERSION, "pass1_initial_extraction", schema_version,
        all_ids_1, by_id, enriched, resp_a1,
        execution_channel="dry_run_no_network" if cfg_a.provider == "dry_run" else "external_api_call"))

    pass2_call_id = f"MC-{doc_id}-AgentB-pass2-001"
    print(f"[{doc_id}] Agent B pass2 ({cfg_b.provider}/{cfg_b.model})...")
    decisions, resp_b2 = call_agent_b(cfg_b, schema, doc_id, blocks, enriched, "pass2_initial_critic")
    if resp_b2.used_fallback_model:
        print(f"[{doc_id}] NOTE: Agent B pass2 ran on backup model "
              f"'{resp_b2.used_fallback_model}' (primary '{cfg_b.model}' was unavailable).")
    # Recompute cross-model independence using the models ACTUALLY used for
    # this document's pass1/pass2 (not just the statically configured
    # primaries) -- a backup-model fallback could in principle land Agent A
    # and Agent B on the same underlying model, which would silently break
    # the "independent critic" assumption if left unchecked.
    actual_model_a = resp_a1.used_fallback_model or resp_a1.model_name
    actual_model_b = resp_b2.used_fallback_model or resp_b2.model_name
    cross_model_independent = (resp_a1.provider, actual_model_a) != (resp_b2.provider, actual_model_b) and resp_a1.provider != "dry_run"
    if not cross_model_independent and cfg_a.provider != "dry_run":
        print(f"[{doc_id}] WARNING: Agent A and Agent B ended up on the SAME model "
              f"({resp_a1.provider}/{actual_model_a}) this run (likely due to a backup-model "
              f"fallback) -- cross-model independence is NOT satisfied for this document; "
              f"treat its agent_b_review.cross_model_independence=false accordingly.")
    OUT_B.mkdir(parents=True, exist_ok=True)
    with open(OUT_B / f"{doc_id}_agentB_pass2.json", "w", encoding="utf-8") as f:
        json.dump(decisions, f, ensure_ascii=False, indent=2)
    all_ids_2 = sorted({eid for dec in decisions.values() for eid in (dec.get("supporting_evidence_ids") or [])})
    manifest.append(build_manifest_entry(
        pass2_call_id, "AgentB", doc_id, AGENT_B_PROMPT_VERSION, "pass2_initial_critic", schema_version,
        all_ids_2, by_id, decisions, resp_b2,
        execution_channel="dry_run_no_network" if cfg_b.provider == "dry_run" else "external_api_call"))

    revise_dims = {d: dec for d, dec in decisions.items() if dec.get("decision") in ("revise", "reject")}
    revisions, finals = {}, {}
    if revise_dims:
        originals = {d: next((r for r in enriched if r["dimension_id"] == d), None) for d in revise_dims}
        originals = {d: r for d, r in originals.items() if r is not None}
        pass3_call_id = f"MC-{doc_id}-AgentA-pass3-001"
        print(f"[{doc_id}] Agent A pass3 revision for {sorted(revise_dims)}...")
        revised_list, resp_a3 = call_agent_a(
            cfg_a, schema, doc_id, blocks, ctx["dimension_retrieval_hits"],
            revise_only=originals, critic_feedback={d: revise_dims[d].get("critic_comment") for d in revise_dims})
        for rec in revised_list:
            revisions[rec["dimension_id"]] = enrich_record(rec, doc_id, schema_version, pass3_call_id, by_id)
        with open(OUT_A / f"{doc_id}_agentA_pass3_revisions.json", "w", encoding="utf-8") as f:
            json.dump(revisions, f, ensure_ascii=False, indent=2)
        ids_3 = sorted({eid for r in originals.values() for eid in (r.get("evidence_ids") or [])})
        manifest.append(build_manifest_entry(
            pass3_call_id, "AgentA", doc_id, AGENT_A_PROMPT_VERSION, "pass3_revision_only", schema_version,
            ids_3, by_id, revisions, resp_a3,
            execution_channel="dry_run_no_network" if cfg_a.provider == "dry_run" else "external_api_call"))

        pass4_call_id = f"MC-{doc_id}-AgentB-pass4-001"
        print(f"[{doc_id}] Agent B pass4 final review...")
        finals, resp_b4 = call_agent_b(cfg_b, schema, doc_id, blocks, list(revisions.values()), "pass4_final_review")
        with open(OUT_B / f"{doc_id}_agentB_pass4_final.json", "w", encoding="utf-8") as f:
            json.dump(finals, f, ensure_ascii=False, indent=2)
        ids_4 = sorted({eid for r in revisions.values() for eid in (r.get("evidence_ids") or [])})
        manifest.append(build_manifest_entry(
            pass4_call_id, "AgentB", doc_id, AGENT_B_PROMPT_VERSION, "pass4_final_review", schema_version,
            ids_4, by_id, finals, resp_b4,
            execution_channel="dry_run_no_network" if cfg_b.provider == "dry_run" else "external_api_call"))

    verified = []
    for rec in enriched:
        dim_id = rec["dimension_id"]
        b2 = decisions.get(dim_id, {"decision": "insufficient_evidence", "critic_comment": "no Agent B decision returned"})
        if b2.get("decision") in ("revise", "reject") and dim_id in revisions:
            rec = dict(revisions[dim_id])
            b4 = finals.get(dim_id, {})
            status = "accepted_after_revision" if b4.get("decision") == "accept" else "adjudication_required"
            rec["agent_b_review"] = {
                "pass2_decision": b2.get("decision"), "pass2_comment": b2.get("critic_comment"),
                "pass4_decision": b4.get("decision"), "pass4_comment": b4.get("critic_comment"),
                "cross_model_independence": cross_model_independent,
            }
            rec["verification_status"] = status
        else:
            rec["agent_b_review"] = {
                "pass2_decision": b2.get("decision"), "pass2_comment": b2.get("critic_comment"),
                "cross_model_independence": cross_model_independent,
            }
            rec["verification_status"] = "accepted_pass1" if b2.get("decision") == "accept" else "adjudication_required"
        verified.append(rec)

    OUT_V.mkdir(parents=True, exist_ok=True)
    with open(OUT_V / f"{doc_id}_verified_10d.json", "w", encoding="utf-8") as f:
        json.dump(verified, f, ensure_ascii=False, indent=2)
    print(f"[{doc_id}] done -> {OUT_V / (doc_id + '_verified_10d.json')}")


def all_doc_ids(index: HybridIndex) -> list[str]:
    return sorted({r["doc_id"] for r in index.records})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc-ids", help="Comma-separated doc_ids to process, e.g. B001-PDF-01,B001-PDF-02")
    ap.add_argument("--all", action="store_true", help="Process every doc_id found in the Stage 03 index")
    ap.add_argument("--schema-version", default=None, help="Override schema_version tag (default: current schema_v2.json value)")
    ap.add_argument("--list-models", action="store_true",
                     help="Fetch and print the live model catalog for Agent A and Agent B (via GET /models) and exit. "
                          "Useful to confirm exact model id strings before a real run (e.g. for CSTCloud's "
                          "Uni-API, whose open model list is documented as subject to change).")
    args = ap.parse_args()

    cfg_a = AgentEndpointConfig.from_env("AgentA")
    cfg_b = AgentEndpointConfig.from_env("AgentB")

    if args.list_models:
        for label, cfg in (("Agent A", cfg_a), ("Agent B", cfg_b)):
            print(f"--- {label} ({cfg.provider} @ {cfg.base_url}) ---")
            try:
                for m in list_models(cfg):
                    print(" ", m)
            except LLMCallError as exc:
                print(f"  (could not list models: {exc})")
        return 0

    schema = load_schema()
    schema_version = args.schema_version or schema["schema_version"]
    index = HybridIndex()

    if args.all:
        doc_ids = all_doc_ids(index)
    elif args.doc_ids:
        doc_ids = [d.strip() for d in args.doc_ids.split(",") if d.strip()]
    else:
        print("Nothing to do: pass --doc-ids A,B,C or --all. Known doc_ids:", all_doc_ids(index))
        return 1

    print(f"Agent A endpoint: provider={cfg_a.provider} model={cfg_a.model} base_url={cfg_a.base_url}"
          + (f" | backup model(s): {', '.join(cfg_a.fallback_models)}" if cfg_a.fallback_models else ""))
    print(f"Agent B endpoint: provider={cfg_b.provider} model={cfg_b.model} base_url={cfg_b.base_url}"
          + (f" | backup model(s): {', '.join(cfg_b.fallback_models)}" if cfg_b.fallback_models else ""))
    if cfg_a.provider == "dry_run" or cfg_b.provider == "dry_run":
        print("*** DRY RUN MODE: no external network calls will be made for any agent left unconfigured. ***")

    for d in (OUT_A, OUT_B, OUT_V, OUT_LOG):
        d.mkdir(parents=True, exist_ok=True)

    manifest = []
    for doc_id in doc_ids:
        try:
            process_document(doc_id, index, schema, cfg_a, cfg_b, schema_version, manifest)
        except LLMCallError as exc:
            print(f"[{doc_id}] FAILED: {exc}", file=sys.stderr)
        except ValueError as exc:
            print(f"[{doc_id}] FAILED: {exc}", file=sys.stderr)

    manifest_path = OUT_LOG / "model_call_manifest.jsonl"
    with open(manifest_path, "a", encoding="utf-8") as f:
        for e in manifest:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Appended {len(manifest)} manifest entries to {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
