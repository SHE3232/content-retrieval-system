# HTTP API 参考

本文描述当前 FastAPI 应用的完整 HTTP 公开面。代码来源是
`backend/src/content_retrieval/api/app.py`、`api/routes/` 和 `api/schemas.py`；客户端对应实现位于
`frontend/lib/features/*/data/`。架构与一致性语义见[架构深度说明](ARCHITECTURE.md)。

## 1. 协议约定

| 项目 | 值 |
|---|---|
| 默认基础地址 | `http://127.0.0.1:8000` |
| API 标题/版本 | `Content Retrieval API` / `0.1.0` |
| 请求与响应 | JSON，路径字段序列化为字符串 |
| 时间 | ISO 8601；持久化记录由后端输出带时区时间 |
| 认证 | 无；只应绑定回环地址 |
| CORS | 未配置；浏览器跨源客户端默认不可用 |
| OpenAPI | `GET /openapi.json` |
| 交互文档 | `GET /docs`（Swagger UI）、`GET /redoc` |

FastAPI/Pydantic 输入校验失败统一返回 422，正文是框架标准 `detail` 数组。应用主动返回的错误使用：

```json
{
  "detail": {
    "code": "JOB_NOT_FOUND",
    "message": "Indexing job not found"
  }
}
```

## 2. 端点总览

| 方法 | 路径 | 成功状态 | 用途 |
|---|---|---:|---|
| GET | `/health/live` | 200 | 进程存活检查 |
| GET | `/health/ready` | 200/503 | Tika、运行时和 Chroma 就绪检查 |
| POST | `/v1/ingestion/jobs` | 202 | 创建只解析、不持久化的摄取任务 |
| GET | `/v1/ingestion/jobs/{job_id}` | 200 | 查询摄取任务及解析结果 |
| POST | `/v1/indexing/jobs` | 202 | 创建解析、嵌入和持久化任务 |
| GET | `/v1/indexing/jobs/{job_id}` | 200 | 查询索引任务状态与汇总 |
| GET | `/v1/indexing/jobs/{job_id}/failures` | 200 | 查询文件级和任务级失败 |
| GET | `/v1/index/files` | 200 | 分页列出已索引文件 |
| DELETE | `/v1/index/files/{source_key}` | 200 | 删除一个来源的索引记录，不删除源文件 |
| POST | `/v1/index/files/{source_key}/reindex` | 202 | 强制重建一个已索引文件 |
| POST | `/v1/search` | 200 | 执行关键词、文本语义和图文语义检索 |
| GET | `/v1/index/stats` | 200 | 返回记录、文件和模态统计 |

## 3. 公共类型与枚举

### 3.1 标识

| 字段 | 形式 | 含义 |
|---|---|---|
| `job_id` | UUID 字符串 | 进程内任务标识；服务重启后失效 |
| `file_id` | 64 位小写十六进制 SHA-256 | 文件内容身份 |
| `source_key` | 64 位小写十六进制 SHA-256 | 规范化绝对路径身份；路径参数严格校验该格式 |
| `source_id` | 64 位小写十六进制 SHA-256 | 文本块或图片向量身份 |

### 3.2 任务状态

摄取和索引任务都使用：

- `queued`
- `running`
- `completed`
- `completed_with_errors`
- `failed`

`queued` 和 `running` 不是终态。调用方应轮询到其余三个状态之一。任务没有服务端超时或取消端点。

### 3.3 搜索枚举

| 类型 | 可选值 |
|---|---|
| 搜索通道 | `keyword`、`text_semantic`、`image_semantic` |
| 搜索模态 | `text`、`image` |
| 解析模态 | `text`、`document`、`image` |

文档和 TXT 在索引后都变成搜索模态 `text`；解析响应仍分别保留 `document` 或 `text`。

## 4. 健康检查

### `GET /health/live`

只证明 FastAPI 进程能够响应，不检查模型、Tika 或存储。

```json
{"status": "ok"}
```

### `GET /health/ready`

200：

```json
{"status": "ready"}
```

503：

```json
{"status": "not_ready"}
```

完整 MVP 中，就绪要求运行时已经构建、Tika `/version` 可用且 Chroma 能返回记录数。探测异常也会
转换成 503，而不会泄露内部异常。

## 5. 摄取 API

摄取只扫描和解析文件，不分块、不生成向量、不写入 Chroma。它使用独立的进程内任务存储。

### `POST /v1/ingestion/jobs`

请求：

| 字段 | 类型 | 必填 | 默认/约束 |
|---|---|---:|---|
| `paths` | `string[]` | 是 | 至少 1 项；可以混合文件和目录 |
| `authorized_roots` | `string[]` | 是 | 至少 1 项；路径解析后必须存在 |
| `recursive` | `boolean` | 否 | 默认 `true` |

