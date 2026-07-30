# Week 4 Search Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, offline end-to-end MVP that parses local files, creates text/image embeddings, stores them in ChromaDB, and returns ranked keyword, text-semantic, and text-to-image search results.

**Architecture:** Keep the existing `api -> services -> domain/adapters` dependency direction. Add a Chroma repository that persists one collection per embedding space, an indexing service that pairs source records with vectors, a BM25 keyword index rebuilt from stored records, and a retrieval service that aggregates per-file candidates with weighted reciprocal-rank fusion. Preserve the existing ingestion API and add separate indexing and search routes.

**Tech Stack:** Python 3.10, FastAPI, ChromaDB 1.5.x, Sentence Transformers, MobileCLIP, pytest, pytest-cov, NQ retrieval subset, COCO 2017 validation subset.

---

## File map

- `backend/src/content_retrieval/domain/retrieval.py`: index records, search filters, hits, results, and indexing summaries.
- `backend/src/content_retrieval/domain/errors.py`: controlled storage, indexing, and retrieval failures.
- `backend/src/content_retrieval/embeddings/text.py`: text-query embedding in the text semantic space.
- `backend/src/content_retrieval/embeddings/service.py`: unified text-query and image-query entry points.
- `backend/src/content_retrieval/storage/chroma.py`: persistent collection lifecycle, upsert, delete, list, and vector query.
- `backend/src/content_retrieval/services/indexing.py`: parse -> chunk/embed -> persistent records.
- `backend/src/content_retrieval/retrieval/keyword.py`: deterministic tokenizer and BM25 ranking.
- `backend/src/content_retrieval/retrieval/fusion.py`: file-level aggregation and weighted reciprocal-rank fusion.
- `backend/src/content_retrieval/retrieval/service.py`: keyword, text-semantic, and text-to-image orchestration.
- `backend/src/content_retrieval/api/schemas.py`: indexing/search request and response DTOs.
- `backend/src/content_retrieval/api/routes/indexing.py`: indexing job endpoints.
- `backend/src/content_retrieval/api/routes/search.py`: synchronous local search endpoint.
- `backend/src/content_retrieval/api/app.py`: dependency injection and route registration.
- `model-tools/benchmark_week4_pipeline.py`: real Chroma-backed NQ/COCO evaluation.
- `docs/week4/evidence/*.json`: machine-readable verification evidence.
- `docs/week4/reports/*.docx`: API, E2E, benchmark, and weekly reports.

### Task 1: Freeze Retrieval Contracts and Add Text Query Embeddings

**Files:**
- Create: `backend/src/content_retrieval/domain/retrieval.py`
- Modify: `backend/src/content_retrieval/domain/errors.py`
- Modify: `backend/src/content_retrieval/embeddings/text.py`
- Modify: `backend/src/content_retrieval/embeddings/service.py`
- Test: `backend/tests/test_retrieval_contracts.py`
- Test: `backend/tests/test_text_query_embeddings.py`

- [x] **Step 1: Write failing contract tests**

```python
def test_index_record_rejects_incompatible_vector() -> None:
    with pytest.raises(ValueError, match="source_id"):
        IndexRecord(source=chunk, vector=vector(source_id="f" * 64), path=path)


def test_search_filters_validate_time_range() -> None:
    with pytest.raises(ValueError, match="modified"):
        SearchFilters(modified_after=later, modified_before=earlier)
```

- [x] **Step 2: Run contract tests and verify RED**

Run:

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_retrieval_contracts.py
```

Expected: collection error because `content_retrieval.domain.retrieval` does not exist.

- [x] **Step 3: Implement immutable domain contracts**

Define:

```python
@dataclass(frozen=True, slots=True)
class IndexRecord:
    record_id: str
    source_id: str
    file_id: str
    source_key: str
    path: Path
    name: str
    mime_type: str
    modality: Literal["text", "image"]
    document: str
    vector: EmbeddingVector
    modified_at: datetime
    size_bytes: int
    page_number: int | None = None
    paragraph_number: int | None = None
    sequence_number: int = 0


@dataclass(frozen=True, slots=True)
class SearchFilters:
    mime_types: tuple[str, ...] = ()
    modalities: tuple[Literal["text", "image"], ...] = ()
    path_prefix: Path | None = None
    modified_after: datetime | None = None
    modified_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    file_id: str
    source_id: str
    path: Path
    name: str
    mime_type: str
    modality: Literal["text", "image"]
    score: float
    match_reasons: tuple[str, ...]
    snippet: str | None
    page_number: int | None
    paragraph_number: int | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    hits: tuple[SearchHit, ...]
    total_candidates: int
    elapsed_ms: float
    weights: dict[str, float]
