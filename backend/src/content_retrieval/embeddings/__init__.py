"""Offline text and image embedding components."""

from typing import Any

from .manifest import ModelEntry, ModelManifest, ModelManifestError
from .mobileclip import (
    LocalMobileClipBackend,
    MobileClipEmbeddingEngine,
    MobileClipEncoderBackend,
)
from .sentence_transformer import SentenceTransformerBackend
from .text import TextEmbeddingEngine, TextEncoderBackend

__all__ = [
    "ModelEntry",
    "ModelManifest",
    "ModelManifestError",
    "LocalMobileClipBackend",
    "MobileClipEmbeddingEngine",
    "MobileClipEncoderBackend",
    "MultimodalEmbeddingService",
    "SentenceTransformerBackend",
    "TextEmbeddingEngine",
    "TextEncoderBackend",
    "cosine_similarity",
]


def __getattr__(name: str) -> Any:
    """Load the orchestration service without coupling model-only tools to parsers."""
    if name in {"MultimodalEmbeddingService", "cosine_similarity"}:
        from .service import MultimodalEmbeddingService, cosine_similarity

        exports = {
            "MultimodalEmbeddingService": MultimodalEmbeddingService,
            "cosine_similarity": cosine_similarity,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
