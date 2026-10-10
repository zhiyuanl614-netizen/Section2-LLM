#!/usr/bin/env python3
"""Path-configurable, fail-closed local loader for a versioned Step 3 index.

Index directory layout is produced by step3_build_hybrid_index_v1_2_local.py.
The embedding model is loaded with local_files_only=True by default so a
missing cache fails locally instead of silently downloading over the network.
Only load index directories created by a trusted local build: the BM25 artifact
uses Python pickle (hashes detect corruption, not maliciously forged content).
"""
from __future__ import annotations

import hashlib
import json
import pickle
import re
from pathlib import Path
from typing import Optional

import numpy as np

# Verbatim tokenizer used by the locked Step 3 index builder.
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


def bm25_tokenize(text: str) -> list[str]:
    text = text.replace(chr(0x00AD), "")
    tokens = TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


RRF_K = 60
PER_LEG_TOP_K = 20
FUSED_TOP_K = 10


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class LocalHybridIndex:
    def __init__(
        self,
        evidence_blocks_path: str | Path,
        index_dir: str | Path,
        *,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        embedding_cache_dir: Optional[str | Path] = None,
        local_files_only: bool = True,
    ) -> None:
        self.evidence_blocks_path = Path(evidence_blocks_path).expanduser().resolve()
        self.index_dir = Path(index_dir).expanduser().resolve()
        self.embedding_model_name = embedding_model
        self.embedding_cache_dir = Path(embedding_cache_dir).expanduser().resolve() if embedding_cache_dir else None
        self.local_files_only = local_files_only
        manifest_path = self.index_dir / "index_build_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Versioned local index manifest is required: {manifest_path}")
        self.index_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if self.index_manifest.get("pipeline_version") != "Step3-v1.2-local-text-scope" or self.index_manifest.get("schema_version") != "v1.2":
            raise ValueError("Index manifest is not from the v1.2 local-text builder")
        if self.index_manifest.get("input_sha256") != sha256_file(self.evidence_blocks_path):
            raise ValueError("Evidence blocks SHA-256 differs from the evidence file used to build this index")
        expected_artifacts = {
            "bm25_index.pkl", "bm25_evidence_ids.json", "dense_embeddings.npy", "dense_evidence_ids.json"
        }
        recorded_hashes = self.index_manifest.get("artifact_sha256", {})
        if set(recorded_hashes) != expected_artifacts:
            raise ValueError("Index manifest has missing/unexpected artifact hashes")
        for name in sorted(expected_artifacts):
            artifact = self.index_dir / name
            if not artifact.is_file() or sha256_file(artifact) != recorded_hashes[name]:
                raise ValueError(f"Index artifact missing or hash mismatch: {artifact}")
        if self.index_manifest.get("dense", {}).get("model_name") != self.embedding_model_name:
            raise ValueError(
                f"Embedding model mismatch: index={self.index_manifest.get('dense', {}).get('model_name')!r}, "
                f"query={self.embedding_model_name!r}"
            )

        self.records = self._load_evidence_blocks()
        self.by_id = {r["evidence_id"]: r for r in self.records}
        if len(self.by_id) != len(self.records):
            raise ValueError("Duplicate evidence_id in evidence_blocks file")
        if self.index_manifest.get("record_count") != len(self.records):
            raise ValueError("Evidence record count does not match v1.2 index manifest")

        with open(self.index_dir / "bm25_index.pkl", "rb") as f:
            bm25_data = pickle.load(f)
        self.bm25 = bm25_data["bm25"]
        self.bm25_ids = self._read_index_ids("bm25_evidence_ids.json")
        self.dense_ids = self._read_index_ids("dense_evidence_ids.json")
        if self.bm25_ids != self.dense_ids:
            raise ValueError("BM25 and dense evidence_id order differs")
        expected = [r["evidence_id"] for r in self.records]
        if expected != self.bm25_ids:
            raise ValueError("Evidence blocks and versioned index do not match in count/order; rebuild a new index version")

        self.dense_embs = np.load(self.index_dir / "dense_embeddings.npy", allow_pickle=False)
        if self.dense_embs.ndim != 2 or self.dense_embs.shape[0] != len(self.dense_ids):
            raise ValueError("Dense embedding matrix shape does not match dense_evidence_ids.json")
        self._dense_norms = np.linalg.norm(self.dense_embs, axis=1) + 1e-9
        self._embed_model = None

    def _read_index_ids(self, name: str) -> list[str]:
        with open(self.index_dir / name, encoding="utf-8") as f:
            ids = json.load(f)
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            raise ValueError(f"Invalid evidence ID list: {self.index_dir / name}")
        return ids

    def _load_evidence_blocks(self) -> list[dict]:
        if not self.evidence_blocks_path.is_file():
            raise FileNotFoundError(self.evidence_blocks_path)
        out = []
        with open(self.evidence_blocks_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                if not isinstance(rec, dict) or not rec.get("evidence_id") or not rec.get("doc_id"):
                    raise ValueError(f"Invalid evidence block at line {line_no}")
                out.append(rec)
        return out

    def _get_embed_model(self):
        if self._embed_model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError("fastembed is required for dense query retrieval; install local requirements first") from exc
            kwargs = {"model_name": self.embedding_model_name, "local_files_only": self.local_files_only}
            if self.embedding_cache_dir is not None:
                kwargs["cache_dir"] = str(self.embedding_cache_dir)
            try:
                self._embed_model = TextEmbedding(**kwargs)
            except TypeError as exc:
                if self.local_files_only:
                    raise RuntimeError(
                        "This FastEmbed version does not support local_files_only; upgrade FastEmbed or run "
                        "with a version that can fail closed without network downloads."
                    ) from exc
                raise
        return self._embed_model

    def bm25_search(self, query: str, top_k: int = PER_LEG_TOP_K) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(bm25_tokenize(query))
        order = np.argsort(-scores)[:top_k]
        return [(self.bm25_ids[int(i)], float(scores[int(i)])) for i in order]

    def dense_search(self, query: str, top_k: int = PER_LEG_TOP_K) -> list[tuple[str, float]]:
        model = self._get_embed_model()
        q_emb = np.asarray(list(model.embed([query], batch_size=1))[0], dtype=np.float32)
        if q_emb.shape[0] != self.dense_embs.shape[1]:
            raise ValueError(f"Query embedding dimension {q_emb.shape[0]} != index dimension {self.dense_embs.shape[1]}")
        q_norm = np.linalg.norm(q_emb) + 1e-9
        sims = (self.dense_embs @ q_emb) / (self._dense_norms * q_norm)
        order = np.argsort(-sims)[:top_k]
        return [(self.dense_ids[int(i)], float(sims[int(i)])) for i in order]

    def hybrid_search(self, query: str, per_leg_top_k: int = PER_LEG_TOP_K,
                      fused_top_k: int = FUSED_TOP_K, rrf_k: int = RRF_K) -> dict:
        bm25_ranked = self.bm25_search(query, per_leg_top_k)
        dense_ranked = self.dense_search(query, per_leg_top_k)
        scores: dict[str, float] = {}
        for rank, (eid, _) in enumerate(bm25_ranked, start=1):
            scores[eid] = scores.get(eid, 0.0) + 1.0 / (rrf_k + rank)
        for rank, (eid, _) in enumerate(dense_ranked, start=1):
            scores[eid] = scores.get(eid, 0.0) + 1.0 / (rrf_k + rank)
        fused = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:fused_top_k]
        return {"query": query, "bm25_top": bm25_ranked, "dense_top": dense_ranked, "fused_top": fused}

    def coverage_pass_ids(self, doc_id: str) -> list[str]:
        return [r["evidence_id"] for r in self.records if r["doc_id"] == doc_id]

    def doc_ids(self) -> list[str]:
        return sorted({r["doc_id"] for r in self.records})