```

Add `StorageError`, `IndexingError`, and `RetrievalError` with stable `code`, `stage`, and `retryable` fields.

- [x] **Step 4: Run contract tests and verify GREEN**

Run the Step 2 command. Expected: all tests pass.

- [x] **Step 5: Write failing text-query tests**

```python
def test_text_queries_use_text_semantic_space() -> None:
    result = TextEmbeddingEngine(FakeTextBackend()).embed_queries(["local search"])
    assert result.items[0].space_id == "text-semantic-v1"
    assert result.items[0].metadata["source_kind"] == "query"


def test_unified_service_exposes_text_queries(service) -> None:
    assert service.embed_text_queries(["notes"]).items[0].space_id == "text-semantic-v1"
```

- [x] **Step 6: Run query tests and verify RED**

Run:

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_text_query_embeddings.py
```

Expected: `AttributeError` for the missing `embed_queries`/`embed_text_queries` methods.

- [x] **Step 7: Implement query embedding**

Normalize query whitespace, reject blank queries as `EmbeddingError`, derive a deterministic SHA-256 query ID from `model_id + "\0" + query`, batch through the same backend, validate dimensions/finite values, and emit normalized `EmbeddingVector` objects with `source_kind="query"`.

- [x] **Step 8: Run focused and existing embedding tests**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_text_query_embeddings.py backend/tests/test_text_embeddings.py backend/tests/test_multimodal_embedding_service.py
```

Expected: all selected tests pass.

- [x] **Step 9: Commit Task 1**

```powershell
git add backend/src/content_retrieval/domain/retrieval.py backend/src/content_retrieval/domain/errors.py backend/src/content_retrieval/embeddings/text.py backend/src/content_retrieval/embeddings/service.py backend/tests/test_retrieval_contracts.py backend/tests/test_text_query_embeddings.py
git commit -m "feat: freeze week 4 retrieval contracts"
```

### Task 2: Implement the Persistent Chroma Repository

**Files:**
- Create: `backend/src/content_retrieval/storage/__init__.py`
- Create: `backend/src/content_retrieval/storage/chroma.py`
- Test: `backend/tests/test_chroma_repository.py`

- [ ] **Step 1: Write failing repository tests**

Cover:

```python
def test_upsert_survives_repository_restart(tmp_path: Path) -> None:
    first = ChromaVectorRepository(tmp_path / "index")
    first.upsert([record])
    second = ChromaVectorRepository(tmp_path / "index")
    assert second.get(record.record_id) == record


def test_repository_keeps_embedding_spaces_isolated(tmp_path: Path) -> None:
    repository.upsert([text_record, image_record])
    assert repository.query(text_query, limit=10)[0].record.space_id == text_query.space_id


def test_delete_source_removes_stale_records_only(tmp_path: Path) -> None:
    assert repository.delete_source(source_key) == 2
    assert repository.count() == 1
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_chroma_repository.py
```

Expected: import failure because the storage module does not exist.

- [ ] **Step 3: Implement collection and metadata mapping**

Use `chromadb.PersistentClient`. Create one collection per `space_id` with cosine distance and `embedding_function=None`. Flatten only scalar metadata; serialize timestamps as epoch seconds; store the chunk text in `documents`; never delete the database on startup.

- [ ] **Step 4: Implement repository operations**

Provide:

```python
def upsert(self, records: Iterable[IndexRecord]) -> int: ...
def get(self, record_id: str) -> IndexRecord | None: ...
def list_records(self) -> list[IndexRecord]: ...
def query(self, vector: EmbeddingVector, *, limit: int, filters: SearchFilters) -> list[VectorCandidate]: ...
def delete_source(self, source_key: str) -> int: ...
def clear(self) -> int: ...
def count(self) -> int: ...
```

Convert Chroma cosine distance with `similarity = max(-1.0, min(1.0, 1.0 - distance))`. Reject non-normalized vectors, wrong dimensions, and collection metadata mismatches before writing.

- [ ] **Step 5: Run repository tests and full storage regression**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_chroma_repository.py
```

Expected: all tests pass without creating repository data outside `tmp_path`.

