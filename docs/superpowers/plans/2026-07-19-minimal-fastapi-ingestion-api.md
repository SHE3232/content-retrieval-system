# Minimal FastAPI Ingestion API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal FastAPI service that accepts authorized mixed local file/directory paths, parses them asynchronously in memory, and exposes health and job-polling endpoints.

**Architecture:** Extend `BatchIngestionService` so all path expansion, authorization, path deduplication, content deduplication, and parsing happen behind one `parse_paths()` boundary. Add a thread-safe in-memory job store and small FastAPI application factory; route handlers create an asyncio task that calls the synchronous parser through `asyncio.to_thread()`, then expose a serialized snapshot to Flutter.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, asyncio, standard-library threading/dataclasses/pathlib, pytest, FastAPI TestClient.

---

## File map

- Modify `backend/src/content_retrieval/domain/errors.py`: controlled path errors.
- Modify `backend/src/content_retrieval/domain/models.py`: represent directory-discovered unsupported files as skipped items.
- Modify `backend/src/content_retrieval/services/batch_ingestion.py`: mixed path expansion, authorization, real-path and SHA-256 deduplication.
- Modify `backend/tests/test_batch_ingestion.py`: service-level red/green coverage.
- Create `backend/src/content_retrieval/services/ingestion_jobs.py`: thread-safe in-memory job state.
- Create `backend/src/content_retrieval/api/__init__.py`: API package boundary.
- Create `backend/src/content_retrieval/api/app.py`: application factory and default app.
- Create `backend/src/content_retrieval/api/schemas.py`: request and response DTOs.
- Create `backend/src/content_retrieval/api/routes/__init__.py`: routes package boundary.
- Create `backend/src/content_retrieval/api/routes/health.py`: liveness/readiness routes.
- Create `backend/src/content_retrieval/api/routes/ingestion.py`: create/query job routes and background runner.
- Create `backend/tests/test_api.py`: end-to-end API contract tests.

### Task 1: Mixed path parsing contract

**Files:**
- Modify: `backend/tests/test_batch_ingestion.py`
- Modify: `backend/src/content_retrieval/domain/errors.py`
- Modify: `backend/src/content_retrieval/domain/models.py`
- Modify: `backend/src/content_retrieval/services/batch_ingestion.py`

- [ ] **Step 1: Write failing tests for mixed file and directory expansion**

Append focused tests that create an explicit TXT file, a directory containing another TXT file and an unsupported `.bin`, then call:

```python
batch = service.parse_paths(
    [explicit, directory],
    authorized_roots=[tmp_path],
)

assert [item.path.name for item in batch.items] == [
    "explicit.txt",
    "nested.txt",
    "ignored.bin",
]
assert batch.succeeded == 2
assert batch.skipped == 1
assert batch.failed == 0
assert batch.total == 3
assert batch.skips[0].reason == "unsupported_format"
```

Also add a separate non-recursive test asserting nested children are omitted when `recursive=False`.

- [ ] **Step 2: Run the new expansion tests and verify RED**

Run:

```powershell
uv run pytest tests/test_batch_ingestion.py -k "mixed_paths or recursive" -v
```

Expected: FAIL because `BatchIngestionService` has no `parse_paths()` method.

- [ ] **Step 3: Implement the minimal expansion model**

Add these controlled errors in `domain/errors.py`:

```python
class PathNotFoundError(ParseError):
    code = "PATH_NOT_FOUND"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Path does not exist: {path}")


class PathNotAuthorizedError(ParseError):
    code = "PATH_NOT_AUTHORIZED"

    def __init__(self, path: Path) -> None:
        super().__init__(path, f"Path is outside the authorized roots: {path}")
```

Change `SkippedFile` so directory-discovered unsupported files are representable without fake hash data:

```python
SkipReason = Literal["duplicate_content", "unsupported_format"]


@dataclass(slots=True)
class SkippedFile:
    path: Path
    reason: SkipReason
    file_id: str | None = None
    duplicate_of: Path | None = None
```

Implement this public service shape:

```python
def parse_paths(
    self,
    paths: list[Path | str],
    *,
    recursive: bool = True,
    authorized_roots: list[Path | str] | None = None,
) -> BatchResult:
    roots = self._resolve_authorized_roots(authorized_roots)
    candidates = self._expand_paths(paths, recursive=recursive, roots=roots)
    return self._parse_candidates(candidates)
```

