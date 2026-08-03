# 第四周可运行离线检索 MVP 实施计划

> **面向执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行本计划。所有步骤使用复选框（`- [ ]`）跟踪。

**目标：** 将已经完成的解析、真实多模态嵌入、Chroma 存储和混合检索模块整合为一个可一键启动、可通过 HTTP 验收并具有持久化证据的离线 FastAPI MVP。

**架构：** 新增小型 MVP 配置与应用工厂，在 FastAPI 生命周期内构建和关闭现有 `LocalRuntime`；新增 PowerShell 启动器负责本地依赖预检、Tika 进程编排和 Uvicorn 启动。另提供独立 HTTP 烟测工具，以真实五格式输入验证索引、三通道检索、混合检索和服务重启后的持久化。

**技术栈：** Python 3.10、FastAPI、Uvicorn、httpx、ChromaDB、Sentence Transformers、MobileCLIP、Apache Tika 3.3.1、PowerShell、pytest、pytest-cov。

---

## 开始前状态

- 设计文档：`docs/superpowers/specs/2026-08-03-week4-runnable-mvp-design.md`
- 工作分支：`codex/week4-runnable-mvp`
- 隔离工作树：`F:\contentretrivalsystem\.worktrees\week4-runnable-mvp`
- 干净基线：`339 passed, 1 skipped in 35.43s`
- 基线跳过原因：工作树中未运行本地 Tika，真实 DOCX 集成用例按既有约定跳过。

## 文件结构

- 新增 `backend/src/content_retrieval/mvp.py`：MVP 配置、Tika 就绪探针和生产 FastAPI 工厂。
- 修改 `backend/src/content_retrieval/api/app.py`：允许注入生命周期、初始就绪状态和动态就绪检查。
- 修改 `backend/src/content_retrieval/api/routes/health.py`：将静态布尔值与动态依赖检查合并为就绪结果。
- 新增 `backend/tests/test_mvp_runtime.py`：配置、Tika 探针、应用启动、动态就绪和资源关闭测试。
- 新增 `tools/start-mvp.ps1`：一键预检、启动或复用 Tika、启动 Uvicorn并定向收尾。
- 新增 `backend/tests/test_mvp_launcher.py`：在临时资源上验证 PowerShell 预检成功和摘要失败。
- 新增 `backend/tools/smoke_mvp.py`：对已启动服务执行五格式 HTTP 烟测并生成 JSON 证据。
- 新增 `backend/tests/test_mvp_smoke.py`：使用 `httpx.MockTransport` 验证烟测协议与持久化前置检查。
- 新增 `docs/week4/MVP_RUNBOOK.md`：中文安装、模型准备、启动、API 演示和故障排查手册。
- 修改 `docs/week4/README.md`：增加 MVP 启动入口、手册和新证据链接。
- 新增 `docs/week4/evidence/mvp-api-smoke-summary.json`：真实启动、五格式、检索和重启验证结果。

### 任务 1：冻结 MVP 配置与 Tika 就绪探针

**文件：**
- 新增：`backend/src/content_retrieval/mvp.py`
- 新增：`backend/tests/test_mvp_runtime.py`

- [ ] **步骤 1：编写配置和探针失败测试**

在 `backend/tests/test_mvp_runtime.py` 中先写入以下测试：

```python
from pathlib import Path

import httpx


def test_mvp_settings_resolve_defaults_from_repository_not_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from content_retrieval.mvp import MvpSettings

    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    settings = MvpSettings.from_environment(
        repository_root=repository_root,
        environ={},
    )

    assert settings.model_root == (repository_root / "models").resolve()
    assert settings.manifest_path == (
        repository_root / "models" / "model-manifest.json"
    ).resolve()
    assert settings.data_dir == (repository_root / "data" / "mvp").resolve()
    assert settings.tika_url == "http://127.0.0.1:9998"


def test_mvp_settings_resolve_relative_overrides_from_repository(
    tmp_path: Path,
) -> None:
    from content_retrieval.mvp import MvpSettings

    settings = MvpSettings.from_environment(
        repository_root=tmp_path,
        environ={
            "CONTENT_RETRIEVAL_MODEL_ROOT": "artifacts/models",
            "CONTENT_RETRIEVAL_MANIFEST_PATH": "artifacts/manifest.json",
            "CONTENT_RETRIEVAL_DATA_DIR": "state/index",
            "CONTENT_RETRIEVAL_TIKA_URL": "http://127.0.0.1:10098",
        },
    )

    assert settings.model_root == (tmp_path / "artifacts/models").resolve()
    assert settings.manifest_path == (
        tmp_path / "artifacts/manifest.json"
    ).resolve()
    assert settings.data_dir == (tmp_path / "state/index").resolve()
    assert settings.tika_url == "http://127.0.0.1:10098"


def test_tika_probe_requires_a_tika_version_response() -> None:
    from content_retrieval.mvp import TikaReadinessProbe

    healthy = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            text="Apache Tika 3.3.1",
            request=request,
        )
    )
    wrong_service = httpx.MockTransport(
        lambda request: httpx.Response(200, text="other", request=request)
    )

    assert TikaReadinessProbe(transport=healthy).is_ready() is True
    assert TikaReadinessProbe(transport=wrong_service).is_ready() is False
```

