from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import os
from typing import Protocol

from content_retrieval.domain.retrieval import (
    IndexRecord,
    SearchChannel,
)


_CHANNEL_ORDER: tuple[SearchChannel, ...] = (
    "keyword",
    "text_semantic",
    "image_semantic",
)
_VALID_CHANNELS = frozenset(_CHANNEL_ORDER)
_RRF_CONSTANT = 60


class RankedCandidate(Protocol):
    record: IndexRecord
    score: float


@dataclass(frozen=True, slots=True)
class FusedCandidate:
    record: IndexRecord
    score: float
    channels: tuple[SearchChannel, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("fused score must be finite and between 0 and 1")
        if not self.channels:
            raise ValueError("fused candidate must include a search channel")


@dataclass(slots=True)
class _FileScore:
    record: IndexRecord
    contribution: float
    total: float
    channels: set[SearchChannel]


def weighted_rrf(
    channels: Mapping[SearchChannel, Sequence[RankedCandidate]],
    weights: Mapping[str, float],
    *,
    limit: int | None = None,
) -> list[FusedCandidate]:
    """Fuse channel ranks after collapsing duplicate chunks by file."""
    unknown_channels = (set(channels) | set(weights)) - _VALID_CHANNELS
    if unknown_channels:
        raise ValueError("unsupported search channel")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    for channel, candidates in channels.items():
        if candidates and channel not in weights:
            raise ValueError(f"missing weight for channel {channel}")
    if any(
        not math.isfinite(weight) or weight <= 0
        for weight in weights.values()
    ):
        raise ValueError("channel weights must be finite and positive")

    active_channels = [
        channel
        for channel in _CHANNEL_ORDER
        if channels.get(channel)
    ]
    if not active_channels:
        return []
    denominator = sum(
        weights[channel] / (_RRF_CONSTANT + 1)
        for channel in active_channels
    )
    scores: dict[str, _FileScore] = {}

    for channel in active_channels:
        seen_files: set[str] = set()
        for rank, candidate in enumerate(channels[channel], start=1):
            file_id = candidate.record.file_id
            if file_id in seen_files:
                continue
            seen_files.add(file_id)
            contribution = weights[channel] / (_RRF_CONSTANT + rank)
            current = scores.get(file_id)
            if current is None:
                scores[file_id] = _FileScore(
                    record=candidate.record,
                    contribution=contribution,
                    total=contribution,
                    channels={channel},
                )
                continue
            current.total += contribution
            current.channels.add(channel)
            if contribution > current.contribution:
                current.record = candidate.record
                current.contribution = contribution

    fused = [
        FusedCandidate(
            record=value.record,
            score=min(1.0, value.total / denominator),
            channels=tuple(
                channel
                for channel in _CHANNEL_ORDER
                if channel in value.channels
            ),
        )
        for value in scores.values()
    ]
    fused.sort(
        key=lambda candidate: (
            -candidate.score,
            os.path.normcase(str(candidate.record.path)),
            candidate.record.file_id,
        )
    )
    return fused if limit is None else fused[:limit]
