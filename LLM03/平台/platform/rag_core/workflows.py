from __future__ import annotations

import hashlib
import importlib.util
import json
import mimetypes
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .retrieval import BM25, FORMULA_QUERY_RE, tokenize


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE_ROOT = PLATFORM_ROOT / "data" / "workflows"
RUN_ID_RE = re.compile(r"run-[A-Za-z0-9-]{12,80}\Z")
ARTIFACT_ID_RE = re.compile(r"artifact-[a-f0-9]{12}\Z")
MAX_PDF_COUNT = 10
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_RUN_BYTES = 120 * 1024 * 1024
PREVIEW_CHARS = 120_000
STAGE2_TIMEOUT_SECONDS = 30 * 60


class WorkflowError(RuntimeError):
    """Safe, user-displayable workflow error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _safe_filename(value: str) -> str:
    name = unicodedata.normalize("NFC", str(value or "")).strip()
    if not name or len(name) > 180 or name in {".", ".."}:
        raise WorkflowError("请提供不超过180个字符的 PDF 文件名")
    if "/" in name or "\\" in name or ":" in name or name.startswith("-") or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise WorkflowError("文件名不能包含路径分隔符、冒号、以短横线开头或含控制字符")
    if not name.lower().endswith(".pdf"):
        raise WorkflowError("仅接受 .pdf 文件")
    if name.startswith("."):
        raise WorkflowError("不接受以点开头的隐藏文件名")
    return name


def missing_step2_dependencies() -> list[str]:
    modules = (("pymupdf", "PyMuPDF"), ("openpyxl", "openpyxl"), ("docx", "python-docx"))
    return [label for module, label in modules if importlib.util.find_spec(module) is None]


def _subprocess_environment() -> dict[str, str]:
    # Do not forward arbitrary environment values (especially API tokens) to the
    # PDF processing subprocesses. These stages are local-only and need no keys.
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "HOME", "USERPROFILE", "LANG", "LC_ALL")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _run_command(command: list[str], *, cwd: Path, timeout: int) -> tuple[int, str]:
    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=_subprocess_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        **popen_kwargs,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            output, _ = process.communicate()
        return 124, (output or "") + f"\n任务超过 {timeout} 秒，已停止。"
    return int(process.returncode or 0), output or ""


class WorkflowManager:
    """Single-user isolated PDF workspaces; never modifies the formal release."""

    def __init__(self, workspace_root: str | Path | None = None, project_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root or DEFAULT_WORKSPACE_ROOT).expanduser().resolve()
        self.project_root = Path(project_root or PROJECT_ROOT).expanduser().resolve()
        self._lock = threading.RLock()

    def status(self, enabled: bool) -> dict[str, Any]:
        missing = missing_step2_dependencies()
        return {
            "enabled": bool(enabled),
            "loopback_only": True,
            "upload_enabled": bool(enabled),
            "formal_release_write_enabled": False,
            "uploaded_pdfs_are_isolated": True,
            "max_files_per_run": MAX_PDF_COUNT,
            "max_pdf_bytes": MAX_PDF_BYTES,
            "max_run_bytes": MAX_RUN_BYTES,
            "implemented_stages": ["01_pdf_registration", "02_pdf_clean_chunk", "03_bm25_index_partial"],
            "not_ready_stages": ["04_llm_extract_critic", "05_human_review_metrics", "06_synthesis_frdi", "07_run_figures_tables"],
            "batch_cloud_evidence_authorized": False,
            "step02_missing_dependencies": missing,
            "step02_ready": not missing,
        }

    def _run_dir(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(str(run_id or "")):
            raise WorkflowError("运行 ID 无效", 404)
        path = (self.workspace_root / run_id).resolve()
        if not path.is_relative_to(self.workspace_root):
            raise WorkflowError("运行目录越界", 404)
        return path

    @staticmethod
    def _stage_template() -> dict[str, dict[str, Any]]:
        return {
            "01_pdf_registration": {
                "title": "PDF 上传与登记", "status": "awaiting_uploads",
                "execution": "local_only", "summary": "等待上传 PDF；新 run 与正式5篇样本隔离。",
            },
            "02_pdf_clean_chunk": {
                "title": "PDF 清洗与分块", "status": "blocked_awaiting_uploads",
                "execution": "local_only", "summary": "需先登记至少一篇 PDF；执行时调用项目 Step 1 与 Step 2 版本化 wrapper。",
            },
            "03_bm25_index": {
                "title": "本地 BM25 索引", "status": "blocked_pending_step2",
                "execution": "local_only_partial", "summary": "只构建可核验 BM25 索引；Dense 与知识图谱索引尚未接入新 run。",
            },
            "04_llm_extract_critic": {
                "title": "LLM 抽取与 Critic", "status": "not_ready",
                "execution": "not_started", "summary": "新 run 的 v1.2 外部 API 批量 runner 尚未集成；不会发送 evidence blocks。",
            },
            "05_human_review_metrics": {
                "title": "人工核验与指标", "status": "not_ready",
                "execution": "not_started", "summary": "依赖真实 Step 4 ledger 与人工核验；当前 run 无可用输入。",
            },
            "06_synthesis_frdi": {
                "title": "跨文献综合与 FRDI", "status": "not_ready",
                "execution": "not_started", "summary": "依赖完整、真实且通过审核的 ledger；D02 边界仍未裁定。",
            },
            "07_run_figures_tables": {
                "title": "图表与章节输出", "status": "not_ready",
                "execution": "not_started", "summary": "新 run 的图表生成未就绪；图库中的旧版/静态先导图只作带版本标记的查看。",
            },
        }

    def create_run(self, label: str = "隔离 PDF 运行") -> dict[str, Any]:
        label = unicodedata.normalize("NFC", str(label or "隔离 PDF 运行")).strip()
        if len(label) > 100 or any(ord(char) < 32 for char in label):
            raise WorkflowError("运行名称最多100个字符，且不能含控制字符")
        label = label or "隔离 PDF 运行"
        with self._lock:
            self.workspace_root.mkdir(parents=True, exist_ok=True)
            run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}"
            run_dir = self._run_dir(run_id)
            run_dir.mkdir(parents=False, exist_ok=False)
            (run_dir / "uploads").mkdir()
            manifest = {
                "schema_version": "isolated-workflow-run-v1",
                "run_id": run_id,
                "label": label,
                "created_at_utc": utc_now(),
                "updated_at_utc": utc_now(),
                "status": "awaiting_uploads",
                "isolation": {
                    "classification": "isolated_user_uploaded_run",
                    "official_release_modified": False,
                    "formal_sample_extension_authorized": False,
                    "batch_cloud_evidence_authorized": False,
                    "full_pdfs_sent_to_external_api": False,
                },
                "uploads": [],
                "stages": self._stage_template(),
                "artifacts": [],
                "notices": [
                    "上传 PDF 只进入本 run 的隔离目录，不自动并入正式5篇样本或既有 release。",
                    "上传和 Step 02/03 仅在本机处理；后续批量云端发送未获默认授权。",
                ],
            }
            self._write_manifest(run_dir, manifest)
            return manifest

    def _read_manifest(self, run_dir: Path) -> dict[str, Any]:
        path = run_dir / "run_manifest.json"
        if not path.is_file() or path.is_symlink():
            raise WorkflowError("找不到该隔离运行", 404)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise WorkflowError("运行记录损坏，已停止读取", 409) from exc
        if manifest.get("schema_version") != "isolated-workflow-run-v1":
            raise WorkflowError("运行记录版本不受支持", 409)
        return manifest

    def _write_manifest(self, run_dir: Path, manifest: dict[str, Any]) -> None:
        manifest["updated_at_utc"] = utc_now()
        _atomic_json(run_dir / "run_manifest.json", manifest)

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            return self._read_manifest(self._run_dir(run_id))

    def list_runs(self) -> list[dict[str, Any]]:
        if not self.workspace_root.is_dir():
            return []
        rows = []
        with self._lock:
            for path in sorted(self.workspace_root.iterdir(), key=lambda item: item.name, reverse=True):
                if not path.is_dir() or path.is_symlink() or not RUN_ID_RE.fullmatch(path.name):
                    continue
                try:
                    manifest = self._read_manifest(path)
                except WorkflowError:
                    continue
                rows.append({
                    "run_id": manifest["run_id"],
                    "label": manifest.get("label"),
                    "created_at_utc": manifest.get("created_at_utc"),
                    "status": manifest.get("status"),
                    "upload_count": len(manifest.get("uploads") or []),
                    "stages": {key: value.get("status") for key, value in (manifest.get("stages") or {}).items()},
                })
        return rows[:100]

    def upload_pdf(self, run_id: str, filename: str, content: bytes) -> dict[str, Any]:
        safe_name = _safe_filename(filename)
        if not isinstance(content, bytes) or not content:
            raise WorkflowError("上传内容为空")
        if len(content) > MAX_PDF_BYTES:
            raise WorkflowError(f"单个 PDF 超过 {MAX_PDF_BYTES // (1024 * 1024)} MB 限制", 413)
        if content[:1024].find(b"%PDF-") < 0:
            raise WorkflowError("文件头不是 PDF；已拒绝保存")
        with self._lock:
            run_dir = self._run_dir(run_id)
            manifest = self._read_manifest(run_dir)
            stage2 = manifest["stages"]["02_pdf_clean_chunk"]
            if stage2.get("status") not in {"blocked_awaiting_uploads", "ready", "blocked_missing_dependencies"}:
                raise WorkflowError("Step 02 已开始；为保持输入指纹稳定，不能再向此 run 添加文件", 409)
            uploads = manifest.get("uploads") or []
            if len(uploads) >= MAX_PDF_COUNT:
                raise WorkflowError(f"每个 run 最多上传 {MAX_PDF_COUNT} 篇 PDF", 413)
            if any(item.get("filename") == safe_name for item in uploads):
                raise WorkflowError("该文件名已存在；请在本机先重命名后再上传", 409)
            total = sum(int(item.get("size_bytes", 0)) for item in uploads) + len(content)
            if total > MAX_RUN_BYTES:
                raise WorkflowError(f"本 run 所有 PDF 合计不能超过 {MAX_RUN_BYTES // (1024 * 1024)} MB", 413)
            upload_dir = run_dir / "uploads"
            if not upload_dir.is_dir() or upload_dir.is_symlink():
                raise WorkflowError("隔离上传目录无效", 409)
            destination = upload_dir / safe_name
            if destination.exists() or destination.is_symlink():
                raise WorkflowError("目标文件已存在，拒绝覆盖", 409)
            temp_path = upload_dir / f".{uuid.uuid4().hex}.upload"
            try:
                with temp_path.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, destination)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            item = {
                "filename": safe_name,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "uploaded_at_utc": utc_now(),
                "storage": "isolated_run_uploads_local_only",
            }
            uploads.append(item)
            manifest["uploads"] = uploads
            manifest["status"] = "ready_for_step02"
            manifest["stages"]["01_pdf_registration"].update({
                "status": "completed", "summary": f"已登记 {len(uploads)} 篇 PDF；仅在隔离 run 内。",
                "completed_at_utc": utc_now(),
            })
            stage2.update({"status": "ready", "summary": f"已登记 {len(uploads)} 篇 PDF，可本机清洗与分块。"})
            self._write_manifest(run_dir, manifest)
            return item

    def run_stage(self, run_id: str, stage_id: str, *, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise WorkflowError("必须在界面明确确认后才能执行此阶段")
        if stage_id == "02_pdf_clean_chunk":
            self._run_stage2(run_id)
        elif stage_id == "03_bm25_index":
            self._run_stage3(run_id)
        else:
            raise WorkflowError("该阶段尚未接入可执行 runner；没有启动任务或发送内容", 409)
        return self.get_run(run_id)

    def _run_stage2(self, run_id: str) -> None:
        with self._lock:
            run_dir = self._run_dir(run_id)
            manifest = self._read_manifest(run_dir)
            stage = manifest["stages"]["02_pdf_clean_chunk"]
            uploads = manifest.get("uploads") or []
            if not uploads:
                raise WorkflowError("请先上传至少一篇 PDF", 409)
            if stage.get("status") == "running":
                raise WorkflowError("Step 02 已在运行；拒绝重复启动", 409)
            if stage.get("status") == "completed":
                raise WorkflowError("此阶段已完成且不可覆盖；如需重跑，请创建新的隔离 run", 409)
            if stage.get("status") not in {"ready", "blocked_missing_dependencies"}:
                raise WorkflowError("当前 run 状态不允许启动 Step 02", 409)
            stage1_dir = run_dir / "step01"
            stage2_dir = run_dir / "step02"
            if stage1_dir.exists() or stage2_dir.exists():
                raise WorkflowError("发现已有 Step 01/02 产物；为避免覆盖，请创建新的隔离 run", 409)
            missing = missing_step2_dependencies()
            if missing:
                stage.update({
                    "status": "blocked_missing_dependencies",
                    "summary": "缺少本地 PDF 解析依赖；未启动脚本、未改动输入或正式产物。",
                    "missing_dependencies": missing,
                    "checked_at_utc": utc_now(),
                })
                manifest["status"] = "blocked_missing_dependencies"
                self._write_manifest(run_dir, manifest)
                return
            stage.update({"status": "running", "started_at_utc": utc_now(), "summary": "Step 1/2 在本机执行中；不调用外部 API。"})
            manifest["status"] = "running_step02"
            self._write_manifest(run_dir, manifest)

        wrapper1 = self.project_root / "04_LLM抽取与Critic审查" / "API批量管线" / "step1_run_versioned_batch_local.py"
        wrapper2 = self.project_root / "04_LLM抽取与Critic审查" / "API批量管线" / "step2_run_versioned_local.py"
        if not wrapper1.is_file() or not wrapper2.is_file():
            output = "Versioned Step 1/2 wrapper is missing; no script was run."
            self._finish_stage2_failure(run_id, output, "runner_missing")
            return
        filenames = [row["filename"] for row in uploads]
        input_dir = run_dir / "uploads"
        batch_id = "web_" + run_id.removeprefix("run-").replace("-", "_")
        command1 = [
            sys.executable, str(wrapper1),
            "--input-dir", str(input_dir),
            "--output-dir", str(stage1_dir),
            "--batch-id", batch_id,
            "--files", *filenames,
        ]
        command2 = [
            sys.executable, str(wrapper2),
            "--input", str(stage1_dir / "step1_sliced_pdf_corpus.json"),
            "--source-manifest", str(stage1_dir / "run_manifest.json"),
            "--output-dir", str(stage2_dir),
        ]
        logs: list[str] = []
        for label, command in (("Step 1 · PDF切片", command1), ("Step 2 · 证据分块", command2)):
            try:
                returncode, output = _run_command(command, cwd=self.project_root, timeout=STAGE2_TIMEOUT_SECONDS)
            except OSError as exc:
                returncode, output = 127, f"无法启动本地 Python 子进程：{type(exc).__name__}"
            logs.append(f"[{label}] exit={returncode}\n{output[-30_000:]}")
            if returncode != 0:
                self._finish_stage2_failure(run_id, "\n\n".join(logs), "stage_command_failed")
                return
        step1_output = stage1_dir / "step1_sliced_pdf_corpus.json"
        evidence_path = stage2_dir / "evidence_blocks.jsonl"
        try:
            documents = json.loads(step1_output.read_text(encoding="utf-8"))
            block_count = sum(1 for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip())
            if not isinstance(documents, list) or not documents or block_count <= 0:
                raise ValueError("Step 1/2 output has no documents or evidence blocks")
        except Exception as exc:
            self._finish_stage2_failure(run_id, "\n\n".join(logs) + f"\nOutput validation failed: {type(exc).__name__}: {exc}", "output_validation_failed")
            return
        with self._lock:
            run_dir = self._run_dir(run_id)
            manifest = self._read_manifest(run_dir)
            manifest["artifacts"] = [item for item in manifest.get("artifacts", []) if item.get("stage_id") not in {"02_pdf_clean_chunk", "03_bm25_index"}]
            manifest["artifacts"].extend(self._collect_artifacts(run_dir, "02_pdf_clean_chunk", [stage1_dir, stage2_dir]))
            stage = manifest["stages"]["02_pdf_clean_chunk"]
            stage.update({
                "status": "completed",
                "completed_at_utc": utc_now(),
                "summary": f"本机完成 {len(documents)} 篇 PDF 切片与 {block_count} 个 evidence blocks。",
                "document_count": len(documents),
                "evidence_block_count": block_count,
                "input_pdf_hashes": [{"filename": row["filename"], "sha256": row["sha256"]} for row in manifest.get("uploads", [])],
                "external_data_sent": False,
                "log_tail": "\n\n".join(logs)[-30_000:],
            })
            stage3 = manifest["stages"]["03_bm25_index"]
            stage3.update({"status": "ready", "summary": "Step 2 evidence blocks 已就绪；可构建本地 BM25-only 索引。Dense 与图谱索引未构建。"})
            manifest["status"] = "ready_for_stage03_bm25"
            manifest["notices"] = list(dict.fromkeys((manifest.get("notices") or []) + [
                "Step 02 仅执行本机 PDF 切片与文本分块；公式风险 metadata 会保留，不进行公式解析。",
            ]))
            self._write_manifest(run_dir, manifest)

    def _finish_stage2_failure(self, run_id: str, output: str, error_code: str) -> None:
        with self._lock:
            run_dir = self._run_dir(run_id)
            manifest = self._read_manifest(run_dir)
            stage = manifest["stages"]["02_pdf_clean_chunk"]
            stage.update({
                "status": "failed",
                "failed_at_utc": utc_now(),
                "error_code": error_code,
                "summary": "Step 1/2 未完成；部分新目录保留供审查，没有覆盖或删除任何历史产物。",
                "log_tail": output[-30_000:],
                "external_data_sent": False,
            })
            manifest["status"] = "step02_failed"
            partial_dirs = [run_dir / "step01", run_dir / "step02"]
            manifest["artifacts"] = [item for item in manifest.get("artifacts", []) if item.get("stage_id") != "02_pdf_clean_chunk"]
            manifest["artifacts"].extend(self._collect_artifacts(run_dir, "02_pdf_clean_chunk", partial_dirs))
            self._write_manifest(run_dir, manifest)

    def _run_stage3(self, run_id: str) -> None:
        with self._lock:
            run_dir = self._run_dir(run_id)
            manifest = self._read_manifest(run_dir)
            stage = manifest["stages"]["03_bm25_index"]
            if manifest["stages"]["02_pdf_clean_chunk"].get("status") != "completed":
                raise WorkflowError("Step 03 需先完成 Step 02", 409)
            if stage.get("status") == "running":
                raise WorkflowError("Step 03 已在运行；拒绝重复启动", 409)
            if stage.get("status") in {"partial_bm25_ready", "completed"}:
                raise WorkflowError("BM25 索引已存在且不可覆盖；如需重建，请创建新的隔离 run", 409)
            if stage.get("status") != "ready":
                raise WorkflowError("当前 run 状态不允许启动 Step 03", 409)
            output_dir = run_dir / "step03"
            if output_dir.exists():
                raise WorkflowError("发现已有 Step 03 目录；为避免覆盖，请创建新的隔离 run", 409)
            evidence_path = run_dir / "step02" / "evidence_blocks.jsonl"
            if not evidence_path.is_file():
                raise WorkflowError("找不到 Step 02 evidence_blocks.jsonl", 409)
            stage.update({"status": "running", "started_at_utc": utc_now(), "summary": "在本机为当前 run 构建 BM25-only 索引。"})
            manifest["status"] = "running_stage03"
            self._write_manifest(run_dir, manifest)

        try:
            records: list[dict[str, Any]] = []
            with evidence_path.open(encoding="utf-8") as stream:
                for line_no, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if not isinstance(record, dict) or not record.get("evidence_id") or not record.get("doc_id"):
                        raise ValueError(f"Invalid evidence block at line {line_no}")
                    records.append(record)
            evidence_ids = [row["evidence_id"] for row in records]
            if not records or len(set(evidence_ids)) != len(evidence_ids):
                raise ValueError("Evidence block set is empty or contains duplicate evidence_id values")
            text_rows = [str(row.get("retrieval_text") or row.get("text") or "") for row in records]
            bm25 = BM25(text_rows)
            output_dir.mkdir(parents=False, exist_ok=False)
            index_payload = {
                "schema_version": "workspace-bm25-index-v1",
                "tokenizer": "rag_core.retrieval.tokenize",
                "source_evidence_sha256": sha256_file(evidence_path),
                "record_count": len(records),
                "evidence_ids": evidence_ids,
                "document_lengths": bm25.lengths,
                "average_document_length": bm25.avgdl,
                "k1": bm25.k1,
                "b": bm25.b,
                "term_frequencies": [dict(freq) for freq in bm25.term_freqs],
                "idf": bm25.idf,
                "formula_risk_record_count": sum(bool(row.get("formula_layout_risk")) for row in records),
                "dense_index": {"status": "not_built", "reason": "本机新 run 尚未配置可验证的 FastEmbed 本地权重；未联网下载。"},
                "graph_index": {"status": "not_built", "reason": "新 run 的 provenance graph builder 尚未接入。"},
            }
            index_path = output_dir / "bm25_index.json"
            _atomic_json(index_path, index_payload)
            source_hash = sha256_file(evidence_path)
            index_hash = sha256_file(index_path)
            with self._lock:
                manifest = self._read_manifest(run_dir)
                stage = manifest["stages"]["03_bm25_index"]
                manifest["artifacts"] = [item for item in manifest.get("artifacts", []) if item.get("stage_id") != "03_bm25_index"]
                manifest["artifacts"].extend(self._collect_artifacts(run_dir, "03_bm25_index", [output_dir]))
                stage.update({
                    "status": "partial_bm25_ready",
                    "completed_at_utc": utc_now(),
                    "summary": f"已建立 {len(records)} 条 evidence blocks 的 BM25 索引；Dense 与图谱部分明确未就绪。",
                    "record_count": len(records),
                    "source_evidence_sha256": source_hash,
                    "index_sha256": index_hash,
                    "formula_risk_records_retained": True,
                    "external_data_sent": False,
                    "capabilities": ["BM25 local retrieval"],
                    "not_implemented": ["Dense query encoder", "new-run provenance graph index"],
                })
                manifest["status"] = "partial_ready_bm25_only"
                self._write_manifest(run_dir, manifest)
        except Exception as exc:
            with self._lock:
                manifest = self._read_manifest(run_dir)
                stage = manifest["stages"]["03_bm25_index"]
                stage.update({
                    "status": "failed",
                    "failed_at_utc": utc_now(),
                    "error_code": "index_build_failed",
                    "summary": f"BM25 索引未就绪：{type(exc).__name__}: {str(exc)[:300]}",
                    "external_data_sent": False,
                })
                manifest["status"] = "stage03_failed"
                self._write_manifest(run_dir, manifest)

    def search_run(self, run_id: str, query: str, top_k: int = 10) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query or len(query) > 1200:
            raise WorkflowError("请输入不超过1200字符的检索问题")
        if top_k < 1 or top_k > 20:
            raise WorkflowError("top_k 必须在1至20之间")
        if FORMULA_QUERY_RE.search(query):
            return {
                "run_id": run_id,
                "query": query,
                "hits": [],
                "out_of_scope": True,
                "active_channels": [],
                "notices": ["公式转录、推导、变量/符号解释与方程类型分析不在当前范围；此查询未执行。"],
            }
        run_dir = self._run_dir(run_id)
        manifest = self._read_manifest(run_dir)
        stage = manifest["stages"]["03_bm25_index"]
        if stage.get("status") != "partial_bm25_ready":
            raise WorkflowError("此 run 尚无可用 BM25 索引", 409)
        evidence_path = run_dir / "step02" / "evidence_blocks.jsonl"
        index_path = run_dir / "step03" / "bm25_index.json"
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if index.get("source_evidence_sha256") != sha256_file(evidence_path):
                raise WorkflowError("Step 2 证据文件指纹与 BM25 索引不匹配", 409)
            with evidence_path.open(encoding="utf-8") as stream:
                records = [json.loads(line) for line in stream if line.strip()]
        except WorkflowError:
            raise
        except Exception as exc:
            raise WorkflowError("无法读取当前 run 的 BM25 索引或证据文件", 409) from exc
        if index.get("schema_version") != "workspace-bm25-index-v1" or index.get("evidence_ids") != [row.get("evidence_id") for row in records]:
            raise WorkflowError("BM25 索引版本或 evidence ID 顺序不匹配", 409)
        query_terms = tokenize(query)
        if not query_terms:
            return {"run_id": run_id, "query": query, "hits": [], "active_channels": ["BM25"], "notices": ["查询词没有可评分的英文/数字 token。"]}
        lengths = index["document_lengths"]
        avgdl = float(index["average_document_length"] or 1.0)
        k1, b = float(index["k1"]), float(index["b"])
        idf = index["idf"]
        term_freqs = index["term_frequencies"]
        scores: list[float] = []
        for position, frequencies in enumerate(term_freqs):
            dl = int(lengths[position])
            norm = k1 * (1.0 - b + b * dl / max(avgdl, 1e-9))
            score = 0.0
            for term in query_terms:
                tf = int(frequencies.get(term, 0))
                if tf:
                    score += float(idf.get(term, 0.0)) * (tf * (k1 + 1.0)) / (tf + norm)
            scores.append(score)
        order = sorted((i for i, score in enumerate(scores) if score > 0), key=lambda i: (-scores[i], i))[:top_k]
        hits = []
        for position in order:
            row = records[position]
            hits.append({
                "evidence_id": row["evidence_id"],
                "doc_id": row["doc_id"],
                "pages": row.get("page_numbers") or [],
                "section_id": row.get("section_id"),
                "section_title": row.get("section_title"),
                "text": row.get("text", ""),
                "score": round(scores[position], 6),
                "formula_layout_risk": bool(row.get("formula_layout_risk", False)),
                "formula_layout_risk_score": row.get("formula_layout_risk_score"),
            })
        return {
            "run_id": run_id,
            "query": query,
            "hits": hits,
            "active_channels": ["BM25"],
            "notices": [
                "这是隔离 run 的本地 BM25 结果，不等于语义检索或研究结论。",
                "带公式版面风险的原始证据与 metadata 保留；本地检索不做公式解析。",
            ],
        }

    def _collect_artifacts(self, run_dir: Path, stage_id: str, roots: list[Path]) -> list[dict[str, Any]]:
        items = []
        for root in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                resolved = path.resolve()
                if not resolved.is_relative_to(run_dir.resolve()):
                    continue
                relative = resolved.relative_to(run_dir.resolve()).as_posix()
                artifact_id = "artifact-" + hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
                content_type, _ = mimetypes.guess_type(path.name)
                items.append({
                    "artifact_id": artifact_id,
                    "stage_id": stage_id,
                    "relative_path": relative,
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "content_type": content_type or "application/octet-stream",
                })
        return items

    def artifact_path(self, run_id: str, artifact_id: str) -> tuple[Path, dict[str, Any]]:
        if not ARTIFACT_ID_RE.fullmatch(str(artifact_id or "")):
            raise WorkflowError("artifact ID 无效", 404)
        run_dir = self._run_dir(run_id)
        manifest = self._read_manifest(run_dir)
        info = next((row for row in manifest.get("artifacts", []) if row.get("artifact_id") == artifact_id), None)
        if not info:
            raise WorkflowError("找不到该运行产物", 404)
        relative = Path(str(info.get("relative_path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise WorkflowError("产物路径无效", 404)
        path = (run_dir / relative).resolve()
        if not path.is_relative_to(run_dir.resolve()) or not path.is_file() or path.is_symlink():
            raise WorkflowError("产物文件不存在或路径越界", 404)
        if sha256_file(path) != info.get("sha256"):
            raise WorkflowError("产物指纹不匹配，已停止读取", 409)
        return path, info

    def artifact_preview(self, run_id: str, artifact_id: str) -> dict[str, Any]:
        path, info = self.artifact_path(run_id, artifact_id)
        allowed_suffixes = {".txt", ".md", ".json", ".jsonl", ".csv", ".log"}
        if path.suffix.lower() not in allowed_suffixes:
            raise WorkflowError("该产物为二进制文件，请使用下载链接", 415)
        raw = path.read_bytes()[: PREVIEW_CHARS * 4]
        text = raw.decode("utf-8", errors="replace")
        truncated = len(raw) < path.stat().st_size or len(text) > PREVIEW_CHARS
        text = text[:PREVIEW_CHARS]
        return {
            "artifact_id": artifact_id,
            "filename": info["filename"],
            "sha256": info["sha256"],
            "text": text,
            "truncated": truncated,
            "max_preview_characters": PREVIEW_CHARS,
        }
