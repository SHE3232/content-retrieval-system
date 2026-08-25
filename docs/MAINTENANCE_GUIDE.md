# How to 维护离线本地内容检索系统

本指南面向修改代码、模型、索引或交付包的维护者。它给出可执行步骤、验证方法和故障处理。
系统原理见[架构深度说明](ARCHITECTURE.md)，字段级接口见[API 参考](API_REFERENCE.md)。

## 1. 维护基线

### 工具链

| 组件 | 当前约束/来源 |
|---|---|
| Python | `backend/pyproject.toml` 要求 `>=3.10,<3.11` |
| Python 依赖 | `backend/uv.lock`，使用 `uv sync --locked` |
| Flutter/Dart | `frontend/pubspec.yaml` 与 `frontend/pubspec.lock`；Dart SDK 约束当前为 `^3.12.2` |
| Java/Tika | 本机 Java 可执行；Tika JAR 固定为 3.3.1 并校验 SHA-512 |
| 模型 | `models/model-manifest.json`，schema 1，模型文件必须通过 SHA-256 |
| 数据库 | Chroma 1.x，持久化 schema 当前为 1 |

不要根据周报中的历史版本号推断当前代码。维护时使用以下事实来源：

| 事实 | 权威代码/配置 |
|---|---|
| HTTP 路径和状态码 | `backend/src/content_retrieval/api/routes/` |
| JSON 字段与输入约束 | `backend/src/content_retrieval/api/schemas.py` |
| 支持格式 | `parsers/registry.py` 及各解析器的 `supported_extensions` |
| 模型 ID 与运行时组装 | `backend/src/content_retrieval/runtime.py` |
| 模型路径、维度和摘要 | 本地 `models/model-manifest.json` |
| 搜索通道、默认权重和融合 | `retrieval/service.py`、`retrieval/fusion.py` |
| Flutter 使用的 API | `frontend/lib/features/*/data/` |
| 测试范围 | `pytest.ini`、`backend/pyproject.toml`、`frontend/test/` |
| Week 6 交付门禁 | `docs/week6/README.md` 与 `tools/week6/validate_evidence.py` |

## 2. 建立或刷新开发环境

### 后端

在仓库根目录执行：

```powershell
uv sync --project backend --locked
& '.\backend\.venv\Scripts\python.exe' --version
```

版本必须是 Python 3.10.x。不要直接对虚拟环境运行无锁 `pip install -U`；依赖变更应先修改
`backend/pyproject.toml`，再通过 `uv` 更新锁文件并运行回归。

大体积同步、构建、解压和验收临时文件应留在 F 盘：

```powershell
$maintenanceTemp = 'F:\contentretrivalsystem\.codex_tmp\maintenance'
New-Item -ItemType Directory -Force -Path $maintenanceTemp | Out-Null
$env:TEMP = $maintenanceTemp
$env:TMP = $maintenanceTemp
```

不要把临时构建或大型模型复制到系统盘。

### Flutter

```powershell
Set-Location frontend
flutter pub get
flutter doctor -v
Set-Location ..
```

包版本以 `pubspec.lock` 为准。升级 Flutter 或依赖后，要在所有实际支持的平台重新构建，不要只以
`flutter analyze` 作为跨平台结论。

### 本地模型

运行时要求清单中同时存在：

- `text-multilingual-v1`
- `mobileclip-s0-v1`

快速验证清单和文件摘要的最安全方式是启动器预检：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
```

`models/model-manifest.example.json` 的全零摘要只是结构示例，不能用于启动。真实模型准备见
[第三周说明](week3/README.md)。

### Apache Tika

仓库提交 `tools/tika/tika-server-standard-3.3.1.jar.sha512`，不提交实际 JAR。把精确版本 JAR 放到
同目录后执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/tika/start-tika.ps1
Invoke-RestMethod http://127.0.0.1:9998/version
```

日常运行通常不需要手动启动；`tools/start-mvp.ps1` 会验证并按需创建 Tika。

## 3. 启动、检查和安全停止

### 预检

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
```

修改端口或数据目录时，预检和正式启动必须使用同一参数：

```powershell
$dataDirectory = 'F:\contentretrivalsystem\data\maintenance-mvp'
powershell -ExecutionPolicy Bypass `
  -File tools/start-mvp.ps1 `
  -DataDir $dataDirectory `
  -Port 8001 `
  -CheckOnly
```

### 正式启动

```powershell
powershell -ExecutionPolicy Bypass `
  -File tools/start-mvp.ps1 `
  -DataDir $dataDirectory `
  -Port 8001
```

