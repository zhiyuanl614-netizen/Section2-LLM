from __future__ import annotations

import importlib.util
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .data import ReleaseStore

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "we", "our", "they", "their", "he", "she", "his", "her", "can", "could", "would", "should",
    "will", "shall", "may", "might", "must", "not", "no", "do", "does", "did", "have", "has", "had", "which",
    "who", "whom", "what", "when", "where", "why", "how", "also", "such", "both", "each", "more", "most",
    "other", "some", "any", "all", "into", "through", "during", "before", "after", "above", "below", "between",
    "out", "up", "down", "over", "under", "again", "further", "once",
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|[0-9]+(?:[.][0-9]+)?")

# Deliberately small, explicit query expansion for this five-paper pilot.
# These are retrieval aids only; they are not labels or evidence.
QUERY_EXPANSIONS = {
    "水电耦合": "water power interdependence water-power",
    "水-电耦合": "water power interdependence water-power",
    "冷却水": "cooling water cooling-water",
    "厂内冷却": "in-plant cooling power plant cooling-water",
    "冷却过程": "cooling process cooling-water demand",
    "快感知": "fast sensing cyber information layer SCADA",
    "信息层": "information layer cyber SCADA sensing",
    "多时间尺度": "multi-timescale time scale timescale multistage",
    "时间尺度": "time scale timescale multi-timescale",
    "早期预警": "early warning warning alert",
    "主动控制": "proactive control anticipatory control closed-loop",
    "社会脆弱性": "social vulnerability social vulnerability index",
    "脆弱性": "social vulnerability vulnerable population",
    "人口影响": "population affected population count human impact",
    "关键设施": "critical facility critical infrastructure facility disruption",
    "服务损失": "service loss service disruption network loss",
    "未来工作": "future work future research limitation",
    "反例": "counterexample counterevidence limitation",
    "研究局限": "limitation future work generalizability",
}

FORMULA_QUERY_RE = re.compile(
    r"(公式|方程|推导|导出方程|变量含义|符号含义|公式类型|方程类型|equation|equations|formula|formulas|derive|derivation|variable definition|symbol definition)",
    re.IGNORECASE,
)


def tokenize(text: str) -> list[str]:
    text = (text or "").replace("\u00ad", "")
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS and len(token) > 1]


def expand_query(query: str) -> tuple[str, list[str]]:
    additions: list[str] = []
    for phrase, expansion in QUERY_EXPANSIONS.items():
        if phrase in query and expansion not in additions:
            additions.append(expansion)
    expanded = query + (" " + " ".join(additions) if additions else "")
    return expanded, additions


