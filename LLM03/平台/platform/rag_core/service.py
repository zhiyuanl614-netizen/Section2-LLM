from __future__ import annotations

from typing import Any

from .data import ReleaseStore
from .generation import (
    LocalChatConfig,
    LocalGenerationError,
    RemoteChatConfig,
    generate_local_answer,
    generate_remote_answer,
)
from .retrieval import LocalRetriever


class PlatformService:
    def __init__(self, release_dir: str) -> None:
        self.store = ReleaseStore(release_dir, verify_hashes=True)
        self.retriever = LocalRetriever(self.store)
        # External API calls are enabled only by app.py when bound to loopback.
        self.remote_api_allowed = False
        try:
            self.chat_config = LocalChatConfig.from_env()
            self.chat_config_error = None
        except LocalGenerationError as exc:
            self.chat_config = None
            self.chat_config_error = str(exc)

    def status(self) -> dict:
        release = self.store.release
        return {
            "ok": True,
            "platform_version": release.get("platform_version"),
            "release_id": release.get("release_id"),
            "release_status": release.get("status"),
            "corpus_size": release.get("corpus_size"),
            "evidence_block_count": release.get("evidence_block_count"),
            "active_record_count": release.get("active_record_count"),
            "graph_node_count": release.get("graph_node_count"),
            "graph_edge_count": release.get("graph_edge_count"),
            "active_dimensions": release.get("active_dimensions"),
            "read_only": True,
            "single_user": True,
            "upload_enabled": False,
            "external_network_required": False,
            "dense": self.retriever.dense_status,
            "local_chat": {
                "configured": bool(self.chat_config),
                "enabled_by_default": False,
                "loopback_only": True,
                "model": self.chat_config.model if self.chat_config else None,
                "config_error": self.chat_config_error,
            },
            "external_api": {
                "allowed": bool(self.remote_api_allowed),
                "requires_explicit_per_request_config": True,
                "api_key_persisted": False,
                "max_evidence_blocks": 5,
                "formula_risk_blocks_sent": False,
                "full_pdfs_sent": False,
            },
            "important_limits": [
                "五篇先导语料，不代表领域总体。",
                "当前 ledger 是 provisional mixed-provenance，非独立人工金标准。",
                "D03 方程类型/公式解析范围不纳入图谱与结论；D03 记录未进入平台活动数据。",
                "PDF-03/D02 边界未裁定；候选标签不是用户或专家批准。",
                "默认只返回检索证据包，不自动生成研究结论。",
            ],
        }

    def documents(self) -> list[dict]:
        output = []
        record_counts: dict[str, int] = {}
        for row in self.store.records:
            record_counts[row["doc_id"]] = record_counts.get(row["doc_id"], 0) + 1
        block_counts: dict[str, int] = {}
        for block in self.store.blocks:
            block_counts[block["doc_id"]] = block_counts.get(block["doc_id"], 0) + 1
        for doc in self.store.documents:
            output.append({
                **doc,
                "evidence_block_count": block_counts.get(doc["doc_id"], 0),
                "active_record_count": record_counts.get(doc["doc_id"], 0),
                "pdf_url": f"/pdf/{doc['doc_id']}",
            })
        return output

    def directions(self) -> list[dict]:
        result = []
        for direction in self.store.directions:
            result.append({
                "id": direction.get("id"),
                "rq": direction.get("rq"),
                "title": direction.get("title"),
                "hypothesis_to_test": direction.get("hypothesis_to_test"),
                "pilot_result": direction.get("v1_2_result"),
                "dimensions": direction.get("dimensions", []),
                "evidence_count": len(direction.get("evidence_ids") or []),
                "interpretation": direction.get("interpretation"),
                "status": "existing candidate; pilot evidence only; not a confirmed gap",
            })
        return result

    def graph(self, direction_id: str | None = None) -> dict:
        return self.store.graph_for_direction(direction_id)

    def search(self, query: str, top_k: int = 10, mode: str = "hybrid", direction: str | None = None, doc_id: str | None = None) -> dict:
        return self.retriever.search(query, top_k=top_k, mode=mode, direction=direction, doc_id=doc_id)

    def qa(
        self, query: str, top_k: int = 8, mode: str = "hybrid", direction: str | None = None,
        doc_id: str | None = None, generate: bool = False, remote_api: dict | None = None,
    ) -> dict:
        search_result = self.search(query, top_k=top_k, mode=mode, direction=direction, doc_id=doc_id)
        packet = self.retriever.build_evidence_packet(query, search_result)
        answer = None
        generation_error = None
        if generate and remote_api is not None:
            generation_error = "Choose either the local model or an external API for a request, not both."
        elif remote_api is not None:
            if not self.remote_api_allowed:
                generation_error = "External API calls are enabled only when the platform is bound to loopback (127.0.0.1)."
            elif search_result.get("hits") and not search_result.get("out_of_scope"):
                try:
                    config = RemoteChatConfig.from_payload(remote_api)
                    answer = generate_remote_answer(query, search_result["hits"], config)
                except LocalGenerationError as exc:
                    generation_error = str(exc)
        elif generate and search_result.get("hits") and not search_result.get("out_of_scope"):
            if not self.chat_config:
                generation_error = self.chat_config_error or "No local loopback chat model is configured; no remote fallback is available."
            else:
                try:
                    answer = generate_local_answer(query, search_result["hits"], self.chat_config)
                except LocalGenerationError as exc:
                    generation_error = str(exc)
        remote_used = bool(answer and answer.get("execution_mode") == "external_api")
        return {
            "search": search_result,
            "evidence_packet": packet,
            "generated_answer": answer,
            "generation_requested": bool(generate or remote_api is not None),
            "generation_error": generation_error,
            "notice": (
                "本次明确调用了用户配置的外部 API；最多发送5条检索证据块（不含公式风险块），不发送整篇 PDF。引用编号可校验，语义支持仍需人工核查。"
                if remote_used else (
                    "模型答案若启用，只通过显式配置的本机 loopback endpoint；引用编号可校验，语义支持仍需人工核查。"
                    if answer else "默认模式不调用生成模型；检索命中不是方向被支持的证明。"
                )
            ),
        }

    def evidence(self, evidence_id: str) -> dict | None:
        block = self.store.block_by_id.get(evidence_id)
        if not block:
            return None
        doc = self.store.document_by_id[block["doc_id"]]
        return {
            "evidence_id": evidence_id,
            "doc_id": block["doc_id"],
            "title": doc.get("title"),
            "pages": block.get("page_numbers") or [],
            "section_id": block.get("section_id"),
            "section_title": block.get("section_title"),
            "zone": block.get("zone"),
            "text": block.get("text", ""),
            "formula_layout_risk": bool(block.get("formula_layout_risk", False)),
            "formula_layout_risk_score": block.get("formula_layout_risk_score"),
            "pdf_url": f"/pdf/{block['doc_id']}#page={min(block.get('page_numbers') or [block.get('page') or 1])}",
            "record_refs": self.retriever.record_refs.get(evidence_id, []),
        }

    def records_for_document(self, doc_id: str) -> list[dict] | None:
        if doc_id not in self.store.document_by_id:
            return None
        return [row for row in self.store.records if row.get("doc_id") == doc_id]
