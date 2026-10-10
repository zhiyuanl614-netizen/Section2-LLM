#!/usr/bin/env python3
"""Provider-agnostic external LLM API client for the Step 4 batch pipeline.

Design goal (per user decision, 2026-10-06): the in-session Arena.ai Agent
reasoning path (step4_pilot_extraction.py, execution_channel =
"arena_agent_mode_in_session") cannot scale to batch/large-corpus work. This
module provides a real external-API calling interface so Agent A and Agent B
can each be pointed at genuine, independently configured LLM endpoints
(potentially two DIFFERENT providers/models) -- which, if configured that
way, finally satisfies the README 2.3.2 "Agent B cannot read Agent A's
reasoning, and the two are independent systems" requirement that the
in-session method explicitly could NOT satisfy (see
agent_prompts_and_manifest_v1_LOCKED.md section 0).

No API keys are present in this sandbox. This module only takes effect when
the user supplies credentials via environment variables (see .env.example in
this directory). Without credentials, use `DryRunLLMClient` to exercise the
rest of the pipeline mechanically (prompt assembly, schema validation,
file/manifest writing) with synthetic placeholder output that is clearly
tagged as non-data.

Built-in adapters:
  - "cstcloud": POSTs to {base_url}/chat/completions against the China
    Science and Technology Cloud (中国科技云) Uni-API gateway
    (https://uni-api.cstcloud.cn/doc/llm/), which the user has selected as
    the actual provider for this project. Confirmed from that documentation
    (2026-10-06): fully OpenAI-Chat-Completions-compatible; base URL
    `https://uni-api.cstcloud.cn/v1`; auth via `Authorization: Bearer
    {Token}`; model catalog retrievable live via `GET /v1/models`; example
    model ids seen in the docs include `deepseek-r1:671b-0528`,
    `deepseek-v3:671b`, `qwen3:235b`, `qwen3.5`, `qwq:32b`,
    `deepseek-v4-flash`, `minimax-m27`, `gpt-oss-120b` (the live catalog
    should always be treated as authoritative over this list -- use
    `--list-models` on the orchestrator or `list_models()` below). Reasoning
    models return an extra non-standard `message.reasoning_content` field
    alongside the normal `message.content`; this adapter keeps only
    `content` as the structured-output text (consistent with the Agent A/B
    prompts' rule against leaking chain-of-thought into the output) while
    preserving the full raw response (including reasoning_content) for
    audit. Some models (`qwen3:235b`, `deepseek-v4-flash`) support a
    `chat_template_kwargs` switch to toggle deep-thinking mode -- exposed
    here via `AGENT_*_CHAT_TEMPLATE_KWARGS` (raw JSON string) if needed.
    NOTE: per CSTCloud's terms, research output produced using this service
    should carry an acknowledgement -- see the note in .env.example / the
    README in this directory.
  - "openai_compatible": generic adapter for OpenAI itself, Azure OpenAI, or
    any other OpenAI-Chat-Completions-compatible gateway (Together, Groq,
    Fireworks, local vLLM/Ollama/LM Studio, etc) -- kept for flexibility if
    Agent A/B are ever pointed at a second, genuinely different provider for
    cross-model independence (see README section on this).
  - "anthropic": POSTs to {base_url}/v1/messages using Anthropic's native
    Messages API contract -- also kept as an option for cross-model
    independence.

All adapters are intentionally minimal (stdlib + `requests` only, no vendor
SDK dependency) so the user does not need to pip-install anything beyond
what's already in this sandbox to get started; a vendor SDK can be swapped in
later without changing the orchestrator's call contract.
"""
from __future__ import annotations

import dataclasses
import json
import os
import time
from typing import Optional

import requests


class LLMCallError(Exception):
    """Raised when an external API call fails after retries are exhausted."""


@dataclasses.dataclass
class LLMResponse:
    text: str                       # raw text content returned by the model
    provider: str
    model_name: str
    model_version: str              # provider-reported model id/version if available, else model_name
    endpoint: str
    temperature: Optional[float]
    seed: Optional[int]
    input_tokens: Optional[int]     # real usage.prompt_tokens from the API response, if provided
    output_tokens: Optional[int]    # real usage.completion_tokens from the API response, if provided
    latency_s: float
    retry_count: int
    raw_response: dict              # full parsed JSON response, kept for audit/debugging
    primary_model: Optional[str] = None     # the model configured as AGENT_*_MODEL (for audit, even on fallback)
    used_fallback_model: Optional[str] = None  # set to the model actually used, iff it was NOT primary_model