class BM25:
    """Small self-contained Okapi BM25 implementation for a 239-block corpus."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.documents = [tokenize(text) for text in documents]
        self.k1 = k1
        self.b = b
        self.n = len(self.documents)
        self.lengths = [len(doc) for doc in self.documents]
        self.avgdl = sum(self.lengths) / max(1, self.n)
        self.term_freqs = [Counter(doc) for doc in self.documents]
        df: Counter[str] = Counter()
        for freq in self.term_freqs:
            df.update(freq.keys())
        self.idf = {
            term: math.log(1.0 + (self.n - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def score(self, query: str) -> list[float]:
        terms = tokenize(query)
        if not terms:
            return [0.0] * self.n
        scores = [0.0] * self.n
        for index, frequencies in enumerate(self.term_freqs):
            dl = self.lengths[index]
            norm = self.k1 * (1.0 - self.b + self.b * dl / max(self.avgdl, 1e-9))
            score = 0.0
            for term in terms:
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                score += self.idf.get(term, 0.0) * (tf * (self.k1 + 1.0)) / (tf + norm)
            scores[index] = score
        return scores


def _top_indices(scores: list[float], limit: int) -> list[int]:
    return sorted((i for i, score in enumerate(scores) if score > 0), key=lambda i: (-scores[i], i))[:limit]


class LocalRetriever:
    def __init__(self, store: ReleaseStore) -> None:
        self.store = store
        self.blocks = store.blocks
        self.ids = [row["evidence_id"] for row in self.blocks]
        self.block_index = {eid: i for i, eid in enumerate(self.ids)}
        self.bm25 = BM25([row.get("retrieval_text") or row.get("text", "") for row in self.blocks])
        self.record_refs: dict[str, list[dict]] = defaultdict(list)
        for record in store.records:
            for evidence_id in record.get("evidence_ids") or []:
                self.record_refs[evidence_id].append({
                    "doc_id": record.get("doc_id"),
                    "dimension_id": record.get("dimension_id"),
                    "primary_label": record.get("primary_label"),
                    "verification_status": record.get("verification_status"),
                    "record_origin": record.get("record_origin"),
                })
        self.direction_by_id = {row.get("id"): row for row in store.directions}
        self.direction_search = BM25([self._direction_search_text(row) for row in store.directions])
        self._dense_model = None
        self._dense_matrix = None
        self._dense_ids: list[str] | None = None
        self._dense_error: str | None = None
        self.dense_enabled = os.environ.get("PLATFORM_ENABLE_DENSE", "0").strip().lower() in {"1", "true", "yes"}
        self.dense_model_name = "BAAI/bge-small-en-v1.5"
        self.dense_cache_dir = os.environ.get("PLATFORM_EMBEDDING_CACHE_DIR", "").strip() or None
        self.chat_enabled = bool(os.environ.get("PLATFORM_LOCAL_CHAT_BASE_URL") and os.environ.get("PLATFORM_LOCAL_CHAT_MODEL"))

    @staticmethod
    def _direction_search_text(direction: dict) -> str:
        dimensions = " ".join(direction.get("dimensions") or [])
        return " ".join([
            str(direction.get("id", "")), str(direction.get("rq", "")),
            str(direction.get("title", "")), str(direction.get("hypothesis_to_test", "")), dimensions,
        ])

    @property
    def dense_status(self) -> dict:
        manifest = self.store.read_json("index/index_manifest.json")
        return {
            "index_present": True,
            "index_model": manifest.get("dense_model"),
            "query_encoder_enabled": self.dense_enabled,
            "fastembed_installed": importlib.util.find_spec("fastembed") is not None,
            "cache_dir_configured": bool(self.dense_cache_dir),
            "error": self._dense_error,
        }

    def _load_dense(self) -> None:
        if self._dense_model is not None:
            return
        try:
            import numpy as np
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError("fastembed is not installed; Dense query retrieval remains disabled") from exc
            index_manifest = self.store.read_json("index/index_manifest.json")
            if index_manifest.get("dense_model") != self.dense_model_name:
                raise RuntimeError("The configured local query model does not match the indexed document model")
            kwargs = {"model_name": self.dense_model_name, "local_files_only": True}
            if self.dense_cache_dir:
                cache = Path(self.dense_cache_dir).expanduser().resolve()
                if not cache.exists():
                    raise RuntimeError("Configured FastEmbed cache directory does not exist")
                kwargs["cache_dir"] = str(cache)
            try:
                self._dense_model = TextEmbedding(**kwargs)
            except TypeError as exc:
                raise RuntimeError("Installed FastEmbed lacks local_files_only support; refusing any download fallback") from exc
            matrix = np.load(self.store.path("index/dense_embeddings.npy"), allow_pickle=False)
            ids = self.store.read_json("index/dense_evidence_ids.json")
            if ids != self.ids or matrix.ndim != 2 or matrix.shape[0] != len(ids):
                raise RuntimeError("Dense matrix/IDs do not align with the loaded evidence blocks")
            self._dense_matrix = matrix
            self._dense_ids = ids
        except Exception as exc:
            self._dense_error = f"{type(exc).__name__}: {exc}"
            self._dense_model = None
            raise

    def dense_search(self, expanded_query: str, limit: int) -> list[tuple[str, float]]:
        self._load_dense()
        import numpy as np
        query_vector = np.asarray(list(self._dense_model.embed([expanded_query], batch_size=1))[0], dtype=np.float32)
        if query_vector.shape[0] != self._dense_matrix.shape[1]:
            raise RuntimeError("Dense query vector dimension differs from the release matrix")
        norm = np.linalg.norm(query_vector) + 1e-9
        matrix_norms = np.linalg.norm(self._dense_matrix, axis=1) + 1e-9
        scores = (self._dense_matrix @ query_vector) / (matrix_norms * norm)
        ids = self._dense_ids or []
        order = sorted(range(len(ids)), key=lambda i: (-float(scores[i]), i))[:limit]
        return [(ids[i], float(scores[i])) for i in order]

    def _direction_candidates(self, expanded_query: str, requested_direction: str | None, limit: int) -> list[tuple[dict, float]]:
        if requested_direction and requested_direction != "all":
            direction = self.direction_by_id.get(requested_direction)
            return [(direction, 1.0)] if direction else []
        scores = self.direction_search.score(expanded_query)
        order = _top_indices(scores, min(3, limit))
        return [(self.store.directions[i], scores[i]) for i in order]

    def graph_search(self, expanded_query: str, requested_direction: str | None, limit: int) -> list[tuple[str, float, list[str]]]:
        direction_hits = self._direction_candidates(expanded_query, requested_direction, limit)
        if not direction_hits:
            return []
        evidence_direction_scores: dict[str, float] = defaultdict(float)
        direction_refs: dict[str, set[str]] = defaultdict(set)
        for direction_rank, (direction, direction_score) in enumerate(direction_hits, 1):
            if not direction:
                continue
            direction_id = direction.get("id")
            direction_weight = 1.0 / (60 + direction_rank)
            candidate_ids = set(direction.get("evidence_ids") or [])
            direction_dims = set(direction.get("dimensions") or [])
            for record in self.store.records:
                if record.get("dimension_id") in direction_dims:
                    candidate_ids.update(record.get("evidence_ids") or [])
            # The relation means “linked/cited by a pilot record or synthesis”,
            # not that it supports or refutes the direction.
            for evidence_id in candidate_ids:
                if evidence_id not in self.store.block_by_id:
                    continue
                evidence_direction_scores[evidence_id] += direction_weight + max(0.0, direction_score) * 1e-5
                direction_refs[evidence_id].add(direction_id)
        ranked = sorted(evidence_direction_scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return [(eid, score, sorted(direction_refs[eid])) for eid, score in ranked]

    def _prepare_hit(self, evidence_id: str, score: float, channels: list[str], direction_refs: list[str]) -> dict:
        block = self.store.block_by_id[evidence_id]
        doc = self.store.document_by_id[block["doc_id"]]
        section_title = block.get("section_title") or ""
        return {
            "evidence_id": evidence_id,
            "doc_id": block["doc_id"],
            "title": doc.get("title") or doc.get("source_filename"),
            "authors": doc.get("authors"),
            "journal": doc.get("journal"),
            "pub_year": doc.get("pub_year"),
            "doi": doc.get("doi"),
            "pages": block.get("page_numbers") or ([block.get("page")] if block.get("page") else []),
            "section_id": block.get("section_id"),
            "section_title": section_title,
            "text": block.get("text", ""),
            "formula_layout_risk": bool(block.get("formula_layout_risk", False)),
            "formula_layout_risk_score": block.get("formula_layout_risk_score"),
            "source_origin": block.get("source_pdf_sha256"),
            "channels": channels,
            "rrf_score": score,
            "direction_refs": direction_refs,
            "record_refs": self.record_refs.get(evidence_id, []),
            "pdf_url": f"/pdf/{block['doc_id']}#page={min(block.get('page_numbers') or [block.get('page') or 1])}",
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        mode: str = "hybrid",
        direction: str | None = None,
        doc_id: str | None = None,
    ) -> dict:
        query = (query or "").strip()
        if not query:
            return {"query": query, "hits": [], "channels": [], "query_expansions": [], "notice": "请输入一个研究问题或检索词。"}
        if FORMULA_QUERY_RE.search(query):
            return {
                "query": query, "hits": [], "channels": [], "query_expansions": [],
                "out_of_scope": True,
                "notice": "公式转录、推导、变量/符号解释与方程类型分析不在本平台分析范围内。原文和公式风险标记仍可用于人工回查。",
            }
        top_k = max(1, min(int(top_k), 20))
        expanded_query, expansions = expand_query(query)
        mode = mode if mode in {"hybrid", "bm25"} else "hybrid"
        if doc_id and doc_id not in self.store.document_by_id:
            return {"query": query, "hits": [], "channels": [], "query_expansions": expansions, "notice": "所选文献 ID 不在当前 release 中。"}

        candidate_channels: dict[str, set[str]] = defaultdict(set)
        candidate_scores: dict[str, float] = defaultdict(float)
        direction_refs: dict[str, set[str]] = defaultdict(set)
        channel_ranks: dict[str, dict[str, int]] = defaultdict(dict)
        channel_scores: dict[str, dict[str, float]] = defaultdict(dict)
        active_channels: list[str] = []

        lexical_scores = self.bm25.score(expanded_query)
        lexical_indices = _top_indices(lexical_scores, 20)
        if doc_id:
            lexical_indices = [i for i in lexical_indices if self.blocks[i].get("doc_id") == doc_id]
        active_channels.append("bm25")
        for rank, index in enumerate(lexical_indices, 1):
            eid = self.ids[index]
            candidate_channels[eid].add("BM25")
            channel_ranks["bm25"][eid] = rank
            channel_scores["bm25"][eid] = lexical_scores[index]

        if mode == "hybrid":
            graph_hits = self.graph_search(expanded_query, direction, 20)
            if doc_id:
                graph_hits = [row for row in graph_hits if self.store.block_by_id[row[0]].get("doc_id") == doc_id]
            if graph_hits:
                active_channels.append("kg_link")
            for rank, (eid, score, refs) in enumerate(graph_hits, 1):
                candidate_channels[eid].add("KG evidence link")
                direction_refs[eid].update(refs)
                channel_ranks["kg_link"][eid] = rank
                channel_scores["kg_link"][eid] = score

            if self.dense_enabled:
                try:
                    dense_hits = self.dense_search(expanded_query, 20)
                    if doc_id:
                        dense_hits = [row for row in dense_hits if self.store.block_by_id[row[0]].get("doc_id") == doc_id]
                    active_channels.append("dense")
                    for rank, (eid, score) in enumerate(dense_hits, 1):
                        candidate_channels[eid].add("Dense")
                        channel_ranks["dense"][eid] = rank
                        channel_scores["dense"][eid] = score
                except Exception as exc:
                    self._dense_error = f"{type(exc).__name__}: {exc}"

        for channel in active_channels:
            for eid, rank in channel_ranks[channel].items():
                candidate_scores[eid] += 1.0 / (60 + rank)
        if not active_channels:
            active_channels = ["bm25"]
        ordered_ids = sorted(candidate_scores, key=lambda eid: (-candidate_scores[eid], eid))[:top_k]
        hits = [
            self._prepare_hit(eid, candidate_scores[eid], sorted(candidate_channels[eid]), sorted(direction_refs[eid]))
            for eid in ordered_ids
        ]
        notices = []
        if mode == "hybrid" and "dense" not in active_channels:
            notices.append("Dense 文档向量已随 release 保存；当前未启用匹配的本地查询编码器，检索使用 BM25 与可匹配的图谱证据链接。")
        if direction and not channel_ranks.get("kg_link"):
            notices.append("该方向当前未产生可用图谱证据链接；结果仍可来自 BM25。")
        notices.append("图谱关系表示记录/引用/来源追溯，不代表证据已支持或反驳研究方向。")
        return {
            "query": query,
            "expanded_query": expanded_query,
            "query_expansions": expansions,
            "mode": "hybrid" if mode == "hybrid" else "bm25",
            "active_channels": active_channels,
            "hits": hits,
            "notices": notices,
            "sample_status": "five-paper pilot; no field-wide inference",
        }

    def build_evidence_packet(self, query: str, search_result: dict) -> dict:
        """Return an extractive, non-generative answer packet with exact source IDs."""
        hits = search_result.get("hits") or []
        return {
            "query": query,
            "answer_mode": "extractive_evidence_packet_no_llm_generation",
            "answer_text": (
                "当前版本只执行本地证据检索和证据包整理，不调用生成模型。请结合引用原文、记录来源和未裁定边界人工判断；"
                "检索命中不等于研究方向得到支持。" if hits else
                "当前没有找到可返回的证据块。请调整检索词，或确认该问题是否属于已限定的公式分析范围外。"
            ),
            "citations": [
                {
                    "citation_id": hit["evidence_id"],
                    "doc_id": hit["doc_id"],
                    "pages": hit["pages"],
                    "section_id": hit["section_id"],
                    "section_title": hit["section_title"],
                    "quote": hit["text"],
                    "formula_layout_risk": hit["formula_layout_risk"],
                    "pdf_url": hit["pdf_url"],
                    "record_refs": hit["record_refs"],
                }
                for hit in hits
            ],
            "notices": search_result.get("notices", []),
        }
