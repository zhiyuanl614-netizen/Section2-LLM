from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = ROOT / "平台" / "platform"
RELEASE_DIR = PLATFORM_ROOT / "data" / "releases" / "B001-v1.2-text-scope-preview-20261010"
sys.path.insert(0, str(PLATFORM_ROOT))

import app as platform_app  # noqa: E402
from rag_core.service import PlatformService  # noqa: E402
from rag_core.workflows import WorkflowManager  # noqa: E402


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = platform_app.SafeThreadingHTTPServer(("127.0.0.1", 0), platform_app.Handler)
        self.server.platform_service = PlatformService(str(RELEASE_DIR)
        )
        self.server.platform_service.remote_api_allowed = False
        self.server.workflow_manager = WorkflowManager(Path(self.temp.name) / "runs", ROOT)
        self.server.local_features_enabled = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        result = (response.status, response.getheader("Content-Type", ""), payload)
        connection.close()
        return result

    def test_loopback_workflow_create_and_upload_are_local_and_isolated(self):
        body = json.dumps({"label": "route test"})
        status, content_type, raw = self.request(
            "POST", "/api/workflows", body,
            {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 201)
        run = json.loads(raw)
        run_id = run["run_id"]
        self.assertFalse(run["isolation"]["official_release_modified"])

        pdf = b"%PDF-1.4\nsmall test PDF"
        status, _, raw = self.request(
            "POST", f"/api/workflows/{run_id}/files?filename=paper.pdf", pdf,
            {"Content-Type": "application/pdf", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 201)
        item = json.loads(raw)
        self.assertEqual(item["filename"], "paper.pdf")
        updated = self.server.workflow_manager.get_run(run_id)
        self.assertEqual(len(updated["uploads"]), 1)
        self.assertEqual(updated["uploads"][0]["sha256"], item["sha256"])

    def test_cross_origin_and_non_loopback_requests_fail_closed(self):
        body = json.dumps({"label": "should not be created"})
        status, _, raw = self.request(
            "POST", "/api/workflows", body,
            {"Content-Type": "application/json", "Origin": "https://attacker.invalid"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"], "cross_origin_request_rejected")
        self.assertEqual(self.server.workflow_manager.list_runs(), [])

        self.server.local_features_enabled = False
        # Use a fresh connection because the rejected handler closes the connection
        # without consuming a browser-supplied POST body.
        status, _, raw = self.request(
            "POST", "/api/workflows", body,
            {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"], "local_workflows_enabled_only_on_loopback")
        self.assertEqual(self.server.workflow_manager.list_runs(), [])

    def test_remote_model_catalog_route_is_disabled_when_remote_api_is_disabled(self):
        status, _, raw = self.request(
            "POST", "/api/models", json.dumps({"api_key": "never-store-me"}),
            {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"], "external_api_disabled_for_non_loopback_server")

    def test_cross_origin_qa_and_dns_rebinding_cannot_trigger_external_generation(self):
        self.server.platform_service.remote_api_allowed = True
        payload = json.dumps({
            "query": "water cooling",
            "remote_api": {"provider": "openai_compatible", "base_url": "https://attacker.example/v1", "model": "x", "api_key": "attacker-key"},
        })
        status, _, raw = self.request(
            "POST", "/api/qa", payload,
            {"Content-Type": "application/json", "Origin": "https://attacker.invalid"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"], "cross_origin_request_rejected")

        status, _, raw = self.request(
            "POST", "/api/qa", payload,
            {"Content-Type": "application/json", "Host": "evil.example", "Origin": "https://evil.example"},
        )
        self.assertEqual(status, 421)
        self.assertEqual(json.loads(raw)["error"], "non_local_host_header_rejected")
        status, _, raw = self.request("GET", "/api/documents", headers={"Host": "evil.example"})
        self.assertEqual(status, 421)
        self.assertEqual(json.loads(raw)["error"], "non_local_host_header_rejected")

    def test_figure_catalog_has_versioned_records_and_serves_only_fixed_assets(self):
        status, content_type, raw = self.request("GET", "/api/figures")
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        catalog = json.loads(raw)["figures"]
        figure_numbers = {row["figure"] for row in catalog}
        self.assertEqual(figure_numbers, {"图2-1", "图2-2", "图2-3", "图2-4"})
        old_22 = next(row for row in catalog if row["id"] == "fig2-2-legacy")
        self.assertIn("历史档案", old_22["status"])
        self.assertIn("D03", old_22["warning"])
        status, image_type, body = self.request("GET", "/figures/fig2-2-legacy")
        self.assertEqual(status, 200)
        self.assertIn("image/png", image_type)
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))
        status, _, _ = self.request("GET", "/figures/../../README.md")
        self.assertNotEqual(status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
