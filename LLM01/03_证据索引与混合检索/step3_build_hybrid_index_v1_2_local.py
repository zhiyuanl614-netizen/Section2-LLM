#!/usr/bin/env python3
"""Build a new, isolated Step 3 index for the v1.2 local text-only pipeline.

The target index directory must not already exist. By default embedding-model
loading is local-only and fails closed if weights are not cached.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import re
import shutil
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import numpy as np

EMBEDDING_MODEL_DEFAULT = "BAAI/bge-small-en-v1.5"
EMBEDDING_BATCH_SIZE = 4
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not row.get("evidence_id") or not row.get("doc_id"):
                raise ValueError(f"Invalid evidence record at {path}:{line_no}")
            if not isinstance(row.get("retrieval_text"), str) or not isinstance(row.get("text"), str):
                raise ValueError(f"Evidence record lacks text/retrieval_text at {path}:{line_no}")
            records.append(row)
    ids = [r["evidence_id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evidence_id in input; index build aborted")
    if not records:
        raise ValueError("No evidence blocks in input")
    return records


def make_embedder(model_name: str, cache_dir: Path | None, local_files_only: bool):
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError("fastembed is required; install dependencies before building the local index") from exc
    kwargs = {"model_name": model_name, "local_files_only": local_files_only}
    if cache_dir is not None:
        kwargs["cache_dir"] = str(cache_dir)
    try:
        return TextEmbedding(**kwargs)
    except TypeError as exc:
        if local_files_only:
            raise RuntimeError(
                "Installed FastEmbed does not support local_files_only; upgrade it before offline index building."
            ) from exc
        raise


def build(args) -> dict:
    evidence_path = Path(args.evidence_blocks).expanduser().resolve()
    output_dir = Path(args.index_dir).expanduser().resolve()
    cache_dir = Path(args.embedding_cache_dir).expanduser().resolve() if args.embedding_cache_dir else None
    if not evidence_path.is_file():
        raise FileNotFoundError(evidence_path)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing index directory: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex[:10]}"
    temp_dir.mkdir(parents=False, exist_ok=False)
    t0 = time.time()
    try:
        records = load_records(evidence_path)
        ids = [r["evidence_id"] for r in records]
        corpus_tokens = [bm25_tokenize(r["retrieval_text"]) for r in records]
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise RuntimeError("rank_bm25 is required; install dependencies before building the local index") from exc
        bm25 = BM25Okapi(corpus_tokens)
        with (temp_dir / "bm25_index.pkl").open("wb") as f:
            pickle.dump({"bm25": bm25, "corpus_tokens": corpus_tokens}, f, protocol=pickle.HIGHEST_PROTOCOL)
        (temp_dir / "bm25_evidence_ids.json").write_text(json.dumps(ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        model = make_embedder(args.embedding_model, cache_dir, local_files_only=not args.allow_model_download)
        texts = [r["retrieval_text"] for r in records]
        embs = list(model.embed(texts, batch_size=EMBEDDING_BATCH_SIZE))
        matrix = np.asarray(embs, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(ids):
            raise ValueError("Embedding output count/shape does not match evidence records")
        np.save(temp_dir / "dense_embeddings.npy", matrix, allow_pickle=False)
        (temp_dir / "dense_evidence_ids.json").write_text(json.dumps(ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        artifact_files = ["bm25_index.pkl", "bm25_evidence_ids.json", "dense_embeddings.npy", "dense_evidence_ids.json"]
        artifact_sha256 = {name: sha256_file(temp_dir / name) for name in artifact_files}
        manifest = {
            "build_id": f"local-v1.2-{uuid.uuid4().hex[:12]}",
            "pipeline_version": "Step3-v1.2-local-text-scope",
            "builder_script_sha256": sha256_file(Path(__file__).resolve()),
            "schema_version": "v1.2",
            "input_evidence_blocks": str(evidence_path),
            "input_sha256": sha256_file(evidence_path),
            "artifact_sha256": artifact_sha256,
            "record_count": len(records),
            "doc_ids": sorted({r["doc_id"] for r in records}),
            "records_per_doc": dict(sorted(Counter(r["doc_id"] for r in records).items())),
            "bm25": {
                "implementation": "rank_bm25.BM25Okapi",
                "tokenizer": "copied verbatim from locked Step 3 tokenizer",
                "empty_token_evidence_ids": [eid for eid, toks in zip(ids, corpus_tokens) if not toks],
            },
            "dense": {
                "implementation": "fastembed.TextEmbedding",
                "model_name": args.embedding_model,
                "model_cache_dir": str(cache_dir) if cache_dir else "FastEmbed default cache",
                "local_files_only": not args.allow_model_download,
                "matrix_shape": list(matrix.shape),
                "batch_size": EMBEDDING_BATCH_SIZE,
            },
            "fusion": {"method": "RRF", "k": 60, "per_leg_top_k": 20, "fused_top_k": 10},
            "duration_s": round(time.time() - t0, 3),
            "build_timestamp_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        (temp_dir / "index_build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Atomic promotion to a fresh path. Existing targets are never replaced.
        if output_dir.exists():
            raise FileExistsError(f"Target appeared during build; refusing to overwrite: {output_dir}")
        os.rename(temp_dir, output_dir)
        return manifest
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-blocks", required=True, help="Versioned Step 2 evidence_blocks.jsonl")
    p.add_argument("--index-dir", required=True, help="New, non-existing versioned output directory")
    p.add_argument("--embedding-model", default=EMBEDDING_MODEL_DEFAULT)
    p.add_argument("--embedding-cache-dir", default=None, help="Optional local FastEmbed cache directory")
    p.add_argument("--allow-model-download", action="store_true",
                   help="Explicitly permit FastEmbed to download missing weights during this index build")
    args = p.parse_args()
    try:
        manifest = build(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: manifest[k] for k in ("build_id", "record_count", "doc_ids", "dense")}, ensure_ascii=False, indent=2))
    print(f"Index built at: {Path(args.index_dir).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
