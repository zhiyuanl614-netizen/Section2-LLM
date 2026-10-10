#!/usr/bin/env python3
"""Step 3 retrieval module: dense + BM25 hybrid search via Reciprocal Rank
Fusion (RRF), per the locked config in model_and_retrieval_config_v1_LOCKED.md.

Loads the index artifacts built by step3_build_hybrid_index.py and exposes a
single `hybrid_search()` function reused by both the validation harness and
(later) Step 4's coverage-pass + dimension-retrieval-pass construction.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DENSE_DIR = ROOT / "01_稠密向量索引"
BM25_DIR = ROOT / "02_BM25词法索引"
EVIDENCE_PATH = ROOT.parent / "02_PDF清洗与分块" / "02_Chunks" / "evidence_blocks.jsonl"

RRF_K = 60
PER_LEG_TOP_K = 20
FUSED_TOP_K = 10


class HybridIndex:
    def __init__(self) -> None:
        self.records = self._load_evidence_blocks()
        self.by_id = {r["evidence_id"]: r for r in self.records}

        with open(BM25_DIR / "bm25_index.pkl", "rb") as f:
            bm25_data = pickle.load(f)
        self.bm25 = bm25_data["bm25"]
        with open(BM25_DIR / "bm25_evidence_ids.json", encoding="utf-8") as f:
            self.bm25_ids = json.load(f)

        self.dense_embs = np.load(DENSE_DIR / "dense_embeddings.npy")
        with open(DENSE_DIR / "dense_evidence_ids.json", encoding="utf-8") as f:
            self.dense_ids = json.load(f)

        assert self.bm25_ids == self.dense_ids, "BM25 and dense index evidence_id order must match"
        self._dense_norms = np.linalg.norm(self.dense_embs, axis=1) + 1e-9

        self._embed_model = None  # lazy-loaded on first query embedding

    @staticmethod
    def _load_evidence_blocks() -> list[dict]:
        records = []
        with open(EVIDENCE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def _get_embed_model(self):
        if self._embed_model is None:
            from fastembed import TextEmbedding
            self._embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self._embed_model

    def bm25_search(self, query: str, top_k: int = PER_LEG_TOP_K) -> list[tuple[str, float]]:
        from step3_build_hybrid_index import bm25_tokenize
        scores = self.bm25.get_scores(bm25_tokenize(query))
        order = np.argsort(-scores)[:top_k]
        return [(self.bm25_ids[i], float(scores[i])) for i in order]

    def dense_search(self, query: str, top_k: int = PER_LEG_TOP_K) -> list[tuple[str, float]]:
        model = self._get_embed_model()
        q_emb = np.array(list(model.embed([query], batch_size=1))[0], dtype=np.float32)
        q_norm = np.linalg.norm(q_emb) + 1e-9
        sims = (self.dense_embs @ q_emb) / (self._dense_norms * q_norm)
        order = np.argsort(-sims)[:top_k]
        return [(self.dense_ids[i], float(sims[i])) for i in order]

    def hybrid_search(
        self, query: str, per_leg_top_k: int = PER_LEG_TOP_K, fused_top_k: int = FUSED_TOP_K, rrf_k: int = RRF_K
    ) -> dict:
        bm25_ranked = self.bm25_search(query, per_leg_top_k)
        dense_ranked = self.dense_search(query, per_leg_top_k)

        rrf_scores: dict[str, float] = {}
        for rank, (eid, _) in enumerate(bm25_ranked, start=1):
            rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (rrf_k + rank)
        for rank, (eid, _) in enumerate(dense_ranked, start=1):
            rrf_scores[eid] = rrf_scores.get(eid, 0.0) + 1.0 / (rrf_k + rank)

        fused = sorted(rrf_scores.items(), key=lambda kv: -kv[1])[:fused_top_k]
        return {
            "query": query,
            "bm25_top": bm25_ranked,
            "dense_top": dense_ranked,
            "fused_top": fused,
        }

    def coverage_pass_ids(self, doc_id: str) -> list[str]:
        """Return ALL evidence_ids for a document, regardless of ranking — used for
        the coverage pass (full-text forced traversal), independent of top-k retrieval."""
        return [r["evidence_id"] for r in self.records if r["doc_id"] == doc_id]


if __name__ == "__main__":
    idx = HybridIndex()
    result = idx.hybrid_search("early warning proactive control fast sensing slow hydraulic timescale")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
