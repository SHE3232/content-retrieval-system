# Week 3 Multimodal Embedding Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline dual-space text and image embedding engine with deterministic chunking, local model verification, reproducible retrieval benchmarks, automated tests, and Week 3 deliverables.

**Architecture:** Text chunks use a multilingual semantic-search space, while MobileCLIP images and text queries use a separate joint image-text space. A unified service dispatches `ParseResult` objects without persisting vectors, and every vector carries source, model, space, dimension, and normalization metadata.

**Tech Stack:** Python 3.10, pytest, Sentence Transformers, PyTorch CPU, MobileCLIP-S0, LiteRT Torch, NumPy, python-docx.

---

### Task 1: Finalize Generic Embedding Contracts

**Files:**
- Modify: `backend/src/content_retrieval/domain/models.py`
- Modify: `backend/src/content_retrieval/domain/errors.py`
- Modify: `backend/src/content_retrieval/services/chunking.py`
- Modify: `backend/tests/test_chunking_contracts.py`
- Modify: `docs/week3/p0-interface-and-chunking-contract.md`

- [ ] **Step 1: Write the failing generic-vector contract test**

```python
vector = EmbeddingVector(
    source_id="b" * 64,
    file_id="a" * 64,
    model_id="local-model",
    space_id="text-semantic-v1",
    modality="text",
    values=[1.0, 0.0],
    dimensions=2,
    normalized=True,
)
assert vector.source_id == "b" * 64
assert vector.space_id == "text-semantic-v1"
```

- [ ] **Step 2: Run the focused test and confirm it fails because `source_id` and `space_id` do not exist**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_chunking_contracts.py -q`

- [ ] **Step 3: Replace the text-only vector identity with the generic contract**

```python
@dataclass(slots=True)
class EmbeddingVector:
    source_id: str
    file_id: str
    model_id: str
    space_id: str
    modality: Literal["text", "image"]
    values: list[float]
    dimensions: int
    normalized: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"
```

- [ ] **Step 4: Run focused and full backend tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_chunking_contracts.py -q`

Run: `backend/.venv/Scripts/python.exe -m pytest backend -q`

### Task 2: Add Verified Local Model Manifests

**Files:**
- Create: `backend/src/content_retrieval/embeddings/__init__.py`
- Create: `backend/src/content_retrieval/embeddings/manifest.py`
- Create: `backend/tests/test_model_manifest.py`
- Create: `models/model-manifest.example.json`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing tests for path confinement, SHA-256 verification, and model-space metadata**

```python
manifest = ModelManifest.load(path, model_root=tmp_path / "models")
entry = manifest.require("text-multilingual-v1")
assert entry.space_id == "text-semantic-v1"
assert entry.verify_file() == expected_sha256
```

- [ ] **Step 2: Run the test and confirm import failure**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_model_manifest.py -q`

- [ ] **Step 3: Implement immutable `ModelEntry` and `ModelManifest` types**

```python
@dataclass(frozen=True, slots=True)
class ModelEntry:
    model_id: str
    space_id: str
    modality: str
    dimensions: int
    relative_path: Path
    sha256: str
    license_name: str
    runtime: str
```

- [ ] **Step 4: Verify focused tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_model_manifest.py -q`

### Task 3: Implement Text Embedding

**Files:**
- Create: `backend/src/content_retrieval/embeddings/text.py`
- Create: `backend/src/content_retrieval/embeddings/sentence_transformer.py`
- Create: `backend/tests/test_text_embeddings.py`
- Create: `model-tools/download_models.py`

- [ ] **Step 1: Write failing tests for batching, normalization, order, dimensions, zero vectors, and isolated backend failures**

```python
batch = TextEmbeddingEngine(FakeTextBackend(), batch_size=2).embed(chunks)
assert [item.source_id for item in batch.items] == [chunk.chunk_id for chunk in chunks]
assert all(abs(sum(v * v for v in item.values) - 1.0) < 1e-6 for item in batch.items)
```

- [ ] **Step 2: Run the focused tests and confirm import failure**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_text_embeddings.py -q`

- [ ] **Step 3: Implement backend protocol and engine**

```python
class TextEncoderBackend(Protocol):
    model_id: str
    space_id: str
    dimensions: int
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...
```

- [ ] **Step 4: Implement local-only Sentence Transformers adapter**

```python
self._model = SentenceTransformer(
    str(model_path),
    device="cpu",
    local_files_only=True,
)
```

- [ ] **Step 5: Run focused and full tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_text_embeddings.py -q`

Run: `backend/.venv/Scripts/python.exe -m pytest backend -q`

### Task 4: Implement MobileCLIP Image and Query Embedding