```json
{
  "paths": ["F:\\notes", "F:\\single\\guide.pdf"],
  "authorized_roots": ["F:\\notes", "F:\\single"],
  "recursive": true
}
```

202 响应：

```json
{
  "job_id": "cf85ba65-71c3-4373-8c93-b1dbe2348567",
  "status": "queued"
}
```

显式传入的不支持文件会成为 `UNSUPPORTED_FORMAT` 错误；扫描目录时发现的不支持文件会成为
`unsupported_format` skip。单次请求内内容完全相同的后续文件会成为 `duplicate_content` skip。

### `GET /v1/ingestion/jobs/{job_id}`

不存在的任务返回 404 `JOB_NOT_FOUND`。成功响应结构：

```json
{
  "job_id": "cf85ba65-71c3-4373-8c93-b1dbe2348567",
  "status": "completed_with_errors",
  "counts": {
    "total": 3,
    "pending": 0,
    "running": 0,
    "succeeded": 1,
    "failed": 1,
    "skipped": 1
  },
  "results": [],
  "errors": [],
  "skips": []
}
```

`queued`、`running` 或没有批次结果的 `failed` 任务会返回全零 counts 和三个空数组。

#### `results[]` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `file_id` | `string` | 内容 SHA-256 |
| `path`、`name` | `string` | 解析后的绝对路径与文件名 |
| `mime_type` | `string` | 解析器确认的 MIME 类型 |
| `modality` | enum | `text`、`document` 或 `image` |
| `size_bytes` | `integer >= 0` | 文件字节数 |
| `modified_at` | `datetime` | 文件修改时间 |
| `text` | `string|null` | TXT/PDF/DOCX 正文；图片为 null |
| `page_count` | `integer|null` | PDF 页数，否则通常为 null |
| `width`、`height` | `integer|null` | 图片尺寸，否则为 null |
| `metadata` | `object` | 受解析器控制的元数据 |
| `warnings` | `string[]` | 空文本、空页等非致命问题 |

#### `errors[]` 字段

`path`、`code`、`message`、`retryable`。可能的解析错误码包括：

| code | retryable | 含义 |
|---|---:|---|
| `PATH_NOT_FOUND` | false | 路径不存在 |
| `PATH_NOT_AUTHORIZED` | false | 文件不在任一授权根下 |
| `UNSUPPORTED_FORMAT` | false | 显式文件没有注册解析器 |
| `CORRUPTED_FILE` | false | PDF 等结构损坏 |
| `TEXT_DECODE_ERROR` | false | 文本不符合确定性编码策略 |
| `IMAGE_DECODE_ERROR` | false | JPEG/PNG 解码失败或触发安全限制 |
| `PDF_ENCRYPTED` | false | PDF 需要密码 |
| `TIKA_UNAVAILABLE` | true | 本地 Tika 连接失败 |
| `PARSE_TIMEOUT` | true | Tika 请求超时 |
| `FILE_TOO_LARGE` | true | 超过默认 100 MiB 单文件限制 |
| `INTERNAL_ERROR` | false | 未预期解析异常的安全边界 |

#### `skips[]` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | `string` | 被跳过文件 |
| `reason` | enum | `duplicate_content` 或 `unsupported_format` |
| `file_id` | `string|null` | 重复内容时存在 |
| `duplicate_of` | `string|null` | 同一批次中首个相同内容文件的路径 |

## 6. 索引任务 API

### `POST /v1/indexing/jobs`

请求字段与摄取任务完全相同。索引服务不可用时返回 503 `SERVICE_UNAVAILABLE`；已有索引变更正在
运行时返回 409 `INDEX_MUTATION_CONFLICT`。

```powershell
$body = @{
  paths = @('F:\Knowledge')
  authorized_roots = @('F:\Knowledge')
  recursive = $true
} | ConvertTo-Json -Depth 4

$job = Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/v1/indexing/jobs' `
  -ContentType 'application/json' `
  -Body $body
$job
```

202 响应包含 `job_id` 和初始 `status="queued"`。

### `GET /v1/indexing/jobs/{job_id}`

任务不存在时返回 404 `JOB_NOT_FOUND`。活动或失败任务的 `result` 可以为 null；完成后结构为：

```json
{
  "job_id": "cf85ba65-71c3-4373-8c93-b1dbe2348567",
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
    "failures": []
  }
}
```

计数语义：