验证三个层次：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health/live
Invoke-RestMethod http://127.0.0.1:8001/health/ready
Invoke-RestMethod http://127.0.0.1:8001/v1/index/stats
```

`live` 通过但 `ready` 失败，说明 HTTP 进程活着，但 Tika、运行时或存储不可用。`stats` 通过才证明
检索服务能读取索引。

### 停止

在启动终端按 `Ctrl+C` 并等待进程退出。不要按进程名批量结束 `java` 或 `python`：启动器会跟踪
自己创建的 Tika 进程，应用还要排空后台索引任务并关闭 Chroma。只有进程无响应且已确认没有索引
写入时，才使用针对精确 PID 的恢复操作。

## 4. 运行测试和质量门禁

### 快速后端回归

适合解析、API、索引、检索和存储逻辑的日常修改，不加载真实模型或 Tika：

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest `
  backend/tests `
  -m 'not requires_models and not requires_tika and not stress'
```

修改 API 时至少运行：

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest `
  backend/tests/test_api.py `
  backend/tests/test_api_extended.py `
  backend/tests/test_week4_api.py `
  backend/tests/test_ui_index_api.py
```

修改解析、索引或检索时按模块增加对应文件，例如
`test_parsing_contracts.py`、`test_indexing_service.py`、`test_retrieval_service.py` 和
`test_chroma_repository.py`。

### Flutter 回归

```powershell
Push-Location frontend
try {
  flutter analyze
  if ($LASTEXITCODE -ne 0) { throw 'flutter analyze failed' }
  flutter test
  if ($LASTEXITCODE -ne 0) { throw 'flutter test failed' }
}
finally {
  Pop-Location
}
```

API 字段变更必须覆盖：

- `test/features/search/search_api_client_test.dart`
- `test/features/library/index_library_api_client_test.dart`
- `test/features/status/backend_status_controller_test.dart`
- 受影响 controller/page 测试

### 数据、模型和转换工具

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest `
  datasets `
  model-tools `
  conversion-tools
```

真实模型和 Tika 测试应在资产就绪后显式运行。不要为了让本地环境“全绿”而移除
`requires_models` 或 `requires_tika` 标记。

### 周交付门禁

Week 5 允许查看未完成证据：

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  tools/week5/validate_evidence.py `
  docs/week5/evidence `
  --allow-incomplete
```

Week 6 最终门禁不得带 `--allow-incomplete`：

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  tools/week6/validate_evidence.py `
  docs/week6/evidence
```

证据状态为 `NOT_RUN` 或缺少外部平台验证时，必须保留真实状态，不能手工改为 PASS。

## 5. 备份、恢复和重建索引

索引是派生数据，源文件和模型清单才是重建依据；但对大型资料库，备份可以节省重新嵌入时间。

### 创建一致性备份

1. 用 `Ctrl+C` 正常停止后端并等待退出。
2. 确认没有 `tools/start-mvp.ps1` 或打包启动器仍在使用该数据目录。
3. 复制整个数据目录，而不是只复制单个 Chroma collection。

```powershell
$sourceData = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\data\mvp'
)
$backupData = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\backups\mvp-2026-08-22'
)
if (-not (Test-Path -LiteralPath $sourceData -PathType Container)) {
  throw "Data directory not found: $sourceData"
}
if (Test-Path -LiteralPath $backupData) {
  throw "Backup target already exists: $backupData"
}
New-Item -ItemType Directory -Force -Path (
  Split-Path $backupData -Parent
) | Out-Null
Copy-Item -LiteralPath $sourceData -Destination $backupData -Recurse
```

备份完成后，用单独的数据目录启动并检查 `stats`，不要在原目录仍打开时复制数据库文件。

### 可恢复地替换损坏索引

不要直接递归删除当前索引。停止服务后先把它移动到明确的隔离目录：

```powershell
$currentData = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\data\mvp'
)
$quarantineData = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\backups\mvp-corrupt-2026-08-22'
)
if (-not (Test-Path -LiteralPath $currentData -PathType Container)) {
  throw "Current data directory not found: $currentData"
}
if (Test-Path -LiteralPath $quarantineData) {
  throw "Quarantine target already exists: $quarantineData"
}
New-Item -ItemType Directory -Force -Path (
  Split-Path $quarantineData -Parent
) | Out-Null
Move-Item -LiteralPath $currentData -Destination $quarantineData
```

随后重新启动，运行时会创建新数据目录，再通过 `/v1/indexing/jobs` 重新索引受控源目录。验证搜索和
记录数后再决定是否保留隔离副本。

若要恢复已经验证过的备份，保持服务停止，先按上例隔离当前目录，再把备份复制回原位置：

