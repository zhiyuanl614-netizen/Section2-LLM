from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "04_LLM抽取与Critic审查" / "API批量管线"
sys.path.insert(0, str(API_DIR))

from llm_api_client_v1_2_local import (  # noqa: E402
    LocalEndpointConfig,
    call_llm,
    LLMCallError,
    validate_local_base_url,
)
from step4_api_batch_extraction_v1_2_local_text import (  # noqa: E402
    load_prompts,
    load_schema,
    process_document,
)


class FakeIndex:
    def __init__(self, doc_id="TEST-PDF-01"):
        self.records = [{
            "evidence_id": f"{doc_id}-E001",
            "doc_id": doc_id,
            "text": "Plain natural-language evidence used only by the local mock test.",
            "retrieval_text": "Plain natural-language evidence used only by the local mock test.",
            "zone": "Zone B",
            "section_id": "1",
            "page_numbers": [1],
            "formula_layout_risk": False,
            "text_sha256": "mock-hash",
        }]
        self.by_id = {r["evidence_id"]: r for r in self.records}

    def coverage_pass_ids(self, doc_id):
        return [r["evidence_id"] for r in self.records if r["doc_id"] == doc_id]

    def hybrid_search(self, query):
        return {"fused_top": [(self.records[0]["evidence_id"], 0.01)]}