Use a small private candidate record containing `path` and `explicit`. Directory expansion must include all files in stable path order so unsupported entries can become `unsupported_format` skips; real paths are deduplicated before task-item creation. Preserve `scan_directory()` as a supported-file-only helper and rewrite `parse_directory()` as:

```python
def parse_directory(
    self, directory: Path | str, *, recursive: bool = True
) -> BatchResult:
    return self.parse_paths([directory], recursive=recursive)
```

- [ ] **Step 4: Run the expansion tests and verify GREEN**

Run the same targeted command. Expected: all selected tests PASS.

- [ ] **Step 5: Write failing tests for explicit errors and authorization**

Add separate tests asserting:

```python
assert batch.errors[0].code == "UNSUPPORTED_FORMAT"
assert missing_batch.errors[0].code == "PATH_NOT_FOUND"
assert unauthorized_batch.errors[0].code == "PATH_NOT_AUTHORIZED"
```

Use one explicit `.bin`, one missing path, and one existing file outside `authorized_roots`. Add a symlink/junction authorization test when the platform permits creating it; skip only on `OSError`/`NotImplementedError` from fixture setup.

- [ ] **Step 6: Run the error tests and verify RED**

Run:

```powershell
uv run pytest tests/test_batch_ingestion.py -k "unsupported or not_found or authorized" -v
```

Expected: at least the new path-error assertions FAIL because expansion does not yet convert those cases into `BatchItem` failures.

- [ ] **Step 7: Implement minimal path-error and authorization handling**

Resolve paths with `Path.expanduser().resolve(strict=True)`. Use `candidate.is_relative_to(root)` against resolved roots, never string prefix matching. Convert a missing requested path into `PathNotFoundError`; convert an input or expanded real path outside all roots into `PathNotAuthorizedError`. An explicitly supplied unsupported file must flow through `ParserRegistry.resolve()` and become `UNSUPPORTED_FORMAT`; a directory-discovered unsupported file must append a `SkippedFile(reason="unsupported_format")`.

- [ ] **Step 8: Run the targeted and existing batch tests**

Run:

```powershell
uv run pytest tests/test_batch_ingestion.py -v
```

Expected: all batch tests PASS.

- [ ] **Step 9: Write failing tests for path and content deduplication**

Add one test supplying the same real file both explicitly and through a directory, and assert it produces one item. Extend the existing duplicate-content assertion to verify two different real paths still produce two items and the later item has `reason == "duplicate_content"`, a SHA-256 `file_id`, and `duplicate_of` pointing to the first path.

- [ ] **Step 10: Run deduplication tests and verify RED if behavior is incomplete**

Run:

```powershell
uv run pytest tests/test_batch_ingestion.py -k "duplicate" -v
```

Expected: the new real-path duplicate test FAILS until path deduplication is applied during expansion; existing content deduplication remains green.

- [ ] **Step 11: Complete minimal deduplication and verify GREEN**

Track resolved paths in insertion order during expansion. Keep existing per-batch SHA-256 tracking during parsing. Run the full batch test file and expect all tests PASS.

- [ ] **Step 12: Commit the service slice**

Stage only the four task files and commit:

```powershell
git add backend/src/content_retrieval/domain/errors.py backend/src/content_retrieval/domain/models.py backend/src/content_retrieval/services/batch_ingestion.py backend/tests/test_batch_ingestion.py
git commit -m "feat: support mixed ingestion paths"
```

### Task 2: In-memory job state

**Files:**
- Create: `backend/src/content_retrieval/services/ingestion_jobs.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing job-store tests**

Create `test_api.py` with tests for a fresh queued job, running transition, successful completion, completion with item errors, and unknown lookup. The wished-for API is:

```python
store = InMemoryIngestionJobStore()
job = store.create()
store.mark_running(job.job_id)
store.complete(job.job_id, batch)
snapshot = store.get(job.job_id)
```

Assert each state transition replaces the previous frozen snapshot and status becomes `completed_with_errors` when `batch.failed > 0`, otherwise `completed`.

- [ ] **Step 2: Run store tests and verify RED**

Run:

```powershell
uv run pytest tests/test_api.py -k "job_store" -v
```

Expected: collection/import ERROR because `services.ingestion_jobs` does not exist.

- [ ] **Step 3: Implement the thread-safe store**

Create:

```python
JobStatus = Literal[
    "queued", "running", "completed", "completed_with_errors", "failed"
]