@dataclasses.dataclass
class AgentEndpointConfig:
    """Configuration for one agent's (A or B) external API endpoint.

    Agent A and Agent B each get their own AgentEndpointConfig, loaded from
    separate env-var prefixes (AGENT_A_* / AGENT_B_*) -- this is what allows
    them to point at two genuinely different providers/models.
    """
    agent_name: str                 # "AgentA" | "AgentB"
    provider: str                   # "cstcloud" | "openai_compatible" | "anthropic" | "dry_run"
    api_key: Optional[str]
    base_url: str
    model: str
    temperature: float = 0.0
    seed: Optional[int] = None
    max_tokens: int = 4096
    request_timeout_s: int = 180
    max_retries: int = 3
    retry_backoff_s: float = 2.0
    chat_template_kwargs: Optional[dict] = None  # e.g. {"enable_thinking": false} for qwen3:235b on cstcloud
    # --- Backup/fallback model(s), per user decision 2026-10-08 ---
    # If the primary model (above) exhausts all of its own retries (e.g. a
    # provider-side outage like the 2026-10-08 CSTCloud deepseek-v4-flash
    # "upstream connect error"), call_llm() automatically switches to the
    # next model in this list and tries it (with its own full retry budget)
    # before giving up. Populated from AGENT_*_FALLBACK_MODEL (comma-separated
    # for more than one backup, tried in order). Fallback attempts reuse the
    # SAME provider/base_url/api_key/temperature/max_tokens/timeout/retries as
    # the primary unless overridden by the AGENT_*_FALLBACK_* variants below.
    fallback_models: list = dataclasses.field(default_factory=list)
    fallback_provider: Optional[str] = None
    fallback_api_key: Optional[str] = None
    fallback_base_url: Optional[str] = None
    fallback_chat_template_kwargs: Optional[dict] = None
    fallback_max_tokens: Optional[int] = None
    fallback_request_timeout_s: Optional[int] = None
    fallback_max_retries: Optional[int] = None

    @classmethod
    def from_env(cls, agent_name: str) -> "AgentEndpointConfig":
        prefix = "AGENT_A" if agent_name == "AgentA" else "AGENT_B"
        provider = os.environ.get(f"{prefix}_PROVIDER", "dry_run").strip().lower()
        api_key = os.environ.get(f"{prefix}_API_KEY")
        default_base = {
            "cstcloud": "https://uni-api.cstcloud.cn/v1",
            "openai_compatible": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "dry_run": "N/A",
        }.get(provider, "N/A")
        base_url = os.environ.get(f"{prefix}_BASE_URL", default_base)
        model = os.environ.get(f"{prefix}_MODEL", "unset-model")
        temperature = float(os.environ.get(f"{prefix}_TEMPERATURE", "0.0"))
        seed_raw = os.environ.get(f"{prefix}_SEED")
        seed = int(seed_raw) if seed_raw not in (None, "") else None
        max_tokens = int(os.environ.get(f"{prefix}_MAX_TOKENS", "4096"))
        # Thinking-enabled models (e.g. qwen3.5/qwen3:235b with the default
        # enable_thinking=true, or deepseek-r1-style reasoning models) can take
        # well over 120s to answer a large structured-extraction/critic prompt.
        # Default raised to 180s; override per-agent if your model+prompt combo
        # still times out (observed on a real 2026-10-07 run: Agent B on
        # qwen3.5's default thinking mode exhausted 3x120s retries on a single
        # 10-dimension critic pass). Consider also setting
        # AGENT_B_CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}' if your
        # model supports it and you don't need chain-of-thought for this task.
        request_timeout_s = int(os.environ.get(f"{prefix}_REQUEST_TIMEOUT_S", "180"))
        max_retries = int(os.environ.get(f"{prefix}_MAX_RETRIES", "3"))
        ctk_raw = os.environ.get(f"{prefix}_CHAT_TEMPLATE_KWARGS")
        chat_template_kwargs = json.loads(ctk_raw) if ctk_raw else None

        fallback_raw = os.environ.get(f"{prefix}_FALLBACK_MODEL", "")
        fallback_models = [m.strip() for m in fallback_raw.split(",") if m.strip()]
        fallback_provider = os.environ.get(f"{prefix}_FALLBACK_PROVIDER")
        fallback_api_key = os.environ.get(f"{prefix}_FALLBACK_API_KEY")
        fallback_base_url = os.environ.get(f"{prefix}_FALLBACK_BASE_URL")
        fctk_raw = os.environ.get(f"{prefix}_FALLBACK_CHAT_TEMPLATE_KWARGS")
        fallback_chat_template_kwargs = json.loads(fctk_raw) if fctk_raw else None
        fmt_raw = os.environ.get(f"{prefix}_FALLBACK_MAX_TOKENS")
        fallback_max_tokens = int(fmt_raw) if fmt_raw else None
        frt_raw = os.environ.get(f"{prefix}_FALLBACK_REQUEST_TIMEOUT_S")
        fallback_request_timeout_s = int(frt_raw) if frt_raw else None
        fmr_raw = os.environ.get(f"{prefix}_FALLBACK_MAX_RETRIES")
        fallback_max_retries = int(fmr_raw) if fmr_raw else None

        return cls(
            agent_name=agent_name, provider=provider, api_key=api_key, base_url=base_url,
            model=model, temperature=temperature, seed=seed, max_tokens=max_tokens,
            request_timeout_s=request_timeout_s, max_retries=max_retries,
            chat_template_kwargs=chat_template_kwargs,
            fallback_models=fallback_models, fallback_provider=fallback_provider,
            fallback_api_key=fallback_api_key, fallback_base_url=fallback_base_url,
            fallback_chat_template_kwargs=fallback_chat_template_kwargs,
            fallback_max_tokens=fallback_max_tokens,
            fallback_request_timeout_s=fallback_request_timeout_s,
            fallback_max_retries=fallback_max_retries,
        )

    def build_attempt_chain(self) -> list:
        """Return the ordered list of AgentEndpointConfig to actually try:
        [self (unmodified), fallback#1, fallback#2, ...]. Each fallback entry
        is a shallow copy of `self` with `model` swapped and any
        AGENT_*_FALLBACK_* overrides applied; its own `fallback_models` is
        cleared so there is no recursive fallback-of-a-fallback chaining."""
        chain = [self]
        for m in self.fallback_models:
            chain.append(dataclasses.replace(
                self,
                model=m,
                provider=self.fallback_provider or self.provider,
                api_key=self.fallback_api_key or self.api_key,
                base_url=self.fallback_base_url or self.base_url,
                chat_template_kwargs=(
                    self.fallback_chat_template_kwargs
                    if self.fallback_chat_template_kwargs is not None
                    else self.chat_template_kwargs
                ),
                max_tokens=self.fallback_max_tokens or self.max_tokens,
                request_timeout_s=self.fallback_request_timeout_s or self.request_timeout_s,
                max_retries=self.fallback_max_retries if self.fallback_max_retries is not None else self.max_retries,
                fallback_models=[],
            ))
        return chain