- [ ] **步骤 2：运行测试并确认红灯**

运行：

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_mvp_runtime.py
```

预期：收集失败，提示 `ModuleNotFoundError: No module named 'content_retrieval.mvp'`。

- [ ] **步骤 3：实现最小配置与探针**

创建 `backend/src/content_retrieval/mvp.py`：

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

import httpx


MODEL_ROOT_ENV = "CONTENT_RETRIEVAL_MODEL_ROOT"
MANIFEST_PATH_ENV = "CONTENT_RETRIEVAL_MANIFEST_PATH"
DATA_DIR_ENV = "CONTENT_RETRIEVAL_DATA_DIR"
TIKA_URL_ENV = "CONTENT_RETRIEVAL_TIKA_URL"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_local_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class MvpSettings:
    model_root: Path
    manifest_path: Path
    data_dir: Path
    tika_url: str

    @classmethod
    def from_environment(
        cls,
        *,
        repository_root: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> MvpSettings:
        root = (repository_root or _repository_root()).resolve()
        values = os.environ if environ is None else environ
        return cls(
            model_root=_resolve_local_path(
                root,
                values.get(MODEL_ROOT_ENV, "models"),
            ),
            manifest_path=_resolve_local_path(
                root,
                values.get(
                    MANIFEST_PATH_ENV,
                    "models/model-manifest.json",
                ),
            ),
            data_dir=_resolve_local_path(
                root,
                values.get(DATA_DIR_ENV, "data/mvp"),
            ),
            tika_url=values.get(
                TIKA_URL_ENV,
                "http://127.0.0.1:9998",
            ).rstrip("/"),
        )


class TikaReadinessProbe:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9998",
        *,
        timeout_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def is_ready(self) -> bool:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = client.get("/version")
        except httpx.HTTPError:
            return False
        return response.status_code == 200 and "Apache Tika" in response.text
```

- [ ] **步骤 4：运行测试并确认绿灯**

运行步骤 2 的命令。预期：3 项测试全部通过。

- [ ] **步骤 5：提交任务 1**

```powershell
git add backend/src/content_retrieval/mvp.py backend/tests/test_mvp_runtime.py
git commit -m "feat: add offline MVP settings and Tika probe"
```

### 任务 2：在 FastAPI 生命周期中装配并关闭真实运行时

**文件：**
- 修改：`backend/src/content_retrieval/mvp.py`
- 修改：`backend/src/content_retrieval/api/app.py:1-38`
- 修改：`backend/src/content_retrieval/api/routes/health.py:1-23`
- 修改：`backend/tests/test_mvp_runtime.py`
- 测试：`backend/tests/test_api.py`
- 测试：`backend/tests/test_week4_api.py`

- [ ] **步骤 1：编写应用工厂生命周期失败测试**

向 `backend/tests/test_mvp_runtime.py` 添加：

```python
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


class FakeRepository:
    def __init__(self) -> None:
        self.close_calls = 0

    def count(self) -> int:
        return 0

    def close(self) -> None:
        self.close_calls += 1


class FakeRuntime:
    def __init__(self) -> None:
        self.repository = FakeRepository()
        self.indexing_service = object()
        self.retrieval_service = SimpleNamespace(repository=self.repository)

    def close(self) -> None:
        self.repository.close()


class FakeProbe:
    def __init__(self, ready: bool = True) -> None:
        self.ready = ready

    def is_ready(self) -> bool:
        return self.ready


@pytest.mark.anyio
async def test_mvp_factory_builds_runtime_on_start_and_closes_on_stop(
    tmp_path: Path,
) -> None:
    from content_retrieval.mvp import MvpSettings, create_mvp_app

    runtime = FakeRuntime()
    calls: list[dict[str, object]] = []

    def build_runtime(**kwargs):
        calls.append(kwargs)
        return runtime

    settings = MvpSettings(
        model_root=tmp_path / "models",
        manifest_path=tmp_path / "models/manifest.json",
        data_dir=tmp_path / "data",
        tika_url="http://127.0.0.1:9998",
    )
    app = create_mvp_app(
        settings,
        runtime_builder=build_runtime,
        tika_probe=FakeProbe(),
    )

    assert app.state.ready is False
    async with app.router.lifespan_context(app):
        assert app.state.ready is True
        assert app.state.runtime is runtime
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health/ready")
        assert response.status_code == 200

    assert runtime.repository.close_calls == 1
    assert app.state.ready is False
    assert calls == [
        {
            "model_root": settings.model_root,
            "manifest_path": settings.manifest_path,
            "data_dir": settings.data_dir,
        }
    ]


@pytest.mark.anyio
async def test_mvp_ready_turns_unavailable_when_tika_stops(
    tmp_path: Path,
) -> None:
    from content_retrieval.mvp import MvpSettings, create_mvp_app

    runtime = FakeRuntime()
    probe = FakeProbe(ready=True)
    settings = MvpSettings(
        model_root=tmp_path / "models",
        manifest_path=tmp_path / "manifest.json",
        data_dir=tmp_path / "data",
        tika_url="http://127.0.0.1:9998",
    )
    app = create_mvp_app(
        settings,
        runtime_builder=lambda **kwargs: runtime,
        tika_probe=probe,
    )

    async with app.router.lifespan_context(app):
        probe.ready = False
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
```

