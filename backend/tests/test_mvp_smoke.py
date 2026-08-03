from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REQUIRED_FILES = ("a.txt", "b.pdf", "c.docx", "d.jpg", "e.png")


def _write_inputs(root: Path, *, names: tuple[str, ...] = REQUIRED_FILES) -> None:
    for name in names:
        (root / name).write_bytes(b"fixture")


def _stats(record_count: int) -> dict[str, int]:
    return {
        "record_count": record_count,
        "file_count": 5 if record_count else 0,
        "text_record_count": max(0, record_count - 2),
        "image_record_count": min(2, record_count),
    }


def _index_result(
    *,
    failed_files: int = 0,
    partial_files: int = 0,
) -> dict[str, object]:
    return {
        "parsed_files": 5,
        "indexed_files": 5 - failed_files,
        "indexed_records": 12,
        "skipped_files": 0,
        "failed_files": failed_files,
        "partial_files": partial_files,
        "unchanged_files": 0,
        "removed_stale_records": 0,
        "failures": [],
    }


def _search_payload(*, modality: str = "image") -> dict[str, object]:
    return {
        "query": "fixture",
        "hits": [
            {
                "name": "e.png" if modality == "image" else "a.txt",
                "modality": modality,
                "match_reasons": ["image_semantic"],
            }
        ],
        "total_candidates": 1,
        "elapsed_ms": 1.0,
        "weights": {"image_semantic": 1.0},
    }


def test_run_smoke_exercises_exact_five_format_http_protocol(
    tmp_path: Path,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    requests: list[tuple[str, str, object | None]] = []
    poll_count = 0
    stats_count = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count, stats_count
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path == "/v1/index/stats":
            stats_count += 1
            return httpx.Response(200, json=_stats(7 if stats_count == 1 else 12))
        if request.method == "POST" and request.url.path == "/v1/indexing/jobs":
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
        if request.method == "GET" and request.url.path == "/v1/indexing/jobs/job-1":
            statuses = ("queued", "running", "completed")
            status = statuses[poll_count]
            poll_count += 1
            payload: dict[str, object] = {"job_id": "job-1", "status": status}
            if status == "completed":
                payload["result"] = _index_result()
            return httpx.Response(200, json=payload)
        if request.method == "POST" and request.url.path == "/v1/search":
            assert isinstance(body, dict)
            filters = body.get("filters")
            modality = "image" if filters or body["channels"] == ["image_semantic"] else "text"
            return httpx.Response(200, json=_search_payload(modality=modality))
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        result = run_smoke(
            client,
            input_root=tmp_path,
            queries=SmokeQueries("exact", "semantic", "image"),
            require_existing_index=True,
            poll_interval_seconds=0,
        )

    root = str(tmp_path.resolve())
    assert requests == [
        ("GET", "/v1/index/stats", None),
        (
            "POST",
            "/v1/indexing/jobs",
            {"paths": [root], "authorized_roots": [root], "recursive": True},
        ),
        ("GET", "/v1/indexing/jobs/job-1", None),
        ("GET", "/v1/indexing/jobs/job-1", None),
        ("GET", "/v1/indexing/jobs/job-1", None),
        (
            "POST",
            "/v1/search",
            {"query": "exact", "top_k": 5, "channels": ["keyword"]},
        ),
        (
            "POST",
            "/v1/search",
            {"query": "semantic", "top_k": 5, "channels": ["text_semantic"]},
        ),
        (
            "POST",
            "/v1/search",
            {"query": "image", "top_k": 5, "channels": ["image_semantic"]},
        ),
        (
            "POST",
            "/v1/search",
            {
                "query": "semantic",
                "top_k": 5,
                "channels": ["keyword", "text_semantic", "image_semantic"],
            },
        ),
        (
            "POST",
            "/v1/search",
            {
                "query": "image",
                "top_k": 5,
                "channels": ["image_semantic"],
                "filters": {"modalities": ["image"]},
            },
        ),
        ("GET", "/v1/index/stats", None),
    ]
    assert result["status"] == "passed"
    assert result["formats"] == ["DOCX", "JPG", "PDF", "PNG", "TXT"]
    assert result["pre_index_record_count"] == 7
    assert result["stats"] == _stats(12)
    assert [item["name"] for item in result["searches"]] == [
        "keyword",
        "text_semantic",
        "image_semantic",
        "hybrid",
        "filtered_image",
    ]
    assert result["persistent_restart"] == {"required": True, "passed": True}


def test_persistence_check_requires_records_before_reindex(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json=_stats(0))

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match="no records existed before indexing after restart",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                require_existing_index=True,
            )

    assert requests == ["/v1/index/stats"]


