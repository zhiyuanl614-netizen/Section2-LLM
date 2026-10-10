#!/usr/bin/env python3
"""Local-only OpenAI-compatible chat client for the v1.2 text-scope pipeline.

This module intentionally supports only a loopback/private endpoint and a
network-free dry-run stub. It never configures cloud providers or fallback
models. HTTP proxies and redirects are disabled in local-only mode.
"""
from __future__ import annotations

import dataclasses
import ipaddress
import json
import os
import time
from typing import Optional
from urllib.parse import urlsplit

import requests


class LLMCallError(RuntimeError):
    pass


@dataclasses.dataclass
class LLMResponse:
    text: str
    provider: str
    model_name: str
    model_version: str
    endpoint: str
    temperature: Optional[float]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    latency_s: float
    retry_count: int
    finish_reason: Optional[str]
    raw_response: dict
    execution_channel: str
    call_id: Optional[str] = None


@dataclasses.dataclass
class LocalEndpointConfig:
    agent_name: str
    provider: str
    base_url: str
    model: str
    api_key: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 4096
    request_timeout_s: int = 180
    max_retries: int = 1
    retry_backoff_s: float = 1.0
    allow_private_network: bool = False

    @classmethod
    def from_env(cls, agent_name: str, *, allow_private_network: bool = False) -> "LocalEndpointConfig":
        prefix = "AGENT_A" if agent_name == "AgentA" else "AGENT_B"
        provider = os.environ.get(f"{prefix}_PROVIDER", "dry_run").strip().lower()
        model = os.environ.get(f"{prefix}_MODEL", "dry-run-stub").strip()
        if provider == "dry_run":
            return cls(agent_name, "dry_run", "N/A", model or "dry-run-stub", None, 0.0, 4096, 10, 0, 0.0, False)
        if provider != "openai_compatible":
            raise ValueError(
                f"{agent_name}: v1.2 local pipeline supports only provider='openai_compatible' "
                "or 'dry_run'; remote providers are intentionally disabled."
            )
        base_url = os.environ.get(f"{prefix}_BASE_URL", "http://127.0.0.1:11434/v1").strip()
        validate_local_base_url(base_url, allow_private_network=allow_private_network)
        key = os.environ.get(f"{prefix}_API_KEY", "").strip() or None
        return cls(
            agent_name=agent_name,
            provider=provider,
            base_url=base_url.rstrip("/"),
            model=model,
            api_key=key,
            temperature=float(os.environ.get(f"{prefix}_TEMPERATURE", "0.0")),
            max_tokens=int(os.environ.get(f"{prefix}_MAX_TOKENS", "4096")),
            request_timeout_s=int(os.environ.get(f"{prefix}_REQUEST_TIMEOUT_S", "180")),
            max_retries=int(os.environ.get(f"{prefix}_MAX_RETRIES", "1")),
            retry_backoff_s=float(os.environ.get(f"{prefix}_RETRY_BACKOFF_S", "1.0")),
            allow_private_network=allow_private_network,
        )

    def validate(self) -> None:
        if self.provider == "dry_run":
            return
        if self.provider != "openai_compatible":
            raise ValueError(f"Unsupported local provider: {self.provider}")
        validate_local_base_url(self.base_url, allow_private_network=self.allow_private_network)
        if not self.model or self.model in {"unset-local-model", "REPLACE_WITH_LOCAL_MODEL_ID"} or "REPLACE_" in self.model:
            raise ValueError(f"{self.agent_name}: set an exact local model ID in AGENT_*_MODEL")
        if self.max_tokens <= 0 or self.request_timeout_s <= 0 or self.max_retries < 0:
            raise ValueError(f"{self.agent_name}: invalid max_tokens/timeout/retry configuration")