- [ ] **步骤 2：运行测试并确认红灯**

运行：

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_mvp_runtime.py
```

预期：失败，提示 `content_retrieval.mvp` 中不存在 `create_mvp_app`。

- [ ] **步骤 3：扩展通用应用工厂的生命周期与就绪注入点**

将 `backend/src/content_retrieval/api/app.py` 的 `create_app` 签名和初始化改为：

```python
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI


AppLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    ingestion_service: BatchIngestionService | None = None,
    *,
    indexing_service=None,
    retrieval_service=None,
    lifespan: AppLifespan | None = None,
    ready: bool = True,
    readiness_check: Callable[[], bool] | None = None,
) -> FastAPI:
    application = FastAPI(
        title="Content Retrieval API",
        lifespan=lifespan,
    )
    application.state.ingestion_service = (
        ingestion_service
        or BatchIngestionService(
            create_default_registry(),
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        )
    )
    application.state.job_store = InMemoryIngestionJobStore()
    application.state.indexing_job_store = InMemoryIndexingJobStore()
    application.state.indexing_service = indexing_service
    application.state.retrieval_service = retrieval_service
    application.state.background_tasks = set()
    application.state.ready = ready
    application.state.readiness_check = readiness_check
    application.include_router(health.router)
    application.include_router(ingestion.router)
    application.include_router(indexing.router)
    application.include_router(search.router)
    return application
```

保留文件末尾的 `app = create_app()`，避免破坏现有测试和仅解析启动方式。

- [ ] **步骤 4：实现动态就绪检查**

将 `backend/src/content_retrieval/api/routes/health.py` 中的 `ready` 改为：

```python
@router.get("/health/ready")
def ready(request: Request, response: Response) -> dict[str, str]:
    is_ready = bool(request.app.state.ready)
    readiness_check = request.app.state.readiness_check
    if is_ready and readiness_check is not None:
        try:
            is_ready = bool(readiness_check())
        except Exception:
            is_ready = False
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}
```

- [ ] **步骤 5：实现 MVP 应用工厂**

> 质量评审修正（2026-08-04）：索引任务内部使用 `asyncio.to_thread`，取消 asyncio task wrapper 不会停止底层线程，会导致 `runtime.close()` 与 Chroma 写入竞态。因此 shutdown 必须 `gather` 排空全部活动后台索引任务后再关闭 runtime。

> 质量复审第二次修正（2026-08-04）：shutdown drain 使用明确的 30 秒 grace；到期只告警并继续以 `shield` 等待真实工作结束，绝不在线程仍运行时强关 Chroma。外部取消先记录，待 drain 完成并关闭 runtime 后重抛；已有主异常时则记录取消并保留主异常。

在 `backend/src/content_retrieval/mvp.py` 中增加：

```python
import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from content_retrieval.api.app import create_app
from content_retrieval.runtime import LocalRuntime, build_local_runtime


class RuntimeBuilder(Protocol):
    def __call__(
        self,
        *,
        model_root: Path,
        manifest_path: Path,
        data_dir: Path,
    ) -> LocalRuntime: ...


