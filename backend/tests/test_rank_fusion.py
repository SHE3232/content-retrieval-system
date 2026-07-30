from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from content_retrieval.domain.models import EmbeddingVector
from content_retrieval.domain.retrieval import IndexRecord, VectorCandidate
from content_retrieval.retrieval.fusion import weighted_rrf
from content_retrieval.retrieval.keyword import KeywordCandidate


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_record(
    tmp_path: Path,
    *,
    key: str,
    file_key: str,
    name: str,
    sequence_number: int = 0,
) -> IndexRecord:
    source_id = digest(f"source:{key}")
    file_id = digest(f"file:{file_key}")
    path = (tmp_path / name).resolve()
    return IndexRecord(
        record_id=source_id,
        source_id=source_id,
        file_id=file_id,
        source_key=digest(f"path:{name}"),
        path=path,
        name=name,
        mime_type="text/plain",
        modality="text",
        document=f"snippet {key}",
        vector=EmbeddingVector(
            source_id=source_id,
            file_id=file_id,
            model_id="text-test-v1",
            space_id="text-semantic-v1",
            modality="text",
            values=[1.0, 0.0],
            dimensions=2,
            normalized=True,
        ),
        modified_at=NOW,
        size_bytes=10,
        paragraph_number=sequence_number + 1,
        sequence_number=sequence_number,
    )


def test_fusion_aggregates_chunks_before_combining_channels(
    tmp_path: Path,
) -> None:
    first_chunk = make_record(
        tmp_path,
        key="a1",
        file_key="a",
        name="a.txt",
    )
    second_chunk = make_record(
        tmp_path,
        key="a2",
        file_key="a",
        name="a.txt",
        sequence_number=1,
    )
    other_file = make_record(
        tmp_path,
        key="b1",
        file_key="b",
        name="b.txt",
    )

    result = weighted_rrf(
        {
            "keyword": [
                KeywordCandidate(first_chunk, 4.0),
                KeywordCandidate(second_chunk, 3.0),
                KeywordCandidate(other_file, 2.0),
            ],
            "text_semantic": [
                VectorCandidate(other_file, 0.9),
                VectorCandidate(second_chunk, 0.8),
            ],
        },
        {"keyword": 0.5, "text_semantic": 1.0},
    )

    assert [candidate.record.file_id for candidate in result] == [
        other_file.file_id,
        first_chunk.file_id,
    ]
    assert result[0].channels == ("keyword", "text_semantic")
    assert result[1].channels == ("keyword", "text_semantic")
    assert all(0.0 <= candidate.score <= 1.0 for candidate in result)


def test_fusion_uses_rank_not_incompatible_raw_scores(tmp_path: Path) -> None:
    first = make_record(
        tmp_path,
        key="a",
        file_key="a",
        name="a.txt",
    )
    second = make_record(
        tmp_path,
        key="b",
        file_key="b",
        name="b.txt",
    )

    result = weighted_rrf(
        {
            "keyword": [
                KeywordCandidate(first, 0.01),
                KeywordCandidate(second, 999.0),
            ]
        },
        {"keyword": 1.0},
    )

    assert [candidate.record for candidate in result] == [first, second]


def test_fusion_ties_are_deterministic_and_limit_is_applied(
    tmp_path: Path,
) -> None:
    later = make_record(
        tmp_path,
        key="b",
        file_key="b",
        name="b.txt",
    )
    earlier = make_record(
        tmp_path,
        key="a",
        file_key="a",
        name="a.txt",
    )

    result = weighted_rrf(
        {
            "keyword": [KeywordCandidate(later, 1.0)],
            "text_semantic": [VectorCandidate(earlier, 0.5)],
        },
        {"keyword": 1.0, "text_semantic": 1.0},
        limit=1,
    )

    assert [candidate.record for candidate in result] == [earlier]


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({"keyword": 0.0}, "positive"),
        ({"unknown": 1.0}, "channel"),
    ],
)
def test_fusion_validates_weights(
    tmp_path: Path,
    weights: dict[str, float],
    message: str,
) -> None:
    record = make_record(
        tmp_path,
        key="a",
        file_key="a",
        name="a.txt",
    )

    with pytest.raises(ValueError, match=message):
        weighted_rrf(
            {"keyword": [KeywordCandidate(record, 1.0)]},
            weights,
        )
