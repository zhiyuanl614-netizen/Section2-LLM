from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
STEP3_DIR = ROOT / "03_证据索引与混合检索"
sys.path.insert(0, str(STEP3_DIR))

from step3_build_hybrid_index_v1_2_local import build, bm25_tokenize  # noqa: E402
from step3_hybrid_retrieval_v1_2_local import LocalHybridIndex  # noqa: E402


class FakeBM25:
    def __init__(self, corpus):
        self.corpus = corpus
        self.doc_len = [len(x) for x in corpus]

    def get_scores(self, query):
        query = set(query)
        return np.asarray([float(len(query.intersection(set(doc)))) for doc in self.corpus], dtype=np.float32)


class FakeTextEmbedding:
    def __init__(self, model_name, local_files_only=True, cache_dir=None):
        self.model_name = model_name
        self.local_files_only = local_files_only
        self.cache_dir = cache_dir

    def embed(self, texts, batch_size=4):
        for text in texts:
            toks = bm25_tokenize(text)
            yield np.asarray([
                1.0 + len(toks),
                1.0 + sum(map(len, toks)),
                1.0 + (sum(ord(c) for c in text) % 101),
            ], dtype=np.float32)


class LocalIndexTests(unittest.TestCase):
    def test_versioned_index_build_load_search_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            evidence = tmp / "evidence_blocks.jsonl"
            rows = [
                {"evidence_id": "B900-PDF-01-E001", "doc_id": "B900-PDF-01", "text": "water network evidence", "retrieval_text": "water network evidence", "formula_layout_risk": True},
                {"evidence_id": "B900-PDF-01-E002", "doc_id": "B900-PDF-01", "text": "power infrastructure control", "retrieval_text": "power infrastructure control", "formula_layout_risk": False},
                {"evidence_id": "B900-PDF-02-E001", "doc_id": "B900-PDF-02", "text": "water cooling process", "retrieval_text": "water cooling process", "formula_layout_risk": False},
            ]
            evidence.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            index_dir = tmp / "new-index"
            rank_module = types.ModuleType("rank_bm25")
            rank_module.BM25Okapi = FakeBM25
            embed_module = types.ModuleType("fastembed")
            embed_module.TextEmbedding = FakeTextEmbedding
            args = types.SimpleNamespace(
                evidence_blocks=str(evidence), index_dir=str(index_dir),
                embedding_cache_dir=str(tmp / "cache"), embedding_model="mock-local-embedding",
                allow_model_download=False,
            )
            with patch.dict(sys.modules, {"rank_bm25": rank_module, "fastembed": embed_module}):
                manifest = build(args)
                self.assertTrue(manifest["dense"]["local_files_only"])
                index = LocalHybridIndex(
                    evidence, index_dir, embedding_model="mock-local-embedding",
                    embedding_cache_dir=tmp / "cache", local_files_only=True,
                )
                self.assertEqual(index.doc_ids(), ["B900-PDF-01", "B900-PDF-02"])
                self.assertEqual(index.coverage_pass_ids("B900-PDF-01"), ["B900-PDF-01-E001", "B900-PDF-01-E002"])
                result = index.hybrid_search("water cooling")
                self.assertEqual(len(result["fused_top"]), 3)
                self.assertIn("B900-PDF-01-E001", index.by_id)
                before = (index_dir / "index_build_manifest.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "Embedding model mismatch"):
                    LocalHybridIndex(evidence, index_dir, embedding_model="different-model", local_files_only=True)
                dense_path = index_dir / "dense_embeddings.npy"
                dense_before = dense_path.read_bytes()
                dense_path.write_bytes(dense_before + b"tamper")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    LocalHybridIndex(evidence, index_dir, embedding_model="mock-local-embedding", local_files_only=True)
                dense_path.write_bytes(dense_before)
                with self.assertRaises(FileExistsError):
                    build(args)
                self.assertEqual((index_dir / "index_build_manifest.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
