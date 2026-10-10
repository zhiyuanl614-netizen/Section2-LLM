from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = ROOT / "平台" / "platform"
sys.path.insert(0, str(PLATFORM_ROOT))

from rag_core.workflows import WorkflowError, WorkflowManager  # noqa: E402


class WorkflowManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workflows"
        self.manager = WorkflowManager(self.root, ROOT)

    def tearDown(self):
        self.temp.cleanup()

    def create_run_with_pdf(self):
        run = self.manager.create_run("test isolated batch")
        self.manager.upload_pdf(run["run_id"], "paper-a.pdf", b"%PDF-1.4\nlocal-only-test-pdf")
        return self.manager.get_run(run["run_id"])

    def test_new_run_is_isolated_and_does_not_mutate_formal_release(self):
        run = self.manager.create_run("separate corpus")
        self.assertEqual(run["isolation"]["formal_sample_extension_authorized"], False)
        self.assertEqual(run["isolation"]["official_release_modified"], False)
        self.assertEqual(run["isolation"]["batch_cloud_evidence_authorized"], False)
        self.assertEqual(run["stages"]["02_pdf_clean_chunk"]["status"], "blocked_awaiting_uploads")
        self.assertEqual(self.manager.list_runs()[0]["run_id"], run["run_id"])

    def test_upload_checks_pdf_magic_filename_and_hash(self):
        run = self.manager.create_run()
        item = self.manager.upload_pdf(run["run_id"], "paper-a.pdf", b"%PDF-1.7\ncontent")
        self.assertEqual(item["sha256"], __import__("hashlib").sha256(b"%PDF-1.7\ncontent").hexdigest())
        stored = self.root / run["run_id"] / "uploads" / "paper-a.pdf"
        self.assertTrue(stored.is_file())
        updated = self.manager.get_run(run["run_id"])
        self.assertEqual(updated["uploads"][0]["filename"], "paper-a.pdf")
        self.assertEqual(updated["stages"]["02_pdf_clean_chunk"]["status"], "ready")
        self.assertFalse(updated["isolation"]["official_release_modified"])
        for unsafe_name in ("../escape.pdf", "folder/escape.pdf", r"C:\\temp\\escape.pdf", "C:drive-relative.pdf", "-option.pdf"):
            with self.subTest(filename=unsafe_name), self.assertRaises(WorkflowError):
                self.manager.upload_pdf(run["run_id"], unsafe_name, b"%PDF-1.4\nx")
        self.assertFalse((self.root / run["run_id"] / "escape.pdf").exists())
        with self.assertRaises(WorkflowError):
            self.manager.upload_pdf(run["run_id"], "bad.txt", b"%PDF-1.4\nx")
        with self.assertRaises(WorkflowError):
            self.manager.upload_pdf(run["run_id"], "not-a-pdf.pdf", b"not a PDF")

    def test_stage_requires_explicit_confirmation_and_real_runner_is_dependency_gated(self):
        run = self.create_run_with_pdf()
        with self.assertRaises(WorkflowError):
            self.manager.run_stage(run["run_id"], "02_pdf_clean_chunk", confirm=False)
        with patch("rag_core.workflows.missing_step2_dependencies", return_value=["PyMuPDF"]):
            updated = self.manager.run_stage(run["run_id"], "02_pdf_clean_chunk", confirm=True)
        stage = updated["stages"]["02_pdf_clean_chunk"]
        self.assertEqual(stage["status"], "blocked_missing_dependencies")
        self.assertEqual(stage["missing_dependencies"], ["PyMuPDF"])
        self.assertFalse(stage.get("external_data_sent", False))
        self.assertFalse((self.root / run["run_id"] / "step01").exists())
        self.assertFalse((self.root / run["run_id"] / "step02").exists())

    def test_bm25_only_index_is_hash_bound_and_searchable_without_model_calls(self):
        run = self.create_run_with_pdf()
        run_id = run["run_id"]
        step2_dir = self.root / run_id / "step02"
        step2_dir.mkdir()
        records = [
            {
                "evidence_id": "UP-PDF-01-ZA-S01-I-C001", "doc_id": "UP-PDF-01",
                "page_numbers": [1], "text": "Cooling water supports power generation at the facility.",
                "retrieval_text": "Cooling water supports power generation at the facility.",
                "formula_layout_risk": False,
            },
            {
                "evidence_id": "UP-PDF-01-ZB-S02-I-C002", "doc_id": "UP-PDF-01",
                "page_numbers": [2], "text": "Population exposure is discussed in the report.",
                "retrieval_text": "Population exposure is discussed in the report.",
                "formula_layout_risk": True, "formula_layout_risk_score": 2.5,
            },
        ]
        evidence_path = step2_dir / "evidence_blocks.jsonl"
        evidence_path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
        run_dir = self.root / run_id
        manifest = self.manager.get_run(run_id)
        manifest["stages"]["02_pdf_clean_chunk"].update({"status": "completed", "evidence_block_count": 2})
        manifest["stages"]["03_bm25_index"].update({"status": "ready"})
        self.manager._write_manifest(run_dir, manifest)

        indexed = self.manager.run_stage(run_id, "03_bm25_index", confirm=True)
        stage = indexed["stages"]["03_bm25_index"]
        self.assertEqual(stage["status"], "partial_bm25_ready")
        self.assertEqual(stage["record_count"], 2)
        self.assertTrue(stage["formula_risk_records_retained"])
        self.assertFalse(stage["external_data_sent"])
        self.assertIn("Dense query encoder", stage["not_implemented"])

        result = self.manager.search_run(run_id, "cooling water", top_k=5)
        self.assertEqual(result["active_channels"], ["BM25"])
        self.assertTrue(result["hits"])
        self.assertEqual(result["hits"][0]["evidence_id"], "UP-PDF-01-ZA-S01-I-C001")
        self.assertFalse(result["hits"][0]["formula_layout_risk"])
        formula_query = self.manager.search_run(run_id, "derive the equations and explain variables")
        self.assertTrue(formula_query["out_of_scope"])
        self.assertEqual(formula_query["hits"], [])

        artifact = next(row for row in indexed["artifacts"] if row["filename"] == "bm25_index.json")
        path, info = self.manager.artifact_path(run_id, artifact["artifact_id"])
        self.assertTrue(path.is_file())
        preview = self.manager.artifact_preview(run_id, artifact["artifact_id"])
        self.assertEqual(preview["filename"], "bm25_index.json")
        self.assertIn("workspace-bm25-index-v1", preview["text"])
        self.assertEqual(info["sha256"], artifact["sha256"])

    def test_artifact_ids_and_run_ids_cannot_escape_workspace(self):
        run = self.manager.create_run()
        with self.assertRaises(WorkflowError):
            self.manager.get_run("../../outside")
        with self.assertRaises(WorkflowError):
            self.manager.artifact_path(run["run_id"], "../run_manifest.json")

    def test_unimplemented_batch_llm_stage_fails_closed(self):
        run = self.create_run_with_pdf()
        with self.assertRaises(WorkflowError) as error:
            self.manager.run_stage(run["run_id"], "04_llm_extract_critic", confirm=True)
        self.assertIn("尚未接入", str(error.exception))
        after = self.manager.get_run(run["run_id"])
        self.assertEqual(after["stages"]["04_llm_extract_critic"]["status"], "not_ready")
        self.assertFalse(after["isolation"]["batch_cloud_evidence_authorized"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
