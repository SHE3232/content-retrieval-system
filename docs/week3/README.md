# 第三周交付说明

第三周完成离线多模态嵌入引擎：文本分块与多语言文本向量、MobileCLIP-S0 图片/文字向量、统一批处理服务、模型清单校验、LiteRT 导出与一致性验证，以及 NQ/COCO 冻结评测。

## 核心产物

- `backend/src/content_retrieval/embeddings/`：模型清单、文本与 MobileCLIP 适配器、统一服务。
- `backend/src/content_retrieval/services/chunking.py`：确定性文本分块。
- `model-tools/`：离线真实模型烟测和 NQ/COCO/CPU 评测工具。
- `conversion-tools/`：Sentence Transformer 与 MobileCLIP 的 LiteRT 导出和一致性校验。
- `datasets/prepare_*_retrieval.py`：可重复的数据准备脚本；冻结元数据位于 `datasets/processed/`。
- `docs/week3/evidence/`：覆盖率、转换一致性、准确率和性能的机器可读证据。
- `docs/week3/reports/`：API、测试、准确率和周报四份正式 DOCX。

## 模型准备

运行时不自动联网。复制 `models/model-manifest.example.json` 为本地清单，按实际文件更新相对路径和 SHA-256：

- `text-multilingual-v1`：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，384 维，`text-semantic-v1`。
- `mobileclip-s0-v1`：MobileCLIP-S0，512 维，`mobileclip-image-text-v1`。

两个 `space_id` 严格隔离；只有相同空间、相同维度且已 L2 归一化的向量可以比较余弦相似度。

## 验证命令

```powershell
backend\.venv\Scripts\python.exe -m pytest -q
backend\.venv\Scripts\python.exe -m pytest -q backend `
  --cov=content_retrieval.embeddings `
  --cov-report=term-missing `
  --cov-report=json:output/week3/embedding-coverage.json `
  --cov-fail-under=85
model-tools\.venv\Scripts\python.exe model-tools/smoke_test.py
```

转换工具在 WSL 的 TensorFlow 环境中运行：

```bash
cd conversion-tools
uv sync --locked
source .venv/bin/activate
python -m pytest -q test_verify_parity.py
python smoke_test.py
```

## 已验证基线

- Python 统一回归：262 passed，1 skipped。
- 嵌入包覆盖率：86.51%，门槛 85%。
- NQ 冻结集：40 查询、5,446 段落，Recall@10 59.58%，MRR@10 0.2841。
- COCO 冻结集：40 图片、201 captions，Recall@1 91.04%，Recall@5/10 100%。
- LiteRT：三个真实模型产物均通过 `cosine >= 0.999`、`max_abs_error <= 1e-4`。

## 发布边界

公开代码包不包含模型权重、由受限权重转换得到的 TFLite、NQ 原始文件、COCO 图片二进制、用户提供的 PDF/DOCX、数据库、虚拟环境或缓存。MobileCLIP 权重按 Apple Research Model License 单独管理；COCO 图片按逐图 Flickr 许可记录管理。
