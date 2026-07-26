# 第 1 周本地验证数据集仓库

## 1. 目的

本目录为文件解析、去重、文本检索、图像向量和异常处理提供一个小型、可审计、可重复的本地验证集。第一周不下载完整大型公开数据集；大型数据只在模型和指标方案确定后按需取得验证子集。

## 2. 当前内容

当前烟测集由以下内容组成：

- 5 个受项目控制的 UTF-8 文本样本：中文、英文、中英混合和重复文件对。
- 1 个项目需求 PDF，用于 PDF 解析烟测。
- 1 个项目说明 DOCX，用于 Office 文档解析烟测。
- 2 个 Flutter 示例 PNG，用于图片尺寸和图片向量管线烟测。
- 1 个项目自建的 4×3 JPG，包含描述和方向 EXIF，用于 JPEG 解码和安全元数据提取烟测。

所有条目记录在 `manifest.csv`，路径以仓库根目录为基准。清单包含文件哈希、格式、语言、预期处理结果、许可证状态和用途。

## 3. 目录结构

```text
datasets/
├── README.md
├── manifest.csv
├── prepare_nq_retrieval.py
├── test_prepare_nq_retrieval.py
├── licenses/
│   └── NOTICE.md
├── processed/
│   └── nq/
│       ├── metadata.json
│       ├── validation/
│       └── benchmark/
├── raw/
│   ├── .gitkeep
│   └── nq/dev.jsonl.gz
├── splits/
│   └── nq_retrieval_split.csv
└── smoke/
    ├── image/
    │   └── jpg_with_exif.jpg
    └── text/
        ├── zh_local_search.txt
        ├── en_accessibility.txt
        ├── mixed_metadata.txt
        ├── duplicate_a.txt
        └── duplicate_b.txt
```

`raw/` 用于后续按许可下载的外部数据，并已从 Git 提交中排除。

## 4. 清单字段

| 字段 | 含义 |
|---|---|
| `id` | 稳定样本编号 |
| `split` | 当前为 `smoke`，后续可增加 `validation`、`benchmark` |
| `modality` | `text`、`document`、`image` |
| `format` | 文件格式 |
| `path` | 相对仓库根目录的路径 |
| `sha256` | 文件内容 SHA-256 |
| `bytes` | 文件字节数 |
| `language` | `zh`、`en`、`mixed` 或 `n/a` |
| `expected_status` | 预期处理结果，例如 `parse_ok`、`duplicate` |
| `expected_keywords` | 用于人工或自动烟测的关键词 |
| `license_status` | 可使用范围或待核查状态 |
| `purpose` | 样本用途 |

## 5. 候选公开数据集登记

| 数据集 | 计划用途 | 第一周处理决定 | 许可/规模注意事项 |
|---|---|---|---|
| Google Natural Questions | 文本语义检索与长文档评估 | 已从 `sentence-transformers/NQ-retrieval` dev 衍生集整理 200 条；不下载 42 GB 完整集 | 原始 NQ 为 CC BY-SA 3.0；Google 旧 GCS 桶当前返回 403，衍生来源需单独记录 |
| COCO | 图片和图文语义检索 | 第 3 周已按稳定哈希固定 200 张 val2017 图片；160 validation、40 benchmark | 图片来自 Flickr，逐项保留许可证、来源 URL 与 SHA-256；原图不进入公开代码包 |
| RVL-CDIP | 扫描文档和文档图片分类 | 暂缓 | 原项目链接已重定向，当前下载源和许可需要重新确认 |
| Wikipedia Dumps | 长文本与批处理性能 | 暂不下载；后续选择少量文章或小型 dump | 文本通常为 CC BY-SA 4.0/GFDL，仍需保留署名和同方式共享要求 |

## 6. 数据治理规则

1. 不把用户私人文件加入公开仓库。
2. 外部数据必须记录来源 URL、版本/日期、许可证和校验值。
3. 无法确认许可证的数据不得进入发布包或公开仓库。
4. 大型文件只保存在 `datasets/raw/`，不提交 Git。
5. 训练、验证和测试集合必须分开，禁止使用测试答案调参。
6. 对损坏文件、空文件、加密文件和超大文件使用单独的合成测试夹具，不直接传播未知来源文件。
7. 数据清理或替换必须更新 `manifest.csv`，不能只按文件名判断版本。

## 7. 第一周验收标准

- 存在可被 TXT、PDF、DOCX、JPG 和 PNG 管线读取的本地样本。
- 存在中英文和重复文件场景。
- 每个样本均有 SHA-256 和预期行为记录。
- 外部候选数据集已登记，但未在许可不明确时擅自下载。
- 原始大数据目录已排除在 Git 之外。

## 8. NQ 检索验证集

2026-07-14 尝试访问 Google 官方文档中的 `gs://bert-nq/tiny-dev` 和
`gs://natural_questions/v1.0/sample/nq-dev-sample.jsonl.gz`，已登录账号仍同时缺少
`storage.objects.list` 与 `storage.objects.get` 权限。因此当前本地数据使用
Sentence Transformers 发布的 `NQ-retrieval/dev.jsonl.gz` 衍生集，并在清单中保留来源区别。

本地原始文件：

```text
datasets/raw/nq/dev.jsonl.gz
SHA-256: ad23b7e4f50b0f02c9395a4f8fe39946e3e1242edea7c826aaf7ac378f3e8779
```

重建命令：

```powershell
python datasets/prepare_nq_retrieval.py `
  --input datasets/raw/nq/dev.jsonl.gz `
  --output-dir datasets/processed/nq `
  --split-manifest datasets/splits/nq_retrieval_split.csv `
  --validation-size 160 `
  --benchmark-size 40
```

整理规则：

1. 只选择存在 `long_answers` 且索引有效的查询。
2. 每个 `document_url` 最多保留一个查询，防止同一 Wikipedia 文档跨集泄漏。
3. 使用 `document_url + question` 的 SHA-256 前缀生成稳定查询 ID，按 ID 排序。
4. 前 160 条为 `validation`，用于模型选择和参数调整；后 40 条为冻结 `benchmark`。
5. 输出 `queries.jsonl`、`corpus.jsonl`、`qrels.tsv` 及包含所有哈希的 `metadata.json`。

当前统计：

- validation：160 个查询，20,122 个候选段落。
- benchmark：40 个查询，5,446 个候选段落。

## 9. COCO 图文检索验证集

第三周使用 COCO 2017 validation 官方 captions 与 instances 标注。准备脚本只选择同时具有
caption、图片元数据和可识别 Flickr 许可证的条目，再按
`SHA-256("coco-2017-val\0" + image_id)` 排序固定前 200 张：

- validation：160 张，用于开发期验证；
- benchmark：40 张冻结评测集，共 201 条 caption 查询；
- 每条元数据保存图片 ID、caption、COCO/Flickr URL、许可证 ID/URL、文件 SHA-256 和字节数；
- 200 张原图共 32,130,102 字节，仅保存在 `datasets/raw/coco/val2017/`，不进入 Git 或公开代码包。

重建命令：

```powershell
python datasets/prepare_coco_retrieval.py `
  --size 200 `
  --validation-size 160
```

生成文件：

```text
datasets/processed/coco/
├── metadata.json
├── validation/items.jsonl
└── benchmark/items.jsonl
```

图片许可分布包含 CC BY-NC-SA 2.0、CC BY-NC 2.0、CC BY-NC-ND 2.0、
CC BY 2.0、CC BY-SA 2.0 和 CC BY-ND 2.0。任何图片再分发必须按单图记录执行对应条款。
