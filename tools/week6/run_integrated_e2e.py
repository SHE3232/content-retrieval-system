#!/usr/bin/env python3
"""Run the Week 6 real-model, persistent-backend and Flutter UI E2E gate."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.week6.run_stress import write_json_atomic


BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src"
REQUIRED_UI_OPERATIONS = frozenset(
    {
        "add_directory",
        "poll_indexing",
        "keyword_search",
        "text_semantic_search",
        "image_semantic_search",
        "hybrid_search",
        "filter_results",
        "copy_path",
        "open_file",
        "delete_index",
        "reindex",
        "disconnect_recovery",
    }
)
REQUIRED_SECTIONS = frozenset(
    {
        "five_format_index",
        "search_channels",
        "filters",
        "mutations",
        "persistence",
        "disconnect_recovery",
        "flutter_ui",
    }
)
TERMINAL_JOB_STATUSES = {"completed", "completed_with_errors", "failed"}


def assert_ui_evidence(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read Flutter UI evidence: {path}") from error
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise ValueError("Flutter UI evidence is not PASS")
    if value.get("real_backend") is not True:
        raise ValueError("Flutter UI evidence must use a real backend")
    operations = value.get("operations")
    if not isinstance(operations, dict):
        raise ValueError("Flutter UI evidence operations must be an object")
    for operation in sorted(REQUIRED_UI_OPERATIONS):
        if operations.get(operation) is not True:
            raise ValueError(f"Flutter UI operation is not PASS: {operation}")
    return value


def workflow_status(sections: dict[str, str]) -> str:
    return (
        "PASS"
        if set(sections) >= REQUIRED_SECTIONS
        and all(sections[name] == "PASS" for name in REQUIRED_SECTIONS)
        else "FAIL"
    )


def catalog_items_under_root(items: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    normalized_root = os.path.normcase(str(root.resolve()))
    selected: list[dict[str, Any]] = []
    for item in items:
        value = item.get("path")
        if not isinstance(value, str):
            continue
        normalized_path = os.path.normcase(str(Path(value).resolve()))
        try:
            if os.path.commonpath([normalized_path, normalized_root]) == normalized_root:
                selected.append(item)
        except ValueError:
            continue
    return selected


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request_json(base_url: str, method: str, path: str, payload: Any = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/")),
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with _opener().open(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {error.code}: {detail}") from error


def _wait_ready(base_url: str, process: subprocess.Popen[bytes], timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"backend exited before readiness with code {process.returncode}")
        try:
            value = request_json(base_url, "GET", "/health/ready")
            if value.get("status") == "ready":
                return
        except (OSError, RuntimeError, ValueError):
            pass
        time.sleep(0.5)
    raise TimeoutError("backend did not become ready")


def _wait_tika(port: int, process: subprocess.Popen[bytes], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/version"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Tika exited before readiness with code {process.returncode}")
        try:
            with _opener().open(url, timeout=2) as response:
                if response.status == 200 and b"Apache Tika" in response.read():
                    return
        except OSError:
            pass
        time.sleep(0.25)
    raise TimeoutError("Tika did not become ready")


def _wait_job(base_url: str, job_id: str, timeout: float = 900) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = request_json(base_url, "GET", f"/v1/indexing/jobs/{job_id}")
        if value["status"] in TERMINAL_JOB_STATUSES:
            return value
        time.sleep(1)
    raise TimeoutError(f"indexing job did not finish: {job_id}")


def _start_backend(args: argparse.Namespace, log_stream: Any) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment.update(
        {
            "CONTENT_RETRIEVAL_MODEL_ROOT": str(args.model_root.resolve()),
            "CONTENT_RETRIEVAL_MANIFEST_PATH": str(args.manifest.resolve()),
            "CONTENT_RETRIEVAL_DATA_DIR": str(args.data_dir.resolve()),
            "CONTENT_RETRIEVAL_TIKA_URL": f"http://127.0.0.1:{args.tika_port}",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONPATH": str(BACKEND_SOURCE),
        }
    )
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(
        [
            str(args.python),
            "-m",
            "uvicorn",
            "content_retrieval.mvp:create_mvp_app",
            "--factory",
            "--app-dir",
            str(BACKEND_SOURCE),
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )


def _stop_process(process: subprocess.Popen[bytes], *, graceful: bool = True) -> None:
    if process.poll() is not None:
        return
    try:
        if graceful and os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        elif graceful:
            process.send_signal(signal.SIGINT)
        else:
            process.terminate()
        process.wait(timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=15)


def _search(base_url: str, query: str, channels: list[str], filters: dict[str, Any] | None = None):
    return request_json(
        base_url,
        "POST",
        "/v1/search",
        {
            "query": query,
            "top_k": 10,
            "channels": channels,
            "filters": filters or {},
        },
    )


def _assert_hit(response: dict[str, Any], expected_name: str, *, first: bool = False) -> None:
    names = [hit["name"] for hit in response.get("hits", [])]
    if expected_name not in names or (first and names[0] != expected_name):
        raise AssertionError(f"expected {expected_name} in search results, got {names}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    from tools.week5.run_real_five_format_e2e import create_fixtures

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    api_log = output / "backend.log"
    tika_log = output / "tika.log"
    session_id = uuid.uuid4().hex
    fixture_root = Path(tempfile.gettempdir()) / f"contentretrieval-week6-{session_id}"
    ui_fixture_root = Path(tempfile.gettempdir()) / f"contentretrieval-week6-ui-{session_id}"
    fixture_root.mkdir(parents=True)
    ui_fixture_root.mkdir(parents=True)
    tokens = create_fixtures(fixture_root)
    create_fixtures(ui_fixture_root)
    fixture_names = sorted(path.name for path in fixture_root.iterdir())
    ui_evidence_path = output / "flutter-ui.json"
    flutter_log = output / "flutter-ui.log"
    sections = {name: "FAIL" for name in REQUIRED_SECTIONS}
    report: dict[str, Any] = {
        "status": "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "fixtures": fixture_names,
        "searches": {},
        "mutations": {},
        "persistence": {},
        "flutter_ui": {},
    }
    backend: subprocess.Popen[bytes] | None = None
    source_keys: list[str] = []
    base_url = f"http://127.0.0.1:{args.port}"
    with ExitStack() as stack:
        api_stream = stack.enter_context(api_log.open("ab"))
        tika_stream = stack.enter_context(tika_log.open("ab"))
        tika = subprocess.Popen(
            [str(args.java), "-jar", str(args.tika_jar.resolve()), "-p", str(args.tika_port)],
            cwd=REPOSITORY_ROOT,
            stdout=tika_stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            _wait_tika(args.tika_port, tika)
            backend = _start_backend(args, api_stream)
            _wait_ready(base_url, backend)

            flutter_result = subprocess.run(
                [
                    str(args.flutter),
                    "test",
                    "integration_test/week6_real_backend_ui_test.dart",
                    "-d",
                    "windows",
                    f"--dart-define=WEEK6_BASE_URL={base_url}",
                    f"--dart-define=WEEK6_FIXTURE_ROOT={ui_fixture_root}",
                    f"--dart-define=WEEK6_OUTPUT={ui_evidence_path}",
                ],
                cwd=REPOSITORY_ROOT / "frontend",
                capture_output=True,
                check=False,
                timeout=1200,
            )
            flutter_log.write_bytes(flutter_result.stdout + b"\n" + flutter_result.stderr)
            if flutter_result.returncode != 0:
                raise RuntimeError(f"Flutter real-backend UI test failed with code {flutter_result.returncode}")
            ui = assert_ui_evidence(ui_evidence_path)
            report["flutter_ui"] = ui
            sections["flutter_ui"] = "PASS"

            created = request_json(
                base_url,
                "POST",
                "/v1/indexing/jobs",
                {"paths": [str(fixture_root)], "authorized_roots": [str(fixture_root)], "recursive": True},
            )
            indexed = _wait_job(base_url, created["job_id"])
            result = indexed.get("result") or {}
            if indexed["status"] != "completed" or result.get("indexed_files") != 5:
                raise AssertionError(f"five-format index failed: {indexed}")
            sections["five_format_index"] = "PASS"

            catalog = request_json(base_url, "GET", "/v1/index/files?page=1&page_size=100")
            ours = catalog_items_under_root(catalog["items"], fixture_root)
            if len(ours) != 5:
                raise AssertionError(f"catalog contains {len(ours)} of five fixtures")
            source_keys = [item["source_key"] for item in ours]
            count_before_restart = int(catalog["total"])

            for name, token in tokens.items():
                response = _search(base_url, token, ["keyword"])
                _assert_hit(response, name)
                report["searches"][f"keyword:{name}"] = "PASS"
            semantic = _search(base_url, "controlled local fixture notes", ["text_semantic"])
            if not semantic["hits"]:
                raise AssertionError("text semantic search returned no hits")
            report["searches"]["text_semantic"] = "PASS"
            for name, query in (
                ("week5-red-apple.jpg", "a simple red apple on a white background"),
                ("week5-blue-square.png", "a simple blue square on a white background"),
            ):
                response = _search(base_url, query, ["image_semantic"])
                _assert_hit(response, name, first=True)
                report["searches"][f"image_semantic:{name}"] = "PASS"
            hybrid = _search(base_url, next(iter(tokens.values())), ["keyword", "text_semantic"])
            if not hybrid["hits"]:
                raise AssertionError("hybrid search returned no hits")
            sections["search_channels"] = "PASS"

            filtered = _search(
                base_url,
                "controlled local fixture",
                ["keyword", "text_semantic"],
                {"mime_types": ["text/plain"], "modalities": ["text"]},
            )
            if not filtered["hits"] or any(hit["mime_type"] != "text/plain" for hit in filtered["hits"]):
                raise AssertionError("MIME filter returned an invalid result")
            sections["filters"] = "PASS"

            target = next(item for item in ours if item["name"] == "week5-notes.txt")
            reindex = request_json(base_url, "POST", f"/v1/index/files/{target['source_key']}/reindex", {})
            reindexed = _wait_job(base_url, reindex["job_id"])
            if reindexed["status"] != "completed":
                raise AssertionError(f"reindex failed: {reindexed}")
            report["mutations"]["reindex"] = "PASS"

            _stop_process(backend)
            backend = None
            disconnected = False
            try:
                request_json(base_url, "GET", "/health/ready")
            except OSError:
                disconnected = True
            if not disconnected:
                raise AssertionError("backend disconnect was not observable")
            backend = _start_backend(args, api_stream)
            _wait_ready(base_url, backend)
            sections["disconnect_recovery"] = "PASS"

            after_restart = request_json(base_url, "GET", "/v1/index/files?page=1&page_size=100")
            if int(after_restart["total"]) != count_before_restart:
                raise AssertionError("catalog count changed across restart")
            unchanged_job = request_json(
                base_url,
                "POST",
                "/v1/indexing/jobs",
                {"paths": [str(fixture_root)], "authorized_roots": [str(fixture_root)], "recursive": True},
            )
            unchanged = _wait_job(base_url, unchanged_job["job_id"])
            unchanged_result = unchanged.get("result") or {}
            if unchanged_result.get("indexed_files") != 0 or unchanged_result.get("unchanged_files") != 5:
                raise AssertionError(f"unchanged rescan was not incremental: {unchanged}")
            report["persistence"] = {
                "count_before_restart": count_before_restart,
                "count_after_restart": int(after_restart["total"]),
                "unchanged_files": unchanged_result.get("unchanged_files"),
            }
            sections["persistence"] = "PASS"

            deleted = request_json(base_url, "DELETE", f"/v1/index/files/{target['source_key']}")
            if deleted.get("deleted_records", 0) < 1:
                raise AssertionError("delete removed no records")
            source_keys.remove(target["source_key"])
            report["mutations"]["delete"] = "PASS"
            sections["mutations"] = "PASS"
            report["status"] = workflow_status(sections)
        finally:
            if backend is not None:
                for source_key in source_keys:
                    try:
                        request_json(base_url, "DELETE", f"/v1/index/files/{source_key}")
                    except Exception as error:
                        report.setdefault("cleanup_errors", []).append(str(error))
                _stop_process(backend)
            _stop_process(tika, graceful=False)
    report["evidence"] = {
        "backend_log": {"path": api_log.name, "sha256": _sha256(api_log)},
        "tika_log": {"path": tika_log.name, "sha256": _sha256(tika_log)},
        "flutter_log": {"path": flutter_log.name, "sha256": _sha256(flutter_log)},
        "ui_evidence": {"path": ui_evidence_path.name, "sha256": _sha256(ui_evidence_path)},
    }
    return report


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flutter", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--tika-jar", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--tika-port", type=int, default=0)
    args = parser.parse_args()
    if args.port == 0:
        args.port = _available_port()
    if args.tika_port == 0:
        args.tika_port = _available_port()
    return args


def main() -> int:
    args = parse_args()
    summary_path = args.output / "summary.json"
    try:
        result = run(args)
    except BaseException as error:
        result = {
            "status": "FAIL",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(error).__name__}: {error}",
        }
        write_json_atomic(summary_path, result)
        raise
    write_json_atomic(summary_path, result)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