```powershell
$verifiedBackup = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\backups\mvp-2026-08-22'
)
$restoreTarget = [System.IO.Path]::GetFullPath(
  'F:\contentretrivalsystem\data\mvp'
)
if (-not (Test-Path -LiteralPath $verifiedBackup -PathType Container)) {
  throw "Verified backup not found: $verifiedBackup"
}
if (Test-Path -LiteralPath $restoreTarget) {
  throw "Restore target must be absent: $restoreTarget"
}
New-Item -ItemType Directory -Force -Path (
  Split-Path $restoreTarget -Parent
) | Out-Null
Copy-Item -LiteralPath $verifiedBackup -Destination $restoreTarget -Recurse
```

用恢复目录执行 `-CheckOnly` 并启动服务，再比较 `/v1/index/stats` 和代表性查询。备份与当前模型
空间或 schema 不兼容时，不要修改 collection 元数据；改用新目录全量重建。

### 处理移动或删除的源文件

`source_key` 来自绝对路径。文件移动后，新路径会形成新来源，旧记录不会自动消失。维护流程是：

1. `GET /v1/index/files` 找到旧路径的 `source_key`。
2. `DELETE /v1/index/files/{source_key}` 删除旧来源记录。
3. 对新路径提交索引任务。
4. 检查任务 `failed_files`、`partial_files` 和 `/failures`。

删除 API 不删除源文件。若删除返回 `RETRIEVAL_UNAVAILABLE`，向量删除已经发生，应先恢复关键词
目录或重启运行时，再根据目录状态决定下一步，不能盲目重复删除。

## 6. 扩展解析格式

以新增一个格式为例：

1. 在 `backend/src/content_retrieval/parsers/` 实现 `Parser` 协议：
   `supported_extensions`、`supported_mime_types` 和 `parse(Path) -> ParseResult`。
2. 在 `create_default_registry()` 注册解析器。后注册的相同扩展名/MIME 会覆盖先前映射，应避免冲突。
3. 决定解析模态。可提取文本的文档使用 `document`，纯文本使用 `text`，视觉文件使用 `image`。
4. 若是文本/文档，提供稳定正文；需要保留页码时按 PDF 约定写入 `metadata.page_texts`。
5. 把可预期异常转换为受控 `ParseError`，不要把第三方库异常和本机路径细节直接返回给 API。
6. 添加解析器单元测试、注册表测试、批量摄取测试和端到端索引测试。
7. 同步 Flutter `contentTypeMimeTypes`、UI 文案、验证数据清单及本文档。

当前解析器安全策略包括完整图片解码、压缩炸弹警告转错误、PDF 加密拒绝、TXT 严格解码、
100 MiB 文件限制和 DOCX 元数据白名单。新解析器应提供等价的资源与元数据边界。

如果要真正支持 WebP，必须先完成后端解析器和测试，再保留/确认 Flutter 现有 `image/webp` 筛选；
仅修改前端筛选不会增加索引能力。

## 7. 更换模型或存储 schema

### 更换模型

1. 为新模型准备离线文件，计算路径摘要并更新真实模型清单。
2. 若语义空间、模型或维度发生变化，使用新的 `space_id`。不要复用旧空间名写入不兼容向量。
3. 若修改固定 `model_id`，同步 `runtime.py` 中的 `TEXT_MODEL_ID` 或 `IMAGE_MODEL_ID`。
4. 运行清单、嵌入、空间兼容、准确率和性能测试。
5. 使用独立数据目录完成全量重建和检索验收，再切换生产数据目录。
6. 更新 `models/model-manifest.example.json`、架构文档和交付许可证材料。

Chroma collection 会校验 `schema_version`、`space_id`、`model_id` 和 `dimensions`。不匹配时应明确
迁移或重建，不要绕过校验。

### 修改持久化 schema

当前 `ChromaVectorRepository.schema_version` 为 `1`。升级时必须先回答：

- 旧 collection 是原地迁移，还是从源文件全量重建？
- 失败后如何恢复备份？
- 新旧运行时同时打开同一数据目录时会发生什么？
- 打包版本如何标识所需 schema？

桌面离线系统通常优先选择“停止服务、备份、在新目录重建、验证后切换”，因为索引可从源文件和
模型重新生成，迁移代码反而可能扩大损坏面。

## 8. 保持代码与文档同步

每次合并前按变更类型执行：

| 代码变化 | 必须检查的文档 |
|---|---|
| 路由、schema、错误 code、状态码 | `API_REFERENCE.md`、Flutter README |
| 解析格式、大小或编码策略 | 根 README、`ARCHITECTURE.md`、API 解析错误表 |
| 模型 ID、空间、维度、缓存或权重 | `ARCHITECTURE.md`、模型示例清单、Week 3/6 说明 |
| 数据目录、环境变量、端口、启动行为 | 根 README、本文、`docs/week4/MVP_RUNBOOK.md` |
| Flutter 设置键、默认值或路径 | `frontend/README.md`、相关用户指南 |
| 验收阈值、证据路径、包名 | `docs/week6/README.md` 与生成/验证工具帮助文本 |

