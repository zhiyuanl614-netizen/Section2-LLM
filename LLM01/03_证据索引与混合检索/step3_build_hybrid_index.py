#!/usr/bin/env python3
"""Step 3: Build dense (fastembed/BAAI-bge-small-en-v1.5) + BM25 hybrid index
over the frozen Step 2 evidence_blocks.jsonl, per
P1_frozen_pipeline_config_v1_LOCKED.md / model_and_retrieval_config_v1_LOCKED.md.

This script only builds and persists the index artifacts. Retrieval-quality
validation (coverage/recall against RQ1-4 / D01-D10 test queries) is a
separate script (step3_retrieval_validation.py) that must pass before the
index is trusted for Step 4.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
EVIDENCE_PATH = ROOT.parent / "02_PDF清洗与分块" / "02_Chunks" / "evidence_blocks.jsonl"
DENSE_DIR = ROOT / "01_稠密向量索引"
BM25_DIR = ROOT / "02_BM25词法索引"

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_BATCH_SIZE = 4  # locked: avoids onnxruntime OOM in this sandbox (~1.9GB RAM)

# --- BM25 tokenizer: verbatim copy of the locked spec in
# model_and_retrieval_config_v1_LOCKED.md section 3. Do not edit here without
# also updating that file and bumping the config version. ---
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "we", "our", "they", "their", "he", "she", "his", "her", "can", "could", "would", "should",
    "will", "shall", "may", "might", "must", "not", "no", "do", "does", "did", "have", "has", "had", "which",
    "who", "whom", "what", "when", "where", "why", "how", "also", "such", "both", "each", "more", "most",
    "other", "some", "any", "all", "into", "through", "during", "before", "after", "above", "below", "between",
    "out", "up", "down", "over", "under", "again", "further", "once",
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|\d+(?:\.\d+)?")


def bm25_tokenize(text: str) -> list[str]:
    text = text.replace("\u00ad", "")
    tokens = TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_evidence_blocks() -> list[dict]:
    records = []
    with open(EVIDENCE_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_bm25_index(records: list[dict]) -> dict:
    from rank_bm25 import BM25Okapi

    corpus_tokens = [bm25_tokenize(r["retrieval_text"]) for r in records]
    bm25 = BM25Okapi(corpus_tokens)
    BM25_DIR.mkdir(parents=True, exist_ok=True)
    with open(BM25_DIR / "bm25_index.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "corpus_tokens": corpus_tokens}, f)
    evidence_ids = [r["evidence_id"] for r in records]
    with open(BM25_DIR / "bm25_evidence_ids.json", "w", encoding="utf-8") as f:
        json.dump(evidence_ids, f, ensure_ascii=False, indent=2)
    empty_token_ids = [eid for eid, toks in zip(evidence_ids, corpus_tokens) if len(toks) == 0]
    return {
        "n_docs": len(records),
        "avg_tokens_per_doc": round(sum(len(t) for t in corpus_tokens) / max(1, len(corpus_tokens)), 2),
        "empty_token_doc_ids": empty_token_ids,
    }


def build_dense_index(records: list[dict]) -> dict:
    from fastembed import TextEmbedding

    DENSE_DIR.mkdir(parents=True, exist_ok=True)
    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    texts = [r["retrieval_text"] for r in records]
    t0 = time.time()
    embs = list(model.embed(texts, batch_size=EMBEDDING_BATCH_SIZE))
    elapsed = time.time() - t0
    doc_embs = np.array(embs, dtype=np.float32)
    np.save(DENSE_DIR / "dense_embeddings.npy", doc_embs)
    evidence_ids = [r["evidence_id"] for r in records]
    with open(DENSE_DIR / "dense_evidence_ids.json", "w", encoding="utf-8") as f:
        json.dump(evidence_ids, f, ensure_ascii=False, indent=2)
    return {
        "n_docs": len(records),
        "dim": int(doc_embs.shape[1]),
        "embedding_model": EMBEDDING_MODEL_NAME,
        "batch_size": EMBEDDING_BATCH_SIZE,
        "elapsed_seconds": round(elapsed, 1),
    }


def main() -> None:
    records = load_evidence_blocks()
    print(f"Loaded {len(records)} evidence blocks from {EVIDENCE_PATH}")

    bm25_stats = build_bm25_index(records)
    print("BM25 index built:", bm25_stats)

    dense_stats = build_dense_index(records)
    print("Dense index built:", dense_stats)

    manifest = {
        "step": "Step 3 hybrid index build",
        "config_source": "P1_frozen_pipeline_config_v1_LOCKED.md / model_and_retrieval_config_v1_LOCKED.md",
        "evidence_blocks_path": str(EVIDENCE_PATH.relative_to(ROOT.parent)),
        "evidence_blocks_sha256": sha256_file(EVIDENCE_PATH),
        "n_evidence_blocks": len(records),
        "bm25": {
            "library": "rank_bm25.BM25Okapi",
            "tokenizer": "locked bm25_tokenize() in step3_build_hybrid_index.py (verbatim copy of locked spec)",
            **bm25_stats,
        },
        "dense": dense_stats,
        "fusion_method": "Reciprocal Rank Fusion (RRF), k=60, top-20 per leg -> fused top-10 (see retrieval module)",
        "build_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(ROOT / "03_检索运行清单" / "index_build_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\nIndex build manifest written to 03_检索运行清单/index_build_manifest.json")
    if bm25_stats["empty_token_doc_ids"]:
        print("WARNING: evidence blocks with zero BM25 tokens:", bm25_stats["empty_token_doc_ids"])


if __name__ == "__main__":
    sys.exit(main())
