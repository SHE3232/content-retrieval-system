from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REQUIRED_FILES = ("a.txt", "b.pdf", "c.docx", "d.jpg", "e.png")
EXPECTED_TOP_HITS = {
    "keyword": "local-guide.docx",
    "text_semantic": "private-search.pdf",
    "image_semantic": "blue-logo.jpg",
    "hybrid": "private-search.pdf",
    "filtered_image": "blue-logo.jpg",
}


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


def _search_payload(
    *,
    modality: str = "image",
    match_reasons: list[str] | None = None,
    channels: list[str] | None = None,
    name: str | None = None,
) -> dict[str, object]:
    reasons = match_reasons or ["image_semantic"]
    active_channels = channels or reasons
    if name is None:
        if active_channels == ["keyword"]:
            name = EXPECTED_TOP_HITS["keyword"]
        elif active_channels == ["text_semantic"]:
            name = EXPECTED_TOP_HITS["text_semantic"]
        elif active_channels == ["image_semantic"]:
            name = EXPECTED_TOP_HITS["image_semantic"]
        else:
            name = EXPECTED_TOP_HITS["hybrid"]
    return {
        "query": "fixture",
        "hits": [
            {
                "name": name,
                "modality": modality,
                "match_reasons": reasons,
            }
        ],
        "total_candidates": 1,
        "elapsed_ms": 1.0,
        "weights": {channel: 1.0 for channel in active_channels},
    }


def test_run_smoke_exercises_exact_five_format_http_protocol(
    tmp_path: Path,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    requests: list[tuple[str, str, object | None]] = []
    poll_count = 0
    stats_count = 0
    restart_result = _index_result()
    restart_result.update(
        indexed_files=0,
        indexed_records=0,
        unchanged_files=5,
    )

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
                payload["result"] = restart_result
            return httpx.Response(200, json=payload)
        if request.method == "POST" and request.url.path == "/v1/search":
            assert isinstance(body, dict)
            filters = body.get("filters")
            modality = (
                "image"
                if filters or body["channels"] == ["image_semantic"]
                else "text"
            )
            channels = body["channels"]
            return httpx.Response(
                200,
                json=_search_payload(
                    modality=modality,
                    match_reasons=[channels[0]],
                    channels=channels,
                ),
            )
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
    assert result["schema_version"] == "2"
    assert result["status"] == "passed"
    assert result["formats"] == ["DOCX", "JPG", "PDF", "PNG", "TXT"]
    assert result["expected_input_file_count"] == 5
    assert result["pre_index_record_count"] == 7
    assert result["stats"] == _stats(12)
    assert [item["name"] for item in result["searches"]] == [
        "keyword",
        "text_semantic",
        "image_semantic",
        "hybrid",
        "filtered_image",
    ]
    assert [item["name"] for item in result["pre_index_searches"]] == [
        "keyword",
        "text_semantic",
        "image_semantic",
        "hybrid",
        "filtered_image",
    ]
    for search in result["pre_index_searches"] + result["searches"]:
        assert search["top_hit"] == EXPECTED_TOP_HITS[search["name"]]
        assert search["expected_top_hit"] == EXPECTED_TOP_HITS[search["name"]]
    assert result["persistent_restart"] == {
        "required": True,
        "passed": True,
        "pre_index_search_count": 5,
    }


def test_persistence_search_failure_happens_before_reindex(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    requests: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(7))
        if request.url.path == "/v1/search":
            body = json.loads(request.content)
            channels = body["channels"]
            return httpx.Response(
                200,
                json=_search_payload(
                    modality="text",
                    match_reasons=[channels[0]],
                    channels=channels,
                    name="wrong-document.txt",
                ),
            )
        raise AssertionError("reindex must not start after a pre-index search failure")

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match="pre-index keyword search top hit.*local-guide\\.docx",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                require_existing_index=True,
            )

    assert requests == [
        ("GET", "/v1/index/stats"),
        ("POST", "/v1/search"),
    ]


@pytest.mark.parametrize("wrong_check", list(EXPECTED_TOP_HITS))
def test_run_smoke_rejects_wrong_top_hit_for_each_controlled_search(
    tmp_path: Path,
    wrong_check: str,
) -> None:
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
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": _index_result(),
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        check_name = (
            "filtered_image"
            if body.get("filters")
            else "hybrid"
            if len(channels) > 1
            else channels[0]
        )
        return httpx.Response(
            200,
            json=_search_payload(
                modality=(
                    "image"
                    if body.get("filters") or channels == ["image_semantic"]
                    else "text"
                ),
                match_reasons=[channels[0]],
                channels=channels,
                name=(
                    "wrong-document.txt"
                    if check_name == wrong_check
                    else EXPECTED_TOP_HITS[check_name]
                ),
            ),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match=rf"{wrong_check} search top hit.*{EXPECTED_TOP_HITS[wrong_check]}",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_persistence_check_requires_idempotent_reindex(tmp_path: Path) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(7))
        if request.url.path == "/v1/indexing/jobs":
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
        if request.url.path == "/v1/indexing/jobs/job-1":
            return httpx.Response(
                200,
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": _index_result(),
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        return httpx.Response(
            200,
            json=_search_payload(
                modality=(
                    "image"
                    if body.get("filters") or channels == ["image_semantic"]
                    else "text"
                ),
                match_reasons=[channels[0]],
                channels=channels,
            ),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match="restart indexing was not idempotent.*indexed_files=0.*unchanged_files=5",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                require_existing_index=True,
                poll_interval_seconds=0,
            )


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
    poll_requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal poll_requests
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(0))
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "job-slow", "status": "queued"})
        poll_requests += 1
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

    assert poll_requests == 0


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("timeout_seconds", math.nan),
        ("timeout_seconds", math.inf),
        ("poll_interval_seconds", math.nan),
        ("poll_interval_seconds", math.inf),
    ],
)
def test_run_smoke_rejects_non_finite_timing_values_before_http(
    tmp_path: Path,
    field: str,
    invalid_value: float,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)

    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    timing = {"timeout_seconds": 1.0, "poll_interval_seconds": 0.0}
    timing[field] = invalid_value
    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(unexpected),
    ) as client:
        with pytest.raises(
            ValueError,
            match=f"{field} must be finite and non-negative",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                **timing,
            )


