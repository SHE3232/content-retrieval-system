"""Offline text and image embedding components."""

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
    "SentenceTransformerBackend",
    "TextEmbeddingEngine",
    "TextEncoderBackend",
]
