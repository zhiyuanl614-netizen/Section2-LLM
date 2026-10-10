#!/usr/bin/env python3
"""Run the single-user Section2-LLM local evidence and isolated-workflow platform.

The formal release remains read-only. New PDF uploads, Step 02 processing and
BM25-only indexing are confined to loopback-only, versioned run directories.
External question answering and model-catalog lookup are explicit per-request
operations; no batch evidence is sent to a cloud API by default.
"""
from __future__ import annotations

import ipaddress
import json
import mimetypes
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
PROJECT_ROOT = HERE.parents[1]
DEFAULT_RELEASE_ID = "B001-v1.2-text-scope-preview-20261010"
DEFAULT_RELEASE_DIR = HERE / "data" / "releases" / DEFAULT_RELEASE_ID
FIGURE_ROOT = PROJECT_ROOT / "07_图表与章节输出" / "01_图表_2-1至2-4"
FIGURE_CATALOG = {
    "fig2-1-v12-r2": {
        "path": FIGURE_ROOT / "v1.2_text_scope_static_pilot_20261010_r2" / "figure_2_1_label_matrix_v1.2_text_scope.png",
        "figure": "图2-1", "version": "v1.2 text-scope · static-pilot · r2",
        "status": "静态先导图；非新 run 输出", "warning": "展示9个活动维度，不含 D03；PDF-03/D02仍未裁定。",
    },
    "fig2-1-legacy": {
        "path": FIGURE_ROOT / "figure_2_1_label_matrix.png",
        "figure": "图2-1", "version": "历史 v1.0 图表",
        "status": "历史档案；不得作为当前 v1.2 结论图", "warning": "该旧图包含 D03 方程相关标签，与当前公式范围边界不同。",
    },
    "fig2-2-legacy": {
        "path": FIGURE_ROOT / "figure_2_2_paradigm_clusters.png",
        "figure": "图2-2", "version": "历史 v1.0 图表",
        "status": "历史档案；当前 v1.2 对应图未生成", "warning": "该旧图含 D03/方程相关描述；仅供追溯旧版本，不得用于当前结论。",
    },
    "fig2-3-v12-r2": {
        "path": FIGURE_ROOT / "v1.2_text_scope_static_pilot_20261010_r2" / "figure_2_3_frdi_sensitivity_v1.2_text_scope.png",
        "figure": "图2-3", "version": "v1.2 text-scope · static-pilot · r2",
        "status": "静态先导图；非新 run 输出", "warning": "探索性情景值，不是统计置信区间或方向确认。",
    },
    "fig2-3-legacy": {
        "path": FIGURE_ROOT / "figure_2_3_frdi_robustness.png",
        "figure": "图2-3", "version": "历史 v1.0 图表",
        "status": "历史档案；不得作为当前 v1.2 结果图", "warning": "此图来自旧版本 FRDI 输入与口径。",
    },
    "fig2-4-legacy": {
        "path": FIGURE_ROOT / "figure_2_4_achievement_timeline.png",
        "figure": "图2-4", "version": "历史 v1.0 图表",
        "status": "历史档案；当前 v1.2 对应图未生成", "warning": "仅供旧版本来源核对；不可视作新 run 时间趋势结论。",
    },
}

sys.path.insert(0, str(HERE))

from rag_core.data import ReleaseIntegrityError  # noqa: E402
from rag_core.generation import (  # noqa: E402
    RemoteGenerationError,
    list_remote_models,
)
from rag_core.service import PlatformService  # noqa: E402
from rag_core.workflows import WorkflowError, WorkflowManager  # noqa: E402


class SafeThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16