- [ ] **Step 6: Commit Task 2**

```powershell
git add backend/src/content_retrieval/storage backend/tests/test_chroma_repository.py
git commit -m "feat: add persistent Chroma vector repository"
```

### Task 3: Build the End-to-End Indexing Pipeline

**Files:**
- Create: `backend/src/content_retrieval/services/indexing.py`
- Test: `backend/tests/test_indexing_service.py`

- [ ] **Step 1: Write failing indexing tests**

Cover text chunk pairing, image records, partial embedding failures, idempotent repeated indexing, and same-path changed-content replacement:

```python
def test_index_paths_persists_text_and_image_records(tmp_path: Path) -> None:
    result = service.index_paths([text_path, image_path], authorized_roots=[tmp_path])
    assert result.indexed_files == 2
    assert repository.count() == 2


def test_changed_file_replaces_records_for_same_source_key(tmp_path: Path) -> None:
    first = service.index_paths([path], authorized_roots=[tmp_path])
    path.write_text("changed", encoding="utf-8")
    second = service.index_paths([path], authorized_roots=[tmp_path])
    assert second.removed_stale_records == first.indexed_records
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_indexing_service.py
```

Expected: import failure for `IndexingService`.

- [ ] **Step 3: Implement deterministic source identity**

Resolve the path, apply `os.path.normcase`, encode as UTF-8, and hash with SHA-256. Use the path hash as `source_key`; use the existing content hash as `file_id`. Before writing a changed file, delete records sharing `source_key` but carrying a different `file_id`.

- [ ] **Step 4: Implement text and image record construction**

For text/document inputs, call `TextChunker.chunk`, embed those exact chunks, and pair vectors by `source_id`. For image inputs, call `MobileClipEmbeddingEngine.embed_images`. Preserve name, path, MIME, modification time, size, page/paragraph locator, and sequence number.

- [ ] **Step 5: Implement batch summaries and partial failure isolation**

Return `IndexingResult` counters for parsed, indexed files, indexed records, skipped, failed, unchanged, and removed stale records. Convert per-file failures into controlled stage-aware entries while continuing the batch.

- [ ] **Step 6: Run indexing tests and relevant regressions**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_indexing_service.py backend/tests/test_batch_ingestion.py backend/tests/test_chunking_contracts.py backend/tests/test_text_embeddings.py backend/tests/test_mobileclip_embeddings.py
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add backend/src/content_retrieval/services/indexing.py backend/tests/test_indexing_service.py
git commit -m "feat: connect ingestion embeddings and storage"
```

### Task 4: Implement Keyword Search and Rank Fusion

**Files:**
- Create: `backend/src/content_retrieval/retrieval/__init__.py`
- Create: `backend/src/content_retrieval/retrieval/keyword.py`
- Create: `backend/src/content_retrieval/retrieval/fusion.py`
- Test: `backend/tests/test_keyword_retrieval.py`
- Test: `backend/tests/test_rank_fusion.py`

- [ ] **Step 1: Write failing keyword tests**

Test Unicode/case normalization, matching filename/path/body, BM25 ordering, MIME/path/time filters, and deterministic tie breaks.

- [ ] **Step 2: Run keyword tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_keyword_retrieval.py
```

Expected: missing retrieval package.

- [ ] **Step 3: Implement deterministic BM25**

Tokenize with case-folded Unicode word runs, preserve CJK single characters and contiguous Latin/digit words, index `name + path + document`, and use BM25 parameters `k1=1.5`, `b=0.75`. Apply `SearchFilters` before ranking and sort equal scores by normalized path then record ID.

- [ ] **Step 4: Verify keyword GREEN**

Run Step 2. Expected: all keyword tests pass.

- [ ] **Step 5: Write failing fusion tests**

```python
def test_fusion_aggregates_chunks_before_combining_channels() -> None:
    result = weighted_rrf({"keyword": keyword, "text_semantic": semantic}, weights)
    assert [item.file_id for item in result] == [expected_file, other_file]
    assert len({item.file_id for item in result}) == len(result)
```

Also prove that image and text raw similarity scores are never directly added.

