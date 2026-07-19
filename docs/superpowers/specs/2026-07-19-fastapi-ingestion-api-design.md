# 最小 FastAPI 导入接口设计

## 目标与范围

本次为 Flutter 提供最小本地 HTTP 接口，使其可以提交文件与目录混合路径，并轮询查看解析状态和结果。

实现以下接口：

- `GET /health/live`
- `GET /health/ready`
- `POST /v1/ingestion/jobs`
- `GET /v1/ingestion/jobs/{job_id}`

任务状态和结果仅保存在 FastAPI 进程内。本次不接入 Embedding、ChromaDB、持久化任务队列、取消接口或认证令牌。

## 请求契约

创建任务请求：

```json
{
  "paths": [
    "C:\\Users\\example\\Documents\\notes.txt",
    "C:\\Users\\example\\Documents\\reports"
  ],
  "authorized_roots": [
    "C:\\Users\\example\\Documents"
  ],
  "recursive": true
}
```

约束：

- `paths` 和 `authorized_roots` 都必须是非空数组。
- `paths` 可混合包含文件和目录。
- 文件直接进入候选集合；目录按 `recursive` 展开。
- 所有输入路径及目录展开后的真实路径都必须位于至少一个真实授权根目录内。
- 不接受越过授权根目录的符号链接或目录联接目标。

## 路径展开与批处理

`BatchIngestionService` 新增统一入口：

```python
parse_paths(
    paths: list[Path | str],
    *,
    recursive: bool = True,
    authorized_roots: list[Path | str] | None = None,
) -> BatchResult
```

`parse_directory()` 保留为兼容包装方法，并将单个目录交给 `parse_paths()`。

处理顺序固定为：

1. 规范化授权根目录和输入路径。
2. 对不存在或越权的输入生成受控错误项。
3. 文件直接保留，目录按稳定顺序展开。
4. 对展开后的每个真实路径再次执行授权检查。
5. 目录发现的不支持格式文件记录为 `unsupported_format` 跳过项。
6. 按规范化真实路径去重，同一文件只生成一个任务项。
7. 对支持格式按 SHA-256 去重；首个文件解析，后续内容副本记录为 `duplicate_content`。
8. 调用注册表选择解析器并生成现有 `ParseResult`。

显式传入的不支持格式文件不会被扫描规则静默忽略，而是生成 `UNSUPPORTED_FORMAT` 失败项。不存在路径和越权路径分别生成 `PATH_NOT_FOUND`、`PATH_NOT_AUTHORIZED` 失败项。

## 统计语义

`total` 等于路径展开、真实路径去重后生成的任务项数量，而不是请求中 `paths` 的数量。目录本身不计数。

任务项包括：

- 成功解析的文件；
- 解析失败或显式输入无效的文件/路径；
- 内容重复的文件；
- 目录扫描中发现但格式不支持的文件。

因此计数保持以下不变量：

```text
total = pending + running + succeeded + failed + skipped
```

同一真实文件同时被显式传入并由目录扫描发现时，仅保留首次出现的任务项，不额外增加 `total`。内容相同但真实路径不同的文件均计入 `total`，后出现者计为 `skipped`。

## 任务执行与 API 响应

应用使用线程安全的进程内任务仓储。`POST` 创建任务快照后立即返回 `202 Accepted`；同步解析服务通过 `asyncio.to_thread()` 在工作线程执行，避免阻塞 FastAPI 事件循环。

创建响应至少包含：

```json
{
  "job_id": "UUID",
  "status": "queued"
}
```

查询响应包含：

- `job_id`
- `status`：`queued`、`running`、`completed` 或 `completed_with_errors`
- `counts`：`total`、`pending`、`running`、`succeeded`、`failed`、`skipped`
- `results`：可 JSON 序列化的解析结果
- `errors`：包含路径、稳定错误码、消息和 `retryable`
- `skips`：包含路径、原因以及适用时的内容哈希和原始文件路径

未知 `job_id` 返回 `404` 和稳定错误明细。

最小实现可在任务开始和完成时更新状态；无需本周实现单文件级实时进度推送。Flutter 可轮询直到任务进入终态。

## 健康检查

- `/health/live` 在应用进程可响应时返回 `200` 和 `{"status": "ok"}`。
- `/health/ready` 在任务仓储和解析服务初始化成功时返回 `200` 和 `{"status": "ready"}`；初始化失败时返回 `503`。
- Tika 不可用不阻止应用核心就绪；DOCX 解析失败由现有受控错误处理表达。

## 错误与安全边界

- 原始文件只读，不移动、覆盖或删除。
- 授权判断使用解析后的真实路径，并采用路径层级判断，不能使用字符串前缀判断。
- 文件级异常隔离在 `BatchResult` 内，不终止同一批次中的其他文件。
- 未知第三方异常继续转换为现有 `INTERNAL_ERROR`，不向 Flutter 暴露堆栈。
- 请求结构错误由 FastAPI/Pydantic 返回 `422`，不创建任务。

## 测试策略

测试遵循红—绿循环，至少覆盖：

- 两个健康检查接口；
- 创建任务返回 `202`，随后可查询终态和解析结果；
- 文件与目录混合输入及 `recursive` 行为；
- 授权根目录校验，包括目录展开后的越权目标；
- 显式不支持文件、目录内不支持文件及路径不存在；
- 真实路径去重、内容哈希去重和统计不变量；
- 未知任务返回 `404`；
- `parse_directory()` 的兼容行为；
- 现有解析器与批处理测试无回归。
