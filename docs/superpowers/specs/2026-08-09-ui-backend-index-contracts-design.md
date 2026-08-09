# UI 后端索引管理契约设计

## 目标

为本地 Flutter UI 补齐四类 FastAPI 契约：索引文件分页列表、单文件删除、单文件
强制重建索引，以及独立的索引失败详情查询。所有单文件操作使用稳定的
`source_key`，不使用会随文件内容变化的 `file_id`。

## 范围

### 纳入范围

- 从现有 Chroma 记录聚合文件级分页列表。
- 删除某个 `source_key` 对应的全部索引记录，但不删除磁盘原文件。
- 使用已保存的绝对路径强制重建一个文件的索引，并复用现有后台任务轮询协议。
- 为逐文件失败和任务级意外失败提供独立查询接口。
- 为服务、任务仓库和 HTTP 契约增加自动化测试。

### 不纳入范围

- 持久化索引任务历史；任务和失败详情仍随进程重启丢失。
- 删除、移动或修改用户磁盘上的原文件。
- 文件列表搜索、筛选、任意排序或游标分页。
- 批量删除、批量重建、取消任务和失败自动重试。
- 新增数据库或改变 Chroma 的持久化格式。

## 选定方案

新增 `IndexCatalogService`，在服务层将 Chroma 的记录级数据聚合为文件级视图，
并封装查找与删除。API 路由保持 HTTP 编排职责；现有 `IndexingService` 继续负责
解析、嵌入、写入和陈旧记录清理。

未选择直接在路由内遍历 Chroma，因为这会让分页和文件聚合规则与 HTTP 层耦合。
未选择新增持久化目录数据库，因为当前 UI 只需要现有索引的实时视图，额外数据库
会引入双写一致性和迁移成本。

## 组件与依赖

```text
FastAPI indexing router
  -> IndexCatalogService
      -> ChromaVectorRepository
  -> IndexingService(force=True)
      -> parsing / chunking / embedding / Chroma
  -> InMemoryIndexingJobStore
```

- `services/index_catalog.py`：定义文件级只读模型、分页结果、文件查找和精确删除。
- `IndexMutationCoordinator`：使用进程内全局 claim 串行化批量索引、删除、重建及
  随后的检索刷新，防止不同任务用旧快照覆盖新关键词状态。
- `services/indexing.py`：为 `index_paths` 增加默认关闭的 `force` 参数。
- `services/indexing_jobs.py`：保存安全的任务级错误对象。
- `api/routes/indexing.py`：暴露列表、删除、重建和失败详情端点。
- `api/schemas.py`：冻结 UI 可消费的请求与响应字段。
- `api/app.py`：允许注入目录服务；真实运行时可由索引服务的仓库自动构造它。

## API 契约

### 文件分页列表

`GET /v1/index/files?page=1&page_size=20`

- `page` 从 1 开始，最小值为 1。
- `page_size` 默认 20，允许 1 至 100。
- 先按 `source_key` 聚合记录，再按规范化路径不区分大小写排序；路径相同时以
  `source_key` 打破平局。
- 超出末页返回空 `items`，同时保留真实 `total` 和 `total_pages`。
- 空索引的 `total_pages` 为 0。

成功响应：

```json
{
  "items": [
    {
      "source_key": "64 位十六进制 SHA-256",
      "file_id": "64 位十六进制 SHA-256",
      "path": "C:/docs/notes.txt",
      "name": "notes.txt",
      "mime_type": "text/plain",
      "modality": "text",
      "size_bytes": 1234,
      "modified_at": "2026-08-09T08:00:00Z",
      "record_count": 3
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "total_pages": 1
}
```

如果同一个 `source_key` 因历史部分更新临时包含多个 `file_id`，列表选择
`modified_at` 最新的记录作为文件元数据代表，但 `record_count` 统计该
`source_key` 的全部记录。

### 单文件删除

`DELETE /v1/index/files/{source_key}`

成功返回：

```json
{
  "source_key": "64 位十六进制 SHA-256",
  "deleted_records": 3
}
```

删除前先确认该文件存在于索引，再调用仓库的 `delete_source`。操作只删除派生索引
记录；磁盘原文件保持不变。删除要求检索运行时可用，并在持有全局索引变更
claim 时完成删除和刷新。刷新失败时清空易失关键词索引，避免继续返回已删除
文件，同时返回结构化 `503 RETRIEVAL_UNAVAILABLE`，明确持久化删除已经发生。

### 单文件重建索引