- [ ] **Step 6: Run fusion tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_rank_fusion.py
```

Expected: missing fusion function.

- [ ] **Step 7: Implement file-level weighted RRF**

For each channel, keep the best source record per file. Calculate:

```python
rrf_score = sum(weight / (60 + rank) for channel, rank in ranks.items())
normalized = rrf_score / sum(weight / 61 for weight in active_weights)
```

Keep match reasons, the best text snippet/locator, and deterministic file-level ordering.

- [ ] **Step 8: Run keyword and fusion suites**

Expected: all tests pass.

- [ ] **Step 9: Commit Task 4**

```powershell
git add backend/src/content_retrieval/retrieval backend/tests/test_keyword_retrieval.py backend/tests/test_rank_fusion.py
git commit -m "feat: add keyword ranking and reciprocal rank fusion"
```

### Task 5: Implement Multimodal Retrieval Service

**Files:**
- Create: `backend/src/content_retrieval/retrieval/service.py`
- Test: `backend/tests/test_retrieval_service.py`

- [ ] **Step 1: Write failing retrieval-service tests**

Cover keyword-only, text semantic, text-to-image, all-channel fusion, filters, empty query rejection, repository errors, and duplicate chunk aggregation.

- [ ] **Step 2: Run tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_retrieval_service.py
```

Expected: missing `RetrievalService`.

- [ ] **Step 3: Implement search orchestration**

Use default channel weights:

```python
{"keyword": 0.35, "text_semantic": 1.0, "image_semantic": 0.85}
```

Rebuild the in-memory BM25 index from `repository.list_records()` at startup and after successful indexing. Query text and image spaces independently, aggregate each channel by `file_id`, fuse rankings, truncate to `top_k`, and record monotonic elapsed time.

- [ ] **Step 4: Run retrieval suite and all new core tests**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_retrieval_service.py backend/tests/test_chroma_repository.py backend/tests/test_keyword_retrieval.py backend/tests/test_rank_fusion.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/src/content_retrieval/retrieval/service.py backend/tests/test_retrieval_service.py
git commit -m "feat: add multimodal hybrid retrieval service"
```

### Task 6: Expose Indexing and Search through FastAPI

**Files:**
- Modify: `backend/src/content_retrieval/api/schemas.py`
- Create: `backend/src/content_retrieval/api/routes/indexing.py`
- Create: `backend/src/content_retrieval/api/routes/search.py`
- Modify: `backend/src/content_retrieval/api/routes/__init__.py`
- Modify: `backend/src/content_retrieval/api/app.py`
- Test: `backend/tests/test_week4_api.py`

- [ ] **Step 1: Write failing API tests**

Test:

```python
response = client.post("/v1/indexing/jobs", json=payload)
assert response.status_code == 202

response = client.post("/v1/search", json={"query": "local notes", "top_k": 5})
assert response.status_code == 200
assert response.json()["hits"][0]["match_reasons"]
```

Also cover invalid top-k, blank query, filters, unknown jobs, and controlled `503` when runtime services are unavailable.

- [ ] **Step 2: Run API tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_week4_api.py
```

Expected: routes return 404.

- [ ] **Step 3: Add DTOs and route handlers**

Expose:

- `POST /v1/indexing/jobs`
- `GET /v1/indexing/jobs/{job_id}`
- `POST /v1/search`
- `GET /v1/index/stats`

Keep indexing in `asyncio.to_thread`; never block the event loop with parsing, model inference, or Chroma calls.

- [ ] **Step 4: Extend application dependency injection**

Accept optional `indexing_service` and `retrieval_service` in `create_app`. Register week-four routes without breaking existing health and ingestion routes. If runtime services are not configured, return a stable `SERVICE_UNAVAILABLE` response instead of importing models or accessing the network.

- [ ] **Step 5: Run API and legacy API suites**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_week4_api.py backend/tests/test_api.py backend/tests/test_api_extended.py
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 6**

```powershell
git add backend/src/content_retrieval/api backend/tests/test_week4_api.py
git commit -m "feat: expose indexing and hybrid search APIs"
```

### Task 7: Verify the Real End-to-End MVP and Retrieval Quality

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Create: `backend/src/content_retrieval/runtime.py`
- Create: `backend/tests/test_runtime_factory.py`
- Create: `backend/tests/test_week4_e2e.py`
- Create: `model-tools/benchmark_week4_pipeline.py`
- Create: `model-tools/test_benchmark_week4_pipeline.py`
- Create: `docs/week4/evidence/e2e-summary.json`
- Create: `docs/week4/evidence/retrieval-benchmark-summary.json`
- Create: `docs/week4/evidence/performance-summary.json`

