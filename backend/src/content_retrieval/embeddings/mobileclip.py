from __future__ import annotations

from collections.abc import Iterable, Sequence
import hashlib
import math
from pathlib import Path
from typing import Protocol, runtime_checkable

from content_retrieval.domain.errors import EmbeddingError
from content_retrieval.domain.models import (
    BatchProcessingResult,
    EmbeddingVector,
    ParseResult,
)


@runtime_checkable
class MobileClipEncoderBackend(Protocol):
    model_id: str
    space_id: str
    dimensions: int

    def encode_images(
        self,
        paths: Sequence[Path],
    ) -> Sequence[Sequence[float]]:
        """Encode local images without network access."""
        ...

    def encode_texts(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        """Encode text queries into the same space as images."""
        ...


class LocalMobileClipBackend:
    """Local-only CPU adapter for MobileCLIP-S0 weights."""

    def __init__(
        self,
        weights_path: Path | str,
        *,
        model_id: str,
        space_id: str,
        dimensions: int = 512,
    ) -> None:
        path = Path(weights_path).resolve(strict=True)
        if not path.is_file():
            raise FileNotFoundError(f"weights_path is not a file: {path}")
        if not model_id.strip():
            raise ValueError("model_id must not be blank")
        if not space_id.strip():
            raise ValueError("space_id must not be blank")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")

        import mobileclip
        import torch

        model, _, preprocess = mobileclip.create_model_and_transforms(
            "mobileclip_s0",
            pretrained=str(path),
        )
        model.eval()
        self.model_id = model_id
        self.space_id = space_id
        self.dimensions = dimensions
        self.weights_path = path
        self._mobileclip = mobileclip
        self._torch = torch
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = mobileclip.get_tokenizer("mobileclip_s0")

    def encode_images(self, paths: Sequence[Path]) -> list[list[float]]:
        from PIL import Image, ImageOps

        source = list(paths)
        if not source:
            return []
        tensors: list[object] = []
        for path in source:
            with Image.open(Path(path).resolve(strict=True)) as image:
                corrected = ImageOps.exif_transpose(image).convert("RGB")
                tensors.append(self._preprocess(corrected))
        batch = self._torch.stack(tensors)
        with self._torch.no_grad():
            encoded = self._model.encode_image(batch)
        return self._to_rows(encoded)

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        source = list(texts)
        if not source:
            return []
        tokens = self._tokenizer(source)
        with self._torch.no_grad():
            encoded = self._model.encode_text(tokens)
        return self._to_rows(encoded)

    @staticmethod
    def _to_rows(encoded: object) -> list[list[float]]:
        detached = encoded.detach().cpu()
        rows = detached.tolist()
        return [[float(value) for value in row] for row in rows]


class MobileClipEmbeddingEngine:
    """Validate and normalize MobileCLIP image and query embeddings."""

    def __init__(
        self,
        backend: MobileClipEncoderBackend,
        *,
        batch_size: int = 8,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not backend.model_id.strip():
            raise ValueError("backend model_id must not be blank")
        if not backend.space_id.strip():
            raise ValueError("backend space_id must not be blank")
        if backend.dimensions <= 0:
            raise ValueError("backend dimensions must be positive")
        self.backend = backend
        self.batch_size = batch_size

    def embed_images(
        self,
        images: Iterable[ParseResult],
    ) -> BatchProcessingResult:
        result = BatchProcessingResult()
        valid: list[tuple[int, ParseResult]] = []
        for input_index, image in enumerate(images):
            if image.modality != "image":
                result.errors.append(
                    EmbeddingError(
                        "parse result is not an image",
                        file_id=image.file_id,
                    )
                )
            else:
                valid.append((input_index, image))

        for start in range(0, len(valid), self.batch_size):
            self._embed_image_batch(
                valid[start : start + self.batch_size],
                result,
            )
        return result

    def embed_queries(self, queries: Iterable[str]) -> BatchProcessingResult:
        result = BatchProcessingResult()
        valid: list[tuple[int, str, str]] = []
        for input_index, query in enumerate(queries):
            normalized = query.strip()
            if not normalized:
                result.errors.append(EmbeddingError("query text is empty"))
                continue
            query_id = hashlib.sha256(
                f"{self.backend.model_id}\0{normalized}".encode("utf-8")
            ).hexdigest()
            valid.append((input_index, normalized, query_id))

        for start in range(0, len(valid), self.batch_size):
            self._embed_query_batch(
                valid[start : start + self.batch_size],
                result,
            )
        return result

    def _embed_image_batch(
        self,
        entries: list[tuple[int, ParseResult]],
        result: BatchProcessingResult,
    ) -> None:
        if not entries:
            return
        try:
            vectors = self.backend.encode_images(
                [image.path for _, image in entries]
            )
            if len(vectors) != len(entries):
                raise ValueError(
                    "backend output count does not match input count"
                )
        except Exception:
            if len(entries) == 1:
                _, image = entries[0]
                result.errors.append(
                    EmbeddingError(
                        "image encoder failed for one file",
                        file_id=image.file_id,
                    )
                )
                return
            for entry in entries:
                self._embed_image_batch([entry], result)
            return

        for (input_index, image), vector in zip(entries, vectors, strict=True):
            try:
                values = self._normalize(vector)
                result.items.append(
                    EmbeddingVector(
                        source_id=image.file_id,
                        file_id=image.file_id,
                        model_id=self.backend.model_id,
                        space_id=self.backend.space_id,
                        modality="image",
                        values=values,
                        dimensions=self.backend.dimensions,
                        normalized=True,
                        metadata={
                            "input_index": input_index,
                            "source_name": image.name,
                            "mime_type": image.mime_type,
                            "width": image.width,
                            "height": image.height,
                        },
                    )
                )
            except (TypeError, ValueError) as error:
                result.errors.append(
                    EmbeddingError(str(error), file_id=image.file_id)
                )

    def _embed_query_batch(
        self,
        entries: list[tuple[int, str, str]],
        result: BatchProcessingResult,
    ) -> None:
        if not entries:
            return
        try:
            vectors = self.backend.encode_texts(
                [query for _, query, _ in entries]
            )
            if len(vectors) != len(entries):
                raise ValueError(
                    "backend output count does not match input count"
                )
        except Exception:
            if len(entries) == 1:
                result.errors.append(
                    EmbeddingError("MobileCLIP text encoder failed for one query")
                )
                return
            for entry in entries:
                self._embed_query_batch([entry], result)
            return

        for (input_index, _, query_id), vector in zip(
            entries,
            vectors,
            strict=True,
        ):
            try:
                values = self._normalize(vector)
                result.items.append(
                    EmbeddingVector(
                        source_id=query_id,
                        file_id=query_id,
                        model_id=self.backend.model_id,
                        space_id=self.backend.space_id,
                        modality="text",
                        values=values,
                        dimensions=self.backend.dimensions,
                        normalized=True,
                        metadata={
                            "input_index": input_index,
                            "source_kind": "query",
                        },
                    )
                )
            except (TypeError, ValueError) as error:
                result.errors.append(EmbeddingError(str(error)))

    def _normalize(self, vector: Sequence[float]) -> list[float]:
        values = list(vector)
        if len(values) != self.backend.dimensions:
            raise ValueError(
                "backend vector dimensions do not match the declared dimensions"
            )
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in values
        ):
            raise ValueError("backend vector values must be finite numbers")
        norm = math.sqrt(sum(float(value) * float(value) for value in values))
        if norm == 0.0:
            raise ValueError("backend returned a zero vector")
        return [float(value) / norm for value in values]
