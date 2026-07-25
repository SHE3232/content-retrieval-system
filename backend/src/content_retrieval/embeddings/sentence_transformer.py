from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any


class SentenceTransformerBackend:
    """Local-only CPU adapter for a Sentence Transformers model directory."""

    def __init__(
        self,
        model_path: Path | str,
        *,
        model_id: str,
        space_id: str,
        dimensions: int,
        batch_size: int = 16,
    ) -> None:
        path = Path(model_path).resolve(strict=True)
        if not path.is_dir():
            raise FileNotFoundError(f"model_path is not a directory: {path}")
        if not model_id.strip():
            raise ValueError("model_id must not be blank")
        if not space_id.strip():
            raise ValueError("space_id must not be blank")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        from sentence_transformers import SentenceTransformer

        self.model_id = model_id
        self.space_id = space_id
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.model_path = path
        self._model = SentenceTransformer(
            str(path),
            device="cpu",
            local_files_only=True,
        )
        if hasattr(self._model, "get_embedding_dimension"):
            actual_dimensions = self._model.get_embedding_dimension()
        else:
            actual_dimensions = self._model.get_sentence_embedding_dimension()
        if actual_dimensions != dimensions:
            raise ValueError(
                "model embedding dimension does not match the manifest: "
                f"expected {dimensions}, got {actual_dimensions}"
            )

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        source = list(texts)
        if not source:
            return []
        encoded: Any = self._model.encode(
            source,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        rows = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        return [[float(value) for value in row] for row in rows]
