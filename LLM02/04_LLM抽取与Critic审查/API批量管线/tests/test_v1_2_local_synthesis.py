from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STEP6_DIR = ROOT / "06_跨文献综合与FRDI" / "01_跨文献LLM综合"
sys.path.insert(0, str(STEP6_DIR))

from step6_local_evidence_challenge_v1_2 import (  # noqa: E402
    build_direction_payload,
    validate_complete_pilot_doc_ids,
    validate_result,
)


class LocalSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.doc_id = "B001-PDF-03"
        self.eid = "B001-PDF-03-ZB-E001"
        self.block = {
            "evidence_id": self.eid,
            "doc_id": self.doc_id,
            "section_id": "2.1",
            "page_numbers": [4],
            "formula_layout_risk": False,
            "text": "The model states that power plants receive water from local water facilities.",
        }
        self.evidence_by_id = {self.eid: self.block}
        self.record = {
            "doc_id": self.doc_id,
            "dimension_id": "D02",
            "primary_label": "Mentioned_Only_Not_Modeled",
            "verification_status": "adjudication_required",
            "record_origin": "v1.2_local_api_model_run",
            "own_method_vs_cited": "Paper_Own_Method",
            "mechanism_judgment": "A generic dependency is described; the D02 boundary remains unresolved.",
            "uncertainty_note": "Human adjudication required.",
            "evidence_ids": [self.eid],
            "verbatim_quote": "The model states that power plants receive water from local water facilities.",
        }
        self.direction = {"id": "3-1", "summary": "Detailed cooling-water representation in water-power operation."}

    def test_step6_requires_exact_five_document_pilot(self):
        doc_ids = [f"B001-PDF-{i:02d}" for i in range(1, 6)]
        self.assertIsNone(validate_complete_pilot_doc_ids(doc_ids))
        for invalid in (doc_ids[:-1], doc_ids[:-1] + [doc_ids[0]], ["B002-PDF-01"]):
            with self.assertRaises(ValueError):
                validate_complete_pilot_doc_ids(invalid)

    def test_payload_keeps_boundary_provisional_and_omits_d03(self):
        payload = build_direction_payload(self.direction, "RQ1", ["D02"], [self.record], self.evidence_by_id)
        packed = payload["records"][0]
        self.assertEqual(packed["verification_status"], "adjudication_required")
        self.assertNotIn("D03", {r["dimension_id"] for r in payload["records"]})
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("boundary_rule", serialized)
        self.assertIn(self.eid, payload["input_evidence_ids"])

    def test_exact_evidence_quote_is_accepted(self):
        payload = build_direction_payload(self.direction, "RQ1", ["D02"], [self.record], self.evidence_by_id)
        result = {
            "direction_id": "3-1",
            "pilot_assessment": "mixed_evidence",
            "pilot_limited_conclusion": "The pilot evidence is mixed and does not establish a field-wide gap.",
            "supporting_evidence": [{
                "doc_id": self.doc_id, "dimension_id": "D02", "evidence_id": self.eid,
                "quote": self.block["text"], "why_relevant": "It states a generic water-to-power dependency.",
            }],
            "counterevidence": [],
            "unresolved_issues": ["The D02 boundary remains unresolved."],
            "scope_limitations": ["Five papers are a pilot sample."],
        }
        cleaned, errors = validate_result(result, direction_id="3-1", input_payload=payload,
                                          evidence_by_id=self.evidence_by_id)
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["direction_id"], "3-1")

    def test_unprovided_id_and_nonmatching_quote_are_rejected(self):
        payload = build_direction_payload(self.direction, "RQ1", ["D02"], [self.record], self.evidence_by_id)
        result = {
            "direction_id": "3-1",
            "pilot_assessment": "pilot_support",
            "pilot_limited_conclusion": "A limited pilot conclusion.",
            "supporting_evidence": [{
                "doc_id": self.doc_id, "dimension_id": "D02", "evidence_id": "invented-id",
                "quote": "invented quote", "why_relevant": "unsupported",
            }],
            "counterevidence": [],
            "unresolved_issues": [],
            "scope_limitations": ["Pilot only."],
        }
        cleaned, errors = validate_result(result, direction_id="3-1", input_payload=payload,
                                          evidence_by_id=self.evidence_by_id)
        self.assertIsNone(cleaned)
        self.assertTrue(any("cites evidence not included" in e for e in errors))

    def test_formula_or_extra_fields_are_rejected(self):
        payload = build_direction_payload(self.direction, "RQ1", ["D02"], [self.record], self.evidence_by_id)
        result = {
            "direction_id": "3-1",
            "pilot_assessment": "unresolved",
            "pilot_limited_conclusion": "Unresolved in this pilot.",
            "supporting_evidence": [],
            "counterevidence": [],
            "unresolved_issues": [],
            "scope_limitations": ["Pilot only."],
            "equation_detail": {"equation": "not allowed"},
        }
        cleaned, errors = validate_result(result, direction_id="3-1", input_payload=payload,
                                          evidence_by_id=self.evidence_by_id)
        self.assertIsNone(cleaned)
        self.assertTrue(any("unexpected keys" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
