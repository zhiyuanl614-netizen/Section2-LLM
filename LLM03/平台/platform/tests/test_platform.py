from __future__ import annotations

import json
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = ROOT / "平台" / "platform"
RELEASE_DIR = PLATFORM_ROOT / "data" / "releases" / "B001-v1.2-text-scope-preview-20261010"
sys.path.insert(0, str(PLATFORM_ROOT))

from rag_core.data import ReleaseIntegrityError, ReleaseStore  # noqa: E402
from rag_core.generation import (
    CSTCLOUD_API_BASE_URL,
    LocalChatConfig,
    LocalGenerationError,
    RemoteChatConfig,
    RemoteGenerationError,
    _post_remote_chat,
    generate_remote_answer,
    list_remote_models,
)  # noqa: E402
from rag_core.service import PlatformService  # noqa: E402


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = ReleaseStore(RELEASE_DIR, verify_hashes=True)
        cls.service = PlatformService(str(RELEASE_DIR))

    def test_release_is_hash_verified_and_pilot_marked(self):
        self.assertEqual(self.store.release["release_id"], "B001-v1.2-text-scope-preview-20261010")
        self.assertEqual(self.store.release["status"], "pilot_preview_not_final_not_production_released")
        self.assertEqual(len(self.store.documents), 5)
        self.assertEqual(len(self.store.blocks), 239)

    def test_active_records_and_graph_exclude_d03(self):
        self.assertEqual(len(self.store.records), 45)
        self.assertFalse(any(row.get("dimension_id") == "D03" for row in self.store.records))
        self.assertFalse(any("D03" in str(node) for node in self.store.graph["nodes"]))

    def test_graph_links_resolve_to_source_documents(self):
        graph = self.store.graph
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertTrue(graph["edges"])
        self.assertTrue(all(edge["from"] in node_ids and edge["to"] in node_ids for edge in graph["edges"]))
        evidence_nodes = [node for node in graph["nodes"] if node.get("type") == "evidence"]
        self.assertTrue(evidence_nodes)
        for node in evidence_nodes:
            self.assertIn(node["doc_id"], self.store.document_by_id)

    def test_direction_filtered_graph_retains_unresolved_boundary(self):
        graph = self.service.graph("3-1")
        self.assertEqual(graph["filtered_direction"], "3-1")
        record_nodes = [n for n in graph["nodes"] if n.get("type") == "record"]
        d02_pdf03 = [n for n in record_nodes if n.get("doc_id") == "B001-PDF-03" and n.get("dimension_id") == "D02"]
        self.assertTrue(d02_pdf03)
        self.assertIn(d02_pdf03[0]["verification_status"], {"adjudication_required", "preliminary_agent_assisted_not_final"})

    def test_offline_search_returns_exact_source_ids(self):
        result = self.service.search("厂内冷却水过程建模", top_k=5, mode="hybrid")
        self.assertTrue(result["hits"])
        self.assertIn("bm25", result["active_channels"])
        self.assertTrue(all(hit["evidence_id"] in self.store.block_by_id for hit in result["hits"]))
        self.assertTrue(any("C001" in hit["evidence_id"] for hit in result["hits"]))

    def test_formula_analysis_query_is_out_of_scope(self):
        result = self.service.search("derive the equations and explain variables", top_k=5)
        self.assertTrue(result["out_of_scope"])
        self.assertEqual(result["hits"], [])

    def test_default_qa_is_extract_only_and_does_not_call_generation(self):
        result = self.service.qa("社会脆弱性和人口影响", top_k=3, generate=False)
        self.assertIsNone(result["generated_answer"])
        self.assertEqual(result["evidence_packet"]["answer_mode"], "extractive_evidence_packet_no_llm_generation")
        self.assertTrue(result["evidence_packet"]["citations"])

    def test_pdf_paths_are_confined_and_hash_checked(self):
        for doc in self.store.documents:
            path = self.store.pdf_path(doc["doc_id"])
            self.assertTrue(path and path.is_file())
        self.assertIsNone(self.store.pdf_path("../../README"))

    def test_non_loopback_chat_endpoint_is_rejected(self):
        env = {
            "PLATFORM_LOCAL_CHAT_BASE_URL": "https://example.com/v1",
            "PLATFORM_LOCAL_CHAT_MODEL": "remote-model",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(LocalGenerationError):
                LocalChatConfig.from_env()

    def test_loopback_chat_config_has_no_network_fallback(self):
        env = {
            "PLATFORM_LOCAL_CHAT_BASE_URL": "http://127.0.0.1:1234/v1",
            "PLATFORM_LOCAL_CHAT_MODEL": "local-model",
        }
        with patch.dict(os.environ, env, clear=False):
            config = LocalChatConfig.from_env()
        self.assertEqual(config.endpoint, "http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(config.model, "local-model")

    def test_remote_api_config_requires_public_https_and_blocks_private_dns(self):
        with self.assertRaises(RemoteGenerationError):
            RemoteChatConfig.from_payload({
                "provider": "openai_compatible",
                "base_url": "http://api.example.com/v1",
                "model": "test-model",
            })
        private_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("rag_core.generation.socket.getaddrinfo", return_value=private_answer):
            with self.assertRaises(RemoteGenerationError):
                RemoteChatConfig.from_payload({
                    "provider": "openai_compatible",
                    "base_url": "https://api.example.com/v1",
                    "model": "test-model",
                })

    def test_cstcloud_preset_uses_fixed_host_and_hides_key_from_repr(self):
        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with patch("rag_core.generation.socket.getaddrinfo", return_value=public_answer):
            config = RemoteChatConfig.from_payload({
                "provider": "cstcloud",
                "model": "deepseek-v4-flash",
                "api_key": "never-log-this-key",
            })
        self.assertEqual(config.base_url, CSTCLOUD_API_BASE_URL)
        self.assertEqual(config.endpoint, CSTCLOUD_API_BASE_URL + "/chat/completions")
        self.assertNotIn("never-log-this-key", repr(config))

    def test_remote_transport_uses_resolved_public_ip_and_blocks_redirects(self):
        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with patch("rag_core.generation.socket.getaddrinfo", return_value=public_answer):
            config = RemoteChatConfig.from_payload({
                "provider": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model": "test-model",
            })
        created = []

        class FakeResponse:
            def __init__(self, status, body=b"{}"):
                self.status = status
                self.body = body
            def read(self, _limit):
                return self.body

        class FakeConnection:
            status = 200
            def __init__(self, hostname, pinned_ip, timeout=45):
                created.append((hostname, pinned_ip, timeout))
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return FakeResponse(self.status, b'{"ok":true}')
            def close(self):
                pass

        with patch("rag_core.generation._PinnedHTTPSConnection", FakeConnection):
            self.assertTrue(_post_remote_chat(config, b"{}", {})["ok"])
            FakeConnection.status = 302
            with self.assertRaisesRegex(RemoteGenerationError, "redirects are blocked"):
                _post_remote_chat(config, b"{}", {})
        self.assertEqual(created, [
            ("api.example.com", "8.8.8.8", 45),
            ("api.example.com", "8.8.8.8", 45),
        ])

    def test_remote_generation_only_sends_five_safe_hits_and_never_returns_key(self):
        blocks = [block for block in self.store.blocks if not block.get("formula_layout_risk")][:6]
        self.assertGreaterEqual(len(blocks), 6)
        safe_hits = [{
            "evidence_id": block["evidence_id"],
            "doc_id": block["doc_id"],
            "pages": block.get("page_numbers") or [],
            "text": f"SAFE_SENTINEL_{index}",
            "formula_layout_risk": False,
        } for index, block in enumerate(blocks)]
        risk_block = next(block for block in self.store.blocks if block.get("formula_layout_risk"))
        hits = [{
            "evidence_id": risk_block["evidence_id"],
            "doc_id": risk_block["doc_id"],
            "pages": risk_block.get("page_numbers") or [],
            "text": "FORMULA_RISK_SENTINEL",
            "formula_layout_risk": True,
        }, *safe_hits]
        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with patch("rag_core.generation.socket.getaddrinfo", return_value=public_answer):
            config = RemoteChatConfig.from_payload({
                "provider": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model": "test-model",
                "api_key": "never-log-this-key",
            })

        captured = {}
        def fake_post(remote_config, body, headers):
            captured["body"] = body.decode("utf-8")
            captured["headers"] = headers
            answer = f"找到一条候选证据 [{safe_hits[0]['evidence_id']}]"
            return {"choices": [{"message": {"content": answer}}]}

        with patch("rag_core.generation._post_remote_chat", side_effect=fake_post):
            result = generate_remote_answer("测试问题", hits, config)
        sent_body = captured["body"]
        self.assertIn("SAFE_SENTINEL_0", sent_body)
        self.assertIn("SAFE_SENTINEL_4", sent_body)
        self.assertNotIn("SAFE_SENTINEL_5", sent_body)
        self.assertNotIn("FORMULA_RISK_SENTINEL", sent_body)
        self.assertNotIn("never-log-this-key", sent_body)
        self.assertEqual(captured["headers"]["Authorization"], "Bearer never-log-this-key")
        self.assertEqual(result["sent_evidence_block_count"], 5)
        self.assertFalse(result["full_pdfs_sent"])
        self.assertNotIn("never-log-this-key", repr(result))

    def test_service_calls_remote_generator_only_after_explicit_opt_in(self):
        service = PlatformService(str(RELEASE_DIR))
        service.remote_api_allowed = True
        config = RemoteChatConfig(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model="test-model",
            resolved_ips=("8.8.8.8",),
        )
        generated = {
            "status": "external_api_preliminary_not_semantically_verified",
            "answer": "候选证据 [B001-PDF-01-ZA-S01-I-C001]",
            "citations": ["B001-PDF-01-ZA-S01-I-C001"],
            "model": "test-model",
            "provider": "openai_compatible",
            "execution_mode": "external_api",
        }
        with patch("rag_core.service.RemoteChatConfig.from_payload", return_value=config):
            with patch("rag_core.service.generate_remote_answer", return_value=generated) as call:
                result = service.qa(
                    "厂内冷却水过程建模",
                    remote_api={"provider": "openai_compatible", "base_url": "https://api.example.com/v1", "model": "test-model"},
                )
        self.assertEqual(result["generated_answer"]["execution_mode"], "external_api")
        self.assertIn("不发送整篇 PDF", result["notice"])
        call.assert_called_once()

    def test_live_model_catalog_uses_explicit_key_and_never_returns_it(self):
        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        captured = {}

        class FakeResponse:
            status = 200
            def read(self, _limit):
                return b'{"data":[{"id":"qwen3.5"},{"id":"deepseek-v4-flash"}]}'

        class FakeConnection:
            def __init__(self, hostname, pinned_ip, timeout=30):
                captured["connection"] = (hostname, pinned_ip, timeout)
            def request(self, method, target, headers=None):
                captured["request"] = (method, target, dict(headers or {}))
            def getresponse(self):
                return FakeResponse()
            def close(self):
                pass

        with patch("rag_core.generation.socket.getaddrinfo", return_value=public_answer):
            with patch("rag_core.generation._PinnedHTTPSConnection", FakeConnection):
                models = list_remote_models({
                    "provider": "cstcloud",
                    "base_url": CSTCLOUD_API_BASE_URL,
                    "api_key": "catalog-key-sentinel",
                })
        self.assertEqual(models, ["deepseek-v4-flash", "qwen3.5"])
        self.assertEqual(captured["request"][0:2], ("GET", "/v1/models"))
        self.assertEqual(captured["request"][2]["Authorization"], "Bearer catalog-key-sentinel")
        self.assertNotIn("catalog-key-sentinel", repr(models))

    def test_external_api_is_not_enabled_in_unconfigured_service(self):
        status = self.service.status()
        self.assertFalse(status["external_api"]["allowed"])
        self.assertFalse(status["external_api"]["api_key_persisted"])
        result = self.service.qa(
            "厂内冷却水过程建模",
            remote_api={"provider": "invalid", "api_key": "must-not-be-used"},
        )
        self.assertIsNone(result["generated_answer"])
        self.assertIn("only when the platform is bound to loopback", result["generation_error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