API 改动的最小同步闭环：

1. 修改 Pydantic schema 或路由。
2. 修改/新增后端契约测试。
3. 修改 Flutter domain model、序列化/解析和测试。
4. 启动无模型的 `create_app()` 或运行测试，确认 `/openapi.json` 反映新契约。
5. 更新 [API 参考](API_REFERENCE.md) 的端点表、字段、示例和错误矩阵。
6. 运行链接检查、API 测试和 Flutter 测试。

不要把周交付文档当作项目级 API 的唯一入口。周文档保留历史验收语境，项目级文档描述当前代码。

## 9. 诊断常见故障

| 现象/错误 | 原因定位 | 处理 |
|---|---|---|
| `Python 3.10 is required` | 解释器不在 `>=3.10,<3.11` | 让 `uv` 使用 64 位 Python 3.10 后重新同步 |
| `Model manifest verification failed` | 缺模型 ID、路径不存在或摘要不匹配 | 阅读冒号后的安全错误，重新准备资产，不要改摘要迁就错误文件 |
| `Tika server JAR SHA-512 mismatch` | JAR 版本或内容错误 | 重新取得 3.3.1 JAR，保留仓库摘要文件不变 |
| `/health/live` 200、`/health/ready` 503 | Tika、运行时或 Chroma 不可用 | 查看启动终端首个异常，直连检查 Tika `/version`，再检查数据目录 |
| 409 `INDEX_MUTATION_CONFLICT` | 已有索引/删除/重建任务 | 轮询当前任务到终态后重试，不要启动多 worker 绕过锁 |
| 任务 `completed_with_errors` | 至少一个文件失败或部分写入 | 查询 `/failures`，按 `stage` 和 `retryable` 分类处理 |
| 任务 `failed` 且 `result=null` | 任务级异常或搜索刷新失败 | 查询 `/failures` 中的 `error`；恢复存储/检索后重试 |
| 搜索没有关键词结果但向量结果存在 | 关键词目录失效或刷新失败 | 检查最近索引/删除错误；正常重启会从 Chroma 重建目录 |
| 重建返回 `SOURCE_FILE_NOT_FOUND` | 索引记录的原绝对路径已失效 | 删除旧来源并索引新路径 |
| Web 客户端显示离线，桌面端正常 | 浏览器同源/CORS 限制 | 使用同源代理或明确配置 CORS；不要把无认证 API 暴露到非可信网络 |
| WebP 无法索引 | 前端过滤值领先于后端解析能力 | 转为 JPEG/PNG，或按第 6 节完整实现 WebP |
| Chroma collection incompatible | 模型/空间/维度/schema 与旧索引不一致 | 备份并在新数据目录重建，不要跳过兼容性校验 |

### 查看任务失败详情

```powershell
$jobId = '<job UUID>'
Invoke-RestMethod (
  'http://127.0.0.1:8000/v1/indexing/jobs/' + $jobId + '/failures'
)
```

优先处理 `storage`、`retrieval` 这类系统级失败，再处理单文件解析或嵌入失败。

## 10. 打包与发布维护

Windows 集成包由 `tools/week6/package_stable_build.ps1` 组装。脚本有意要求：

- `SourceCommit` 是当前 HEAD 的完整 40 位小写提交；
- 工作树完全干净；
- 输出 ZIP 位于 `output/week6/`；
- 模型、Tika、Python、Java、Flutter release 和第三方许可证均存在；
- 轻量包严格小于十进制 `1,000,000,000` 字节；
- 轻量化在独立 staging 中执行，不修改源虚拟环境。

因此发布前先完成测试，再从精确提交构建。不要为了绕过 clean-worktree 门禁在用户的脏工作树中
临时隐藏或删除文件。大型 staging、压缩与解压审计继续放在 F 盘。详细参数和正式证据约定见
[Week 6 说明](week6/README.md)。

最终 ZIP 生成后只做只读清单、哈希和独立解压审计；不要在用于最终打包的白名单暂存目录里再次
运行会生成缓存或数据库的测试。

## 11. 定期维护建议

- 每次代码变更：运行受影响模块测试和文档链接检查。
- 每次 API 变更：完成第 8 节的后端、Flutter、OpenAPI 和文档闭环。
- 每次模型变更：重新校验摘要、准确率、性能、离线安全和许可证。
- 每次发布候选：从精确提交和干净 worktree 构建，在独立目录验证。
- 定期抽检：真实五格式索引、服务重启持久化、关键词/双语义搜索和索引删除/重建。
- 备份前后：停止服务，并记录模型清单摘要、代码提交和数据目录，以便可重复恢复。