**Files:**
- Create: `backend/src/content_retrieval/embeddings/mobileclip.py`
- Create: `backend/tests/test_mobileclip_embeddings.py`
- Create: `model-tools/mobileclip_local.py`

- [ ] **Step 1: Write failing tests for image order, RGB/EXIF preprocessing delegation, normalization, query IDs, joint space, and item-level failures**

```python
image_batch = engine.embed_images(images)
query_batch = engine.embed_queries(["a red square"])
assert image_batch.items[0].space_id == query_batch.items[0].space_id
assert image_batch.items[0].modality == "image"
assert query_batch.items[0].modality == "text"
```

- [ ] **Step 2: Run the test and confirm import failure**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_mobileclip_embeddings.py -q`

- [ ] **Step 3: Implement the dependency-injected engine and stable query IDs**

```python
query_id = hashlib.sha256(
    f"{backend.model_id}\0{query}".encode("utf-8")
).hexdigest()
```

- [ ] **Step 4: Implement the production local MobileCLIP adapter**

```python
model, _, preprocess = mobileclip.create_model_and_transforms(
    "mobileclip_s0",
    pretrained=str(weights_path),
)
tokenizer = mobileclip.get_tokenizer("mobileclip_s0")
```

- [ ] **Step 5: Run focused and full tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_mobileclip_embeddings.py -q`

Run: `backend/.venv/Scripts/python.exe -m pytest backend -q`

### Task 5: Implement the Unified Dual-Space Service

**Files:**
- Create: `backend/src/content_retrieval/embeddings/service.py`
- Create: `backend/tests/test_multimodal_embedding_service.py`

- [ ] **Step 1: Write failing tests for modality dispatch, order metadata, partial failures, and cross-space similarity rejection**

```python
result = service.embed_documents([text_result, image_result])
assert [item.modality for item in result.items] == ["text", "image"]
with pytest.raises(ValueError, match="different embedding spaces"):
    cosine_similarity(result.items[0], result.items[1])
```

- [ ] **Step 2: Run the focused tests and confirm import failure**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_multimodal_embedding_service.py -q`

- [ ] **Step 3: Implement dispatch and guarded cosine similarity**

```python
def cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    if left.space_id != right.space_id:
        raise ValueError("cannot compare vectors from different embedding spaces")
    if left.dimensions != right.dimensions:
        raise ValueError("cannot compare vectors with different dimensions")
    return sum(a * b for a, b in zip(left.values, right.values, strict=True))
```

- [ ] **Step 4: Run focused and full tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_multimodal_embedding_service.py -q`

Run: `backend/.venv/Scripts/python.exe -m pytest backend -q`

### Task 6: Add Offline Export and Parity Tools

**Files:**
- Create: `conversion-tools/export_text_encoder.py`
- Create: `conversion-tools/export_mobileclip.py`
- Create: `conversion-tools/verify_parity.py`
- Create: `conversion-tools/test_verify_parity.py`
- Modify: `conversion-tools/pyproject.toml`

- [ ] **Step 1: Write failing tests for cosine parity, absolute-error reporting, and manifest output**

```python
report = compare_outputs(reference, converted)
assert report["cosine_similarity"] >= 0.999
assert report["max_absolute_error"] <= 1e-4
```

- [ ] **Step 2: Run the focused tests and confirm import failure**

Run: `conversion-tools/.venv/bin/python -m pytest conversion-tools/test_verify_parity.py -q`

- [ ] **Step 3: Implement pure NumPy parity reporting and model-specific export entry points**

```python
def compare_outputs(reference: np.ndarray, converted: np.ndarray) -> dict[str, float]:
    difference = np.abs(reference - converted)
    cosine = float(np.dot(reference.ravel(), converted.ravel()) /
                   (np.linalg.norm(reference) * np.linalg.norm(converted)))
    return {"cosine_similarity": cosine,
            "max_absolute_error": float(difference.max()),
            "mean_absolute_error": float(difference.mean())}
```

- [ ] **Step 4: Run the existing LiteRT smoke test and attempt both real exports**

Run: `wsl -d Ubuntu-24.04 -- /home/aaron/.virtualenvs/content-retrieval-conversion/bin/python /mnt/f/contentretrivalsystem/.worktrees/week3-embedding-engine/conversion-tools/smoke_test.py`

Record unsupported operators as explicit conversion findings; do not report a failed real-model export as successful.

### Task 7: Implement NQ Retrieval Evaluation and Performance Baseline

**Files:**
- Create: `model-tools/benchmark_nq.py`
- Create: `model-tools/benchmark_performance.py`
- Create: `model-tools/test_benchmark_nq.py`

- [ ] **Step 1: Write failing metric tests using a three-document synthetic ranking**