def validate_local_base_url(base_url: str, *, allow_private_network: bool = False) -> None:
    """Fail closed unless the URL points to loopback or an explicitly allowed private IP.

    Hostnames other than localhost are rejected; this prevents a seemingly local
    DNS name from silently resolving to a public service. For a service in another
    container/host, use a private numeric IP and explicitly opt in.
    """
    u = urlsplit(base_url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("Local API BASE_URL must be an http(s) URL with a host")
    if u.username or u.password or u.query or u.fragment:
        raise ValueError("BASE_URL must not embed credentials, query parameters, or fragments")
    if u.path.rstrip("/").endswith(("/chat/completions", "/models")):
        raise ValueError("BASE_URL must be the API root (e.g. http://127.0.0.1:11434/v1), not an endpoint URL")
    host = u.hostname.lower().rstrip(".")
    if host == "localhost":
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(
            f"Non-local hostname {host!r} rejected in local-only mode; use localhost/loopback, "
            "or a private numeric IP with --allow-private-network."
        ) from exc
    if ip.is_loopback:
        return
    if allow_private_network and (ip.is_private or ip.is_link_local) and not ip.is_global:
        return
    raise ValueError(
        f"Endpoint host {host!r} is not loopback. Private LAN use requires --allow-private-network; "
        "public endpoints are blocked."
    )


def _session() -> requests.Session:
    s = requests.Session()
    # Do not silently route a loopback request through HTTP(S)_PROXY from the shell.
    s.trust_env = False
    return s


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
    return "" if content is None else str(content)


def call_llm(cfg: LocalEndpointConfig, system_prompt: str, user_prompt: str) -> LLMResponse:
    cfg.validate()
    t0 = time.time()
    if cfg.provider == "dry_run":
        return _dry_run_response(cfg, system_prompt, user_prompt, t0)

    endpoint = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    session = _session()
    last_error = None
    for attempt in range(cfg.max_retries + 1):
        try:
            resp = session.post(endpoint, headers=headers, json=payload,
                                timeout=cfg.request_timeout_s, allow_redirects=False)
            if 300 <= resp.status_code < 400:
                raise LLMCallError(f"Local endpoint returned redirect HTTP {resp.status_code}; redirects are disabled")
            if resp.status_code in (408, 425, 429) or resp.status_code >= 500:
                raise LLMCallError(f"Local endpoint transient HTTP {resp.status_code}: {resp.text[:300]}")
            if resp.status_code >= 400:
                raise LLMCallError(f"Local endpoint client HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            choice = (data.get("choices") or [None])[0]
            if not isinstance(choice, dict):
                raise LLMCallError("OpenAI-compatible response lacks choices[0]")
            message = choice.get("message") or {}
            text = _content_to_text(message.get("content"))
            if not text:
                raise LLMCallError("OpenAI-compatible response has empty message.content")
            usage = data.get("usage") or {}
            return LLMResponse(
                text=text,
                provider="openai_compatible_local",
                model_name=cfg.model,
                model_version=str(data.get("model", cfg.model)),
                endpoint=endpoint,
                temperature=cfg.temperature,
                input_tokens=usage.get("prompt_tokens", usage.get("input_tokens")),
                output_tokens=usage.get("completion_tokens", usage.get("output_tokens")),
                latency_s=time.time() - t0,
                retry_count=attempt,
                finish_reason=choice.get("finish_reason"),
                raw_response=data,
                execution_channel="local_api_call",
            )
        except LLMCallError as exc:
            last_error = exc
            retryable = "transient HTTP" in str(exc)
        except requests.RequestException as exc:
            last_error = exc
            retryable = True
        except (ValueError, KeyError, TypeError) as exc:
            last_error = exc
            retryable = False
        if not retryable or attempt >= cfg.max_retries:
            break
        time.sleep(cfg.retry_backoff_s * (2 ** attempt))
    raise LLMCallError(f"{cfg.agent_name} local API call failed at {endpoint}: {last_error}")


def list_models(cfg: LocalEndpointConfig) -> list[str]:
    cfg.validate()
    if cfg.provider == "dry_run":
        return ["dry-run-stub"]
    endpoint = cfg.base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
    with _session() as session:
        resp = session.get(endpoint, headers=headers, timeout=cfg.request_timeout_s, allow_redirects=False)
        if 300 <= resp.status_code < 400:
            raise LLMCallError("Local /models endpoint returned a redirect; redirects are disabled")
        resp.raise_for_status()
        data = resp.json()
    return [str(m["id"]) for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]


def _dry_run_response(cfg: LocalEndpointConfig, system_prompt: str, user_prompt: str, t0: float) -> LLMResponse:
    """Generate explicit synthetic placeholders for pipeline mechanics only."""
    try:
        payload = json.loads(user_prompt)
    except Exception:
        payload = {}
    is_agent_a = "Agent A" in system_prompt and ("Extractor" in system_prompt or "抽取器" in system_prompt)
    is_agent_b = "Agent B" in system_prompt and ("Critic" in system_prompt or "审查员" in system_prompt)
    if is_agent_a:
        dims = payload.get("dimensions_schema") or {}
        text = json.dumps([
            {
                "dimension_id": dim_id,
                "primary_label": "Insufficient_Evidence",
                "secondary_labels": [],
                "own_method_vs_cited": "Paper_Own_Method",
                "mechanism_judgment": "DRY RUN placeholder only; no model inference was performed.",
                "uncertainty_note": "Synthetic test output, not a paper judgment.",
                "evidence_ids": [],
                "verbatim_quote": "",
                "confidence": 0.0,
            }
            for dim_id in dims
        ], ensure_ascii=False)
    elif is_agent_b:
        records = payload.get("agent_a_structured_output") or []
        text = json.dumps({
            r["dimension_id"]: {
                "decision": "insufficient_evidence",
                "corrected_label": None,
                "critic_comment": "DRY RUN placeholder only; not a review or adjudication.",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
                "confidence": 0.0,
                "checks_failed": [],
            }
            for r in records if isinstance(r, dict) and r.get("dimension_id")
        }, ensure_ascii=False)
    else:
        text = json.dumps({"dry_run": True, "notice": "No model inference was performed."})
    return LLMResponse(
        text=text,
        provider="dry_run_no_network",
        model_name="dry-run-stub",
        model_version="dry-run-stub",
        endpoint="N/A_dry_run",
        temperature=cfg.temperature,
        input_tokens=None,
        output_tokens=None,
        latency_s=time.time() - t0,
        retry_count=0,
        finish_reason="stop",
        raw_response={"dry_run": True},
        execution_channel="dry_run_no_network",
    )