`POST /v1/index/files/{source_key}/reindex`

成功返回 HTTP `202`：

```json
{
  "job_id": "UUID",
  "status": "queued"
}
```

路由先从目录服务读取已索引路径并确认它仍为普通文件，然后创建标准索引任务。
创建任务前先取得全局索引变更 claim；已有批量索引、删除或重建占用时返回 409。
claim 保持到后台索引和检索刷新都结束，任务的成功、失败和取消路径都会释放它。
任务使用 `recursive=false`、授权根目录为文件父目录，并向
`IndexingService.index_paths` 传入 `force=true`。强制模式只绕过“文件未变化”
判断，不改变索引流水线：新记录成功写入后才删除陈旧记录；完整解析、嵌入或写入
失败时保留原有记录。出现部分分块失败时也不删除旧记录，下一次完整成功重建再
清理陈旧记录。任务完成后沿用现有检索刷新行为。

### 索引失败详情

`GET /v1/indexing/jobs/{job_id}/failures`

响应包含：

```json
{
  "job_id": "UUID",
  "status": "completed_with_errors",
  "total": 1,
  "failures": [
    {
      "path": "C:/docs/broken.pdf",
      "code": "CORRUPTED_FILE",
      "message": "...",
      "stage": "parsing",
      "retryable": false,
      "file_id": null,
      "source_id": null
    }
  ],
  "error": null
}
```

`failures` 来自已完成任务的逐文件失败；`error` 用于任务级意外终止，字段为
`code`、`message` 和 `retryable`。受控 `ProcessingError` 保留其稳定代码、消息
和可重试标记；其他异常转换为 `INDEXING_JOB_FAILED` 和安全通用消息，不返回堆栈。
排队或运行中的任务返回空失败列表和空任务错误。

## 错误契约

- 非 64 位小写十六进制 `source_key`：`422`。
- 索引中不存在该 `source_key`：`404 FILE_NOT_INDEXED`。
- 重建时原文件已不存在或不是普通文件：`404 SOURCE_FILE_NOT_FOUND`。
- 任务 ID 不存在：`404 JOB_NOT_FOUND`。
- 未配置索引、目录或检索运行时：`503 SERVICE_UNAVAILABLE`。
- Chroma 读取、删除不可用：`503 STORAGE_UNAVAILABLE`。
- 已有批量索引、删除或重建正在修改索引：`409 INDEX_MUTATION_CONFLICT`。
- 删除已持久化但检索刷新失败：`503 RETRIEVAL_UNAVAILABLE`；易失关键词索引
  同时失效，避免陈旧命中。

所有 HTTP 错误沿用现有 `{ "detail": { "code", "message" } }` 结构。

## 测试策略

实现使用红灯、绿灯、重构流程：

1. 服务测试先覆盖跨记录聚合、确定性排序、分页边界、代表记录选择和精确删除。
2. 索引服务测试证明默认模式仍跳过未变化文件，`force=true` 会重新嵌入和写入，
   且部分失败不会删除旧有效记录。
3. 任务仓库测试覆盖逐文件失败状态与受控/意外任务级错误。
4. API 测试覆盖四个端点、参数校验、删除后刷新、重建任务参数、原文件缺失、
   结构化 404/409/503、刷新失败失效、运行时前置条件和失败序列化。
5. 生命周期测试证明真实运行时每次启动都绑定新的目录服务，并在关闭后清除引用。
6. 运行聚焦测试、完整后端测试和 `git diff --check`。

## 验收标准

1. UI 可按页读取不重复的文件级索引记录。
2. 使用列表返回的 `source_key` 可精确删除该文件全部索引，且原文件不受影响。
3. 使用同一 `source_key` 可创建强制重建任务，未变化内容也会重新执行索引流水线。
4. UI 可独立查询逐文件失败和任务级失败，不需要解析完整任务结果。
5. 所有新增错误响应稳定且自动化测试覆盖成功与失败路径。
6. 重叠索引变更被确定性拒绝，部分失败或刷新失败不会留下错误的可检索状态。
7. 完整测试套件通过，且提交不包含用户文件、模型、数据库或缓存。

## 设计自审

- 没有待定字段或占位符。
- `source_key` 在列表、删除和重建之间保持同一语义。
- 分页发生在文件聚合之后，不会把同一文件的向量记录拆到多页。
- 强制重建复用现有任务和安全写入顺序，不引入第二套索引流程。
- 任务历史仍是进程内状态，符合现有 MVP 边界。
