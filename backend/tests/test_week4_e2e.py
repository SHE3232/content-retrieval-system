from datetime import datetime, timezone
import hashlib
from pathlib import Path

from content_retrieval.domain.models import ParseResult
from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine
from content_retrieval.embeddings.service import MultimodalEmbeddingService
from content_retrieval.embeddings.text import TextEmbeddingEngine
from content_retrieval.parsers.registry import ParserRegistry
from content_retrieval.retrieval.service import RetrievalService
from content_retrieval.services.batch_ingestion import BatchIngestionService
from content_retrieval.services.chunking import TextChunker
from content_retrieval.services.indexing import IndexingService
from content_retrieval.storage.chroma import ChromaVectorRepository


class FixtureParser:
    supported_extensions = frozenset(
        {".txt", ".pdf", ".docx", ".jpg", ".png"}
    )
    supported_mime_types = frozenset()

    def parse(self, path: Path) -> ParseResult:
        data = path.read_bytes()
        file_id = hashlib.sha256(data).hexdigest()
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".png"}:
            return ParseResult(
                file_id=file_id,
                path=path.resolve(),
                name=path.name,
                mime_type=(
                    "image/jpeg" if suffix == ".jpg" else "image/png"
                ),
                modality="image",
                size_bytes=len(data),
                modified_at=datetime.now(timezone.utc),
                width=16,
                height=16,
            )
        text = data.decode("utf-8")
        mime_type = {
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".docx": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        }[suffix]
        metadata = {"page_texts": [text]} if suffix == ".pdf" else {}
        return ParseResult(
            file_id=file_id,
            path=path.resolve(),
            name=path.name,
            mime_type=mime_type,
            modality="text" if suffix == ".txt" else "document",
            size_bytes=len(data),
            modified_at=datetime.now(timezone.utc),
            text=text,
            page_count=1 if suffix == ".pdf" else None,
            metadata=metadata,
        )


class FixtureTextBackend:
    model_id = "fixture-text-v1"
    space_id = "fixture-text-space-v1"
    dimensions = 3

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [
            [
                float("offline" in text.lower()),
                float("schedule" in text.lower()),
                1.0,
            ]
            for text in texts
        ]


class FixtureImageBackend:
    model_id = "fixture-image-v1"
    space_id = "fixture-image-space-v1"
    dimensions = 2

    def encode_images(self, paths: list[Path]) -> list[list[float]]:
        return [
            [1.0, 0.0] if path.suffix.lower() == ".png" else [0.0, 1.0]
            for path in paths
        ]

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if "logo" in text.lower() else [0.0, 1.0]
            for text in texts
        ]


def test_five_format_index_search_and_persistent_restart(
    tmp_path: Path,
) -> None:
    contents = {
        "notes.txt": "offline local notes and private search",
        "guide.pdf": "project schedule and milestone",
        "design.docx": "hybrid retrieval architecture",
        "photo.jpg": "jpeg fixture",
        "logo.png": "png fixture",
    }
    paths = []
    for name, content in contents.items():
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)

    repository = ChromaVectorRepository(tmp_path / "chroma")
    chunker = TextChunker()
    text_engine = TextEmbeddingEngine(FixtureTextBackend())
    image_engine = MobileClipEmbeddingEngine(FixtureImageBackend())
    embeddings = MultimodalEmbeddingService(
        chunker=chunker,
        text_engine=text_engine,
        mobileclip_engine=image_engine,
    )
    indexing = IndexingService(
        ingestion_service=BatchIngestionService(
            ParserRegistry([FixtureParser()]),
            max_file_size_bytes=1024,
        ),
        chunker=chunker,
        text_engine=text_engine,
        mobileclip_engine=image_engine,
        repository=repository,
    )

    result = indexing.index_paths(
        paths,
        authorized_roots=[tmp_path],
    )
    retrieval = RetrievalService(
        repository=repository,
        embedding_service=embeddings,
    )
    keyword = retrieval.search(
        "private search",
        channels=("keyword",),
    )
    semantic = retrieval.search(
        "offline knowledge",
        channels=("text_semantic",),
    )
    image = retrieval.search(
        "blue logo",
        channels=("image_semantic",),
    )

    assert result.failed_files == 0
    assert result.indexed_files == 5
    assert repository.count() == 5
    assert keyword.hits[0].name == "notes.txt"
    assert semantic.hits[0].name == "notes.txt"
    assert image.hits[0].name == "logo.png"

    restarted_repository = ChromaVectorRepository(tmp_path / "chroma")
    restarted = RetrievalService(
        repository=restarted_repository,
        embedding_service=embeddings,
    )
    repeated = restarted.search(
        "private search",
        channels=("keyword",),
    )
    assert restarted_repository.count() == 5
    assert repeated.hits[0].name == "notes.txt"
