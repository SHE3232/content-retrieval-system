from __future__ import annotations

from collections.abc import Iterable

from content_retrieval.domain.errors import ProcessingError
from content_retrieval.domain.models import (
    BatchProcessingResult,
    EmbeddingVector,
    ParseResult,
)
from content_retrieval.services.chunking import TextChunker

from .mobileclip import (
    MobileClipEmbeddingEngine,
    UnavailableMobileClipEmbeddingEngine,
)
from .text import TextEmbeddingEngine


class MultimodalEmbeddingService:
    """Dispatch parsed files to the compatible local embedding space."""

    def __init__(
        self,
        *,
        chunker: TextChunker,
        text_engine: TextEmbeddingEngine,
        mobileclip_engine: (
            MobileClipEmbeddingEngine | UnavailableMobileClipEmbeddingEngine
        ),
    ) -> None:
        self.chunker = chunker
        self.text_engine = text_engine
        self.mobileclip_engine = mobileclip_engine

    @property
    def image_semantic_available(self) -> bool:
        return bool(getattr(self.mobileclip_engine, "available", True))

    def embed_documents(
        self,
        documents: Iterable[ParseResult],
    ) -> BatchProcessingResult:
        result = BatchProcessingResult()
        for input_index, document in enumerate(documents):
            try:
                if document.modality == "image":
                    embedded = self.mobileclip_engine.embed_images([document])
                else:
                    chunks = self.chunker.chunk(document)
                    embedded = self.text_engine.embed(chunks)
            except ProcessingError as error:
                result.errors.append(error)
                continue

            for item in embedded.items:
                item.metadata["input_index"] = input_index
                result.items.append(item)
            result.errors.extend(embedded.errors)
        return result

    def embed_image_queries(
        self,
        queries: Iterable[str],
    ) -> BatchProcessingResult:
        """Embed text queries in the joint MobileCLIP image-text space."""
        return self.mobileclip_engine.embed_queries(queries)

    def embed_text_queries(
        self,
        queries: Iterable[str],
    ) -> BatchProcessingResult:
        """Embed text queries in the document text semantic space."""
        return self.text_engine.embed_queries(queries)


def cosine_similarity(
    left: EmbeddingVector,
    right: EmbeddingVector,
) -> float:
    """Compare two normalized vectors only when their spaces are compatible."""
    if left.space_id != right.space_id:
        raise ValueError("cannot compare vectors from different embedding spaces")
    if left.dimensions != right.dimensions:
        raise ValueError("cannot compare vectors with different dimensions")
    if not left.normalized or not right.normalized:
        raise ValueError("cosine similarity requires L2-normalized vectors")

    score = sum(
        left_value * right_value
        for left_value, right_value in zip(
            left.values,
            right.values,
            strict=True,
        )
    )
    return max(-1.0, min(1.0, score))