| 字段 | 含义 |
|---|---|
| `parsed_files` | 解析成功文件加解析失败文件，不包含 skip |
| `indexed_files` | 至少成功写入一条当前记录的文件数 |
| `indexed_records` | 本轮 upsert 的文本块/图片记录数 |
| `skipped_files` | 不支持格式或请求内重复内容数 |
| `failed_files` | 没有写入可用记录的文件数 |
| `partial_files` | 写入了记录但仍有分块、嵌入或存储失败的文件数 |
| `unchanged_files` | 内容、分块身份和模型契约均未变化，未重写的文件数 |
| `removed_stale_records` | 完整成功后删除的旧分片记录数 |

`parsed_files = indexed_files + failed_files + unchanged_files`，且
`partial_files <= indexed_files`。`completed_with_errors` 表示 `failed_files` 或 `partial_files` 非零。

### `GET /v1/indexing/jobs/{job_id}/failures`

```json
{
  "job_id": "cf85ba65-71c3-4373-8c93-b1dbe2348567",
  "status": "failed",
  "total": 0,
  "failures": [],
  "error": {
    "code": "STORAGE_ERROR",
    "message": "local index is locked",
    "retryable": true
  }
}
```

`failures[]` 是文件/记录级错误，字段为 `path`、`code`、`message`、`stage`、`retryable`、
`file_id|null`、`source_id|null`。`stage` 常见值是 `parsing`、`chunking`、`embedding`、`storage`
或 `indexing`。`error` 是使整个任务失败的错误；未预期异常会被净化为
`INDEXING_JOB_FAILED`，不会返回内部异常文本。

轮询示例：

```powershell
do {
  Start-Sleep -Milliseconds 250
  $state = Invoke-RestMethod (
    'http://127.0.0.1:8000/v1/indexing/jobs/' + $job.job_id
  )
} while ($state.status -in @('queued', 'running'))
$state
```

## 7. 索引目录 API

### `GET /v1/index/files`

查询参数：

| 参数 | 类型 | 默认 | 约束 |
|---|---|---:|---|
| `page` | integer | 1 | `>= 1` |
| `page_size` | integer | 20 | `1..100` |

```json
{
  "items": [
    {
      "source_key": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "file_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "path": "F:\\Knowledge\\notes.txt",
      "name": "notes.txt",
      "mime_type": "text/plain",
      "modality": "text",
      "size_bytes": 1024,
      "modified_at": "2026-08-09T10:00:00Z",
      "record_count": 2
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "total_pages": 1
}
```

没有记录时 `items=[]`、`total=0`、`total_pages=0`。存储不可读返回 503
`STORAGE_UNAVAILABLE`。

### `DELETE /v1/index/files/{source_key}`

只删除该来源的索引记录，不删除本地源文件。成功后刷新关键词目录。

```json
{
  "source_key": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "deleted_records": 2
}
```

错误：

- 404 `FILE_NOT_INDEXED`：目录中没有该来源。
- 409 `INDEX_MUTATION_CONFLICT`：另一个索引变更正在运行。
- 503 `SERVICE_UNAVAILABLE` 或 `STORAGE_UNAVAILABLE`。
- 503 `RETRIEVAL_UNAVAILABLE`：记录已删除，但关键词目录刷新失败。此状态不是回滚。
- 422：`source_key` 不是 64 位小写十六进制字符串。

### `POST /v1/index/files/{source_key}/reindex`

不需要请求体。端点读取目录中的绝对源路径，要求文件仍存在，并以 `force=True` 创建后台任务。
202 响应与创建索引任务相同。

错误：

- 404 `FILE_NOT_INDEXED`：目录中没有该来源。
- 404 `SOURCE_FILE_NOT_FOUND`：目录记录存在，但源文件已不存在。
- 409 `INDEX_MUTATION_CONFLICT`：另一个索引变更正在运行。
- 503 `SERVICE_UNAVAILABLE` 或 `STORAGE_UNAVAILABLE`。

重建后的刷新错误通过任务状态和 `/failures` 暴露，而不是改变已经返回的 202 响应。

## 8. 搜索 API

### `POST /v1/search`

请求：

| 字段 | 类型 | 必填 | 默认/约束 |
|---|---|---:|---|
| `query` | string | 是 | 去除并折叠空白后不得为空 |
| `top_k` | integer | 否 | 默认 10，范围 `1..100` |
| `filters` | object | 否 | 默认空过滤器 |
| `channels` | enum[] | 否 | 默认三个通道；至少 1 项且不能重复 |
| `weights` | object/null | 否 | 默认 null；键只能是已知通道，值必须 `> 0` |

`filters`：

| 字段 | 类型 | 默认/约束 |
|---|---|---|
| `mime_types` | `string[]` | 默认空；不能含空字符串 |
| `modalities` | `("text"|"image")[]` | 默认空 |
| `path_prefix` | `string|null` | 必须是绝对路径 |
| `modified_after` | `datetime|null` | 必须带时区 |
| `modified_before` | `datetime|null` | 必须带时区，且不能早于 `modified_after` |