def _post_with_retries(url: str, headers: dict, payload: dict, cfg: AgentEndpointConfig):
    last_exc = None
    for attempt in range(cfg.max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=cfg.request_timeout_s)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMCallError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
            return resp.json(), attempt
        except Exception as exc:  # noqa: BLE001 - deliberately broad, we retry/backoff uniformly
            last_exc = exc
            if attempt < cfg.max_retries:
                time.sleep(cfg.retry_backoff_s * (2 ** attempt))
            else:
                break
    raise LLMCallError(f"Exhausted {cfg.max_retries} retries calling {url}: {last_exc}")


def call_llm(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str) -> LLMResponse:
    """Dispatch to the configured provider adapter, with automatic backup-model
    fallback: if the primary model (cfg.model) exhausts its own retry budget,
    and cfg.fallback_models is non-empty, each backup model is tried in turn
    (with its own full retry budget) before finally raising LLMCallError.
    This is what lets a transient single-model outage on the provider side
    (e.g. the 2026-10-08 CSTCloud deepseek-v4-flash "upstream connect error")
    be absorbed automatically instead of failing the whole document/run.
    """
    chain = cfg.build_attempt_chain()
    last_exc: Optional[Exception] = None
    for i, acfg in enumerate(chain):
        try:
            resp = _dispatch_single(acfg, system_prompt, user_prompt)
            resp.primary_model = cfg.model
            if i > 0:
                resp.used_fallback_model = acfg.model
                print(f"[fallback] {cfg.agent_name}: primary model '{cfg.model}' was unavailable; "
                      f"request SUCCEEDED using backup model '{acfg.model}' "
                      f"(backup #{i}/{len(chain) - 1}).")
            return resp
        except LLMCallError as exc:
            last_exc = exc
            if i < len(chain) - 1:
                print(f"[fallback] {cfg.agent_name}: model '{acfg.model}' exhausted its retries "
                      f"({exc}); switching to backup model '{chain[i + 1].model}'...")
            continue
    attempted = " -> ".join(c.model for c in chain)
    raise LLMCallError(
        f"{cfg.agent_name}: all configured model(s) exhausted retries ({attempted}). "
        f"Last error: {last_exc}"
    )