def test_run_smoke_rejects_missing_required_format_before_http(
    tmp_path: Path,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path, names=REQUIRED_FILES[:-1])

    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(unexpected),
    ) as client:
        with pytest.raises(ValueError, match=r"missing formats: \.png"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
            )


def test_run_smoke_times_out_nonterminal_indexing_job(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(0))
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "job-slow", "status": "queued"})
        return httpx.Response(200, json={"job_id": "job-slow", "status": "running"})

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(TimeoutError, match="job-slow did not finish"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                timeout_seconds=0,
                poll_interval_seconds=0,
            )


@pytest.mark.parametrize(
    ("status", "result", "message"),
    [
        ("failed", None, "ended as failed"),
        ("completed_with_errors", _index_result(partial_files=1), "partial files"),
        ("completed", _index_result(failed_files=1), "failed files"),
    ],
)
def test_run_smoke_rejects_unsuccessful_indexing_terminal_state(
    tmp_path: Path,
    status: str,
    result: dict[str, object] | None,
    message: str,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(0))
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "job-bad", "status": "queued"})
        payload: dict[str, Any] = {"job_id": "job-bad", "status": status}
        if result is not None:
            payload["result"] = result
        return httpx.Response(200, json=payload)

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(RuntimeError, match=message):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_run_smoke_rejects_malformed_json(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
    )
    with httpx.Client(base_url="http://testserver", transport=transport) as client:
        with pytest.raises(RuntimeError, match="invalid JSON"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
            )


def test_run_smoke_rejects_any_filtered_non_image_hit(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    stats_count = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal stats_count
        if request.url.path == "/v1/index/stats":
            stats_count += 1
            return httpx.Response(200, json=_stats(0 if stats_count == 1 else 12))
        if request.url.path == "/v1/indexing/jobs":
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
        if request.url.path == "/v1/indexing/jobs/job-1":
            return httpx.Response(
                200,
                json={"job_id": "job-1", "status": "completed", "result": _index_result()},
            )
        body = json.loads(request.content)
        payload = _search_payload()
        if body.get("filters"):
            payload["hits"].append(
                {"name": "a.txt", "modality": "text", "match_reasons": ["keyword"]}
            )
        return httpx.Response(200, json=payload)

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(RuntimeError, match="violated its modality filter"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_main_uses_proxy_free_client_and_atomically_writes_utf8_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import smoke_mvp

    output = tmp_path / "nested" / "evidence.json"
    evidence = {"status": "passed", "query": "离线检索"}
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(smoke_mvp.httpx, "Client", FakeClient)
    monkeypatch.setattr(smoke_mvp, "run_smoke", lambda *args, **kwargs: evidence)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke_mvp.py",
            "--input-root",
            str(tmp_path),
            "--keyword-query",
            "exact",
            "--text-query",
            "semantic",
            "--image-query",
            "image",
            "--output",
            str(output),
        ],
    )

    assert smoke_mvp.main() == 0

    assert captured["trust_env"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == evidence
    assert output.read_bytes().endswith(b"\n")
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


def test_main_failure_does_not_replace_previous_passed_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import smoke_mvp

    output = tmp_path / "evidence.json"
    output.write_text('{"status":"passed","previous":true}\n', encoding="utf-8")

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fail(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("smoke failed")

    monkeypatch.setattr(smoke_mvp.httpx, "Client", FakeClient)
    monkeypatch.setattr(smoke_mvp, "run_smoke", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke_mvp.py",
            "--input-root",
            str(tmp_path),
            "--keyword-query",
            "exact",
            "--text-query",
            "semantic",
            "--image-query",
            "image",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(RuntimeError, match="smoke failed"):
        smoke_mvp.main()

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "status": "passed",
        "previous": True,
    }