def create_mvp_app(
    settings: MvpSettings | None = None,
    *,
    runtime_builder: RuntimeBuilder = build_local_runtime,
    tika_probe: TikaReadinessProbe | None = None,
) -> FastAPI:
    resolved = settings or MvpSettings.from_environment()
    probe = tika_probe or TikaReadinessProbe(resolved.tika_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        runtime = runtime_builder(
            model_root=resolved.model_root,
            manifest_path=resolved.manifest_path,
            data_dir=resolved.data_dir,
        )
        try:
            if not probe.is_ready():
                raise RuntimeError(
                    "Apache Tika is not ready at " + resolved.tika_url
                )
            application.state.runtime = runtime
            application.state.indexing_service = runtime.indexing_service
            application.state.retrieval_service = runtime.retrieval_service
            application.state.ready = True
            yield
        finally:
            application.state.ready = False
            tasks = list(application.state.background_tasks)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            runtime.close()

    application = create_app(lifespan=lifespan, ready=False)

    def readiness_check() -> bool:
        runtime = getattr(application.state, "runtime", None)
        return (
            runtime is not None
            and probe.is_ready()
            and runtime.repository.count() >= 0
        )

    application.state.readiness_check = readiness_check
    return application
```

- [ ] **步骤 6：运行聚焦测试并确认绿灯**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q `
  backend/tests/test_mvp_runtime.py `
  backend/tests/test_api.py `
  backend/tests/test_week4_api.py
```

预期：全部通过，现有默认 `create_app()` 健康检查行为不变。

- [ ] **步骤 7：提交任务 2**

```powershell
git add backend/src/content_retrieval/mvp.py `
  backend/src/content_retrieval/api/app.py `
  backend/src/content_retrieval/api/routes/health.py `
  backend/tests/test_mvp_runtime.py
git commit -m "feat: assemble retrieval runtime in FastAPI lifespan"
```

### 任务 3：实现可测试的一键 PowerShell 启动器

**文件：**
- 新增：`tools/start-mvp.ps1`
- 新增：`backend/tests/test_mvp_launcher.py`

- [ ] **步骤 1：编写启动器预检失败测试**

创建 `backend/tests/test_mvp_launcher.py`：

```python
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="the supported MVP launcher is PowerShell on Windows",
)


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    assert executable is not None
    return executable


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _run_preflight(tmp_path: Path, *, checksum: str) -> subprocess.CompletedProcess[str]:
    repository = Path(__file__).resolve().parents[2]
    model_root = tmp_path / "models"
    model_root.mkdir()
    manifest = model_root / "model-manifest.json"
    manifest.write_text('{"schema_version":"1","models":[]}', encoding="utf-8")
    jar = tmp_path / "tika.jar"
    jar.write_bytes(b"tika-fixture")
    checksum_file = tmp_path / "tika.jar.sha512"
    checksum_file.write_text(checksum, encoding="ascii")
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repository / "tools/start-mvp.ps1"),
            "-CheckOnly",
            "-PythonExecutable",
            sys.executable,
            "-JavaExecutable",
            sys.executable,
            "-ModelRoot",
            str(model_root),
            "-ManifestPath",
            str(manifest),
            "-DataDir",
            str(tmp_path / "data"),
            "-TikaJar",
            str(jar),
            "-TikaChecksumFile",
            str(checksum_file),
            "-Port",
            str(_free_port()),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )


def test_launcher_check_only_accepts_verified_local_paths(tmp_path: Path) -> None:
    digest = hashlib.sha512(b"tika-fixture").hexdigest()
    result = _run_preflight(tmp_path, checksum=digest)

    assert result.returncode == 0, result.stderr
    assert "MVP preflight passed" in result.stdout


def test_launcher_rejects_tika_checksum_mismatch(tmp_path: Path) -> None:
    result = _run_preflight(tmp_path, checksum="0" * 128)

    assert result.returncode != 0
    assert "Tika server JAR SHA-512 mismatch" in (result.stdout + result.stderr)
```

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_mvp_launcher.py
```

预期：两项测试失败，因为 `tools/start-mvp.ps1` 尚不存在。

- [ ] **步骤 3：实现启动参数与严格预检**

创建 `tools/start-mvp.ps1`，参数和预检主体如下：

```powershell
param(
    [string]$PythonExecutable = "",
    [string]$JavaExecutable = "",
    [string]$ModelRoot = "models",
    [string]$ManifestPath = "models/model-manifest.json",
    [string]$DataDir = "data/mvp",
    [string]$TikaJar = "tools/tika/tika-server-standard-3.3.1.jar",
    [string]$TikaChecksumFile = "tools/tika/tika-server-standard-3.3.1.jar.sha512",
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Add-Type -AssemblyName System.Net.Http

function Resolve-RepositoryPath([string]$Value) {
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $Value))
}

