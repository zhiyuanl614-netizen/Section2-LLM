#!/usr/bin/env python3
"""Small cross-platform launcher: start the local server, wait for readiness, open a browser."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "platform" / "app.py"


def _browser_host(bind_host: str) -> str:
    if bind_host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    if bind_host in {"", "localhost", "127.0.0.1", "::1"}:
        return "127.0.0.1" if bind_host in {"", "localhost"} else bind_host
    return bind_host


def _ready(url: str, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(url + "/api/status", timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read(64 * 1024).decode("utf-8"))
                    return bool(data.get("ok"))
        except (OSError, urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(0.25)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Start the local server without opening a browser")
    args = parser.parse_args()
    if not APP.is_file():
        print(f"Platform app not found: {APP}", file=sys.stderr)
        return 2
    try:
        port = int(os.environ.get("PLATFORM_PORT", "8765"))
    except ValueError:
        print("PLATFORM_PORT must be an integer", file=sys.stderr)
        return 2
    bind_host = os.environ.get("PLATFORM_HOST", "127.0.0.1").strip() or "127.0.0.1"
    browser_host = _browser_host(bind_host)
    url_host = f"[{browser_host}]" if ":" in browser_host else browser_host
    url = f"http://{url_host}:{port}"
    pdf_missing = [name for module, name in (("pymupdf", "PyMuPDF"), ("openpyxl", "openpyxl"), ("docx", "python-docx")) if importlib.util.find_spec(module) is None]
    if pdf_missing:
        print("PDF Step 02 currently needs local dependencies: " + ", ".join(pdf_missing))
        print("Install once with: python -m pip install -r 平台/requirements-local.txt")
        print("The read-only search UI can still start; Step 02 will remain blocked until installed.")
    if bind_host not in {"127.0.0.1", "localhost", "::1"}:
        print("Warning: non-loopback bind disables uploads, model catalog lookup and external API UI for safety.")

    try:
        process = subprocess.Popen([sys.executable, str(APP)], cwd=str(ROOT), env=os.environ.copy())
    except OSError as exc:
        print(f"Could not start platform: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        if not _ready(url):
            code = process.poll()
            if code is None:
                print(f"Platform did not become ready at {url} within 20 seconds.", file=sys.stderr)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                return 2
            return int(code)
        if process.poll() is not None:
            return int(process.returncode or 1)
        print(f"平台已就绪：{url}")
        if not args.no_browser:
            webbrowser.open(url, new=2)
        return int(process.wait())
    except KeyboardInterrupt:
        print("\n正在停止本地平台…")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