完整请求：

```json
{
  "query": "离线检索私人文档",
  "top_k": 10,
  "filters": {
    "mime_types": ["text/plain", "application/pdf"],
    "modalities": ["text"],
    "path_prefix": "F:\\Knowledge",
    "modified_after": "2026-01-01T00:00:00+08:00",
    "modified_before": null
  },
  "channels": ["keyword", "text_semantic"],
  "weights": {
    "keyword": 0.35,
    "text_semantic": 1.0
  }
}
```

200 响应：

```json
{
  "query": "离线检索私人文档",
  "hits": [
    {
      "file_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "source_id": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "path": "F:\\Knowledge\\notes.txt",
      "name": "notes.txt",
      "mime_type": "text/plain",
      "modality": "text",
      "score": 0.75,
      "match_reasons": ["keyword", "text_semantic"],
      "snippet": "本地内容检索不会上传私人文档……",
      "page_number": null,
      "paragraph_number": 1
    }
  ],
  "total_candidates": 1,
  "elapsed_ms": 3.5,
  "weights": {
    "keyword": 0.35,
    "text_semantic": 1.0
  }
}
```

`score` 是文件级融合分数，范围 `[0,1]`，不是概率。图片命中的 `snippet`、`page_number` 和
`paragraph_number` 为 null。文本命中恰有一个定位字段，PDF 使用页码，其他文本使用段落号。
`total_candidates` 是所有活动通道去重后的候选文件数，不一定等于 `hits.length`。

未提供 `weights` 时默认值为：

```json
{
  "keyword": 0.35,
  "text_semantic": 1.0,
  "image_semantic": 0.85
}
```

响应只返回实际活动通道的权重。过滤器排除某模态时，对应语义通道会被自动移除。

搜索服务不可用返回 503 `SERVICE_UNAVAILABLE`。查询编码、向量检索或领域校验失败返回 400
`SEARCH_FAILED`。输入 schema 不合法则返回 422。

PowerShell 示例：

```powershell
$body = @{
  query = '离线检索私人文档'
  top_k = 10
  channels = @('keyword', 'text_semantic', 'image_semantic')
  filters = @{}
  weights = $null
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/v1/search' `
  -ContentType 'application/json' `
  -Body $body
```

## 9. 索引统计

### `GET /v1/index/stats`

```json
{
  "record_count": 12,
  "file_count": 5,
  "text_record_count": 10,
  "image_record_count": 2
}
```

`record_count` 统计文本块和图片记录，`file_count` 按 `file_id` 去重。存储不可读返回 503
`STORAGE_UNAVAILABLE`，检索运行时未配置返回 503 `SERVICE_UNAVAILABLE`。

## 10. 应用错误矩阵

| HTTP | code | 出现场景 |
|---:|---|---|
| 400 | `SEARCH_FAILED` | 查询编码、向量检索或搜索领域校验失败 |
| 404 | `JOB_NOT_FOUND` | 摄取或索引任务不存在 |
| 404 | `FILE_NOT_INDEXED` | 删除/重建目标不在索引目录 |
| 404 | `SOURCE_FILE_NOT_FOUND` | 重建时源文件已不存在 |
| 409 | `INDEX_MUTATION_CONFLICT` | 另一个索引、删除或重建正在运行 |
| 422 | 框架校验错误 | 请求体、查询参数或 `source_key` 不符合 schema |
| 503 | `SERVICE_UNAVAILABLE` | 完整搜索运行时没有安装到应用 |
| 503 | `STORAGE_UNAVAILABLE` | Chroma 列表、统计或删除失败 |
| 503 | `RETRIEVAL_UNAVAILABLE` | 删除已发生，但关键词目录刷新失败 |

文件级解析/处理错误通常放在任务结果中，任务 HTTP 查询本身仍返回 200。调用方必须同时检查任务
终态、`result.failed_files`、`result.partial_files`、`failures` 和任务级 `error`。

## 11. 兼容性规则

当前没有显式的 API 版本协商机制，只有路径前缀 `/v1`。修改契约时遵循：

1. 新增可选响应字段通常向后兼容；删除、改名或改变类型不兼容。
2. 新增枚举值可能使当前 Flutter 客户端解析失败，必须同步更新客户端枚举和测试。
3. `source_key`、任务状态、错误 code 和计数字段属于客户端依赖的稳定契约。
4. 路由或 Pydantic schema 改动后，应重新生成/检查 `/openapi.json`，运行 API 与 Flutter 客户端测试，
   再更新本文。具体检查表见[维护指南](MAINTENANCE_GUIDE.md#8-保持代码与文档同步)。
