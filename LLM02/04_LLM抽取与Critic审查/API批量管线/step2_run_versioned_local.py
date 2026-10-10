#!/usr/bin/env python3
"""Run the existing Step 2 chunker into a new directory and retain input/output hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STEP2 = ROOT / "02_PDF清洗与分块" / "step2_evidence_chunker.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Versioned Step 1 JSON")
    parser.add_argument("--source-manifest", type=Path, required=True, help="Step 1 run_manifest.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="Must not already exist")
    parser.add_argument("--target-words", type=int, default=180)
    parser.add_argument("--max-words", type=int, default=240)
    parser.add_argument("--step2-script", type=Path, default=DEFAULT_STEP2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    source_manifest_path = args.source_manifest.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    step2_script = args.step2_script.expanduser().resolve()
    if not input_path.is_file() or not source_manifest_path.is_file() or not step2_script.is_file():
        raise SystemExit("Input JSON, Step 1 source manifest, and Step 2 script must all exist")
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")
    if args.target_words < 1 or args.max_words < args.target_words:
        raise SystemExit("Require 1 <= target-words <= max-words")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("status") != "completed" or not source_manifest.get("input_files"):
        raise SystemExit("Source manifest must be a completed Step 1 versioned run with input_files hashes")
    expected_step1_output = source_manifest.get("outputs", {}).get(input_path.name, {}).get("sha256")
    if not expected_step1_output or sha256_file(input_path) != expected_step1_output:
        raise SystemExit("Step 1 JSON SHA-256 does not match its completed source manifest")
    documents = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(documents, list) or not documents:
        raise SystemExit("Step 1 input must be a non-empty JSON array")
    file_names = {str(x.get("file_name", "")) for x in source_manifest["input_files"]}
    missing = [str(doc.get("file_name", "")) for doc in documents if str(doc.get("file_name", "")) not in file_names]
    if missing:
        raise SystemExit(f"Step 1 documents do not match source manifest file_names: {missing}")
    if len({doc.get("doc_id") for doc in documents}) != len(documents):
        raise SystemExit("Step 1 input has duplicate doc_id values")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=False, exist_ok=False)
    run_manifest_path = output_dir / "step2_run_manifest.json"
    run_manifest = {
        "manifest_version": "step2_versioned_local_v1",
        "status": "started",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_json": {"path": str(input_path), "sha256": sha256_file(input_path)},
        "source_manifest": {"path": str(source_manifest_path), "sha256": sha256_file(source_manifest_path)},
        "source_pdf_hashes": source_manifest["input_files"],
        "step2_script": str(step2_script),
        "step2_script_sha256": sha256_file(step2_script),
        "wrapper_script_sha256": sha256_file(Path(__file__).resolve()),
        "configuration": {"target_words": args.target_words, "max_words": args.max_words},
        "output_dir": str(output_dir),
    }
    atomic_write_json(run_manifest_path, run_manifest)
    command = [
        sys.executable, str(step2_script),
        "--input", str(input_path),
        "--source-manifest", str(source_manifest_path),
        "--output-dir", str(output_dir),
        "--target-words", str(args.target_words),
        "--max-words", str(args.max_words),
    ]
    try:
        subprocess.run(command, check=True)
        expected = ("evidence_blocks.jsonl", "chunk_qa.md", "chunking_manifest.json")
        missing_outputs = [name for name in expected if not (output_dir / name).is_file()]
        if missing_outputs:
            raise RuntimeError(f"Step 2 completed without expected output(s): {missing_outputs}")
        run_manifest.update({
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "outputs": {
                name: {"size_bytes": (output_dir / name).stat().st_size, "sha256": sha256_file(output_dir / name)}
                for name in expected
            },
        })
        atomic_write_json(run_manifest_path, run_manifest)
    except Exception as exc:
        run_manifest.update({
            "status": "failed",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        atomic_write_json(run_manifest_path, run_manifest)
        raise
    print(f"Versioned Step 2 evidence blocks saved (no overwrite): {output_dir}")
    print(f"Evidence blocks: {output_dir / 'evidence_blocks.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