def _dispatch_single(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str) -> LLMResponse:
    """Single-model dispatch (no fallback logic) -- what call_llm() tries once
    per entry in the attempt chain built by AgentEndpointConfig.build_attempt_chain()."""
    t0 = time.time()

    if cfg.provider == "dry_run":
        return _dry_run_response(cfg, system_prompt, user_prompt, t0)

    if cfg.provider == "cstcloud":
        return _call_openai_style(cfg, system_prompt, user_prompt, t0, provider_label="cstcloud", send_seed=False)

    if cfg.provider == "openai_compatible":
        return _call_openai_style(cfg, system_prompt, user_prompt, t0, provider_label="openai_compatible", send_seed=True)

    if cfg.provider == "anthropic":
        return _call_anthropic(cfg, system_prompt, user_prompt, t0)

    raise LLMCallError(
        f"Unknown provider '{cfg.provider}' for {cfg.agent_name}. "
        "Supported: cstcloud | openai_compatible | anthropic | dry_run."
    )


def _call_openai_style(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str, t0: float,
                        provider_label: str, send_seed: bool) -> LLMResponse:
    """Shared implementation for any OpenAI-Chat-Completions-compatible
    gateway (covers both generic "openai_compatible" and the CSTCloud
    Uni-API, which is documented as fully OpenAI-API-Compatible -- see
    https://uni-api.cstcloud.cn/doc/llm/)."""
    if not cfg.api_key:
        raise LLMCallError(f"{cfg.agent_name}: provider={provider_label} requires an API key "
                            f"(set AGENT_{'A' if cfg.agent_name=='AgentA' else 'B'}_API_KEY).")
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if send_seed and cfg.seed is not None:
        payload["seed"] = cfg.seed
    if cfg.chat_template_kwargs:
        # CSTCloud-specific extension: e.g. {"enable_thinking": false} for
        # qwen3:235b, or {"thinking": true} for deepseek-v4-flash. Harmless
        # no-op for models/providers that don't recognize the field.
        payload["chat_template_kwargs"] = cfg.chat_template_kwargs

    data, retries = _post_with_retries(url, headers, payload, cfg)
    message = data["choices"][0]["message"]
    text = message.get("content") or ""
    # Reasoning models on CSTCloud (e.g. deepseek-r1:*) return an extra
    # non-standard `reasoning_content` field alongside `content`. We
    # deliberately do NOT fold it into `text` -- Agent A/B structured output
    # must be the final answer only, per the locked prompts' rule against
    # leaking chain-of-thought -- but it is preserved in raw_response for audit.
    usage = data.get("usage", {})
    return LLMResponse(
        text=text, provider=provider_label, model_name=cfg.model,
        model_version=data.get("model", cfg.model), endpoint=url,
        temperature=cfg.temperature, seed=cfg.seed if send_seed else None,
        input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
        latency_s=time.time() - t0, retry_count=retries, raw_response=data,
    )


