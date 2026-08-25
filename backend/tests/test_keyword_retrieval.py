from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord, SearchFilters
from content_retrieval.retrieval.keyword import KeywordIndex, tokenize


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_record(
    tmp_path: Path,
    *,
    key: str,
    name: str,
    document: str,
    relative_directory: str = "",
    mime_type: str = "text/plain",
    modality: str = "text",
    modified_at: datetime = NOW,
    sequence_number: int = 0,
    file_id: str | None = None,
) -> IndexRecord:
    source_id = digest(f"source:{key}")
    resolved_file_id = file_id or digest(f"file:{key}")
    path = (tmp_path / relative_directory / name).resolve()
    vector = EmbeddingVector(
        source_id=source_id,
        file_id=resolved_file_id,
        model_id="keyword-fixture-model",
        space_id="keyword-fixture-space",
        modality=modality,
        values=[1.0, 0.0],
        dimensions=2,
        normalized=True,
    )
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=resolved_file_id,
        source_key=digest(f"path:{path}"),
        path=path,
        name=name,
        mime_type=mime_type,
        modality=modality,
        document=document,
        vector=vector,
        modified_at=modified_at,
        size_bytes=10,
        paragraph_number=1 if modality == "text" else None,
        sequence_number=sequence_number,
    )


def test_tokenize_casefolds_latin_and_preserves_cjk_search_terms() -> None:
    assert tokenize("  LOCAL_Search 本地检索 2.0 ") == [
        "local",
        "search",
        "本",
        "地",
        "检",
        "索",
        "本地",
        "地检",
        "检索",
        "2",
        "0",
    ]


def test_keyword_searches_name_path_and_document_with_field_weighting(
    tmp_path: Path,
) -> None:
    filename_match = make_record(
        tmp_path,
        key="a",
        name="project-plan.txt",
        document="unrelated material",
    )
    path_match = make_record(
        tmp_path,
        key="b",
        name="notes.txt",
        document="unrelated material",
        relative_directory="project-plan",
    )
    body_match = make_record(
        tmp_path,
        key="c",
        name="notes.txt",
        document="the project plan is stored locally",
        relative_directory="other",
    )
    index = KeywordIndex([body_match, path_match, filename_match])

    candidates = index.search("project plan", limit=10)

    assert [candidate.record for candidate in candidates] == [
        filename_match,
        path_match,
        body_match,
    ]
    assert all(candidate.score > 0 for candidate in candidates)


def test_keyword_search_handles_chinese_terms(tmp_path: Path) -> None:
    relevant = make_record(
        tmp_path,
        key="a",
        name="笔记.txt",
        document="这是一个离线本地检索系统",
    )
    unrelated = make_record(
        tmp_path,
        key="b",
        name="其他.txt",
        document="天气预报",
    )

    candidates = KeywordIndex([unrelated, relevant]).search(
        "本地检索",
        limit=5,
    )

    assert [candidate.record for candidate in candidates] == [relevant]


def test_multichar_chinese_query_does_not_match_one_shared_character(
    tmp_path: Path,
) -> None:
    apple = make_record(
        tmp_path,
        key="apple",
        name="红色苹果.jpg",
        document="红色苹果",
        mime_type="image/jpeg",
        modality="image",
    )
    accessibility = make_record(
        tmp_path,
        key="accessibility",
        name="无障碍设计指南.pdf",
        document="提供减少动态效果选项，降低视觉干扰。",
        mime_type="application/pdf",
    )

    candidates = KeywordIndex([accessibility, apple]).search(
        "苹果",
        limit=5,
    )

    assert [candidate.record for candidate in candidates] == [apple]


def test_keyword_filters_before_ranking(tmp_path: Path) -> None:
    included = make_record(
        tmp_path,
        key="a",
        name="included.txt",
        document="offline search",
        relative_directory="allowed",
    )
    wrong_path = make_record(
        tmp_path,
        key="b",
        name="wrong-path.txt",
        document="offline search",
        relative_directory="other",
    )
    wrong_mime = make_record(
        tmp_path,
        key="c",
        name="wrong.pdf",
        document="offline search",
        relative_directory="allowed",
        mime_type="application/pdf",
    )
    too_old = make_record(
        tmp_path,
        key="d",
        name="old.txt",
        document="offline search",
        relative_directory="allowed",
        modified_at=NOW - timedelta(days=30),
    )
    index = KeywordIndex([wrong_path, wrong_mime, too_old, included])

    candidates = index.search(
        "offline search",
        limit=10,
        filters=SearchFilters(
            mime_types=("text/plain",),
            modalities=("text",),
            path_prefix=(tmp_path / "allowed").resolve(),
            modified_after=NOW - timedelta(days=1),
        ),
    )

    assert [candidate.record for candidate in candidates] == [included]


def test_keyword_ties_are_deterministic_and_rebuild_replaces_corpus(
    tmp_path: Path,
) -> None:
    later_path = make_record(
        tmp_path,
        key="a",
        name="b.txt",
        document="same token",
    )
    earlier_path = make_record(
        tmp_path,
        key="b",
        name="a.txt",
        document="same token",
    )
    replacement = make_record(
        tmp_path,
        key="c",
        name="replacement.txt",
        document="new corpus",
    )
    index = KeywordIndex([later_path, earlier_path])

    assert [
        candidate.record
        for candidate in index.search("same token", limit=10)
    ] == [earlier_path, later_path]

    index.rebuild([replacement])

    assert index.search("same token", limit=10) == []
    assert [
        candidate.record
        for candidate in index.search("new corpus", limit=10)
    ] == [replacement]


def test_keyword_search_validates_limit(tmp_path: Path) -> None:
    index = KeywordIndex([])

    with pytest.raises(ValueError, match="limit"):
        index.search("query", limit=0)
