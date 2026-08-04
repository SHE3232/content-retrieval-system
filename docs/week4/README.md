# 第四周交付说明

第四周完成离线检索核心：将第三周文本与 MobileCLIP 嵌入接入持久化 ChromaDB，新增增量索引、字段加权 BM25、文本/图片语义检索、加权 RRF 文件级融合，以及 FastAPI 异步索引、搜索和统计接口。

## 核心产物

- `backend/src/content_retrieval/storage/chroma.py`：按向量空间隔离的持久化 Chroma 仓库、过滤、删除、统计与重启恢复。
- `backend/src/content_retrieval/services/indexing.py`：解析、分块/图片处理、嵌入、增量 upsert、陈旧记录清理和单文件失败隔离。
- `backend/src/content_retrieval/retrieval/`：字段加权 BM25、加权 Reciprocal Rank Fusion 和三通道检索服务。
- `backend/src/content_retrieval/runtime.py`：显式本地路径、模型清单哈希校验和完整离线运行时组装。
- `backend/src/content_retrieval/api/`：`POST /v1/indexing/jobs`、`GET /v1/indexing/jobs/{job_id}`、`POST /v1/search`、`GET /v1/index/stats`。
- `model-tools/benchmark_week4_pipeline.py`：真实模型、冻结 NQ/COCO、持久化 Chroma 和 10,000 条性能验证。
- `docs/week4/evidence/`：E2E、准确率、性能和覆盖率机器可读证据。
- `docs/week4/reports/`：API、端到端测试、准确率和周报四份正式 DOCX。

## 运行约束

运行时不自动联网，也不自动下载模型。必须提供 `models/model-manifest.json`，并确保文本模型目录与 MobileCLIP 权重的 SHA-256、模型 ID、空间 ID 和维度与清单一致。启动器默认使用 `data/mvp`，也可通过 `-DataDir` 显式指定其他生产数据目录；启动过程不会清空现有索引。

检索接口和服务层均限制 `top_k` 为 1–100。ChromaDB 1.5.9 在大型集合上执行 `n_results=collection.count()` 可能少返回条目并使同一客户端后续全量读取失败，因此本周准确率评测使用 Top-100 排名，禁止把 HNSW 查询作为全表扫描器。

## 一键启动 MVP

生产 MVP 通过仓库根目录的 `tools/start-mvp.ps1` 完成本地资源预检、Tika
启动或复用、严格真实模型运行时注入和 FastAPI 启动。资源准备完成后运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

完整的一次性资源准备、`-CheckOnly`、API 调用、五格式首次/重启烟测、进程所有权和
故障排查见 [离线 FastAPI MVP 运行手册](MVP_RUNBOOK.md)。生产入口使用应用生命周期
持有文本模型、MobileCLIP 和 Chroma；默认 `create_app()` 仍为自动化测试和仅解析场景
保留，不代表未配置的默认实例具备第四周检索运行时。

本次可运行交付同时关联：

- [端到端功能测试报告](reports/端到端功能测试报告.docx)
- [检索准确率基准报告](reports/检索准确率基准报告.docx)
- [MVP HTTP 烟测证据](evidence/mvp-api-smoke-summary.json)：按运行手册完成首次索引和
  重启持久化烟测后生成；提交级验证前不存在预制证据。

## 验证命令

从仓库根目录运行：

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest -q

& '.\backend\.venv\Scripts\python.exe' -m pytest -q backend `
  --cov=content_retrieval.storage `
  --cov=content_retrieval.retrieval `
  --cov=content_retrieval.services.indexing `
  --cov-report=term-missing `
  --cov-report=json:docs/week4/evidence/week4-coverage.json `
  --cov-fail-under=85

& '.\backend\.venv\Scripts\python.exe' `
  model-tools/benchmark_week4_pipeline.py `
  --mode all `
  --model-root models `
  --manifest models/model-manifest.json `
  --data-root datasets/processed `
  --evidence-root docs/week4/evidence
```

真实 DOCX 解析需要本机 Apache Tika 3.3.1 服务；测试与基准应在完成后同时确认相关 Java 进程已退出且 9998 端口未监听。

## 已验证基线

- 重新整合后的提交级全量回归：精确提交
  `833e83ee402de8894ff7ae7a37d8699ca9fc0f73` 在干净 detached worktree
  中为 340 passed、0 skipped；第四周核心覆盖率为 88.08%，通过 85% 门槛。
- 提交级全量自动化回归：精确提交
  `199ecec74577fc0f6a92e92c104e7d93a5165aa0` 在干净 detached worktree
  中为 337 passed、0 skipped；机器证据见
  `evidence/test-reconciliation-2026-08-03.json`。
- 原始提交 `537e06239717494dfca3bedd70cb1e2d16c14dce` 的可复现基线为
  162 passed；337 项结果属于后续测试证据整改提交，不追溯改写原提交。
- 测试证据整改时的第四周核心覆盖率为 87.91%；重新整合后为 88.08%。
- 五格式真实 E2E：TXT/PDF/DOCX/JPG/PNG 共 5 文件、20 条记录、0 失败；持久化重启复查通过。
- NQ 冻结集：5,446 段、40 查询，Recall@10 59.58%，MRR@10 0.2820，nDCG@10 0.3490，中位排名 6.5。
- COCO 冻结集：40 图片、201 captions，Recall@1 91.04%，Recall@5/10 100%。
- 10,000 条 CPU 性能：50 次计时查询，P50 40.85 ms、P95 62.76 ms、最大 116.29 ms；通过 P95 不高于 2 秒门槛。

审核记录：

- [第四周原始审核](AUDIT_2026-08-02.md)
- [337 项测试证据整改](TEST_RECONCILIATION_2026-08-03.md)
- [第四周提交内容重新整合记录](REINTEGRATION_2026-08-03.md)

## 正式报告

- [向量存储与检索模块 API 文档](reports/向量存储与检索模块API文档.docx)
- [端到端功能测试报告](reports/端到端功能测试报告.docx)
- [检索准确率基准报告](reports/检索准确率基准报告.docx)
- [第四周工作周报](reports/第四周工作周报.docx)

四份文档均使用 Times New Roman、黑色文字/线条和白色页面/表格背景，已通过逐页渲染检查、可访问性审计和精确表格几何校验。

## 发布边界

代码提交不包含模型权重、Chroma 数据库、冻结数据集原文件、用户提供的 PDF/DOCX、虚拟环境、缓存或渲染中间文件。MobileCLIP 权重和 COCO 图片继续按各自许可单独管理。