function Test-TcpPort([int]$TargetPort) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $TargetPort)
        return $task.Wait(250) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-TikaReady {
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(1)
    try {
        $response = $client.GetAsync("http://127.0.0.1:9998/version").GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return $response.IsSuccessStatusCode -and $body.Contains("Apache Tika")
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

$python = if ($PythonExecutable) {
    Resolve-RepositoryPath $PythonExecutable
} else {
    Resolve-RepositoryPath "backend/.venv/Scripts/python.exe"
}
$java = if ($JavaExecutable) {
    Resolve-RepositoryPath $JavaExecutable
} else {
    (Get-Command java -ErrorAction Stop).Source
}
$models = Resolve-RepositoryPath $ModelRoot
$manifest = Resolve-RepositoryPath $ManifestPath
$data = Resolve-RepositoryPath $DataDir
$jar = Resolve-RepositoryPath $TikaJar
$checksumFile = Resolve-RepositoryPath $TikaChecksumFile

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python executable not found: $python" }
if (-not (Test-Path -LiteralPath $java -PathType Leaf)) { throw "Java executable not found: $java" }
if (-not (Test-Path -LiteralPath $models -PathType Container)) { throw "Model root not found: $models" }
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Model manifest not found: $manifest" }
if (-not (Test-Path -LiteralPath $jar -PathType Leaf)) { throw "Tika server JAR not found: $jar" }
if (-not (Test-Path -LiteralPath $checksumFile -PathType Leaf)) { throw "Tika checksum file not found: $checksumFile" }
if (Test-TcpPort $Port) { throw "API port is already in use: 127.0.0.1:$Port" }

$expected = (Get-Content -LiteralPath $checksumFile -Raw).Trim().ToLowerInvariant()
if ($expected -notmatch '^[0-9a-f]{128}$') { throw "Tika checksum file must contain one SHA-512 digest" }
$stream = [System.IO.File]::OpenRead($jar)
$sha512 = [System.Security.Cryptography.SHA512]::Create()
try {
    $actual = [System.BitConverter]::ToString($sha512.ComputeHash($stream)).Replace("-", "").ToLowerInvariant()
}
finally {
    $sha512.Dispose()
    $stream.Dispose()
}
if ($actual -ne $expected) { throw "Tika server JAR SHA-512 mismatch: expected $expected, got $actual" }

[System.IO.Directory]::CreateDirectory($data) | Out-Null
$writeProbe = Join-Path $data ".mvp-write-probe"
try {
    [System.IO.File]::WriteAllText($writeProbe, "ok")
}
finally {
    if ([System.IO.File]::Exists($writeProbe)) { [System.IO.File]::Delete($writeProbe) }
}

if ($CheckOnly) {
    Write-Output "MVP preflight passed"
    exit 0
}
```

- [ ] **步骤 4：实现 Tika 编排、Uvicorn 启动和定向收尾**

在同一脚本的预检之后追加：

```powershell
$startedTika = $null
try {
    if (-not (Test-TikaReady)) {
        $startedTika = Start-Process `
            -FilePath $java `
            -ArgumentList @("-jar", "`"$jar`"", "-p", "9998") `
            -PassThru `
            -WindowStyle Hidden
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        while (-not (Test-TikaReady)) {
            if ($startedTika.HasExited) {
                throw "Tika exited before becoming ready with code $($startedTika.ExitCode)"
            }
            if ([DateTime]::UtcNow -ge $deadline) {
                throw "Tika did not become ready within 30 seconds"
            }
            Start-Sleep -Milliseconds 250
        }
    }

    $env:CONTENT_RETRIEVAL_MODEL_ROOT = $models
    $env:CONTENT_RETRIEVAL_MANIFEST_PATH = $manifest
    $env:CONTENT_RETRIEVAL_DATA_DIR = $data
    $env:CONTENT_RETRIEVAL_TIKA_URL = "http://127.0.0.1:9998"
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"

    & $python -m uvicorn `
        content_retrieval.mvp:create_mvp_app `
        --factory `
        --app-dir (Join-Path $repositoryRoot "backend/src") `
        --host 127.0.0.1 `
        --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Uvicorn exited with code $LASTEXITCODE"
    }
}
finally {
    if ($null -ne $startedTika -and -not $startedTika.HasExited) {
        Stop-Process -Id $startedTika.Id -Force
        $startedTika.WaitForExit(5000)
    }
}
```

- [ ] **步骤 5：运行启动器测试并确认绿灯**

运行步骤 2 的命令。预期：2 项测试全部通过；测试进程不启动 Java 或 Uvicorn。

- [ ] **步骤 6：运行已有 Tika 启动器测试回归**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q `
  backend/tests/test_docx_tika_extended.py `
  backend/tests/test_runtime_factory.py
```

预期：全部通过，现有摘要算法和运行时工厂契约不变。

- [ ] **步骤 7：提交任务 3**

```powershell
git add tools/start-mvp.ps1 backend/tests/test_mvp_launcher.py
git commit -m "feat: add one-command offline MVP launcher"
```

### 任务 4：实现可重复的 HTTP 五格式烟测工具

**文件：**
- 新增：`backend/tools/smoke_mvp.py`
- 新增：`backend/tests/test_mvp_smoke.py`

- [ ] **步骤 1：编写烟测协议失败测试**

创建 `backend/tests/test_mvp_smoke.py`：

```python
from pathlib import Path
import sys

import httpx


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from smoke_mvp import SmokeQueries, run_smoke


def test_smoke_indexes_five_formats_and_checks_all_channels(tmp_path: Path) -> None:
    for name in ("a.txt", "b.pdf", "c.docx", "d.jpg", "e.png"):
        (tmp_path / name).write_bytes(b"fixture")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/index/stats":
            return httpx.Response(
                200,
                json={
                    "record_count": 0,
                    "file_count": 0,
                    "text_record_count": 0,
                    "image_record_count": 0,
                },
            )
        if request.method == "POST" and request.url.path == "/v1/indexing/jobs":
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
        if request.url.path == "/v1/indexing/jobs/job-1":
            return httpx.Response(
                200,
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": {
                        "parsed_files": 5,
                        "indexed_files": 5,
                        "indexed_records": 12,
                        "skipped_files": 0,
                        "failed_files": 0,
                        "partial_files": 0,
                        "unchanged_files": 0,
                        "removed_stale_records": 0,
                        "failures": [],
                    },
                },
            )
        if request.method == "POST" and request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "query": "fixture",
                    "hits": [
                        {
                            "name": "e.png",
                            "modality": "image",
                            "match_reasons": ["image_semantic"],
                        }
                    ],
                    "total_candidates": 1,
                    "elapsed_ms": 1.0,
                    "weights": {"keyword": 1.0},
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(respond),
    ) as client:
        result = run_smoke(
            client,
            input_root=tmp_path,
            queries=SmokeQueries("exact", "semantic", "image"),
            poll_interval_seconds=0,
        )

    assert result["status"] == "passed"
    assert result["formats"] == ["DOCX", "JPG", "PDF", "PNG", "TXT"]
    assert [item["name"] for item in result["searches"]] == [
        "keyword",
        "text_semantic",
        "image_semantic",
        "hybrid",
        "filtered_image",
    ]


def test_persistence_check_requires_records_before_reindex(tmp_path: Path) -> None:
    for name in ("a.txt", "b.pdf", "c.docx", "d.jpg", "e.png"):
        (tmp_path / name).write_bytes(b"fixture")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "record_count": 0,
                "file_count": 0,
                "text_record_count": 0,
                "image_record_count": 0,
            },
        )
    )

    with httpx.Client(base_url="http://testserver", transport=transport) as client:
        try:
            run_smoke(
                client,
                input_root=tmp_path,
                queries=SmokeQueries("exact", "semantic", "image"),
                require_existing_index=True,
            )
        except RuntimeError as error:
            assert "no records existed before indexing" in str(error)
        else:
            raise AssertionError("persistence check unexpectedly passed")
```

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend/tests/test_mvp_smoke.py
```

预期：收集失败，提示找不到 `smoke_mvp`。

- [ ] **步骤 3：实现烟测核心协议**

创建 `backend/tools/smoke_mvp.py`，包含以下接口：

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import httpx


REQUIRED_SUFFIXES = {".txt", ".pdf", ".docx", ".jpg", ".png"}


@dataclass(frozen=True, slots=True)
class SmokeQueries:
    keyword: str
    text_semantic: str
    image_semantic: str


def _require_formats(input_root: Path) -> list[str]:
    suffixes = {
        path.suffix.lower()
        for path in input_root.rglob("*")
        if path.is_file()
    }
    missing = sorted(REQUIRED_SUFFIXES - suffixes)
    if missing:
        raise ValueError("input root is missing formats: " + ", ".join(missing))
    return sorted(suffix[1:].upper() for suffix in REQUIRED_SUFFIXES)


def _request_json(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("API returned a non-object JSON payload")
    return payload


def run_smoke(
    client: httpx.Client,
    *,
    input_root: Path,
    queries: SmokeQueries,
    require_existing_index: bool = False,
    timeout_seconds: float = 180.0,
    poll_interval_seconds: float = 0.25,
) -> dict[str, object]:
    root = input_root.expanduser().resolve(strict=True)
    formats = _require_formats(root)
    before = _request_json(client.get("/v1/index/stats"))
    pre_index_records = int(before["record_count"])
    if require_existing_index and pre_index_records <= 0:
        raise RuntimeError("no records existed before indexing after restart")

    created = _request_json(
        client.post(
            "/v1/indexing/jobs",
            json={
                "paths": [str(root)],
                "authorized_roots": [str(root)],
                "recursive": True,
            },
        )
    )
    job_id = str(created["job_id"])
    deadline = time.monotonic() + timeout_seconds
    while True:
        job = _request_json(client.get(f"/v1/indexing/jobs/{job_id}"))
        if job["status"] not in {"queued", "running"}:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"indexing job {job_id} did not finish")
        time.sleep(poll_interval_seconds)
    if job["status"] not in {"completed", "completed_with_errors"}:
        raise RuntimeError(f"indexing job ended as {job['status']}")
    result = job.get("result")
    if not isinstance(result, dict) or int(result["failed_files"]) != 0:
        raise RuntimeError("indexing smoke contains failed files")

    checks = [
        ("keyword", queries.keyword, ["keyword"], None, None),
        (
            "text_semantic",
            queries.text_semantic,
            ["text_semantic"],
            None,
            None,
        ),
        (
            "image_semantic",
            queries.image_semantic,
            ["image_semantic"],
            None,
            None,
        ),
        (
            "hybrid",
            queries.text_semantic,
            ["keyword", "text_semantic", "image_semantic"],
            None,
            None,
        ),
        (
            "filtered_image",
            queries.image_semantic,
            ["image_semantic"],
            {"modalities": ["image"]},
            "image",
        ),
    ]
    searches: list[dict[str, object]] = []
    for name, query, channels, filters, expected_modality in checks:
        request_payload: dict[str, object] = {
            "query": query,
            "top_k": 5,
            "channels": channels,
        }
        if filters is not None:
            request_payload["filters"] = filters
        payload = _request_json(
            client.post(
                "/v1/search",
                json=request_payload,
            )
        )
        hits = payload.get("hits")
        if not isinstance(hits, list) or not hits:
            raise RuntimeError(f"{name} search returned no hits")
        if expected_modality is not None and any(
            hit.get("modality") != expected_modality for hit in hits
        ):
            raise RuntimeError(f"{name} search violated its modality filter")
        searches.append(
            {
                "name": name,
                "query": query,
                "channels": channels,
                "top_hit": hits[0]["name"],
                "match_reasons": hits[0]["match_reasons"],
                "elapsed_ms": payload["elapsed_ms"],
                "passed": True,
            }
        )

    after = _request_json(client.get("/v1/index/stats"))
    return {
        "schema_version": "1",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "formats": formats,
        "pre_index_record_count": pre_index_records,
        "indexing": result,
        "stats": after,
        "searches": searches,
        "persistent_restart": {
            "required": require_existing_index,
            "passed": require_existing_index and pre_index_records > 0,
        },
    }
```

- [ ] **步骤 4：实现烟测命令行入口与 JSON 输出**

在同一文件增加：

```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the running MVP API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--keyword-query", required=True)
    parser.add_argument("--text-query", required=True)
    parser.add_argument("--image-query", required=True)
    parser.add_argument("--require-existing-index", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with httpx.Client(
        base_url=args.base_url,
        timeout=30.0,
        trust_env=False,
    ) as client:
        evidence = run_smoke(
            client,
            input_root=args.input_root,
            queries=SmokeQueries(
                keyword=args.keyword_query,
                text_semantic=args.text_query,
                image_semantic=args.image_query,
            ),
            require_existing_index=args.require_existing_index,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 5：运行测试并确认绿灯**

运行步骤 2 的命令。预期：2 项测试全部通过。

- [ ] **步骤 6：提交任务 4**

```powershell
git add backend/tools/smoke_mvp.py backend/tests/test_mvp_smoke.py
git commit -m "test: add repeatable MVP HTTP smoke runner"
```

### 任务 5：编写中文运行手册并接入第四周交付入口

**文件：**
- 新增：`docs/week4/MVP_RUNBOOK.md`
- 修改：`docs/week4/README.md:1-71`

- [ ] **步骤 1：写入无占位符的本地资源准备命令**

在 `docs/week4/MVP_RUNBOOK.md` 中记录以下固定来源和顺序：

```powershell
# 1. 恢复固定 MobileCLIP 源码依赖
New-Item -ItemType Directory -Force third_party/mobileclip-src | Out-Null
Invoke-WebRequest `
  -Uri "https://github.com/apple/ml-mobileclip/archive/aecfb5453d022e9deff12f81a150ea8f35194baa.zip" `
  -OutFile "third_party/ml-mobileclip-aecfb545.zip"
Expand-Archive `
  -LiteralPath "third_party/ml-mobileclip-aecfb545.zip" `
  -DestinationPath "third_party/mobileclip-src" `
  -Force

# 2. 同步锁定的后端依赖
uv sync --project backend --locked

# 3. 下载固定 revision 的文本模型并生成本地清单
backend\.venv\Scripts\python.exe model-tools/download_models.py `
  --revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42

# 4. 下载并校验固定 MobileCLIP-S0 权重
backend\.venv\Scripts\python.exe model-tools/download_mobileclip.py

# 5. 下载 Apache Tika 3.3.1 JAR；仓库内摘要文件负责真实性校验
Invoke-WebRequest `
  -Uri "https://archive.apache.org/dist/tika/3.3.1/tika-server-standard-3.3.1.jar" `
  -OutFile "tools/tika/tika-server-standard-3.3.1.jar"

# 6. 核对完整启动预检
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
```

说明文本必须明确：第 1 至 4 步需要联网且只执行一次；正常 MVP 启动设置
`HF_HUB_OFFLINE=1` 和 `TRANSFORMERS_OFFLINE=1`，不会访问网络。文本模型 revision
来自 Hugging Face 官方模型 API 的固定提交
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`。

- [ ] **步骤 2：写入一键启动、API 演示和退出说明**

手册必须包含以下可直接运行的命令：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

启动后访问：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/health/live
http://127.0.0.1:8000/health/ready
```

加入 `POST /v1/indexing/jobs`、轮询任务、`POST /v1/search` 和过滤搜索的完整
PowerShell `Invoke-RestMethod` 示例。退出说明使用当前终端的 `Ctrl+C`，并说明
启动器只收尾自己创建的 Tika 进程。

- [ ] **步骤 3：写入五格式烟测和重启持久化步骤**

使用既有真实 E2E 查询作为默认演示内容：

```powershell
backend\.venv\Scripts\python.exe backend/tools/smoke_mvp.py `
  --input-root mvp-input `
  --keyword-query "没有互联网连接" `
  --text-query "offline system for searching private documents" `
  --image-query "a blue geometric logo on a white rounded square" `
  --output docs/week4/evidence/mvp-api-smoke-summary.json
```

停止并重新启动同一 `data/mvp` 后，执行：

```powershell
backend\.venv\Scripts\python.exe backend/tools/smoke_mvp.py `
  --input-root mvp-input `
  --keyword-query "没有互联网连接" `
  --text-query "offline system for searching private documents" `
  --image-query "a blue geometric logo on a white rounded square" `
  --require-existing-index `
  --output docs/week4/evidence/mvp-api-smoke-summary.json
```

手册必须列出 `mvp-input` 所需的五种扩展名，并说明输入文件、模型和数据库不会
进入 Git。

- [ ] **步骤 4：补充故障排查与合规边界**

至少覆盖以下稳定错误字符串和处理动作：

- `Python executable not found`：运行 `uv sync --project backend --locked`。
- `Model manifest not found`：重新执行两个模型下载脚本。
- `Tika server JAR not found`：按 `tools/tika/README.md` 放置 3.3.1 JAR。
- `Tika server JAR SHA-512 mismatch`：删除错误 JAR，重新从 Apache 官方归档获取。
- `API port is already in use`：使用 `-Port 8001`，并相应调整访问地址。
- `status: not_ready`：检查 Tika、模型摘要和 `data/mvp` 写入权限。

明确说明本 MVP 使用现有 Python 真实推理适配器；不宣称已经将服务运行时替换为
TensorFlow Lite，也不宣称已经完成第五周 Flutter 和无障碍交付。

- [ ] **步骤 5：更新第四周 README**

在 `docs/week4/README.md` 的“运行约束”后增加“一键启动 MVP”小节，链接：

- `MVP_RUNBOOK.md`
- `reports/端到端功能测试报告.docx`
- `reports/检索准确率基准报告.docx`
- `evidence/mvp-api-smoke-summary.json`

同时将原来“默认 `create_app()` 未注入 Week 4 运行时”的第五周 P0 描述更新为：
生产 MVP 已通过 `tools/start-mvp.ps1` 注入运行时；默认 `create_app()` 仍为测试和
仅解析场景保留。

- [ ] **步骤 6：执行文档静态自审**

```powershell
$files = @('docs/week4/MVP_RUNBOOK.md', 'docs/week4/README.md')
$redFlags = @(('T' + 'BD'), ('T' + 'ODO'), ('FIX' + 'ME'))
Select-String -Path $files -Pattern $redFlags
git diff --check -- $files
```

预期：第一条命令没有匹配；第二条命令退出码为 0。

- [ ] **步骤 7：提交任务 5**

```powershell
git add docs/week4/MVP_RUNBOOK.md docs/week4/README.md
git commit -m "docs: add runnable offline MVP guide"
```

### 任务 6：生成真实证据并完成提交级验证

**文件：**
- 新增：`docs/week4/evidence/mvp-api-smoke-summary.json`
- 验证：全部已修改源码、测试和文档

- [ ] **步骤 1：完成聚焦自动化回归**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q `
  backend/tests/test_mvp_runtime.py `
  backend/tests/test_mvp_launcher.py `
  backend/tests/test_mvp_smoke.py `
  backend/tests/test_api.py `
  backend/tests/test_week4_api.py `
  backend/tests/test_runtime_factory.py
```

预期：退出码为 0，无失败和错误。

- [ ] **步骤 2：执行完整仓库回归**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q
```

预期：退出码为 0；如果 Tika 未运行，只允许既有真实 DOCX 集成项跳过。

- [ ] **步骤 3：执行第四周核心覆盖率门**

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q backend `
  --cov=content_retrieval.storage `
  --cov=content_retrieval.retrieval `
  --cov=content_retrieval.services.indexing `
  --cov=content_retrieval.mvp `
  --cov-report=term-missing `
  --cov-fail-under=85
```

预期：退出码为 0，总覆盖率不低于 85%。

- [ ] **步骤 4：用真实资源执行首次 HTTP 烟测**

确保 `models/model-manifest.json`、两个模型、Tika 3.3.1 和 `mvp-input` 五格式文件
均已准备。启动：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

在另一终端运行任务 5 步骤 3 的首次烟测命令。预期：JSON 中
`status="passed"`、五种格式齐全、`failed_files=0`、四类检索均有命中，且图片
模态过滤检查通过。

- [ ] **步骤 5：重启并生成最终持久化证据**

在启动终端按 `Ctrl+C`，确认 API 已停止；使用同一命令再次启动服务。在另一终端
运行带 `--require-existing-index` 的烟测命令。

预期：`pre_index_record_count > 0` 且
`persistent_restart.required=true`、`persistent_restart.passed=true`。

- [ ] **步骤 6：校验证据结构后提交**

```powershell
$evidence = Get-Content -Raw `
  docs/week4/evidence/mvp-api-smoke-summary.json | ConvertFrom-Json
if ($evidence.status -ne 'passed') { throw 'MVP smoke did not pass' }
if ($evidence.formats.Count -ne 5) { throw 'MVP smoke did not cover five formats' }
if (-not $evidence.persistent_restart.passed) { throw 'Persistence did not pass' }

git add docs/week4/evidence/mvp-api-smoke-summary.json
git commit -m "test: record runnable MVP HTTP evidence"
```

- [ ] **步骤 7：审计提交内容**

```powershell
git status --short
git diff master...HEAD --name-status
git diff master...HEAD --check
git ls-files models data mvp-input tools/tika backend/.venv | Select-String `
  -Pattern '\.(pt|bin|safetensors|jar|sqlite3?)$|chroma|mvp-input'
```

预期：功能工作树无意外未提交源码；差异只包含计划列出的代码、测试、文档和 JSON
证据；最后一条命令不显示模型权重、Tika JAR、数据库、用户输入或虚拟环境。

- [ ] **步骤 8：在精确提交的干净 detached worktree 中复验**

```powershell
$verifyPath = 'F:\contentretrivalsystem\.worktrees\week4-runnable-mvp-verify'
git worktree add --detach $verifyPath HEAD
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q
git worktree remove $verifyPath
```

预期：精确提交在不依赖功能工作树未跟踪源码的情况下退出码为 0。若未运行 Tika，
只允许既有真实 DOCX 集成项跳过。

## 计划自审

- 规格覆盖：一键启动、真实模型、Tika、运行时生命周期、健康检查、五格式索引、
  三通道与混合检索、排序过滤、Chroma 重启持久化、中文运行手册、E2E 报告和
  准确率报告均映射到具体任务。
- 范围控制：没有加入 Flutter、无障碍、身份认证、云服务、持久化任务队列或
  TensorFlow Lite 运行时迁移。
- 类型一致性：`MvpSettings`、`TikaReadinessProbe`、`create_mvp_app`、
  `SmokeQueries` 和 `run_smoke` 在首次定义后保持相同名称与参数。
- 安全边界：启动器只停止自身创建的 Tika PID；运行时关闭不清空索引；测试与
  证据提交不包含模型、数据库或用户文件。
- 测试顺序：每项生产代码均先有能够观察到预期失败的测试，再写最小实现并运行
  聚焦回归。
