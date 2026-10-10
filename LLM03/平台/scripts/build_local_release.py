#!/usr/bin/env python3
"""Build a new, hash-verified, read-only pilot release for the local platform.

This packages only existing project files. It makes no model/API calls, does
not edit source artifacts, and refuses to replace an existing release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT / "平台" / "platform"
DEFAULT_RELEASE_ID = "B001-v1.2-text-scope-preview-20261010"

EVIDENCE_PATH = ROOT / "02_PDF清洗与分块" / "02_Chunks" / "evidence_blocks.jsonl"
CORPUS_PATH = ROOT / "02_PDF清洗与分块" / "01_Zones" / "step1_sliced_pdf_corpus.json"
LEDGER_PATH = ROOT / "04_LLM抽取与Critic审查" / "06_v1.2文本范围预分类" / "B001_v1.2_scope_aligned_50record_provisional_ledger.json"
SYNTHESIS_PATH = ROOT / "06_跨文献综合与FRDI" / "01_跨文献LLM综合" / "synthesis_v1.2_text_scope_preliminary.json"
INDEX_MANIFEST_PATH = ROOT / "03_证据索引与混合检索" / "03_检索运行清单" / "index_build_manifest.json"
DENSE_IDS_PATH = ROOT / "03_证据索引与混合检索" / "01_稠密向量索引" / "dense_evidence_ids.json"
DENSE_MATRIX_PATH = ROOT / "03_证据索引与混合检索" / "01_稠密向量索引" / "dense_embeddings.npy"
PDF_DIR = ROOT / "01_文献库"
ACTIVE_DIMS = ["D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]
EXPECTED_DOC_IDS = [f"B001-PDF-{i:02d}" for i in range(1, 6)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL row at {path}:{line_no}")
            rows.append(row)
    return rows


def edge_id(from_id: str, relation: str, to_id: str) -> str:
    raw = f"{from_id}\0{relation}\0{to_id}".encode("utf-8")
    return "edge:" + hashlib.sha256(raw).hexdigest()[:18]


def build_graph(
    documents: list[dict], records: list[dict], directions: list[dict], evidence_by_id: dict[str, dict]
) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    edge_ids: set[str] = set()

    def add_node(node: dict) -> None:
        if node["id"] in node_ids:
            raise ValueError(f"Duplicate graph node ID: {node['id']}")
        node_ids.add(node["id"])
        nodes.append(node)

    def add_edge(source: str, relation: str, target: str, label: str, provenance: str) -> None:
        eid = edge_id(source, relation, target)
        if eid in edge_ids:
            return
        edge_ids.add(eid)
        edges.append({
            "id": eid, "from": source, "to": target, "relation": relation,
            "label": label, "provenance": provenance,
        })

    for doc in documents:
        add_node({
            "id": f"document:{doc['doc_id']}", "type": "document", "label": doc["doc_id"],
            "title": doc["title"], "doc_id": doc["doc_id"], "year": doc.get("pub_year"),
            "doi": doc.get("doi"), "pdf_path": doc["pdf_path"], "pdf_sha256": doc["pdf_sha256"],
            "status": "source_document_registered",
        })

    dimension_titles = {
        "D01": "Water–power coupling direction",
        "D02": "In-plant cooling-water model",
        "D04": "Fast information-layer sensing",
        "D05": "Time-scale representation",
        "D06": "Early warning / control",
        "D07": "Physical network service loss",
        "D08": "Human / facility impacts",
        "D09": "Case and validation type",
        "D10": "Limitations / future work",
    }
    for dim in ACTIVE_DIMS:
        add_node({
            "id": f"dimension:{dim}", "type": "dimension", "label": dim,
            "title": dimension_titles.get(dim, dim),
            "status": "operational_coding_dimension_not_a_finding",
        })

    record_by_key: dict[tuple[str, str], dict] = {}
    for record in records:
        doc_id, dim = record["doc_id"], record["dimension_id"]
        key = (doc_id, dim)
        if key in record_by_key:
            raise ValueError(f"Duplicate active record key: {key}")
        record_by_key[key] = record
        rid = f"record:{doc_id}:{dim}"
        label = str(record.get("primary_label") or "<missing>")
        status = record.get("verification_status", "unknown")
        add_node({
            "id": rid, "type": "record", "label": f"{dim} · {label}",
            "title": f"{doc_id} · {dim}", "doc_id": doc_id, "dimension_id": dim,
            "primary_label": label, "verification_status": status,
            "record_origin": record.get("record_origin", "unknown"),
            "source_schema_version": record.get("source_schema_version", record.get("schema_version")),
            "carried_forward_from_v1_0": bool(record.get("carried_forward_from_v1_0", False)),
            "evidence_ids": record.get("evidence_ids") or [],
            "mechanism_judgment": record.get("mechanism_judgment", ""),
            "status": "unresolved_candidate" if status == "adjudication_required" else "provisional_record",
        })
        add_edge(f"dimension:{dim}", "HAS_PROVISIONAL_RECORD", rid, "先导记录", "v1.2 provisional ledger")
        add_edge(rid, "RECORDED_FOR_DOCUMENT", f"document:{doc_id}", "记录归属", "ledger doc_id")
        for evidence_id in record.get("evidence_ids") or []:
            block = evidence_by_id.get(evidence_id)
            if block is None or block.get("doc_id") != doc_id:
                raise ValueError(f"Record {rid} cites a missing or cross-document evidence ID: {evidence_id}")
            add_edge(rid, "CITES_EVIDENCE", f"evidence:{evidence_id}", "引用证据块", "record.evidence_ids")

    direction_ids: set[str] = set()
    for direction in directions:
        direction_id = direction.get("id")
        if direction_id not in {"3-1", "4-1", "5-1"} or direction_id in direction_ids:
            raise ValueError(f"Unexpected or duplicate candidate direction ID: {direction_id!r}")
        direction_ids.add(direction_id)
        add_node({
            "id": f"direction:{direction_id}", "type": "direction", "label": direction_id,
            "title": direction.get("title", direction_id), "rq": direction.get("rq"),
            "hypothesis_to_test": direction.get("hypothesis_to_test", ""),
            "pilot_result": direction.get("v1_2_result", ""),
            "interpretation": direction.get("interpretation", ""),
            "dimensions": direction.get("dimensions") or [],
            "evidence_ids": direction.get("evidence_ids") or [],
            "status": "existing_candidate_preliminary_pilot_not_confirmed",
        })
        for dim in direction.get("dimensions") or []:
            if dim not in ACTIVE_DIMS:
                raise ValueError(f"Direction {direction_id} maps to out-of-scope dimension {dim}")
            add_edge(f"direction:{direction_id}", "USES_DIMENSION", f"dimension:{dim}", "分析维度", "v1.2 synthesis mapping")
        for evidence_id in direction.get("evidence_ids") or []:
            block = evidence_by_id.get(evidence_id)
            if block is None:
                raise ValueError(f"Synthesis cites missing evidence ID: {evidence_id}")
            add_edge(
                f"direction:{direction_id}", "CITES_PILOT_SYNTHESIS_EVIDENCE",
                f"evidence:{evidence_id}", "先导综合引用", "same-session v1.2 pilot synthesis; stance is not inferred",
            )

    if direction_ids != {"3-1", "4-1", "5-1"}:
        raise ValueError("The pilot synthesis must contain exactly the three preserved directions")

    used_evidence_ids = {
        edge["to"] for edge in edges if edge["relation"] in {"CITES_EVIDENCE", "CITES_PILOT_SYNTHESIS_EVIDENCE"}
    }
    for evidence_node_id in sorted(used_evidence_ids):
        evidence_id = evidence_node_id.removeprefix("evidence:")
        block = evidence_by_id[evidence_id]
        doc_id = block["doc_id"]
        add_node({
            "id": evidence_node_id, "type": "evidence", "label": evidence_id,
            "title": block.get("section_title") or "Evidence block",
            "doc_id": doc_id, "section_id": block.get("section_id"),
            "section_title": block.get("section_title"),
            "page_numbers": block.get("page_numbers") or [],
            "text": block.get("text", ""),
            "formula_layout_risk": bool(block.get("formula_layout_risk", False)),
            "formula_layout_risk_score": block.get("formula_layout_risk_score"),
            "status": "source_text_not_semantically_adjudicated_by_platform",
        })
        add_edge(evidence_node_id, "FROM_SOURCE_DOCUMENT", f"document:{doc_id}", "來源文獻", "evidence block doc_id")

    return {
        "graph_version": "Section2-LLM-evidence-trace-graph-v1",
        "status": "provisional_pilot_evidence_trace_graph_not_approved_knowledge_truth",
        "node_count": len(nodes), "edge_count": len(edges),
        "nodes": nodes, "edges": edges,
        "semantics": {
            "edge_policy": "All graph edges express provenance/citation/coding metadata only; no support-versus-counterevidence relation is inferred from an evidence-ID list.",
            "D03": "Excluded from graph nodes, edges, findings, and retrieval directions; scope note retained separately.",
            "PDF03_D02": "Unresolved candidate label; not user-approved and not an adjudication.",
            "sample": "Five-paper pilot only; not a field-wide knowledge graph.",
        },
    }


def build(args: argparse.Namespace) -> Path:
    source_paths = [EVIDENCE_PATH, CORPUS_PATH, LEDGER_PATH, SYNTHESIS_PATH,
                    INDEX_MANIFEST_PATH, DENSE_IDS_PATH, DENSE_MATRIX_PATH]
    for path in source_paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    evidence_sha = sha256_file(EVIDENCE_PATH)
    evidence_manifest = read_json(INDEX_MANIFEST_PATH)
    if evidence_manifest.get("evidence_blocks_sha256") != evidence_sha:
        raise ValueError("Existing dense index manifest is not tied to the current evidence_blocks.jsonl")
    blocks = load_jsonl(EVIDENCE_PATH)
    block_ids = [row.get("evidence_id") for row in blocks]
    if not block_ids or any(not isinstance(eid, str) for eid in block_ids) or len(block_ids) != len(set(block_ids)):
        raise ValueError("Evidence file has invalid/duplicate evidence IDs")
    evidence_by_id = {row["evidence_id"]: row for row in blocks}
    if len(blocks) != evidence_manifest.get("n_evidence_blocks"):
        raise ValueError("Evidence count differs from the existing index manifest")

    corpus_rows = read_json(CORPUS_PATH)
    if not isinstance(corpus_rows, list):
        raise ValueError("Step 1 corpus must be an array")
    corpus_by_id = {row.get("doc_id"): row for row in corpus_rows}
    if set(corpus_by_id) != set(EXPECTED_DOC_IDS):
        raise ValueError("Current pilot corpus must contain exactly the five B001 PDF IDs")

    ledger = read_json(LEDGER_PATH)
    active_dims = ledger.get("active_analysis_dimensions")
    if active_dims != ACTIVE_DIMS:
        raise ValueError("Provisional ledger active dimensions do not match the v1.2 text-scope contract")
    all_records = ledger.get("records") or []
    records = [row for row in all_records if row.get("dimension_id") in ACTIVE_DIMS]
    if any(row.get("dimension_id") == "D03" for row in records):
        raise ValueError("D03 must not enter active records")
    if len(records) != len(EXPECTED_DOC_IDS) * len(ACTIVE_DIMS):
        raise ValueError("The pilot ledger must contain exactly 45 active analytic records")
    if any(row.get("equation_detail") not in (None, {}, []) for row in records):
        raise ValueError("Formula/equation detail is not allowed in the platform active record set")
    for row in records:
        for evidence_id in row.get("evidence_ids") or []:
            block = evidence_by_id.get(evidence_id)
            if block is None or block.get("doc_id") != row.get("doc_id"):
                raise ValueError(f"Record cites invalid/cross-document evidence: {row.get('doc_id')} / {evidence_id}")

    synthesis = read_json(SYNTHESIS_PATH)
    if synthesis.get("status") != "same_session_agent_assisted_pilot_synthesis_not_final":
        raise ValueError("Unexpected synthesis status; refusing to publish this pilot preview")
    directions = synthesis.get("candidate_directions") or []
    synthesis_evidence_ids = {eid for direction in directions for eid in direction.get("evidence_ids", [])}
    if not synthesis_evidence_ids or not synthesis_evidence_ids.issubset(evidence_by_id):
        raise ValueError("Pilot synthesis contains evidence IDs not found in source evidence blocks")

    dense_ids = read_json(DENSE_IDS_PATH)
    if dense_ids != block_ids:
        raise ValueError("Dense index evidence order does not exactly match the current evidence blocks")
    matrix = np.load(DENSE_MATRIX_PATH, allow_pickle=False, mmap_mode="r")
    if matrix.ndim != 2 or matrix.shape[0] != len(block_ids) or matrix.shape[1] != evidence_manifest.get("dense", {}).get("dim"):
        raise ValueError("Existing dense matrix shape does not match the manifest and evidence ID list")
    if not np.isfinite(matrix).all() or np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise ValueError("Existing dense matrix contains non-finite or all-zero vectors")

    release_id = args.release_id
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", release_id):
        raise ValueError("Release ID may contain only letters, digits, dot, underscore, and hyphen")
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / release_id
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing platform release: {target}")
    temp = output_root / f".{release_id}.tmp-{uuid.uuid4().hex[:8]}"
    temp.mkdir(parents=False, exist_ok=False)

    try:
        (temp / "pdfs").mkdir()
        (temp / "index").mkdir()
        shutil.copy2(EVIDENCE_PATH, temp / "evidence_blocks.jsonl")

        documents: list[dict] = []
        for doc_id in EXPECTED_DOC_IDS:
            source = corpus_by_id[doc_id]
            pdf_path = PDF_DIR / source["file_name"]
            if not pdf_path.is_file():
                raise FileNotFoundError(pdf_path)
            actual_pdf_sha = sha256_file(pdf_path)
            expected_pdf_sha = next((b.get("source_pdf_sha256") for b in blocks if b.get("doc_id") == doc_id), None)
            if actual_pdf_sha != expected_pdf_sha:
                raise ValueError(f"PDF hash does not match the evidence lineage for {doc_id}")
            packaged_pdf = temp / "pdfs" / f"{doc_id}.pdf"
            shutil.copy2(pdf_path, packaged_pdf)
            documents.append({
                "doc_id": doc_id,
                "title": source.get("title") or source.get("file_name"),
                "authors": source.get("authors"),
                "journal": source.get("journal"),
                "pub_year": source.get("pub_year"),
                "doi": source.get("doi"),
                "total_pages": source.get("total_pages"),
                "source_filename": source["file_name"],
                "pdf_path": f"pdfs/{doc_id}.pdf",
                "pdf_sha256": actual_pdf_sha,
                "status": "registered_source_pdf; citation metadata remains as extracted",
            })
        write_json(temp / "documents.json", documents)

        active_records = []
        for record in records:
            active_records.append(record)
        write_json(temp / "active_records.json", {
            "status": "provisional_mixed_provenance_not_independent_human_gold",
            "active_dimensions": ACTIVE_DIMS,
            "records": active_records,
        })
        write_json(temp / "directions.json", {
            "status": synthesis.get("status"),
            "origin": "The three existing candidates were proposed by literature comparison in the manuscript Introduction; this platform tests linked evidence and does not regenerate them.",
            "directions": directions,
            "limitations": synthesis.get("limitations", []),
            "overall_conclusion": synthesis.get("overall_llm_validation_conclusion"),
        })
        write_json(temp / "scope.json", {
            "project": "Section2-LLM",
            "status": "five-paper pilot preview; not a production or final release",
            "D03": "Not analyzed/out of scope; excluded from active records, graph, findings, and quality metrics. This is not a claim that the papers contain no equations.",
            "formula_policy": "No formula transcription, derivation, equation-type analysis, or formula-dependent conclusion is included. Original PDFs, evidence blocks, and formula-risk metadata remain available; formula risk is a caution flag only.",
            "PDF03_D02": "Unresolved; any current candidate label is not user-approved or an expert adjudication.",
            "quality_boundary": "No independent human gold standard, semantic entailment review, or model-performance claim is provided by this release.",
            "data_origin": {
                "records": ledger.get("status"),
                "synthesis": synthesis.get("status"),
                "D04-D10": synthesis.get("provenance", {}).get("D04_D10"),
            },
        })
        graph = build_graph(documents, records, directions, evidence_by_id)
        write_json(temp / "graph.json", graph)

        shutil.copy2(DENSE_MATRIX_PATH, temp / "index" / "dense_embeddings.npy")
        shutil.copy2(DENSE_IDS_PATH, temp / "index" / "dense_evidence_ids.json")
        dense_artifact_hashes = {
            "dense_embeddings.npy": sha256_file(temp / "index" / "dense_embeddings.npy"),
            "dense_evidence_ids.json": sha256_file(temp / "index" / "dense_evidence_ids.json"),
        }
        write_json(temp / "index" / "index_manifest.json", {
            "index_status": "existing_prebuilt_dense_matrix_reused_after_lineage_check",
            "source_manifest": str(INDEX_MANIFEST_PATH.relative_to(ROOT)),
            "source_manifest_sha256": sha256_file(INDEX_MANIFEST_PATH),
            "evidence_blocks_sha256": evidence_sha,
            "record_count": len(blocks),
            "evidence_id_order_sha256": hashlib.sha256("\n".join(block_ids).encode("utf-8")).hexdigest(),
            "dense_model": evidence_manifest.get("dense", {}).get("embedding_model"),
            "dense_shape": list(matrix.shape),
            "query_encoder": "not enabled unless the same model is available from a local-only FastEmbed cache",
            "artifact_sha256": dense_artifact_hashes,
        })

        corpus_digest = hashlib.sha256(
            (evidence_sha + sha256_file(LEDGER_PATH) + sha256_file(SYNTHESIS_PATH)).encode("utf-8")
        ).hexdigest()
        file_hashes: dict[str, str] = {}
        for path in sorted(p for p in temp.rglob("*") if p.is_file()):
            file_hashes[path.relative_to(temp).as_posix()] = sha256_file(path)
        release = {
            "release_id": release_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform_version": "local-pilot-platform-v1",
            "project_id": "Section2-LLM-B001",
            "status": "pilot_preview_not_final_not_production_released",
            "corpus_digest": corpus_digest,
            "corpus_size": len(documents),
            "evidence_block_count": len(blocks),
            "active_record_count": len(records),
            "active_dimensions": ACTIVE_DIMS,
            "graph_node_count": graph["node_count"],
            "graph_edge_count": graph["edge_count"],
            "retrieval": {
                "bm25": "self-contained local BM25 implementation using the locked English/number tokenizer; Chinese domain term expansion is explicit and limited",
                "dense_index_present": True,
                "dense_query_encoder_ready_by_default": False,
                "fusion": "RRF over available BM25/KG legs; dense joins only when matching local FastEmbed query encoder is configured",
                "llm_generation": "disabled by default; optional local-loopback-only endpoint may be configured",
            },
            "access": {"read_only": True, "single_user": True, "uploads_enabled": False, "external_network_required": False},
            "provenance": {
                "evidence_blocks_sha256": evidence_sha,
                "step3_manifest_sha256": sha256_file(INDEX_MANIFEST_PATH),
                "ledger_sha256": sha256_file(LEDGER_PATH),
                "synthesis_sha256": sha256_file(SYNTHESIS_PATH),
                "step1_corpus_sha256": sha256_file(CORPUS_PATH),
                "source_pdfs": {doc["doc_id"]: doc["pdf_sha256"] for doc in documents},
            },
            "source_status": {
                "ledger": ledger.get("status"),
                "synthesis": synthesis.get("status"),
                "independent_human_adjudication": False,
                "real_local_step4_batch": False,
            },
            "files_sha256": file_hashes,
        }
        write_json(temp / "release.json", release)
        if target.exists():
            raise FileExistsError(f"Target appeared during build; refusing to overwrite: {target}")
        os.rename(temp, target)
        return target
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output-root", type=Path, default=PLATFORM_ROOT / "data" / "releases")
    args = parser.parse_args()
    try:
        target = build(args)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"Local pilot platform release built: {target}")
    print("No source artifacts were edited; no model/API/network call was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
