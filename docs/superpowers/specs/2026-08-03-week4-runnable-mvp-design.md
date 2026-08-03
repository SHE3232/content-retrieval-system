# Week 4 Runnable Offline Retrieval MVP Design

## Goal

Deliver a one-command, offline FastAPI backend MVP for the Week 4 scope. The
MVP accepts local TXT, PDF, DOCX, JPG, and PNG files or directories and runs the
complete pipeline:

```text
ingestion -> parsing -> text/image embedding -> Chroma persistence
          -> hybrid retrieval -> ranking/filtering -> JSON response
```

The submission also retains the end-to-end functional test report and
retrieval accuracy benchmark report. Flutter UI and accessibility work remain
in the Week 5 scope.

## Scope

### Included

- One-command startup after local runtime artifacts have been provisioned.
- Strict use of verified local text and MobileCLIP model artifacts.
- Local Apache Tika integration for DOCX parsing.
- Recursive batch indexing of TXT, PDF, DOCX, JPG, and PNG inputs.
- Persistent Chroma storage and incremental re-indexing.
- Keyword, text-semantic, image-semantic, and hybrid retrieval.
- MIME type, modality, path-prefix, and modification-time filters.
- FastAPI JSON endpoints, interactive OpenAPI documentation, and health checks.
- Automated regression tests, a real-runtime smoke procedure, and submission
  documentation.

### Excluded

- Flutter UI, keyboard navigation, screen-reader behavior, high-contrast mode,
  dynamic font scaling, WAVE, and Accessibility Scanner validation.
- Bundling model weights, the Tika JAR, Chroma databases, user documents,
  virtual environments, caches, or downloaded datasets in Git.
- Cloud services, runtime downloads, authentication, multi-user isolation, and
  durable indexing-job history.
- Replacing the existing Sentence Transformers and PyTorch MobileCLIP runtime
  adapters with TensorFlow Lite. The repository's converted artifacts remain
  validation outputs; this is a known full-PRD technology-stack gap rather than
  part of the Week 4 startup integration.

## Chosen Approach

Use a strict real-model offline runtime. A PowerShell launcher verifies all
local prerequisites, starts or reuses Tika, and launches a FastAPI application
factory that owns the model and Chroma runtime.

Two alternatives were rejected:

- A fallback demo mode with deterministic fake embeddings would start without
  model artifacts but would not prove real semantic retrieval.
- Bundling models and the complete runtime would simplify setup but would
  create a large submission and conflict with model-license and repository
  boundaries.

## Architecture

### Startup launcher

Add `tools/start-mvp.ps1` as the supported entry point. It will:

1. Resolve repository-relative paths without depending on the caller's current
   directory.
2. Validate the backend Python interpreter, Java, model manifest, text model,
   MobileCLIP weights, Tika JAR, and checksum file.
3. Reuse a healthy Tika service on `127.0.0.1:9998`, or start the verified
   local JAR in a hidden child process and wait for readiness.
4. Set explicit model, manifest, and data-directory configuration for the
   FastAPI factory.
5. Launch Uvicorn on `127.0.0.1` by default.
6. On exit, stop only the Tika process created by this launcher. A pre-existing
   Tika service is never terminated.

The default persistent data directory is `data/mvp/`, which is already outside
the Git submission boundary.

### FastAPI application factory

Add a production MVP factory under the `content_retrieval` package. It will:

- Read explicit local paths from a small validated settings object.
- Call the existing `build_local_runtime` factory.
- Inject `IndexingService` and `RetrievalService` into the existing FastAPI
  application.
- Attach the runtime to application state for health inspection and lifecycle
  ownership.
- Close the Chroma repository during application shutdown, including failed or
  interrupted server sessions.

The existing default `create_app()` behavior remains available for isolated
tests and parse-only use. The runnable MVP uses the new production factory.

### Component boundaries

The existing dependency direction remains unchanged:

```text
PowerShell launcher
  -> FastAPI MVP factory
      -> API routes
          -> indexing/retrieval services
              -> parsers + embedding engines + Chroma repository
```

The work will not duplicate parsing, embedding, storage, BM25, RRF, or retrieval
logic that is already implemented and tested.

## Core Data Flow

### Indexing

1. The client submits files or directories plus explicit authorized roots.
2. Paths are normalized, checked against authorized roots, expanded according
   to the recursive option, and filtered to supported formats.
3. TXT and documents produce text records; PDFs preserve page information;
   DOCX content is extracted through local Tika; JPG and PNG inputs produce
   image records.
4. Text is chunked and embedded in the text semantic space. Images are embedded
   in the MobileCLIP image-text space.
5. Chroma stores records in isolated collections by embedding space.
6. Re-indexing unchanged files is idempotent. Changed files replace stale
   records for the same normalized source path.
7. After a successful batch, the in-memory keyword index is refreshed from
   persistent records.

### Retrieval

1. The request selects one or more of `keyword`, `text_semantic`, and
   `image_semantic`.
2. Filters are applied for MIME type, modality, path prefix, and modification
   time.
3. BM25 ranks filename, path, and body matches. Text and image queries execute
   in their separate compatible vector spaces.
4. Each channel first keeps the best matching record per file.
5. Weighted reciprocal-rank fusion combines channel ranks without directly
   adding incomparable raw similarity scores.
