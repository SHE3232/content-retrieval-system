from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
import sys
import types

import pytest
from PIL import Image

from content_retrieval.domain.models import ParseResult


def make_image(index: int, name: str | None = None) -> ParseResult:
    filename = name or f"image-{index}.png"
    return ParseResult(
        file_id=f"{index + 1:064x}",
        path=Path(filename),
        name=filename,
        mime_type="image/png",
        modality="image",
        size_bytes=10,
        modified_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        width=32,
        height=32,
    )


class RecordingMobileClipBackend:
    model_id = "mobileclip-s0-v1"
    space_id = "mobileclip-image-text-v1"
    dimensions = 3

    def __init__(self) -> None:
        self.image_calls: list[list[Path]] = []
        self.text_calls: list[list[str]] = []

    def encode_images(
        self,
        paths: Sequence[Path],
    ) -> Sequence[Sequence[float]]:
        self.image_calls.append(list(paths))
        return [[3.0, 4.0, float(index)] for index, _ in enumerate(paths)]

    def encode_texts(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        self.text_calls.append(list(texts))
        return [[0.0, 3.0, 4.0] for _ in texts]


class SelectivelyFailingMobileClipBackend(RecordingMobileClipBackend):
    def encode_images(
        self,
        paths: Sequence[Path],
    ) -> Sequence[Sequence[float]]:
        self.image_calls.append(list(paths))
        if any(path.name == "bad.png" for path in paths):
            raise RuntimeError("image failure")
        return [[3.0, 4.0, 0.0] for _ in paths]


def test_mobileclip_engine_batches_images_and_queries_in_the_same_space() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    backend = RecordingMobileClipBackend()
    images = [make_image(index) for index in range(3)]
    engine = MobileClipEmbeddingEngine(backend, batch_size=2)

    image_batch = engine.embed_images(images)
    query_batch = engine.embed_queries(["a red square", "一只猫"])

    assert backend.image_calls == [
        [images[0].path, images[1].path],
        [images[2].path],
    ]
    assert backend.text_calls == [["a red square", "一只猫"]]
    assert [item.source_id for item in image_batch.items] == [
        image.file_id for image in images
    ]
    assert all(item.modality == "image" for item in image_batch.items)
    assert all(item.modality == "text" for item in query_batch.items)
    assert all(
        item.space_id == "mobileclip-image-text-v1"
        for item in image_batch.items + query_batch.items
    )
    assert all(
        abs(sum(value * value for value in item.values) - 1.0) < 1e-9
        for item in image_batch.items + query_batch.items
    )


def test_mobileclip_query_ids_are_stable_and_model_specific() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    backend = RecordingMobileClipBackend()
    engine = MobileClipEmbeddingEngine(backend)

    first = engine.embed_queries(["a cat"]).items[0]
    repeated = engine.embed_queries(["a cat"]).items[0]
    different = engine.embed_queries(["a dog"]).items[0]

    assert first.source_id == repeated.source_id
    assert first.file_id == first.source_id
    assert first.source_id != different.source_id
    assert len(first.source_id) == 64
    assert backend.text_calls == [["a cat"], ["a dog"]]


def test_mobileclip_query_cache_is_bounded() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    backend = RecordingMobileClipBackend()
    engine = MobileClipEmbeddingEngine(backend, query_cache_size=1)

    engine.embed_queries(["a cat"])
    engine.embed_queries(["a cat"])
    engine.embed_queries(["a dog"])
    engine.embed_queries(["a cat"])

    assert backend.text_calls == [["a cat"], ["a dog"], ["a cat"]]


def test_mobileclip_engine_isolates_one_bad_image() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    backend = SelectivelyFailingMobileClipBackend()
    images = [
        make_image(0, "good-one.png"),
        make_image(1, "bad.png"),
        make_image(2, "good-two.png"),
    ]

    batch = MobileClipEmbeddingEngine(backend, batch_size=3).embed_images(images)

    assert [item.source_id for item in batch.items] == [
        images[0].file_id,
        images[2].file_id,
    ]
    assert batch.failed == 1
    assert batch.errors[0].file_id == images[1].file_id
    assert backend.image_calls == [
        [image.path for image in images],
        [images[0].path],
        [images[1].path],
        [images[2].path],
    ]


def test_mobileclip_engine_reports_empty_queries_and_invalid_vectors() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    backend = RecordingMobileClipBackend()
    backend.dimensions = 4
    engine = MobileClipEmbeddingEngine(backend)

    batch = engine.embed_queries([" ", "valid query"])

    assert batch.succeeded == 0
    assert batch.failed == 2
    assert "empty" in str(batch.errors[0])
    assert "dimensions" in str(batch.errors[1])


def test_mobileclip_engine_rejects_non_image_parse_results() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    document = make_image(0)
    document.modality = "document"

    batch = MobileClipEmbeddingEngine(
        RecordingMobileClipBackend()
    ).embed_images([document])

    assert batch.succeeded == 0
    assert batch.failed == 1
    assert "not an image" in str(batch.errors[0])


def test_mobileclip_engine_rejects_invalid_configuration() -> None:
    from content_retrieval.embeddings.mobileclip import MobileClipEmbeddingEngine

    with pytest.raises(ValueError, match="batch_size"):
        MobileClipEmbeddingEngine(RecordingMobileClipBackend(), batch_size=0)

    backend = RecordingMobileClipBackend()
    backend.space_id = ""
    with pytest.raises(ValueError, match="space_id"):
        MobileClipEmbeddingEngine(backend)


def test_local_mobileclip_backend_uses_local_weights_and_rgb_preprocessing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from content_retrieval.embeddings.mobileclip import LocalMobileClipBackend

    weights_path = tmp_path / "mobileclip_s0.pt"
    weights_path.write_bytes(b"weights")
    image_path = tmp_path / "sample.png"
    Image.new("L", (4, 3), color=128).save(image_path)
    calls: dict[str, object] = {}

    class FakeTensor:
        def __init__(self, values: list[list[float]]) -> None:
            self.values = values

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def tolist(self) -> list[list[float]]:
            return self.values

    class FakeModel:
        def eval(self) -> None:
            calls["eval"] = True

        def load_state_dict(self, state: object, *, assign: bool) -> None:
            calls["state"] = state
            calls["assign"] = assign

        def encode_image(self, batch: object) -> FakeTensor:
            calls["image_batch"] = batch
            return FakeTensor([[3.0, 4.0, 0.0]])

        def encode_text(self, tokens: object) -> FakeTensor:
            calls["tokens"] = tokens
            return FakeTensor([[0.0, 3.0, 4.0]])

    def fake_preprocess(image: Image.Image) -> tuple[str, tuple[int, int]]:
        calls["image_mode"] = image.mode
        return image.mode, image.size

    fake_mobileclip = types.ModuleType("mobileclip")
    fake_mobileclip.create_model_and_transforms = (
        lambda name, **kwargs: (
            calls.update({"name": name, "create_kwargs": kwargs})
            or (FakeModel(), None, fake_preprocess)
        )
    )
    fake_mobileclip.reparameterize_model = lambda model: (
        calls.update({"reparameterized": True}) or model
    )
    fake_mobileclip.get_tokenizer = lambda name: (
        lambda texts: {"name": name, "texts": texts}
    )
    monkeypatch.setitem(sys.modules, "mobileclip", fake_mobileclip)

    class NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    fake_torch = types.ModuleType("torch")
    fake_torch.stack = lambda values: list(values)
    fake_torch.no_grad = NoGrad
    fake_torch.load = lambda path, **kwargs: (
        calls.update({"load_path": path, "load_kwargs": kwargs}) or {"weights": 1}
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    backend = LocalMobileClipBackend(
        weights_path,
        model_id="mobileclip-s0-v1",
        space_id="mobileclip-image-text-v1",
        dimensions=3,
    )

    assert backend.encode_images([image_path]) == [[3.0, 4.0, 0.0]]
    assert backend.encode_texts(["a gray rectangle"]) == [[0.0, 3.0, 4.0]]
    assert calls["name"] == "mobileclip_s0"
    assert calls["create_kwargs"] == {"pretrained": None, "reparameterize": False}
    assert calls["load_path"] == str(weights_path.resolve())
    assert calls["load_kwargs"] == {
        "map_location": "cpu",
        "mmap": True,
        "weights_only": True,
    }
    assert calls["state"] == {"weights": 1}
    assert calls["assign"] is True
    assert calls["reparameterized"] is True
    assert calls["eval"] is True
    assert calls["image_mode"] == "RGB"
    assert calls["tokens"] == {
        "name": "mobileclip_s0",
        "texts": ["a gray rectangle"],
    }


def test_local_mobileclip_backend_rejects_missing_weights(tmp_path: Path) -> None:
    from content_retrieval.embeddings.mobileclip import LocalMobileClipBackend

    with pytest.raises(FileNotFoundError):
        LocalMobileClipBackend(
            tmp_path / "missing.pt",
            model_id="mobileclip-s0-v1",
            space_id="mobileclip-image-text-v1",
            dimensions=512,
        )
