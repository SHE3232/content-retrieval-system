# UI Backend Index Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add file-level pagination, delete, forced reindex, and indexing-failure detail contracts required by the UI.

**Architecture:** Introduce a small `IndexCatalogService` that projects record-level Chroma data into stable `source_key` file views. Keep HTTP orchestration in the indexing routes, reuse the existing indexing job store for forced reindex, and extend jobs with safe task-level diagnostics.

**Tech Stack:** Python 3.10, FastAPI, Pydantic 2, ChromaDB, pytest, httpx ASGI transport.

---

## File Structure

- Create `backend/src/content_retrieval/services/index_catalog.py`: file aggregation, deterministic pagination, lookup, and deletion.
- Create `backend/tests/test_index_catalog.py`: focused service tests with real `IndexRecord` objects and a fake repository.
- Modify `backend/src/content_retrieval/services/indexing.py`: add opt-in forced indexing without changing default incremental behavior.
- Modify `backend/tests/test_indexing_service.py`: prove force bypasses unchanged detection.
- Modify `backend/src/content_retrieval/services/indexing_jobs.py`: retain safe job-level error details.
- Modify `backend/tests/test_week4_api.py`: preserve existing task-store/API behavior and cover job error conversion where appropriate.
- Modify `backend/src/content_retrieval/api/schemas.py`: add UI response schemas.
- Modify `backend/src/content_retrieval/api/routes/indexing.py`: add the four UI endpoints and structured storage errors.
- Modify `backend/src/content_retrieval/api/app.py`: accept an injectable catalog service and include the file-management router.
- Create `backend/tests/test_ui_index_api.py`: end-to-end ASGI contract tests for success, validation, and error paths.

### Task 1: File-level catalog projection

**Files:**
- Create: `backend/tests/test_index_catalog.py`
- Create: `backend/src/content_retrieval/services/index_catalog.py`

- [ ] **Step 1: Write failing aggregation and pagination tests**

Create a fake repository with `list_records()` and `delete_source()`, build real
`IndexRecord` values, and assert the wished-for API:

```python
catalog = IndexCatalogService(repository)
page = catalog.list_files(page=1, page_size=1)

assert page.total == 2
assert page.total_pages == 2
assert page.items[0].source_key == first_source_key
assert page.items[0].record_count == 2
assert catalog.list_files(page=3, page_size=1).items == ()
```

Add a second test with two `file_id` values under one `source_key` and assert that
the newest `modified_at` supplies `file_id`, name, MIME type, modality, size, and
path while `record_count` includes all records. Add validation assertions for
`page < 1` and `page_size` outside 1 through 100.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_index_catalog.py
```

Expected: collection fails because `content_retrieval.services.index_catalog`
does not exist.

- [ ] **Step 3: Implement the minimal catalog service**

Define immutable `IndexedFile` and `IndexedFilePage` dataclasses and the service:

```python
@dataclass(frozen=True, slots=True)
class IndexedFile:
    source_key: str
    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    size_bytes: int
    modified_at: datetime
    record_count: int


@dataclass(frozen=True, slots=True)
class IndexedFilePage:
    items: tuple[IndexedFile, ...]
    page: int
    page_size: int
    total: int
    total_pages: int