- [ ] **Step 1: Write failing runtime factory tests**

Prove that the factory requires local model paths, validates the model manifest, creates persistent services under an explicit local data directory, and never downloads models.

- [ ] **Step 2: Run factory tests and verify RED**

Expected: missing runtime factory.

- [ ] **Step 3: Add explicit local ML runtime dependencies**

Add `sentence-transformers>=5,<6`, `mobileclip`, and the local `tool.uv.sources.mobileclip` path already used by `model-tools`. Update the lock file with `uv lock --project backend`, then synchronize the backend environment.

- [ ] **Step 4: Implement runtime factory**

Load `models/model-manifest.json`, validate hashes through `ModelManifest`, construct `SentenceTransformerBackend`, `LocalMobileClipBackend`, `TextChunker`, `ChromaVectorRepository`, `IndexingService`, and `RetrievalService`. Require all paths through explicit arguments or environment variables; do not use network fallback.

- [ ] **Step 5: Run focused runtime tests and real local smoke**

Index one TXT, one PDF, one DOCX, one JPG, and one PNG from controlled fixtures. Search one exact keyword, one text-semantic query, and one image-description query. Restart the repository and repeat one search.

- [ ] **Step 6: Implement actual Chroma-backed benchmarks**

Reuse frozen Week 3 NQ and COCO splits, but route corpus vectors through `ChromaVectorRepository` and all queries through the Week 4 retrieval path. Emit Recall@1/5/10, MRR@10, nDCG@10, median rank, query counts, collection sizes, model IDs, space IDs, and source hashes.

- [ ] **Step 7: Record performance**

Populate a deterministic 10,000-record synthetic Chroma collection, warm it, execute at least 50 queries, and report P50/P95/maximum latency plus device and dependency versions. Treat the PRD target `P95 <= 2 seconds` as the pass gate.

- [ ] **Step 8: Run full verification**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend --cov=content_retrieval.storage --cov=content_retrieval.retrieval --cov=content_retrieval.services.indexing --cov-fail-under=85
```

Expected: all tests pass, one pre-existing skip remains documented, and new Week 4 core coverage is at least 85%.

- [ ] **Step 9: Commit Task 7**

Stage only the runtime, benchmark, tests, lock/config changes, and machine-readable evidence. Never stage model weights, databases, dataset binaries, virtual environments, caches, or user documents.

### Task 8: Produce and Validate Week 4 Deliverables

**Files:**
- Create: `docs/week4/README.md`
- Create: `docs/week4/reports/向量存储与检索模块API文档.docx`
- Create: `docs/week4/reports/端到端功能测试报告.docx`
- Create: `docs/week4/reports/检索准确率基准报告.docx`
- Create: `docs/week4/reports/第四周工作周报.docx`

- [ ] **Step 1: Build reports from verified evidence only**

Use Times New Roman throughout, black text/lines, white page/table backgrounds, and no internal source list in the weekly report. Include exact commands, counts, metrics, failure boundaries, and known limitations.

- [ ] **Step 2: Render every DOCX to page images**

Use the documents skill renderer. If LibreOffice is unavailable, export read-only with Microsoft Word and rasterize with the bundled Poppler executable.

- [ ] **Step 3: Inspect every page at 100%**

Check clipping, table wrapping, headings, page numbers, captions, fonts, and whitespace. Rebuild and re-render after any correction.

- [ ] **Step 4: Audit deliverable consistency**

Verify that every number in the DOCX files matches `docs/week4/evidence/*.json` and the final fresh test outputs.

- [ ] **Step 5: Commit Task 8**

```powershell
git add docs/week4
git commit -m "docs: publish week 4 retrieval deliverables"
```

## Plan self-review

- Spec coverage: Chroma persistence, keyword + semantic retrieval, ranking, filters, full pipeline, E2E testing, NQ/COCO accuracy, latency, offline behavior, and formal deliverables each have an implementation task.
- Scope control: Flutter UI, OCR, release packaging, cloud sync, arbitrary file-opening routes, and deep Week 6 performance tuning are excluded.
- Type consistency: `IndexRecord`, `SearchFilters`, `SearchHit`, `SearchResult`, `VectorCandidate`, `IndexingResult`, `ChromaVectorRepository`, `IndexingService`, and `RetrievalService` are introduced once and reused consistently.
- Safety: all Chroma tests use `tmp_path`; production startup never removes an index directory; model/data binaries remain untracked.