def test_run_smoke_caps_poll_sleep_and_request_at_remaining_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import smoke_mvp

    _write_inputs(tmp_path)
    poll_requests: list[dict[str, float]] = []
    sleeps: list[float] = []
    now = 0.0

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/index/stats":
            return httpx.Response(200, json=_stats(0))
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "job-slow", "status": "queued"})
        poll_requests.append(request.extensions["timeout"])
        return httpx.Response(200, json={"job_id": "job-slow", "status": "running"})

    monkeypatch.setattr(smoke_mvp.time, "monotonic", monotonic)
    monkeypatch.setattr(smoke_mvp.time, "sleep", sleep)
    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(TimeoutError, match="job-slow did not finish"):
            smoke_mvp.run_smoke(
                client,
                input_root=tmp_path,
                queries=smoke_mvp.SmokeQueries("exact", "semantic", "image"),
                timeout_seconds=2,
                poll_interval_seconds=5,
            )

    assert sleeps == [2]
    assert len(poll_requests) == 1
    assert set(poll_requests[0].values()) == {2}


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


@pytest.mark.parametrize(
    ("target_channels", "wrong_reason"),
    [
        (["keyword"], "image_semantic"),
        (["text_semantic"], "keyword"),
    ],
)
def test_run_smoke_rejects_out_of_channel_match_reasons(
    tmp_path: Path,
    target_channels: list[str],
    wrong_reason: str,
) -> None:
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
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": _index_result(),
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        reasons = [wrong_reason] if channels == target_channels else [channels[0]]
        return httpx.Response(
            200,
            json=_search_payload(
                match_reasons=reasons,
                channels=channels,
                modality="image" if body.get("filters") else "text",
            ),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(RuntimeError, match="outside requested channels"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_run_smoke_rejects_weights_outside_requested_channels(
    tmp_path: Path,
) -> None:
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
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": _index_result(),
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        payload = _search_payload(match_reasons=[channels[0]], channels=channels)
        payload["weights"] = {
            "keyword": 0.35,
            "text_semantic": 1.0,
            "image_semantic": 0.85,
        }
        return httpx.Response(200, json=payload)

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match="weights do not match requested channels",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_run_smoke_rejects_partially_processed_duplicate_inputs(
    tmp_path: Path,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    partial_result = _index_result()
    partial_result.update(
        parsed_files=1,
        indexed_files=1,
        indexed_records=1,
        skipped_files=4,
    )
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
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": partial_result,
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        return httpx.Response(
            200,
            json=_search_payload(match_reasons=[channels[0]], channels=channels),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(RuntimeError, match="skipped files"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


def test_run_smoke_rejects_records_without_newly_indexed_files(
    tmp_path: Path,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    result = _index_result()
    result.update(indexed_files=0, indexed_records=12, unchanged_files=5)
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
                json={"job_id": "job-1", "status": "completed", "result": result},
            )
        body = json.loads(request.content)
        channels = body["channels"]
        return httpx.Response(
            200,
            json=_search_payload(match_reasons=[channels[0]], channels=channels),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            RuntimeError,
            match="indexed_records do not match indexed_files",
        ):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
            )


@pytest.mark.parametrize(
    "field",
    [
        "parsed_files",
        "indexed_files",
        "indexed_records",
        "skipped_files",
        "failed_files",
        "partial_files",
        "unchanged_files",
        "removed_stale_records",
    ],
)
@pytest.mark.parametrize("invalid_value", [True, -1])
def test_run_smoke_rejects_invalid_indexing_counters(
    tmp_path: Path,
    field: str,
    invalid_value: object,
) -> None:
    from tools.smoke_mvp import SmokeQueries, run_smoke

    _write_inputs(tmp_path)
    result = _index_result()
    result[field] = invalid_value
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
                json={"job_id": "job-1", "status": "completed", "result": result},
            )
        body = json.loads(request.content)
        channels = body["channels"]
        return httpx.Response(
            200,
            json=_search_payload(match_reasons=[channels[0]], channels=channels),
        )

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(RuntimeError, match=f"invalid {field}"):
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                poll_interval_seconds=0,
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
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": _index_result(),
                },
            )
        body = json.loads(request.content)
        channels = body["channels"]
        payload = _search_payload(
            modality=(
                "image"
                if body.get("filters") or channels == ["image_semantic"]
                else "text"
            ),
            match_reasons=[channels[0]],
            channels=channels,
        )
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
