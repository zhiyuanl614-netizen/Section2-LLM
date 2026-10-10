from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ReleaseIntegrityError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ReleaseIntegrityError(f"Release path escapes its root: {relative}")
    return candidate


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReleaseIntegrityError(f"Cannot parse release JSON {path.name}: {exc}") from exc


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ReleaseIntegrityError(f"Non-object JSONL row at {path.name}:{line_no}")
                records.append(record)
    except ReleaseIntegrityError:
        raise
    except Exception as exc:
        raise ReleaseIntegrityError(f"Cannot read release JSONL {path.name}: {exc}") from exc
    return records


class ReleaseStore:
    """Load one immutable, hash-checked release directory."""

    def __init__(self, release_dir: str | Path, verify_hashes: bool = True) -> None:
        self.release_dir = Path(release_dir).expanduser().resolve()
        manifest_path = self.release_dir / "release.json"
        if not manifest_path.is_file():
            raise ReleaseIntegrityError(f"release.json not found under {self.release_dir}")
        self.release = _read_json(manifest_path)
        if self.release.get("status") != "pilot_preview_not_final_not_production_released":
            raise ReleaseIntegrityError("This runtime only accepts the explicitly marked pilot preview release")
        if verify_hashes:
            self._verify_files()

        self.scope = _read_json(self.path("scope.json"))
        self.documents = _read_json(self.path("documents.json"))
        self.document_by_id = {row.get("doc_id"): row for row in self.documents}
        if len(self.document_by_id) != len(self.documents) or not self.documents:
            raise ReleaseIntegrityError("documents.json has missing or duplicate doc_id values")

        self.blocks = _read_jsonl(self.path("evidence_blocks.jsonl"))
        self.block_by_id = {row.get("evidence_id"): row for row in self.blocks}
        if len(self.block_by_id) != len(self.blocks) or any(not key for key in self.block_by_id):
            raise ReleaseIntegrityError("Evidence blocks contain missing or duplicate evidence_id values")
        self.records_package = _read_json(self.path("active_records.json"))
        if self.records_package.get("status") != "provisional_mixed_provenance_not_independent_human_gold":
            raise ReleaseIntegrityError("Active record provenance status is unexpected")
        self.records = self.records_package.get("records") or []
        if any(row.get("dimension_id") == "D03" for row in self.records):
            raise ReleaseIntegrityError("D03 must not be included in active platform records")
        for record in self.records:
            if record.get("dimension_id") not in self.records_package.get("active_dimensions", []):
                raise ReleaseIntegrityError("Unexpected active dimension in platform record set")
            for evidence_id in record.get("evidence_ids") or []:
                block = self.block_by_id.get(evidence_id)
                if block is None or block.get("doc_id") != record.get("doc_id"):
                    raise ReleaseIntegrityError(f"Record evidence link is invalid: {evidence_id}")

        self.directions_package = _read_json(self.path("directions.json"))
        self.directions = self.directions_package.get("directions") or []
        self.graph = _read_json(self.path("graph.json"))
        self._validate_graph()

    def path(self, relative: str) -> Path:
        return _safe_child(self.release_dir, relative)

    def _verify_files(self) -> None:
        files = self.release.get("files_sha256")
        if not isinstance(files, dict) or not files:
            raise ReleaseIntegrityError("release.json has no artifact hash manifest")
        for relative, expected_hash in files.items():
            if not isinstance(relative, str) or not isinstance(expected_hash, str):
                raise ReleaseIntegrityError("Invalid artifact hash manifest entry")
            path = self.path(relative)
            if not path.is_file():
                raise ReleaseIntegrityError(f"Release artifact is missing: {relative}")
            if sha256_file(path) != expected_hash:
                raise ReleaseIntegrityError(f"Release artifact hash mismatch: {relative}")

    def _validate_graph(self) -> None:
        nodes = self.graph.get("nodes") or []
        edges = self.graph.get("edges") or []
        ids = {node.get("id") for node in nodes}
        if len(ids) != len(nodes) or None in ids:
            raise ReleaseIntegrityError("Graph has missing or duplicate node IDs")
        if any(edge.get("from") not in ids or edge.get("to") not in ids for edge in edges):
            raise ReleaseIntegrityError("Graph has an edge to an unknown node")
        if any(node.get("dimension_id") == "D03" or node.get("id") == "dimension:D03" for node in nodes):
            raise ReleaseIntegrityError("D03 must not appear in the published pilot graph")
        if self.graph.get("status") != "provisional_pilot_evidence_trace_graph_not_approved_knowledge_truth":
            raise ReleaseIntegrityError("Graph status does not disclose provisional provenance")

    def read_json(self, relative: str) -> Any:
        return _read_json(self.path(relative))

    def document(self, doc_id: str) -> dict | None:
        return self.document_by_id.get(doc_id)

    def pdf_path(self, doc_id: str) -> Path | None:
        doc = self.document(doc_id)
        if not doc:
            return None
        path = self.path(doc.get("pdf_path", ""))
        if not path.is_file() or sha256_file(path) != doc.get("pdf_sha256"):
            raise ReleaseIntegrityError(f"Packaged PDF failed its source hash check: {doc_id}")
        return path

    def graph_for_direction(self, direction_id: str | None = None) -> dict:
        if not direction_id or direction_id == "all":
            return self.graph
        allowed_nodes: set[str] = {f"direction:{direction_id}"}
        for edge in self.graph.get("edges", []):
            if edge.get("from") == f"direction:{direction_id}" and edge.get("relation") == "USES_DIMENSION":
                allowed_nodes.add(edge["to"])
            if edge.get("from") == f"direction:{direction_id}" and edge.get("relation") == "CITES_PILOT_SYNTHESIS_EVIDENCE":
                allowed_nodes.add(edge["to"])
        # Keep only selected dimensions and their records/evidence so the view
        # remains an auditable subgraph rather than a cross-direction blend.
        changed = True
        while changed:
            before = len(allowed_nodes)
            for edge in self.graph.get("edges", []):
                if edge.get("from") in allowed_nodes and edge.get("relation") in {
                    "HAS_PROVISIONAL_RECORD", "CITES_EVIDENCE", "RECORDED_FOR_DOCUMENT", "FROM_SOURCE_DOCUMENT"
                }:
                    allowed_nodes.add(edge.get("to"))
                if edge.get("to") in allowed_nodes and edge.get("relation") == "HAS_PROVISIONAL_RECORD":
                    allowed_nodes.add(edge.get("from"))
                if edge.get("to") in allowed_nodes and edge.get("relation") == "CITES_EVIDENCE":
                    allowed_nodes.add(edge.get("from"))
            changed = len(allowed_nodes) != before
        return {
            **self.graph,
            "nodes": [node for node in self.graph.get("nodes", []) if node.get("id") in allowed_nodes],
            "edges": [edge for edge in self.graph.get("edges", []) if edge.get("from") in allowed_nodes and edge.get("to") in allowed_nodes],
            "filtered_direction": direction_id,
        }