def list_models(cfg: AgentEndpointConfig) -> list[str]:
    """Fetch the live model catalog from an OpenAI-style `/models` endpoint
    (supported by both cstcloud and openai_compatible). Useful to confirm the
    exact current model id strings before committing to a batch run, since
    CSTCloud's open model list is documented as subject to change (see their
    "模型发布记录" changelog page)."""
    if cfg.provider not in ("cstcloud", "openai_compatible"):
        raise LLMCallError(f"list_models() is not supported for provider={cfg.provider!r}")
    if not cfg.api_key:
        raise LLMCallError(f"{cfg.agent_name}: listing models requires an API key.")
    url = cfg.base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    resp = requests.get(url, headers=headers, timeout=cfg.request_timeout_s)
    resp.raise_for_status()
    data = resp.json()
    return [m["id"] for m in data.get("data", [])]


def _call_anthropic(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str, t0: float) -> LLMResponse:
    if not cfg.api_key:
        raise LLMCallError(f"{cfg.agent_name}: provider=anthropic requires an API key "
                            f"(set AGENT_{'A' if cfg.agent_name=='AgentA' else 'B'}_API_KEY).")
    url = cfg.base_url.rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": cfg.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
    }
    data, retries = _post_with_retries(url, headers, payload, cfg)
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    usage = data.get("usage", {})
    return LLMResponse(
        text=text, provider="anthropic", model_name=cfg.model,
        model_version=data.get("model", cfg.model), endpoint=url,
        temperature=cfg.temperature, seed=None,
        input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        latency_s=time.time() - t0, retry_count=retries, raw_response=data,
    )


def _dry_run_response(cfg: AgentEndpointConfig, system_prompt: str, user_prompt: str, t0: float) -> LLMResponse:
    """Deterministic, clearly-fake stand-in so the harness (prompt assembly,
    schema validation, enrichment, A+B+A+B merge logic, manifest writing) can
    be exercised end-to-end without network access or API keys. The returned
    content is syntactically shaped like real output (so the orchestrator's
    control flow actually runs) but every value is an explicit, conservative
    fallback/placeholder -- never a fabricated substantive label -- and is
    always tagged non-data by execution_channel="dry_run_no_network" in the
    manifest (see step4_api_batch_extraction.py). Downstream code must never
    treat this as a real extraction.
    """
    time.sleep(0.01)
    is_agent_a = "Full-Text Ontology Extractor" in system_prompt
    is_agent_b = "Independent Critic" in system_prompt

    payload = {}
    try:
        payload = json.loads(user_prompt)
    except Exception:  # noqa: BLE001
        payload = {}

    if is_agent_a:
        dims = payload.get("dimensions_schema") or {}
        records = []
        for dim_id in dims:
            records.append({
                "dimension_id": dim_id,
                "primary_label": "Insufficient_Evidence",
                "secondary_labels": [],
                "own_method_vs_cited": "Cited_Other_Work",
                "mechanism_judgment": "[DRY RUN placeholder -- no external model was called]",
                "uncertainty_note": "dry_run_no_network: synthetic placeholder, not a real judgment",
                "evidence_ids": [],
                "verbatim_quote": "",
                "equation_detail": None,
                "confidence": 0.0,
            })
        fake_text = json.dumps(records, ensure_ascii=False)
    elif is_agent_b:
        agent_a_out = payload.get("agent_a_structured_output") or []
        decisions = {}
        for rec in agent_a_out:
            dim_id = rec.get("dimension_id")
            if not dim_id:
                continue
            decisions[dim_id] = {
                "decision": "insufficient_evidence",
                "corrected_label": None,
                "critic_comment": "DRY RUN placeholder -- no external model was called; "
                                   "not a real critic judgment.",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
                "confidence": 0.0,
                "checks_failed": [],
            }
        fake_text = json.dumps(decisions, ensure_ascii=False)
    else:
        fake_text = json.dumps({
            "_dry_run": True,
            "_notice": "DRY RUN -- no external API was called. This is a synthetic placeholder, not real data.",
        }, ensure_ascii=False)

    return LLMResponse(
        text=fake_text, provider="dry_run",
        model_name="dry-run-stub", model_version="dry-run-stub", endpoint="N/A_dry_run",
        temperature=cfg.temperature, seed=cfg.seed, input_tokens=None, output_tokens=None,
        latency_s=time.time() - t0, retry_count=0, raw_response={"dry_run": True},
    )