class LocalMockHandler(BaseHTTPRequestHandler):
    requests_seen = []
    redirected_seen = False

    def log_message(self, *_args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(n))
        self.__class__.requests_seen.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": request,
        })
        if request.get("model") == "redirect":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/redirected")
            self.end_headers()
            return
        prompt = request["messages"][0]["content"]
        user = json.loads(request["messages"][1]["content"])
        dimensions = user["dimensions_schema"]
        if "抽取器" in prompt:
            content = json.dumps([
                {
                    "dimension_id": dim_id,
                    "primary_label": "Not_Stated_In_Text",
                    "secondary_labels": [],
                    "own_method_vs_cited": "Paper_Own_Method",
                    "mechanism_judgment": "Mock only; this is not a paper judgment.",
                    "uncertainty_note": "Mock API test response.",
                    "evidence_ids": [],
                    "verbatim_quote": "",
                    "confidence": 0.5,
                }
                for dim_id in dimensions
            ], ensure_ascii=False)
        elif "审查员" in prompt:
            content = json.dumps({
                dim_id: {
                    "decision": "accept",
                    "corrected_label": None,
                    "critic_comment": "Mock only; no semantic review was performed.",
                    "supporting_evidence_ids": [],
                    "contradicting_evidence_ids": [],
                    "confidence": 0.5,
                    "checks_failed": [],
                }
                for dim_id in dimensions
            }, ensure_ascii=False)
        else:
            self.send_error(400, "unrecognized mock prompt")
            return
        body = json.dumps({
            "model": request["model"],
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/redirected":
            self.__class__.redirected_seen = True
        body = json.dumps({"data": [{"id": "mock-a"}, {"id": "mock-b"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalTextPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        LocalMockHandler.requests_seen = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalMockHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def test_local_url_guard(self):
        validate_local_base_url("http://127.0.0.1:1234/v1")
        validate_local_base_url("http://localhost:1234/v1")
        with self.assertRaises(ValueError):
            validate_local_base_url("https://api.example.com/v1")
        with self.assertRaises(ValueError):
            validate_local_base_url("http://192.168.1.20:1234/v1")
        validate_local_base_url("http://192.168.1.20:1234/v1", allow_private_network=True)

    def test_local_api_no_auth_and_models(self):
        cfg = LocalEndpointConfig(
            agent_name="AgentA", provider="openai_compatible", base_url=self.base_url,
            model="mock-a", api_key=None, max_retries=0,
        )
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""}):
            response = call_llm(cfg, "Agent A 抽取器", json.dumps({"dimensions_schema": {}}))
        self.assertEqual(response.execution_channel, "local_api_call")
        self.assertEqual(response.endpoint, self.base_url + "/chat/completions")
        self.assertEqual(response.input_tokens, 20)
        seen = LocalMockHandler.requests_seen[-1]
        self.assertEqual(seen["path"], "/v1/chat/completions")
        self.assertIsNone(seen["authorization"])
        self.assertEqual(response.model_version, "mock-a")

    def test_redirect_is_rejected_without_following(self):
        LocalMockHandler.redirected_seen = False
        cfg = LocalEndpointConfig(
            agent_name="AgentA", provider="openai_compatible", base_url=self.base_url,
            model="redirect", api_key=None, max_retries=0,
        )
        with self.assertRaisesRegex(LLMCallError, "redirects are disabled"):
            call_llm(cfg, "Agent A 抽取器", json.dumps({"dimensions_schema": {}}))
        self.assertFalse(LocalMockHandler.redirected_seen)

    def test_pipeline_sends_no_d03_to_model_and_writes_status_locally(self):
        schema = load_schema(ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json")
        prompts = load_prompts(API_DIR / "agent_prompts_v1.2_local_text_scope.json")
        self.assertFalse(any("D03" in prompts[k] or "PDF-03" in prompts[k] or "Out_Of_Scope_Formula_Only" in prompts[k] for k in ("agent_a_system_prompt", "agent_b_system_prompt")))
        self.assertNotIn("Out_Of_Scope_Formula_Only", schema["model_fallback_states"])
        cfg_a = LocalEndpointConfig("AgentA", "openai_compatible", self.base_url, "mock-a", None, max_retries=0)
        cfg_b = LocalEndpointConfig("AgentB", "openai_compatible", self.base_url, "mock-b", None, max_retries=0)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "test-run"
            run_dir.mkdir()
            result = process_document(
                doc_id="TEST-PDF-01", index=FakeIndex(), schema=schema, prompts=prompts,
                cfg_a=cfg_a, cfg_b=cfg_b, run_id="test-run", run_dir=run_dir,
            )
            output_path = Path(result["output"])
            records = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(records), 9)
            self.assertEqual({r["dimension_id"] for r in records}, set(schema["active_analysis_dimensions"]))
            self.assertNotIn("D03", {r["dimension_id"] for r in records})
            d03 = json.loads(Path(result["scope_status_output"]).read_text(encoding="utf-8"))
            self.assertEqual(d03["primary_label"], "Not_Analyzed_Out_Of_Scope")
            self.assertIsNone(d03["agent_a_model_call_id"])
            self.assertIsNone(d03["agent_b_review"])
            self.assertTrue(all(r.get("equation_detail") is None for r in records))
            model_requests = LocalMockHandler.requests_seen[-2:]
            for request in model_requests:
                self.assertEqual(request["path"], "/v1/chat/completions")
                system_text = request["body"]["messages"][0]["content"]
                user_payload = json.loads(request["body"]["messages"][1]["content"])
                self.assertNotIn("D03", system_text)
                self.assertNotIn("D03", json.dumps(user_payload, ensure_ascii=False))
                self.assertNotIn("D03", user_payload["dimensions_schema"])
                self.assertNotIn("Out_Of_Scope_Formula_Only", json.dumps(user_payload, ensure_ascii=False))
                self.assertNotIn("boundary_rule", user_payload["dimensions_schema"]["D02"])
            manifest = [json.loads(x) for x in (run_dir / "02_模型调用日志" / "model_call_manifest.jsonl").read_text().splitlines()]
            self.assertEqual(len(manifest), 2)
            pass1_id = next(x["call_id"] for x in manifest if x["pass"] == "pass1_initial_extraction")
            d01 = next(r for r in records if r["dimension_id"] == "D01")
            self.assertEqual(d01["agent_a_model_call_id"], pass1_id)
            self.assertTrue(all(x["local_only_mode"] for x in manifest))

    def test_unfinalized_pdf03_d02_remains_human_adjudication_required(self):
        schema = load_schema(ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json")
        prompts = load_prompts(API_DIR / "agent_prompts_v1.2_local_text_scope.json")
        cfg_a = LocalEndpointConfig("AgentA", "openai_compatible", self.base_url, "mock-a", None, max_retries=0)
        cfg_b = LocalEndpointConfig("AgentB", "openai_compatible", self.base_url, "mock-b", None, max_retries=0)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "open-boundary"
            run_dir.mkdir()
            result = process_document(
                doc_id="B001-PDF-03", index=FakeIndex("B001-PDF-03"), schema=schema, prompts=prompts,
                cfg_a=cfg_a, cfg_b=cfg_b, run_id="open-boundary", run_dir=run_dir,
            )
            records = json.loads(Path(result["output"]).read_text(encoding="utf-8"))
            d02 = next(r for r in records if r["dimension_id"] == "D02")
            self.assertEqual(d02["verification_status"], "adjudication_required")
            self.assertIn("not been user-finalized", d02["agent_b_review"]["forced_human_adjudication_reason"])
            model_requests = LocalMockHandler.requests_seen[-2:]
            for request in model_requests:
                payload = json.loads(request["body"]["messages"][1]["content"])
                d02_schema = payload["dimensions_schema"]["D02"]
                self.assertNotIn("boundary_rule", d02_schema)
                self.assertNotIn("interpretation_note", d02_schema)
                self.assertIn("human adjudication", d02_schema["adjudication_note"])

    def test_dry_run_is_explicit_non_data(self):
        schema = load_schema(ROOT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json")
        prompts = load_prompts(API_DIR / "agent_prompts_v1.2_local_text_scope.json")
        cfg_a = LocalEndpointConfig("AgentA", "dry_run", "N/A", "dry-run-stub")
        cfg_b = LocalEndpointConfig("AgentB", "dry_run", "N/A", "dry-run-stub")
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "dry"
            run_dir.mkdir()
            result = process_document(
                doc_id="TEST-PDF-01", index=FakeIndex(), schema=schema, prompts=prompts,
                cfg_a=cfg_a, cfg_b=cfg_b, run_id="dry", run_dir=run_dir,
            )
            self.assertEqual(result["status"], "dry_run_placeholder_non_data")
            records = json.loads(Path(result["output"]).read_text(encoding="utf-8"))
            self.assertEqual(len(records), 9)
            self.assertTrue(all(r.get("verification_status") == "dry_run_placeholder_non_data" for r in records))
            scope = json.loads(Path(result["scope_status_output"]).read_text(encoding="utf-8"))
            self.assertEqual(scope["record_status"], "scope_status_not_a_paper_finding")


if __name__ == "__main__":
    unittest.main(verbosity=2)
