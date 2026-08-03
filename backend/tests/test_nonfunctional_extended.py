from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from content_retrieval.domain.errors import TikaUnavailableError
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.parsers.tika import TikaClient
from content_retrieval.parsers.txt import TxtParser
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.ingestion_jobs import InMemoryIngestionJobStore


def make_text_service(*, max_size: int = 4096) -> BatchIngestionService:
    return BatchIngestionService(
        ParserRegistry([TxtParser()]),
        max_file_size_bytes=max_size,
    )


def test_tc_193_processes_one_thousand_files_in_one_batch(tmp_path: Path) -> None:
    for index in range(1000):
        (tmp_path / f"{index:04d}.txt").write_text(
            f"content-{index}", encoding="utf-8"
        )

    batch = make_text_service().parse_paths([tmp_path], authorized_roots=[tmp_path])

    assert batch.total == 1000
    assert batch.succeeded == 1000
    assert batch.failed == batch.skipped == 0


def test_tc_194_accepts_file_at_large_configured_boundary(tmp_path: Path) -> None:
    source = tmp_path / "boundary.txt"
    source.write_bytes(b"x" * (1024 * 1024))

    batch = make_text_service(max_size=1024 * 1024).parse_paths(
        [source], authorized_roots=[tmp_path]
    )

    assert batch.succeeded == 1
    assert batch.results[0].size_bytes == 1024 * 1024


def test_tc_195_parallel_job_transitions_remain_isolated() -> None:
    store = InMemoryIngestionJobStore()
    jobs = [store.create() for _ in range(100)]

    def transition(index: int) -> None:
        job = jobs[index]
        store.mark_running(job.job_id)
        if index % 2:
            store.fail(job.job_id)

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(transition, range(len(jobs))))

    statuses = [store.get(job.job_id).status for job in jobs]  # type: ignore[union-attr]
    assert statuses.count("running") == 50
    assert statuses.count("failed") == 50


def test_tc_196_tika_client_recovers_after_transient_connection_failure(
    tmp_path: Path,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json=[{"X-TIKA:content": "recovered"}])

    client = TikaClient(transport=httpx.MockTransport(handler))
    path = tmp_path / "document.docx"

    try:
        client.extract(path, b"first", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except TikaUnavailableError:
        pass
    else:
        raise AssertionError("first request should expose transient unavailability")

    metadata = client.extract(
        path,
        b"second",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert attempts == 2
    assert metadata["X-TIKA:content"] == "recovered"


def test_tc_197_unicode_paths_and_content_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "研发记录_检索测试.txt"
    source.write_text("中文、emoji 🚀、accent café", encoding="utf-8")

    batch = make_text_service().parse_paths([source], authorized_roots=[tmp_path])

    assert batch.results[0].name == source.name
    assert batch.results[0].text == "中文、emoji 🚀、accent café"


def test_tc_198_long_supported_filename_is_processed(tmp_path: Path) -> None:
    source = tmp_path / (("long-name-" * 12) + ".txt")
    source.write_text("long path", encoding="utf-8")

    batch = make_text_service().parse_paths([source], authorized_roots=[tmp_path])

    assert batch.succeeded == 1
    assert batch.results[0].name == source.name


def test_tc_199_tika_default_endpoint_is_loopback_only() -> None:
    client = TikaClient()

    parsed = httpx.URL(client.base_url)
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 9998


def test_tc_200_supported_extension_set_is_case_normalized() -> None:
    registry = ParserRegistry([TxtParser()])

    assert registry.supported_extensions == frozenset({".txt"})
    assert registry.resolve(Path("REPORT.TXT")).supported_extensions == frozenset(
        {".txt"}
    )
