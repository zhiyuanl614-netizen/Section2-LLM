#!/usr/bin/env python3
"""Run the existing Step 1 slicer into a new, hash-manifested batch directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STEP1 = ROOT / "02_PDF清洗与分块" / "step1_pdf_targeted_slicer.py"


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
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Must be a new directory")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--files", nargs="+", required=True, help="PDF filenames in stable processing order")
    parser.add_argument("--step1-script", type=Path, default=DEFAULT_STEP1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    step1_script = args.step1_script.expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.batch_id):
        raise SystemExit("batch-id must start with an alphanumeric and contain only letters, digits, dot, underscore, or hyphen")
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {input_dir}")
    if not step1_script.is_file():
        raise SystemExit(f"Step 1 script does not exist: {step1_script}")
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")
    if not args.files or len(set(args.files)) != len(args.files):
        raise SystemExit("Provide a non-empty list of unique PDF filenames")
    sources = []
    for name in args.files:
        if Path(name).name != name or not name.lower().endswith(".pdf"):
            raise SystemExit(f"Expected a PDF filename (not a path): {name!r}")
        path = input_dir / name
        if not path.is_file():
            raise SystemExit(f"Source PDF not found: {path}")
        sources.append(path)

    before = [{
        "file_name": path.name,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    } for path in sources]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=False, exist_ok=False)
    manifest_path = output_dir / "run_manifest.json"
    manifest = {
        "manifest_version": "step1_versioned_local_v1",
        "status": "started",
        "batch_id": args.batch_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "input_files": before,
        "output_dir": str(output_dir),
        "step1_script": str(step1_script),
        "step1_script_sha256": sha256_file(step1_script),
        "wrapper_script_sha256": sha256_file(Path(__file__).resolve()),
        "files_order": [p.name for p in sources],
    }
    atomic_write_json(manifest_path, manifest)
    command = [
        sys.executable, str(step1_script),
        "--input-dir", str(input_dir),
        "--out-dir", str(output_dir),
        "--batch-id", args.batch_id,
        "--files", *[p.name for p in sources],
    ]
    try:
        subprocess.run(command, check=True)
        after = [{**item, "sha256_after": sha256_file(Path(item["path"]))} for item in before]
        changed = [x["file_name"] for x in after if x["sha256"] != x["sha256_after"]]
        expected_output = output_dir / "step1_sliced_pdf_corpus.json"
        if not expected_output.is_file():
            raise RuntimeError(f"Step 1 completed without expected output: {expected_output}")
        manifest.update({
            "status": "completed" if not changed else "failed_source_changed_during_processing",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_files_after": after,
            "source_files_changed_during_processing": changed,
            "outputs": {
                name: {"size_bytes": (output_dir / name).stat().st_size, "sha256": sha256_file(output_dir / name)}
                for name in ("step1_sliced_pdf_corpus.json", "step1_sliced_zones_preview.md", "Step1_PDF章节树解析与四区靶向切片实验报告.xlsx")
                if (output_dir / name).is_file()
            },
        })
        atomic_write_json(manifest_path, manifest)
        if changed:
            raise RuntimeError(f"Source PDFs changed while Step 1 was running: {changed}")
    except Exception as exc:
        manifest.update({
            "status": "failed",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        atomic_write_json(manifest_path, manifest)
        raise
    print(f"Versioned Step 1 batch saved (no overwrite): {output_dir}")
    print(f"Source SHA-256 manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
