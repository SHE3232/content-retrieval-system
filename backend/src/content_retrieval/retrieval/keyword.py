from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import math
import os
import re

from content_retrieval.domain.retrieval import IndexRecord, SearchFilters


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Return deterministic case-folded Latin/digit and CJK search tokens."""
    return _TOKEN_PATTERN.findall(text.casefold())


@dataclass(frozen=True, slots=True)
class KeywordCandidate:
    record: IndexRecord
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or self.score < 0:
            raise ValueError("keyword score must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class _IndexedDocument:
    record: IndexRecord
    frequencies: Counter[str]
    length: int


class KeywordIndex:
    """Small local BM25 index rebuilt from the persistent record catalog."""

    def __init__(
        self,
        records: Iterable[IndexRecord] = (),
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.k1 = k1
        self.b = b
        self._documents: list[_IndexedDocument] = []
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 0.0
        self.rebuild(records)

    def rebuild(self, records: Iterable[IndexRecord]) -> None:
        documents: list[_IndexedDocument] = []
        document_frequency: Counter[str] = Counter()
        for record in records:
            name_tokens = tokenize(record.name)
            path_tokens = tokenize(str(record.path))
            document_tokens = tokenize(record.document)
            tokens = (
                name_tokens * 3
                + path_tokens * 2
                + document_tokens
            )
            frequencies = Counter(tokens)
            documents.append(
                _IndexedDocument(
                    record=record,
                    frequencies=frequencies,
                    length=len(tokens),
                )
            )
            document_frequency.update(frequencies.keys())

        self._documents = documents
        self._document_frequency = document_frequency
        self._average_length = (
            sum(document.length for document in documents) / len(documents)
            if documents
            else 0.0
        )

    def search(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters | None = None,
    ) -> list[KeywordCandidate]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms or not self._documents:
            return []
        active_filters = filters or SearchFilters()
        candidates: list[KeywordCandidate] = []
        for document in self._documents:
            if not self._matches_filters(document.record, active_filters):
                continue
            score = self._score(document, terms)
            if score > 0:
                candidates.append(
                    KeywordCandidate(record=document.record, score=score)
                )
        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                os.path.normcase(str(candidate.record.path)),
                candidate.record.sequence_number,
                candidate.record.record_id,
            )
        )
        return candidates[:limit]

    def _score(
        self,
        document: _IndexedDocument,
        terms: list[str],
    ) -> float:
        corpus_size = len(self._documents)
        average_length = self._average_length or 1.0
        score = 0.0
        for term in terms:
            frequency = document.frequencies.get(term, 0)
            if frequency == 0:
                continue
            document_frequency = self._document_frequency[term]
            inverse_document_frequency = math.log(
                1.0
                + (
                    corpus_size
                    - document_frequency
                    + 0.5
                )
                / (document_frequency + 0.5)
            )
            denominator = frequency + self.k1 * (
                1.0
                - self.b
                + self.b * document.length / average_length
            )
            score += inverse_document_frequency * (
                frequency * (self.k1 + 1.0) / denominator
            )
        return score

    @staticmethod
    def _matches_filters(
        record: IndexRecord,
        filters: SearchFilters,
    ) -> bool:
        if filters.mime_types and record.mime_type not in filters.mime_types:
            return False
        if filters.modalities and record.modality not in filters.modalities:
            return False
        if (
            filters.modified_after is not None
            and record.modified_at < filters.modified_after
        ):
            return False
        if (
            filters.modified_before is not None
            and record.modified_at > filters.modified_before
        ):
            return False
        if filters.path_prefix is not None:
            path = os.path.normcase(str(record.path.resolve()))
            prefix = os.path.normcase(str(filters.path_prefix.resolve()))
            try:
                if os.path.commonpath([path, prefix]) != prefix:
                    return False
            except ValueError:
                return False
        return True