```python
metrics = retrieval_metrics(rankings, qrels, cutoffs=(1, 5, 10))
assert metrics["recall@1"] == 0.5
assert metrics["mrr@10"] == 0.75
```

- [ ] **Step 2: Run the tests and confirm import failure**

Run: `model-tools/.venv/Scripts/python.exe -m pytest model-tools/test_benchmark_nq.py -q`

- [ ] **Step 3: Implement JSONL/TSV loading, batched encoding, top-k ranking, metrics, and JSON output**

```python
scores = query_embeddings @ corpus_embeddings.T
top_indices = np.argpartition(scores, -max_k, axis=1)[:, -max_k:]
```

- [ ] **Step 4: Run synthetic tests and the frozen 40-query benchmark**

Run: `model-tools/.venv/Scripts/python.exe model-tools/benchmark_nq.py --split benchmark --output output/week3/nq-benchmark.json`

### Task 8: Implement COCO Subset Preparation and Image Retrieval Evaluation

**Files:**
- Create: `datasets/prepare_coco_retrieval.py`
- Create: `datasets/test_prepare_coco_retrieval.py`
- Create: `model-tools/benchmark_coco.py`
- Create: `model-tools/test_benchmark_coco.py`
- Modify: `datasets/README.md`
- Modify: `datasets/licenses/NOTICE.md`

- [ ] **Step 1: Write failing tests with tiny COCO-style annotations and local image fixtures**

```python
rows = prepare_subset(captions, instances, size=2, validation_size=1)
assert rows[0]["license_url"] == "https://example.test/license"
assert len(rows[0]["sha256"]) == 64
```

- [ ] **Step 2: Run tests and confirm import failure**

Run: `backend/.venv/Scripts/python.exe -m pytest datasets/test_prepare_coco_retrieval.py model-tools/test_benchmark_coco.py -q`

- [ ] **Step 3: Implement deterministic selection, downloads, license manifest, split isolation, and Recall@K**

```python
selected = sorted(images, key=lambda image: stable_id(image["id"]))[:size]
```

- [ ] **Step 4: Prepare the 200-image subset and run the 40-image frozen benchmark**

Run: `model-tools/.venv/Scripts/python.exe datasets/prepare_coco_retrieval.py --size 200 --validation-size 160`

Run: `model-tools/.venv/Scripts/python.exe model-tools/benchmark_coco.py --split benchmark --output output/week3/coco-benchmark.json`

### Task 9: Produce Tests, Reports, and the Submission Package

**Files:**
- Create: `tmp/docx/build_week3_reports.py`
- Create: `docs/week3/reports/多模态嵌入模块API文档.docx`
- Create: `docs/week3/reports/多模态嵌入模块测试报告.docx`
- Create: `docs/week3/reports/模型准确率验证报告.docx`
- Create: `docs/week3/reports/第三周工作周报.docx`
- Create: `output/week3/第三周最终提交材料/`
- Create: `output/week3/第三周最终提交材料_最终版.zip`

- [ ] **Step 1: Run coverage and save machine-readable evidence**

Run: `backend/.venv/Scripts/python.exe -m pytest backend --cov=content_retrieval.embeddings --cov-report=json:output/week3/embedding-coverage.json --cov-fail-under=85`

- [ ] **Step 2: Build four Times New Roman, black-on-white DOCX reports from verified JSON and test outputs**

Use real tables for repeated records, explicit table geometry, and no colored fills.

- [ ] **Step 3: Render every DOCX to PNG and inspect all pages**

Run: bundled `render_docx.py` for each report; if LibreOffice is unavailable, use Word COM PDF export and bundled Poppler rendering.

- [ ] **Step 4: Build the code ZIP from a post-test whitelist staging directory**

Include source, tests, manifests, dataset preparation scripts, evaluation scripts, lock files, and README documents. Exclude virtual environments, downloaded weights, raw datasets, caches, databases, coverage internals, and user-provided source documents.

### Task 10: Final Verification

**Files:**
- Verify all changed and generated files.

- [ ] **Step 1: Run full backend, dataset, model-tool, and conversion-tool test suites**

Run: `backend/.venv/Scripts/python.exe -m pytest backend datasets model-tools -q`

Run: LiteRT smoke and parity commands in WSL2.

- [ ] **Step 2: Audit requirements**

Confirm dual spaces, offline path enforcement, deterministic IDs, partial failure isolation, NQ and COCO reports, 85% embedding coverage, four visually verified DOCX files, and a whitelist-only ZIP.

- [ ] **Step 3: Inspect Git status and package contents**

Run: `git status --short`

Run: list ZIP entries and reject caches, models, raw data, local databases, and temporary files.

