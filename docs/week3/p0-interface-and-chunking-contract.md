# P0 接口与分块规则冻结

状态：冻结  
Schema version：`1`

## 1. 领域接口

### `TextChunk`

| 字段 | 类型 | 规则 |
|---|---|---|
| `chunk_id` | `str` | 64 位小写 SHA-256；按第 3 节确定性生成 |
| `file_id` | `str` | 原文件内容 SHA-256 |
| `text` | `str` | 不允许为空或仅含空白 |
| `sequence_number` | `int` | 文件内全局顺序，从 `0` 开始 |
| `page_number` | `int \| None` | PDF 使用，从 `1` 开始 |
| `paragraph_number` | `int \| None` | 非 PDF 文档使用，从 `1` 开始 |
| `split_number` | `int` | 同一页或段落内的子块顺序，从 `0` 开始 |
| `metadata` | `dict` | 当前包含 `source_name`、`mime_type` |
| `schema_version` | `str` | 固定为 `1` |

`page_number` 与 `paragraph_number` 必须且只能设置一个。

### `EmbeddingVector`

| 字段 | 类型 | 规则 |
|---|---|---|
| `source_id` | `str` | 文本使用 `TextChunk.chunk_id`，图片使用文件 `file_id` |
| `file_id` | `str` | 原文件内容 SHA-256 |
| `model_id` | `str` | 非空的本地模型标识 |
| `space_id` | `str` | 非空向量空间标识；不同空间禁止直接比较 |
| `modality` | `text \| image` | 标识向量来源模态 |
| `values` | `list[float]` | 所有元素必须是有限数值 |
| `dimensions` | `int` | 正整数，且等于 `len(values)` |
| `normalized` | `bool` | 是否已归一化 |
| `metadata` | `dict` | 可序列化扩展信息 |
| `schema_version` | `str` | 固定为 `1` |

### `BatchProcessingResult`

批处理结果固定包含：

- `items: list[TextChunk | EmbeddingVector]`
- `errors: list[ProcessingError]`
- 派生计数：`total`、`succeeded`、`failed`

### 错误

`ProcessingError` 是分块和嵌入阶段的受控错误基类；当前冻结两个子类：

| 类型 | `code` | `stage` | 默认可重试 |
|---|---|---|---|
| `ChunkingError` | `CHUNKING_ERROR` | `chunking` | 否 |
| `EmbeddingError` | `EMBEDDING_ERROR` | `embedding` | 否 |

`to_dict()` 固定返回 `code`、`message`、`retryable`、`stage`、`file_id`、`chunk_id`。

## 2. 分块规则

默认窗口参数：

- `max_characters = 1000`
- `overlap_characters = 100`
- `step = max_characters - overlap_characters`

窗口按 Python Unicode 字符序列确定性截取。参数必须满足：

`max_characters > 0` 且 `0 <= overlap_characters < max_characters`。

来源结构规则：

1. PDF 必须使用解析结果的 `metadata.page_texts`，按原始页序生成，`page_number` 从 `1` 开始。缺失逐页文本时返回 `ChunkingError`，不得退化为无法定位页码的全文分块。
2. TXT、DOCX 等非 PDF 文档先统一换行，再以一个或多个空行切分段落，`paragraph_number` 从 `1` 开始。
3. 空页不生成向量块；整个文档无可提取文本时返回 `ChunkingError`。
4. 页或段落超过窗口上限时使用固定重叠窗口拆分，`split_number` 从 `0` 开始。
5. 所有输出块再按文档顺序赋予全局 `sequence_number`，从 `0` 连续递增。

## 3. 稳定 `chunk_id`

`chunk_id` 是以下 JSON 对象的规范化 UTF-8 表示的 SHA-256：

```json
{
  "file_id": "<原文件内容 SHA-256>",
  "page_number": 1,
  "paragraph_number": null,
  "schema_version": "1",
  "sequence_number": 0,
  "split_number": 0,
  "text": "<分块正文>"
}
```

规范化使用键名排序、紧凑分隔符和非 ASCII 原样编码。路径、文件名、修改时间与处理时间不进入 ID，因此同一内容文件在重复处理或重命名副本中产生相同 `chunk_id`；内容、来源位置或分块正文变化时 ID 随之变化。

## 4. 代码入口

- 领域模型：`backend/src/content_retrieval/domain/models.py`
- 受控错误：`backend/src/content_retrieval/domain/errors.py`
- 分块服务：`backend/src/content_retrieval/services/chunking.py`
- 契约与验收测试：`backend/tests/test_chunking_contracts.py`