class IndexCatalogService:
    def __init__(self, repository: ChromaVectorRepository) -> None:
        self.repository = repository

    def list_files(self, *, page: int, page_size: int) -> IndexedFilePage:
        self._validate_page(page, page_size)
        files = self._list_all_files()
        start = (page - 1) * page_size
        total = len(files)
        return IndexedFilePage(
            items=tuple(files[start : start + page_size]),
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_file(self, source_key: str) -> IndexedFile | None:
        return next(
            (item for item in self._list_all_files()
             if item.source_key == source_key),
            None,
        )

    def delete_file(self, source_key: str) -> int | None:
        if self.get_file(source_key) is None:
            return None
        return self.repository.delete_source(source_key)
```

`_list_all_files()` must group `repository.list_records()` by `source_key`, use
`max(records, key=lambda record: (record.modified_at, record.file_id))` as the
representative, and sort with
`(item.path.as_posix().casefold(), item.source_key)`.

- [ ] **Step 4: Run the service tests and verify GREEN**

Run the command from Step 2. Expected: all catalog tests pass.

- [ ] **Step 5: Commit the catalog unit**

```powershell
git add backend/src/content_retrieval/services/index_catalog.py backend/tests/test_index_catalog.py
git commit -m "feat: add indexed file catalog"
```

### Task 2: Forced single-file indexing behavior

**Files:**
- Modify: `backend/tests/test_indexing_service.py`
- Modify: `backend/src/content_retrieval/services/indexing.py`

- [ ] **Step 1: Write a failing force-reindex test**

Reuse the existing indexing fixture and first index one document. Index it again
with `force=True` and assert that embedding and upsert counts increase while the
result reports an indexed file rather than an unchanged file:

```python
first = service.index_paths([source])
second = service.index_paths([source], force=True)

assert first.indexed_files == 1
assert second.indexed_files == 1
assert second.unchanged_files == 0
assert repository.upsert_calls == 2
```

Keep the existing unchanged-file test unchanged to prove the default remains
incremental.

- [ ] **Step 2: Run the new test and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_indexing_service.py -k "force or unchanged"
```

Expected: failure because `index_paths()` does not accept `force`.

- [ ] **Step 3: Implement the opt-in flag**

Change the public signature and only bypass the unchanged branch when forced:

```python
def index_paths(
    self,
    paths: list[Path | str],
    *,
    recursive: bool = True,
    authorized_roots: list[Path | str] | None = None,
    force: bool = False,
) -> IndexingResult:
    ...
    if not force and self._is_unchanged(document, existing):
        unchanged_files += 1
        continue
```

Do not alter parsing, upsert, or stale-record deletion order.

- [ ] **Step 4: Verify focused and complete indexing tests**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_indexing_service.py
```

Expected: all indexing-service tests pass.

- [ ] **Step 5: Commit forced indexing**

```powershell
git add backend/src/content_retrieval/services/indexing.py backend/tests/test_indexing_service.py
git commit -m "feat: support forced file reindexing"
```

### Task 3: Safe task-level failure diagnostics

**Files:**
- Modify: `backend/src/content_retrieval/services/indexing_jobs.py`
- Modify: `backend/tests/test_week4_api.py`

- [ ] **Step 1: Write failing error-conversion and storage tests**

Assert controlled processing errors retain their public contract and unexpected
errors are sanitized:

```python
controlled = IndexingJobError.from_exception(
    StorageError("local index is locked")
)
unexpected = IndexingJobError.from_exception(RuntimeError("secret detail"))

assert controlled == IndexingJobError(
    code="STORAGE_ERROR",
    message="local index is locked",
    retryable=True,
)
assert unexpected == IndexingJobError(
    code="INDEXING_JOB_FAILED",
    message="Indexing job failed unexpectedly",
    retryable=True,
)
```

Create a job, call `store.fail(job_id, controlled)`, and assert status `failed`,
`result is None`, and `error == controlled`.

- [ ] **Step 2: Run the tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_week4_api.py -k "job_error or task_failure"
```

Expected: import or attribute failure because `IndexingJobError` is absent.

- [ ] **Step 3: Add the immutable error model to the store**

```python
@dataclass(frozen=True, slots=True)
class IndexingJobError:
    code: str
    message: str
    retryable: bool

    @classmethod
    def from_exception(cls, error: Exception) -> IndexingJobError:
        if isinstance(error, ProcessingError):
            return cls(
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        return cls(
            code="INDEXING_JOB_FAILED",
            message="Indexing job failed unexpectedly",
            retryable=True,
        )
```

Add `error: IndexingJobError | None = None` to `IndexingJob`. Extend `_replace`
and `fail` so failure stores the supplied error, while running and completed
transitions leave `error=None`.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: the new task-error tests pass.

- [ ] **Step 5: Commit job diagnostics**

```powershell
git add backend/src/content_retrieval/services/indexing_jobs.py backend/tests/test_week4_api.py
git commit -m "feat: retain safe indexing job errors"
```

### Task 4: UI HTTP contracts

**Files:**
- Create: `backend/tests/test_ui_index_api.py`
- Modify: `backend/src/content_retrieval/api/schemas.py`
- Modify: `backend/src/content_retrieval/api/routes/indexing.py`
- Modify: `backend/src/content_retrieval/api/app.py`

- [ ] **Step 1: Write failing file-list and delete API tests**

Inject a fake catalog through `create_app(index_catalog_service=...)`. Assert:

```python
response = await client.get("/v1/index/files?page=2&page_size=1")
assert response.status_code == 200
assert response.json()["page"] == 2
assert response.json()["items"][0]["source_key"] == source_key
assert catalog.list_calls == [(2, 1)]

deleted = await client.delete(f"/v1/index/files/{source_key}")
assert deleted.json() == {
    "source_key": source_key,
    "deleted_records": 2,
}
assert retrieval.refresh_calls == 1
```

Also assert invalid page values and invalid `source_key` return `422`, an unknown
source returns `404 FILE_NOT_INDEXED`, and a catalog `StorageError` returns
`503 STORAGE_UNAVAILABLE`.

- [ ] **Step 2: Run list/delete tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_ui_index_api.py -k "list or delete"
```

Expected: collection or call failure because the injection argument, schemas,
and routes do not exist.

- [ ] **Step 3: Add file response schemas and list/delete routes**

Add Pydantic models using `ConfigDict(from_attributes=True)`:

```python
class IndexedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_key: str
    file_id: str
    path: Path
    name: str
    mime_type: str
    modality: SearchModality
    size_bytes: int
    modified_at: datetime
    record_count: int


class IndexedFilePageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[IndexedFileResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class DeletedIndexedFileResponse(BaseModel):
    source_key: str
    deleted_records: int
```

Create a second router in `indexing.py` with prefix `/v1/index`. Use FastAPI
`Query(ge=1)` and `Query(default=20, ge=1, le=100)`, validate source keys with
`Path(pattern="^[0-9a-f]{64}$")`, call the catalog through `asyncio.to_thread`,
and translate `StorageError` to the stable 503 response. Include the second
router in `create_app` and store the optional injected catalog service on app
state. `_require_index_catalog_service` may lazily construct the catalog from
`app.state.indexing_service.repository` for the production lifespan.

- [ ] **Step 4: Run list/delete tests and verify GREEN**

Run the command from Step 2. Expected: list/delete contract tests pass.

- [ ] **Step 5: Write failing forced-reindex API tests**

Return an `IndexedFile` from the fake catalog whose path exists. POST the reindex
endpoint, poll the existing job endpoint, and assert:

```python
assert created.status_code == 202
assert completed["status"] == "completed"
assert indexing.calls == [
    ([source], False, [source.parent], True),
]
assert retrieval.refresh_calls == 1
```

Also cover `FILE_NOT_INDEXED` and `SOURCE_FILE_NOT_FOUND` 404 responses.

- [ ] **Step 6: Run reindex tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_ui_index_api.py -k reindex
```

Expected: `404` because the endpoint is absent.

- [ ] **Step 7: Implement reindex task creation**

Refactor `_run_job` to accept `force: bool = False`. Preserve the current call
shape for ordinary jobs; when forced, call:

```python
service.index_paths(
    payload.paths,
    recursive=payload.recursive,
    authorized_roots=payload.authorized_roots,
    force=True,
)
```

Catch `Exception as error` and call
`store.fail(job_id, IndexingJobError.from_exception(error))`. The reindex route
loads the indexed file, checks `indexed_file.path.is_file()`, builds
`CreateIndexingJobRequest(paths=[path], authorized_roots=[path.parent],
recursive=False)`, and schedules `_run_job(..., force=True)`.

- [ ] **Step 8: Run reindex tests and verify GREEN**

Run the command from Step 6. Expected: all reindex tests pass.

- [ ] **Step 9: Write failing failure-detail API tests**

Populate the app job store with a completed `IndexingResult` containing one
`IndexingFailure`; assert the endpoint returns status, total, full file failure,
and `error: null`. Populate another job with `IndexingJobError` and assert a
failed response returns `failures: []` and the task error. Assert an unknown job
returns the existing structured `JOB_NOT_FOUND` 404.

- [ ] **Step 10: Run failure-detail tests and verify RED**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_ui_index_api.py -k failures
```

Expected: `404` because the endpoint is absent.

- [ ] **Step 11: Add failure schemas and endpoint**

```python
class IndexingJobErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    message: str
    retryable: bool


class IndexingFailuresResponse(BaseModel):
    job_id: str
    status: IndexingJobStatus
    total: int
    failures: list[IndexingFailureResponse]
    error: IndexingJobErrorResponse | None = None
```

Add `GET /jobs/{job_id}/failures` to the existing `/v1/indexing` router. Read the
job once, return `job.result.failures` when present, and serialize `job.error`.

- [ ] **Step 12: Run all new API tests and existing Week 4 API tests**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_ui_index_api.py backend/tests/test_week4_api.py
```

Expected: all tests pass without warnings or errors.

- [ ] **Step 13: Commit the HTTP contracts**

```powershell
git add backend/src/content_retrieval/api/app.py backend/src/content_retrieval/api/schemas.py backend/src/content_retrieval/api/routes/indexing.py backend/tests/test_ui_index_api.py
git commit -m "feat: expose UI index management APIs"
```

### Task 5: Contract and regression verification

**Files:**
- Verify all modified source, tests, specification, and plan files.

- [ ] **Step 1: Run the focused feature suite**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_index_catalog.py backend/tests/test_indexing_service.py backend/tests/test_ui_index_api.py backend/tests/test_week4_api.py
```

Expected: zero failures and zero errors.

- [ ] **Step 2: Run the complete repository suite**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q
```

Expected: zero failures; existing dependency-gated tests may remain skipped.

- [ ] **Step 3: Validate OpenAPI routes and schema names**

```powershell
Push-Location backend
$env:PYTHONPATH = "src"
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -c "from content_retrieval.api.app import create_app; app=create_app(); paths=app.openapi()['paths']; required={'/v1/index/files','/v1/index/files/{source_key}','/v1/index/files/{source_key}/reindex','/v1/indexing/jobs/{job_id}/failures'}; assert required <= paths.keys(); print('OpenAPI UI contracts present')"
Pop-Location
```

Expected: `OpenAPI UI contracts present` and exit code 0.

- [ ] **Step 4: Audit diff quality and repository boundaries**

```powershell
git diff master...HEAD --check
git status --short
git diff master...HEAD --name-status
```

Expected: no whitespace errors, no unintended local artifacts, and only the
planned source, test, specification, and plan files.

- [ ] **Step 5: Run a clean-commit verification**

Create a temporary detached worktree at the exact final commit, run the complete
suite there with the shared backend interpreter, then remove only that verified
temporary worktree. Expected: the committed snapshot passes independently of
untracked files in the development worktree.

## Initial Plan Self-Review

- Spec coverage: every endpoint, stable identifier, force behavior, structured
  error, pagination rule, refresh, and verification requirement maps to a task.
- Placeholder scan: the plan contains no deferred implementation markers.
- Type consistency: `IndexedFile`, `IndexedFilePage`, `IndexCatalogService`,
  `IndexingJobError`, `force`, and all schema field names are consistent across
  service, route, and test steps.
- Scope remains limited to the approved UI backend contracts; no persistent job
  database, batch management, file deletion, or UI code is introduced.

### Task 6: Review-driven mutation safety hardening

**Files:**
- Modify: `backend/src/content_retrieval/services/index_catalog.py`
- Modify: `backend/src/content_retrieval/services/indexing.py`
- Modify: `backend/src/content_retrieval/retrieval/service.py`
- Modify: `backend/src/content_retrieval/api/app.py`
- Modify: `backend/src/content_retrieval/api/routes/indexing.py`
- Modify: `backend/src/content_retrieval/mvp.py`
- Test: `backend/tests/test_index_catalog.py`
- Test: `backend/tests/test_indexing_service.py`
- Test: `backend/tests/test_retrieval_service.py`
- Test: `backend/tests/test_ui_index_api.py`
- Test: `backend/tests/test_mvp_runtime.py`

- [ ] **Step 1: Preserve old records on partial forced reindex**

Add a regression test that starts with two valid records, forces a reindex with
one successful and one failed chunk, and expects all old records plus the new
successful record. Skip stale deletion whenever per-item failures exist.

- [ ] **Step 2: Reject overlapping index mutations**

Add a lock-protected process-local coordinator with one global mutation key.
Require the claim for ordinary indexing jobs, delete, and forced reindex, and hold
it through persistent mutation and search refresh. Return
`409 INDEX_MUTATION_CONFLICT` when another index mutation owns the claim.

- [ ] **Step 3: Make retrieval refresh failure explicit and safe**

Require a retrieval runtime before delete or reindex. Add
`RetrievalService.invalidate()` to clear only the volatile keyword catalog. If a
post-delete refresh raises `RetrievalError`, invalidate it and return
`503 RETRIEVAL_UNAVAILABLE` with a message that persistent deletion succeeded.

- [ ] **Step 4: Rebind the catalog across MVP lifespans**

Construct `IndexCatalogService(runtime.repository)` during each lifespan startup
and clear it after background work drains, before closing the runtime.

- [ ] **Step 5: Verify safety regressions**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_index_catalog.py backend/tests/test_indexing_service.py backend/tests/test_retrieval_service.py backend/tests/test_ui_index_api.py backend/tests/test_mvp_runtime.py backend/tests/test_week4_api.py
```

Expected: zero failures and errors, including partial reindex, missing runtime,
refresh invalidation, mutation conflict, active-job failure details, and repeated
MVP lifespan coverage.

## Final Plan Self-Review

- Review findings are mapped to Task 6 with concrete regression tests and stable
  HTTP behavior.
- The mutation claim is process-local and global by design; serial execution is
  acceptable for the local MVP and prevents stale global keyword snapshots
  without adding a persistent job database.
- The refresh-failure response distinguishes committed deletion from a fully
  rejected request, while invalidation prevents stale keyword results.
