# 第三周多模态嵌入引擎设计

## 1. 目标与范围

第三周交付一个可离线运行、可批量处理、可复现评测的多模态嵌入引擎。输入来自第二周的 `ParseResult`，输出为携带模型与向量空间身份的标准化向量。

本周包括：

- 确定性文本分块与来源定位；
- 检索微调的多语言文本编码；
- MobileCLIP 图片编码和文字查询编码；
- 双空间统一批处理；
- 本地模型清单、哈希校验和离线加载；
- LiteRT/TFLite 转换工具与参考输出一致性验证；
- NQ 与 COCO 子集检索评测；
- 单元测试、覆盖率、API 文档、验证报告和周报。

本周不包括 ChromaDB 写入、混合排序、Flutter UI、OCR 和发布程序打包。

## 2. 核心架构决策

系统使用两个独立向量空间。

1. `text-semantic-v1`：多语言文本查询和文档分块进入同一空间，用于文本语义检索。
2. `mobileclip-image-text-v1`：MobileCLIP 的文字编码器和图片编码器进入同一空间，用于文字搜图。

不同 `space_id` 的向量禁止直接计算相似度。第四周分别检索两个集合后再做结果融合。

`EmbeddingVector` 使用通用 `source_id`：

- 文本向量的 `source_id` 是 `TextChunk.chunk_id`；
- 图片向量的 `source_id` 是图片文件的 `ParseResult.file_id`；
- `file_id` 始终保留原文件身份；
- `modality` 区分 `text` 与 `image`；
- `model_id`、`space_id`、`dimensions` 和 `normalized` 共同描述向量兼容性。

## 3. 组件边界

### 3.1 文本分块

`TextChunker` 消费 `ParseResult`。PDF 使用 `metadata.page_texts` 保留页码；其他文本按段落切分，再使用固定字符窗口和重叠生成子块。`chunk_id` 由文件哈希、来源位置、正文和 schema 版本确定性计算。

### 3.2 模型清单

`ModelManifest` 从 JSON 读取模型 ID、向量空间、维度、相对路径、SHA-256、许可证和运行时。加载模型前校验路径位于配置的模型根目录内，文件哈希必须匹配。运行时不得自动访问网络。

### 3.3 文本嵌入

`TextEmbeddingEngine` 依赖一个窄接口 `TextEncoderBackend`。生产适配器使用本地 Sentence Transformers 模型；测试使用内存后端。引擎负责批次切分、有限数值检查、维度检查、L2 归一化和单项失败隔离。

候选模型默认采用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，最终是否保留由 NQ 冻结基准结果决定。模型下载、权重和许可证不进入公开代码包。

### 3.4 MobileCLIP

`MobileClipBackend` 只接受本地预训练权重路径，使用官方图片预处理、tokenizer、`encode_image` 和 `encode_text`。图片在进入模型前应用 EXIF 方向并转换为 RGB。图片和文字输出均做 L2 归一化。

MobileCLIP 代码与权重分开管理。代码遵循仓库许可证；权重按 Apple Research Model License 记录，不默认打入公开发布包。

### 3.5 统一服务

`MultimodalEmbeddingService` 按输入顺序处理：

- `text`、`document`：分块后进入文本嵌入器；
- `image`：进入 MobileCLIP 图片嵌入器；
- 单文件失败转为 `ProcessingError`，不终止其他文件；
- 输出不写数据库。

服务额外提供 MobileCLIP 文字查询编码入口，为第四周文字搜图预留。

## 4. 数据与评测

NQ 继续使用现有固定划分：

- validation：160 查询，用于选择模型和参数；
- benchmark：40 查询，只用于最终报告；
- 指标：Recall@1、Recall@5、Recall@10、MRR@10、nDCG@10。

COCO 准备工具从官方 2017 captions/instances 标注中稳定选取 200 张图片：

- validation：160 张；
- benchmark：40 张；
- 保存图片 ID、caption、来源 URL、license ID、license URL、SHA-256；
- 指标：文字搜图 Recall@1、Recall@5、Recall@10 和 median rank。

性能基线记录 batch 1 与 batch 16 的 P50、P95、吞吐量、模型体积和测试设备信息。

## 5. 错误与安全

- 模型文件缺失或哈希不符：`ModelManifestError`；
- 文本后端异常、输出数量或维度错误：`EmbeddingError`；
- 图片解码或模型推理失败：`EmbeddingError`，包含 `file_id`；
- 零向量不能归一化，作为受控错误返回；
- 模型加载只接受本地路径；
- 日志和报告不记录文档全文、完整用户路径或向量内容。

## 6. 验收标准

1. 同一输入和模型产生稳定维度、有限且归一化的向量。
2. 文本和图片向量都包含明确 `space_id`，跨空间相似度在接口层被拒绝。
3. 模型准备完成后断网可完成加载和推理。
4. MobileCLIP 文字与图片编码位于同一空间，匹配对相似度高于无关对。
5. NQ 和 COCO 工具输出可复现 JSON 报告。
6. 嵌入模块单元测试覆盖率不低于 85%，第二周回归测试保持通过。
7. 正式 DOCX 使用 Times New Roman、黑色文字与线条、白色页面和表格背景。