@dataclass(frozen=True, slots=True)
class IngestionJob:
    job_id: str
    status: JobStatus
    result: BatchResult | None = None


class InMemoryIngestionJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, IngestionJob] = {}
        self._lock = Lock()

    def create(self) -> IngestionJob:
        job = IngestionJob(job_id=str(uuid4()), status="queued")
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> IngestionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        self._replace(job_id, status="running")

    def complete(self, job_id: str, result: BatchResult) -> None:
        status = "completed_with_errors" if result.failed else "completed"
        self._replace(job_id, status=status, result=result)

    def fail(self, job_id: str) -> None:
        self._replace(job_id, status="failed")

    def _replace(
        self,
        job_id: str,
        *,
        status: JobStatus,
        result: BatchResult | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = replace(
                current,
                status=status,
                result=result,
            )
```

Import `replace` from `dataclasses`, `Lock` from `threading`, and `uuid4` from `uuid`. Replace frozen snapshots under the lock; never expose the mutable dictionary.

- [ ] **Step 4: Run job-store tests and verify GREEN**

Run the targeted test command. Expected: all selected tests PASS.

### Task 3: Health API and app factory

**Files:**
- Create: `backend/src/content_retrieval/api/__init__.py`
- Create: `backend/src/content_retrieval/api/app.py`
- Create: `backend/src/content_retrieval/api/routes/__init__.py`
- Create: `backend/src/content_retrieval/api/routes/health.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing health endpoint tests**

Use `with TestClient(create_app(service)) as client:` and assert exact payloads:

```python
assert client.get("/health/live").json() == {"status": "ok"}
assert client.get("/health/ready").json() == {"status": "ready"}
```

- [ ] **Step 2: Run health tests and verify RED**

Run:

```powershell
uv run pytest tests/test_api.py -k "health" -v
```

Expected: import ERROR because `content_retrieval.api.app` does not exist.

- [ ] **Step 3: Implement minimal health routes and application factory**

`health.py` defines an `APIRouter` with the two exact routes. Create `routes/ingestion.py` at this point with exactly `router = APIRouter(prefix="/v1/ingestion", tags=["ingestion"])` so the application factory has a stable import; Task 4 adds handlers to that router. `app.py` defines:

```python
def create_app(
    ingestion_service: BatchIngestionService | None = None,
) -> FastAPI:
    app = FastAPI(title="Content Retrieval API")
    app.state.ingestion_service = ingestion_service or BatchIngestionService(
        create_default_registry(),
        max_file_size_bytes=100 * 1024 * 1024,
    )
    app.state.job_store = InMemoryIngestionJobStore()
    app.state.background_tasks = set()
    app.state.ready = True
    app.include_router(health.router)
    app.include_router(ingestion.router)
    return app


app = create_app()
```

Health readiness reads `request.app.state.ready` and returns `503` only when false.

- [ ] **Step 4: Run health tests and verify GREEN**

Run the targeted command. Expected: both health tests PASS.

### Task 4: Asynchronous ingestion endpoints

**Files:**
- Create: `backend/src/content_retrieval/api/schemas.py`
- Create: `backend/src/content_retrieval/api/routes/ingestion.py`
- Modify: `backend/src/content_retrieval/api/app.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing POST/query happy-path test**

Build a real `BatchIngestionService` with the existing recording TXT parser, submit an absolute file and directory under `tmp_path`, and assert:

```python
created = client.post(
    "/v1/ingestion/jobs",
    json={
        "paths": [str(file_path), str(directory)],
        "authorized_roots": [str(tmp_path)],
        "recursive": True,
    },
)
assert created.status_code == 202
job_id = created.json()["job_id"]
```

Poll `GET /v1/ingestion/jobs/{job_id}` with a short bounded deadline until terminal. Assert status `completed`, correct count invariant, serialized path strings and ISO datetime values, and both parsed text results.

- [ ] **Step 2: Run happy-path API test and verify RED**

Run:

```powershell
uv run pytest tests/test_api.py -k "creates_and_queries" -v
```

Expected: FAIL with HTTP `404` because the ingestion routes do not exist.

- [ ] **Step 3: Implement request/response schemas**

Define non-empty request lists with Pydantic:

```python
class CreateIngestionJobRequest(BaseModel):
    paths: list[Path] = Field(min_length=1)
    authorized_roots: list[Path] = Field(min_length=1)
    recursive: bool = True
```

Add exact DTOs for `ParseResult`, controlled errors, skipped files, counts, creation response, and job response. Use `ConfigDict(from_attributes=True)` for dataclasses and standard Pydantic JSON serialization for `Path` and timezone-aware `datetime`.

- [ ] **Step 4: Implement the minimal background runner and routes**

`POST` creates a store entry, then schedules:

```python
async def run_ingestion_job(app: FastAPI, job_id: str, request: CreateIngestionJobRequest) -> None:
    store.mark_running(job_id)
    try:
        result = await asyncio.to_thread(
            service.parse_paths,
            request.paths,
            recursive=request.recursive,
            authorized_roots=request.authorized_roots,
        )
    except Exception:
        store.fail(job_id)
    else:
        store.complete(job_id, result)
```

Retain each `asyncio.create_task()` in `app.state.background_tasks` and discard it through a done callback. `GET` returns a serialized snapshot or raises:

```python
HTTPException(
    status_code=404,
    detail={"code": "JOB_NOT_FOUND", "message": "Ingestion job not found"},
)
```

- [ ] **Step 5: Run happy-path API test and verify GREEN**

Run the targeted test command. Expected: PASS.

- [ ] **Step 6: Write failing API edge-case tests**

Add independent tests for:

- unknown job returns `404` with `JOB_NOT_FOUND`;
- empty `paths` or `authorized_roots` returns `422` and creates no job;
- mixed success, `PATH_NOT_FOUND`, explicit `UNSUPPORTED_FORMAT`, and directory `unsupported_format` produce `completed_with_errors` plus consistent counts and DTOs;
- recursive false omits nested files.

- [ ] **Step 7: Run API edge tests and verify RED**

Run:

```powershell
uv run pytest tests/test_api.py -k "unknown_job or rejects_empty or reports_errors or non_recursive" -v
```

Expected: newly asserted DTO/count behavior FAILS until serialization covers every result variant.

- [ ] **Step 8: Complete serialization and verify GREEN**

Build response counts from the terminal `BatchResult`; queued/running/failed jobs return zero counts and empty collections. Convert each `ParseError` to `path + to_dict()`. Convert each skip with optional `file_id` and `duplicate_of`. Run all API tests and expect PASS.

- [ ] **Step 9: Commit the API slice**

Stage only API/job files and test file, then commit:

```powershell
git add backend/src/content_retrieval/api backend/src/content_retrieval/services/ingestion_jobs.py backend/tests/test_api.py
git commit -m "feat: add minimal ingestion API"
```

### Task 5: Regression and contract verification

**Files:**
- Verify all files above.

- [ ] **Step 1: Run focused API and batch suites**

```powershell
uv run pytest tests/test_batch_ingestion.py tests/test_api.py -v
```

Expected: all focused tests PASS with no warnings.

- [ ] **Step 2: Run the complete backend suite**

```powershell
uv run pytest -v
```

Expected: all backend tests PASS with no collection errors or warnings.

- [ ] **Step 3: Verify import/startup contract**

```powershell
uv run python -c "from content_retrieval.api.app import app; print(sorted((route.path, ','.join(sorted(route.methods or []))) for route in app.routes if route.path.startswith(('/health', '/v1'))))"
```

Expected output includes the four required method/path pairs.

- [ ] **Step 4: Review exact scope and Git diff**

Run `git status --short`, `git diff --check HEAD`, and `git diff --stat HEAD`. Confirm no Embedding, ChromaDB, persistence, cancellation, shutdown, or unrelated files were added.

- [ ] **Step 5: Commit any verification-only corrections**

If verification required an in-scope correction, first add a failing regression test, apply the minimal fix, rerun the focused and full suites, then commit only those correction files with a specific message.
