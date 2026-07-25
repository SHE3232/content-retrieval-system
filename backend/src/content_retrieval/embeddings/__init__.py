"""Offline text and image embedding components."""

from .manifest import ModelEntry, ModelManifest, ModelManifestError
from .mobileclip import (
    LocalMobileClipBackend,
    MobileClipEmbeddingEngine,
    MobileClipEncoderBackend,
)
from .sentence_transformer import SentenceTransformerBackend
from .service import MultimodalEmbeddingService, cosine_similarity
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