class Handler(BaseHTTPRequestHandler):
    server_version = "Section2EvidencePlatform/1.1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        # Log only the URL path, never query strings, request bodies, prompts or keys.
        path = urlsplit(self.path).path
        print(f"[{self.log_date_time_string()}] {self.command} {path} {args[1] if len(args) > 1 else ''}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

    @property
    def service(self) -> PlatformService:
        return self.server.platform_service  # type: ignore[attr-defined]

    @property
    def workflow_manager(self) -> WorkflowManager:
        return self.server.workflow_manager  # type: ignore[attr-defined]

    def _json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, value: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        body = value.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, relative: str) -> None:
        allow = {
            "index.html", "styles.css", "app.js", "graph.js",
            "architecture_system.svg", "architecture_method.svg",
        }
        if relative not in allow:
            self._text("Not found", HTTPStatus.NOT_FOUND)
            return
        path = (STATIC_DIR / relative).resolve()
        if not path.is_relative_to(STATIC_DIR.resolve()) or not path.is_file():
            self._text("Not found", HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type, _ = mimetypes.guess_type(path.name)
        self.send_response(200)
        self.send_header("Content-Type", (content_type or "application/octet-stream") + ("; charset=utf-8" if content_type and content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _is_loopback_host_header(self) -> bool:
        try:
            host = (urlsplit("//" + (self.headers.get("Host") or "")).hostname or "").lower()
        except ValueError:
            return False
        return host in {"127.0.0.1", "localhost", "::1"}

    def _local_features_allowed(self) -> bool:
        if not bool(getattr(self.server, "local_features_enabled", False)):
            return False
        try:
            peer = ipaddress.ip_address(str(self.client_address[0]).split("%", 1)[0])
        except ValueError:
            return False
        return peer.is_loopback and self._is_loopback_host_header()

    def _same_origin_request(self) -> bool:
        # Localhost endpoints can be reached by a browser visiting hostile sites;
        # reject explicit cross-origin browser requests and DNS-rebinding Host names.
        fetch_site = self.headers.get("Sec-Fetch-Site", "").strip().lower()
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            return False
        origin = self.headers.get("Origin")
        if origin:
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return False
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != (self.headers.get("Host") or "").lower():
                return False
        return True

    def _read_body(self, max_bytes: int) -> bytes | None:
        if self.headers.get("Transfer-Encoding"):
            self._json({"error": "transfer_encoding_not_supported"}, HTTPStatus.BAD_REQUEST)
            return None
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError:
            self._json({"error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST)
            return None
        if length < 0 or length > max_bytes:
            self._json({"error": "request_body_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return None
        body = self.rfile.read(length)
        if len(body) != length:
            self._json({"error": "request_body_incomplete"}, HTTPStatus.BAD_REQUEST)
            return None
        return body

    def _read_json_body(self, max_bytes: int) -> dict | None:
        body = self._read_body(max_bytes)
        if body is None:
            return None
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._json({"error": "invalid_json_body"}, HTTPStatus.BAD_REQUEST)
            return None
        if not isinstance(payload, dict):
            self._json({"error": "json_body_must_be_object"}, HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def _serve_pdf(self, doc_id: str) -> None:
        path = self.service.store.pdf_path(doc_id)
        if path is None:
            self._json({"error": "unknown_document_id"}, HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        range_header = self.headers.get("Range")
        start, end = 0, size - 1
        partial = False
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self._text("Invalid byte range", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            a, b = match.groups()
            if not a and not b:
                self._text("Invalid byte range", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            if not a:
                length = min(int(b), size)
                start = max(0, size - length)
            else:
                start = int(a)
                end = min(int(b) if b else size - 1, size - 1)
            if start >= size or start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            partial = True
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f"inline; filename=\"{doc_id}.pdf\"")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "private, max-age=300")
        self.end_headers()
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _figures(self) -> dict:
        figures = []
        for figure_id, item in FIGURE_CATALOG.items():
            path = item["path"]
            if path.is_file():
                figures.append({
                    "id": figure_id,
                    "figure": item["figure"],
                    "version": item["version"],
                    "status": item["status"],
                    "warning": item["warning"],
                    "url": f"/figures/{figure_id}",
                })
        return {"figures": figures}

    def _serve_figure(self, figure_id: str) -> None:
        item = FIGURE_CATALOG.get(figure_id)
        if not item:
            self._text("Not found", HTTPStatus.NOT_FOUND)
            return
        path = item["path"].resolve()
        if not path.is_relative_to(FIGURE_ROOT.resolve()) or not path.is_file():
            self._text("Not found", HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(path.name)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _workflow_route(self, path: str) -> None:
        if not self._local_features_allowed():
            self._json({"error": "local_workflows_enabled_only_on_loopback"}, HTTPStatus.FORBIDDEN)
            return
        try:
            if path == "/api/workflows":
                self._json({"enabled": True, "runs": self.workflow_manager.list_runs(), "limits": self.workflow_manager.status(True)})
                return
            match = re.fullmatch(r"/api/workflows/([^/]+)", path)
            if match:
                self._json(self.workflow_manager.get_run(unquote(match.group(1))))
                return
            match = re.fullmatch(r"/api/workflows/([^/]+)/search", path)
            if match:
                query = parse_qs(urlsplit(self.path).query).get("q", [""])[0]
                try:
                    top_k = int(parse_qs(urlsplit(self.path).query).get("top_k", ["10"])[0])
                except ValueError:
                    self._json({"error": "top_k_must_be_integer"}, HTTPStatus.BAD_REQUEST)
                    return
                self._json(self.workflow_manager.search_run(unquote(match.group(1)), query, top_k))
                return
            match = re.fullmatch(r"/api/workflows/([^/]+)/artifacts/([^/]+)", path)
            if match:
                run_id, artifact_id = unquote(match.group(1)), unquote(match.group(2))
                query = parse_qs(urlsplit(self.path).query)
                if query.get("preview", [""])[0] == "1":
                    self._json(self.workflow_manager.artifact_preview(run_id, artifact_id))
                    return
                artifact_path, info = self.workflow_manager.artifact_path(run_id, artifact_id)
                size = artifact_path.stat().st_size
                ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", info["filename"]) or "artifact.bin"
                quoted_name = quote(info["filename"], safe="")
                self.send_response(200)
                self.send_header("Content-Type", info.get("content_type") or "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted_name}")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with artifact_path.open("rb") as stream:
                    while True:
                        chunk = stream.read(64 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                return
            raise WorkflowError("找不到工作流路由", 404)
        except WorkflowError as exc:
            self._json({"error": str(exc)}, exc.status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if (path.startswith("/api/") or path.startswith("/pdf/") or path.startswith("/figures/")) and bool(getattr(self.server, "local_features_enabled", False)) and not self._is_loopback_host_header():
            self._json({"error": "non_local_host_header_rejected"}, HTTPStatus.MISDIRECTED_REQUEST)
            return
        if path == "/":
            self._static("index.html")
        elif path.startswith("/assets/"):
            self._static(path.rsplit("/", 1)[-1])
        elif path == "/api/status":
            status = self.service.status()
            enabled = self._local_features_allowed()
            status["upload_enabled"] = enabled
            status["local_workflows"] = self.workflow_manager.status(enabled)
            self._json(status)
        elif path == "/api/documents":
            self._json({"documents": self.service.documents()})
        elif path == "/api/directions":
            self._json({"directions": self.service.directions()})
        elif path == "/api/figures":
            self._json(self._figures())
        elif path.startswith("/figures/"):
            figure_id = unquote(path.removeprefix("/figures/"))
            if "/" in figure_id or "\\" in figure_id:
                self._text("Not found", HTTPStatus.NOT_FOUND)
                return
            self._serve_figure(figure_id)
        elif path == "/api/workflows" or path.startswith("/api/workflows/"):
            self._workflow_route(path)
        elif path == "/api/graph":
            direction = query.get("direction", ["all"])[0]
            self._json(self.service.graph(None if direction == "all" else direction))
        elif path == "/api/search":
            q = query.get("q", [""])[0]
            mode = query.get("mode", ["hybrid"])[0]
            direction = query.get("direction", ["all"])[0]
            doc_id = query.get("doc_id", ["all"])[0]
            try:
                top_k = int(query.get("top_k", ["10"])[0])
            except ValueError:
                self._json({"error": "top_k_must_be_integer"}, HTTPStatus.BAD_REQUEST)
                return
            self._json(self.service.search(
                q, top_k=top_k, mode=mode,
                direction=None if direction == "all" else direction,
                doc_id=None if doc_id == "all" else doc_id,
            ))
        elif path.startswith("/api/evidence/"):
            evidence_id = unquote(path.removeprefix("/api/evidence/"))
            item = self.service.evidence(evidence_id)
            self._json(item if item else {"error": "unknown_evidence_id"}, 200 if item else HTTPStatus.NOT_FOUND)
        elif path.startswith("/pdf/"):
            doc_id = unquote(path.removeprefix("/pdf/"))
            if "/" in doc_id or "\\" in doc_id:
                self._json({"error": "invalid_document_id"}, HTTPStatus.BAD_REQUEST)
                return
            self._serve_pdf(doc_id)
        elif path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._text("Not found", HTTPStatus.NOT_FOUND)

    def _post_qa(self) -> None:
        if not self._same_origin_request():
            self.close_connection = True
            self._json({"error": "cross_origin_request_rejected"}, HTTPStatus.FORBIDDEN)
            return
        payload = self._read_json_body(32 * 1024)
        if payload is None:
            return
        query = payload.get("query")
        if not isinstance(query, str) or len(query.strip()) > 1200:
            self._json({"error": "query_required_and_must_be_at_most_1200_characters"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            top_k = int(payload.get("top_k", 8))
        except (TypeError, ValueError):
            self._json({"error": "top_k_must_be_integer"}, HTTPStatus.BAD_REQUEST)
            return
        direction = payload.get("direction")
        doc_id = payload.get("doc_id")
        generate = payload.get("generate", False) is True
        remote_api = payload.get("remote_api")
        if remote_api is not None and not isinstance(remote_api, dict):
            self._json({"error": "remote_api_must_be_an_object"}, HTTPStatus.BAD_REQUEST)
            return
        if generate and remote_api is not None:
            self._json({"error": "choose_one_generation_mode_per_request"}, HTTPStatus.BAD_REQUEST)
            return
        if remote_api is not None and (not self.service.remote_api_allowed or not self._local_features_allowed()):
            self._json({"error": "external_api_disabled_for_non_loopback_server"}, HTTPStatus.FORBIDDEN)
            return
        if direction not in (None, "all", "3-1", "4-1", "5-1"):
            self._json({"error": "unknown_direction"}, HTTPStatus.BAD_REQUEST)
            return
        if doc_id not in (None, "all") and doc_id not in self.service.store.document_by_id:
            self._json({"error": "unknown_doc_id"}, HTTPStatus.BAD_REQUEST)
            return
        result = self.service.qa(
            query.strip(), top_k=top_k,
            mode=payload.get("mode", "hybrid"),
            direction=None if direction == "all" else direction,
            doc_id=None if doc_id == "all" else doc_id,
            generate=generate,
            remote_api=remote_api,
        )
        self._json(result)

    def _post_workflow(self, path: str, parsed_query: str) -> None:
        if not self._local_features_allowed():
            self.close_connection = True
            self._json({"error": "local_workflows_enabled_only_on_loopback"}, HTTPStatus.FORBIDDEN)
            return
        if not self._same_origin_request():
            self.close_connection = True
            self._json({"error": "cross_origin_request_rejected"}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/workflows":
            payload = self._read_json_body(8 * 1024)
            if payload is None:
                return
            try:
                self._json(self.workflow_manager.create_run(payload.get("label", "隔离 PDF 运行")), HTTPStatus.CREATED)
            except WorkflowError as exc:
                self._json({"error": str(exc)}, exc.status)
            return
        match = re.fullmatch(r"/api/workflows/([^/]+)/files", path)
        if match:
            query = parse_qs(parsed_query)
            filename = query.get("filename", [""])[0]
            body = self._read_body(50 * 1024 * 1024)
            if body is None:
                return
            try:
                self._json(self.workflow_manager.upload_pdf(unquote(match.group(1)), filename, body), HTTPStatus.CREATED)
            except WorkflowError as exc:
                self._json({"error": str(exc)}, exc.status)
            return
        match = re.fullmatch(r"/api/workflows/([^/]+)/stages/([A-Za-z0-9_-]+)", path)
        if match:
            payload = self._read_json_body(8 * 1024)
            if payload is None:
                return
            try:
                result = self.workflow_manager.run_stage(
                    unquote(match.group(1)), match.group(2), confirm=payload.get("confirm") is True,
                )
                self._json(result)
            except WorkflowError as exc:
                self._json({"error": str(exc)}, exc.status)
            return
        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path.startswith("/api/") and bool(getattr(self.server, "local_features_enabled", False)) and not self._is_loopback_host_header():
            self.close_connection = True
            self._json({"error": "non_local_host_header_rejected"}, HTTPStatus.MISDIRECTED_REQUEST)
            return
        if parsed.path == "/api/qa":
            self._post_qa()
            return
        if parsed.path == "/api/models":
            if not self.service.remote_api_allowed or not self._local_features_allowed():
                self.close_connection = True
                self._json({"error": "external_api_disabled_for_non_loopback_server"}, HTTPStatus.FORBIDDEN)
                return
            if not self._same_origin_request():
                self.close_connection = True
                self._json({"error": "cross_origin_request_rejected"}, HTTPStatus.FORBIDDEN)
                return
            payload = self._read_json_body(8 * 1024)
            if payload is None:
                return
            try:
                models = list_remote_models(payload)
                self._json({"provider": payload.get("provider", "openai_compatible"), "models": models, "api_key_persisted": False})
            except RemoteGenerationError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return
        if parsed.path == "/api/workflows" or parsed.path.startswith("/api/workflows/"):
            self._post_workflow(parsed.path, parsed.query)
            return
        self.close_connection = True
        self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)


def _is_loopback_host(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def main() -> int:
    release_env = os.environ.get("PLATFORM_RELEASE_DIR", "").strip()
    release_dir = Path(release_env).expanduser().resolve() if release_env else DEFAULT_RELEASE_DIR
    try:
        service = PlatformService(str(release_dir))
    except (ReleaseIntegrityError, FileNotFoundError, ValueError) as exc:
        print(f"Platform startup blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    host = os.environ.get("PLATFORM_HOST", "127.0.0.1").strip() or "127.0.0.1"
    local_features_enabled = _is_loopback_host(host)
    service.remote_api_allowed = local_features_enabled
    try:
        port = int(os.environ.get("PLATFORM_PORT", "8765"))
    except ValueError:
        print("PLATFORM_PORT must be an integer", file=sys.stderr)
        return 2
    if not 1024 <= port <= 65535:
        print("PLATFORM_PORT must be in 1024..65535", file=sys.stderr)
        return 2
    server = SafeThreadingHTTPServer((host, port), Handler)
    server.platform_service = service  # type: ignore[attr-defined]
    server.workflow_manager = WorkflowManager()  # type: ignore[attr-defined]
    server.local_features_enabled = local_features_enabled  # type: ignore[attr-defined]
    print(f"Section2-LLM local evidence platform v1.1 ready: http://{host}:{port}")
    print(f"Release: {service.store.release.get('release_id')} (read-only, provisional pilot)")
    print(f"Isolated PDF workflows: {'enabled on loopback' if local_features_enabled else 'disabled for this non-loopback bind'}; no writes to the formal release.")
    print(f"Explicit external API calls: {'available on this loopback bind' if service.remote_api_allowed else 'disabled for this non-loopback bind'}; no automatic cloud fallback.")
    print("API credentials are accepted per request only and are not written to project files or logs.")
    try:
        server.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
