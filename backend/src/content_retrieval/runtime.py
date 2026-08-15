from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from content_retrieval.embeddings.manifest import ModelManifest
from content_retrieval.embeddings.mobileclip import (
    LocalMobileClipBackend,
    MobileClipEmbeddingEngine,
)
from content_retrieval.embeddings.sentence_transformer import (
    SentenceTransformerBackend,
)
from content_retrieval.embeddings.service import (
    MultimodalEmbeddingService,
)
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.parsers.registry import create_default_registry
from content_retrieval.retrieval.service import RetrievalService
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.chunking import TextChunker
from content_retrieval.services.indexing import IndexingService
from content_retrieval.storage.chroma import ChromaVectorRepository


TEXT_MODEL_ID = "text-multilingual-v1"
IMAGE_MODEL_ID = "mobileclip-s0-v1"
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class LocalRuntime:
    model_root: Path
    manifest_path: Path
    data_dir: Path
    manifest: ModelManifest
    repository: ChromaVectorRepository
    chunker: TextChunker
    text_engine: TextEmbeddingEngine
    image_engine: MobileClipEmbeddingEngine
    embedding_service: MultimodalEmbeddingService
    ingestion_service: BatchIngestionService
    indexing_service: IndexingService
    retrieval_service: RetrievalService

    def close(self) -> None:
        """Release persistent local resources owned by this runtime."""
        self.repository.close()


def build_local_runtime(
    *,
    model_root: Path | str,
    manifest_path: Path | str,
    data_dir: Path | str,
    tika_url: str = "http://127.0.0.1:9998",
    text_batch_size: int = 16,
    image_batch_size: int = 8,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> LocalRuntime:
    """Build the complete offline runtime from verified local artifacts."""
    root = Path(model_root).expanduser().resolve(strict=True)
    manifest_file = (
        Path(manifest_path).expanduser().resolve(strict=True)
    )
    local_data = Path(data_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"model_root is not a directory: {root}")
    if not manifest_file.is_file():
        raise FileNotFoundError(
            f"manifest_path is not a file: {manifest_file}"
        )
    if max_file_size_bytes <= 0:
        raise ValueError("max_file_size_bytes must be positive")
    if not tika_url.strip():
        raise ValueError("tika_url must not be blank")

    manifest = ModelManifest.load(manifest_file, model_root=root)
    text_entry = manifest.require(TEXT_MODEL_ID)
    image_entry = manifest.require(IMAGE_MODEL_ID)
    text_entry.verify()
    image_entry.verify()

    text_backend = SentenceTransformerBackend(
        text_entry.path,
        model_id=text_entry.model_id,
        space_id=text_entry.space_id,
        dimensions=text_entry.dimensions,
        batch_size=text_batch_size,
    )
    image_backend = LocalMobileClipBackend(
        image_entry.path,
        model_id=image_entry.model_id,
        space_id=image_entry.space_id,
        dimensions=image_entry.dimensions,
    )
    text_engine = TextEmbeddingEngine(
        text_backend,
        batch_size=text_batch_size,
    )
    image_engine = MobileClipEmbeddingEngine(
        image_backend,
        batch_size=image_batch_size,
    )
    chunker = TextChunker()
    embedding_service = MultimodalEmbeddingService(
        chunker=chunker,
        text_engine=text_engine,
        mobileclip_engine=image_engine,
    )
    ingestion_service = BatchIngestionService(
        create_default_registry(tika_url=tika_url.rstrip("/")),
        max_file_size_bytes=max_file_size_bytes,
    )
    local_data.mkdir(parents=True, exist_ok=True)
    repository = ChromaVectorRepository(local_data / "chroma")
    indexing_service = IndexingService(
        ingestion_service=ingestion_service,
        chunker=chunker,
        text_engine=text_engine,
        mobileclip_engine=image_engine,
        repository=repository,
    )
    retrieval_service = RetrievalService(
        repository=repository,
        embedding_service=embedding_service,
    )
    return LocalRuntime(
        model_root=root,
        manifest_path=manifest_file,
        data_dir=local_data,
        manifest=manifest,
        repository=repository,
        chunker=chunker,
        text_engine=text_engine,
        image_engine=image_engine,
        embedding_service=embedding_service,
        ingestion_service=ingestion_service,
        indexing_service=indexing_service,
        retrieval_service=retrieval_service,
    )