6. The service applies deterministic ordering, limits the result to
   `top_k` in the range 1-100, and returns file-level JSON hits.

## API Contract

- `POST /v1/indexing/jobs`: submit files or directories for asynchronous batch
  indexing.
- `GET /v1/indexing/jobs/{job_id}`: return job state, counters, and per-file
  failures.
- `POST /v1/search`: run selected retrieval channels with optional weights and
  filters.
- `GET /v1/index/stats`: return file, text-record, and image-record counts.
- `GET /health/live`: confirm that the API process is alive.
- `GET /health/ready`: confirm that the real retrieval runtime, Chroma, and the
  DOCX dependency are ready.
- `GET /docs`: expose FastAPI's local interactive OpenAPI documentation.

Search hits continue to include the path, name, MIME type, modality, fused
score, match reasons, best text snippet, page number, and paragraph number when
available.

Index data is durable, but job status is intentionally in memory for this MVP.
After restart, previous job IDs are unavailable while indexed files remain
searchable.

## Error Handling

### Startup failures

The launcher exits with a non-zero status and a specific remediation message
when Python, Java, the manifest, model artifacts, Tika, checksum files, the
configured port, or a writable data directory is unavailable. Hash mismatches
are fatal. Startup never downloads missing resources or substitutes fake
embeddings.

### Per-file isolation

A parse, embedding, or persistence failure for one file does not abort other
files in the same indexing batch. The job reports `completed`,
`completed_with_errors`, or `failed`, with stable error code, processing stage,
and retryability information.

### HTTP responses

- `422` for invalid request shapes and schema constraints.
- `400` for validly shaped but invalid search operations.
- `404` for unknown job identifiers.
- `503` for unavailable runtime or storage dependencies.

Logs may contain processing stage and local path for diagnosis. They must not
contain document bodies, embedding vectors, or model weights.

## Offline and Local Security Boundaries

- The server binds to `127.0.0.1` unless the user explicitly overrides it.
- Indexing requires both `paths` and `authorized_roots`.
- Canonicalized paths must remain within an authorized root.
- No endpoint returns arbitrary local file bytes.
- Runtime HTTP clients ignore proxy environment variables where applicable.
- Runtime startup performs no network access.
- Shutdown releases only resources owned by the current process and never
  clears an existing index.

## Testing Strategy

Implementation follows red-green-refactor. New tests will cover:

- Settings defaults, explicit path resolution, missing resources, and clear
  configuration failures.
- Construction of the real-runtime FastAPI factory with injected test doubles.
- Runtime readiness and repository shutdown behavior.
- Indexing, search, filters, index statistics, and structured error responses.
- Persistent search behavior after repository and application restart.
- Launcher preflight logic that can be tested without downloading models.
- Real DOCX parsing when the verified local Tika server is available.

Verification has three layers:

1. Run the complete repository test suite.
2. Run the Week 4 coverage command with the existing 85% core-module gate.
3. Run a real HTTP smoke procedure with verified local models and Tika:
   index one TXT, PDF, DOCX, JPG, and PNG; perform keyword, text-semantic,
   image-semantic, and hybrid searches; restart; then repeat a persistent
   search.

The real smoke procedure records its commands, supported-format counts,
failure count, search checks, and persistence result in machine-readable
evidence. It does not replace the frozen NQ and COCO accuracy benchmarks.

## Documentation and Submission

- Add a concise MVP setup, startup, API, demonstration, and troubleshooting
  guide.
- Update `docs/week4/README.md` with the one-command entry point and links to the
  guide and reports.
- Retain the existing end-to-end functional test report and retrieval accuracy
  benchmark report.
- If fresh real-runtime metrics change, update the relevant report and evidence
  together. Otherwise, add a new integration record without rewriting the
  historical benchmark results.
- Audit the final Git diff to exclude model weights, the Tika JAR, databases,
  user documents, virtual environments, caches, and rendered intermediates.

## Acceptance Criteria

The MVP is accepted when all of the following are true:

1. After the documented one-time local artifact preparation, one command starts
   the API and any required local DOCX dependency.
2. The ready endpoint reports success only when the real retrieval runtime is
   usable.
3. TXT, PDF, DOCX, JPG, and PNG inputs all reach the indexing pipeline.
4. Keyword, text-semantic, image-semantic, and hybrid retrieval return JSON
   results, and ranking filters are demonstrably applied.
5. Chroma records remain searchable after a service restart.
6. The full automated suite and Week 4 coverage gate pass.
7. Fresh smoke evidence and runnable instructions are included alongside the
   existing end-to-end and accuracy reports.
8. No prohibited binary, private, generated, or local runtime artifact is
   included in the Git submission.

## Design Self-Review

- There are no placeholders or deferred decisions in the MVP scope.
- The strict real-model approach is consistent with offline operation and the
  repository's existing model-manifest boundary.
- The launcher owns orchestration; the Python factory owns application runtime
  lifecycle; existing services retain their current responsibilities.
- Five-format support depends on local Tika for DOCX, and the strict startup
  preflight makes that dependency explicit.
- The implementation uses the existing real Python inference adapters and does
  not claim to close the separate TensorFlow Lite runtime gap.
- The design does not claim that the Week 4 backend satisfies Week 5 Flutter or
  accessibility deliverables, or the final cross-platform release scope.
