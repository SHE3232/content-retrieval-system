# 第三方代码、模型、工具和数据集声明

审查日期：2026-08-22

根目录 [LICENSE](LICENSE) 中的 Apache License 2.0 仅适用于项目贡献者有权按该许可证授权的项目自有代码和文档。第三方软件、源代码、模型权重、工具链、数据集和用户内容仍受各自条款约束，不因包含在本仓库、开发环境或发行包中而被重新授权。

完整的软件依赖逐项记录见 [锁定依赖许可证清单](docs/dependency-licenses.csv)，其机器可读审核基线见 [approved-licenses.json](tools/compliance/approved-licenses.json)。本文件列出直接依赖、随项目保存的第三方代码，以及对发行决策有实质影响的模型、工具和数据。

## 第三方软件和代码

### 后端直接依赖与随附源代码

| 组件 | 固定版本或修订 | 官方来源 | 许可证 | 发行决定与义务 |
|---|---:|---|---|---|
| ChromaDB | 1.5.9 | [PyPI](https://pypi.org/project/chromadb/1.5.9/) | Apache-2.0 | 可再分发；保留许可证、NOTICE 和版权声明。 |
| FastAPI | 0.139.0 | [PyPI](https://pypi.org/project/fastapi/0.139.0/) | MIT | 可再分发；保留许可证和版权声明。 |
| HTTPX | 0.28.1 | [PyPI](https://pypi.org/project/httpx/0.28.1/) | BSD-3-Clause | 可再分发；保留许可证和免责声明。 |
| MobileCLIP 源代码 | 0.1.0；提交 `aecfb5453d022e9deff12f81a150ea8f35194baa` | [Apple ml-mobileclip](https://github.com/apple/ml-mobileclip/tree/aecfb5453d022e9deff12f81a150ea8f35194baa) | MIT | 可再分发源代码；保留上游 `LICENSE`、`ACKNOWLEDGEMENTS` 及适用声明。代码许可不覆盖模型权重或训练数据。 |
| Pillow | 12.3.0 | [PyPI](https://pypi.org/project/pillow/12.3.0/) | MIT-CMU | 可再分发；保留许可证和版权声明。 |
| pypdfium2 / PDFium | 4.30.0 | [PyPI](https://pypi.org/project/pypdfium2/4.30.0/) | `(Apache-2.0 OR BSD-3-Clause) AND LicenseRef-PdfiumThirdParty` | 二进制含 PDFium 及其第三方代码；必须随包保留 wheel 中的许可证、NOTICE 和第三方声明。 |
| python-multipart | 0.0.32 | [PyPI](https://pypi.org/project/python-multipart/0.0.32/) | Apache-2.0 | 可再分发；保留许可证和版权声明。 |
| Sentence Transformers | 5.6.1 | [PyPI](https://pypi.org/project/sentence-transformers/5.6.1/) | Apache-2.0 | 可再分发；保留许可证、NOTICE 和版权声明。 |
| Uvicorn | 0.51.0 | [PyPI](https://pypi.org/project/uvicorn/0.51.0/) | BSD-3-Clause | 可再分发；保留许可证和免责声明。 |

开发依赖 pytest 8.4.2 与 pytest-cov 6.3.0 均采用 MIT；它们默认不随运行时发行包分发。

### 模型转换与评测直接依赖

| 组件 | 固定版本 | 官方来源 | 许可证 | 发行决定与义务 |
|---|---:|---|---|---|
| LiteRT Torch | 0.8.0 | [PyPI](https://pypi.org/project/litert-torch/0.8.0/) | Apache-2.0 | 转换工具；保留许可证和 NOTICE。 |
| NumPy | 2.2.6 | [PyPI](https://pypi.org/project/numpy/2.2.6/) | BSD-3-Clause | 保留许可证和免责声明。 |
| OpenCLIP Torch | 3.3.0 | [PyPI](https://pypi.org/project/open-clip-torch/3.3.0/) | MIT | 保留许可证和版权声明。 |
| timm | 1.0.28 | [PyPI](https://pypi.org/project/timm/1.0.28/) | Apache-2.0 | 保留许可证、NOTICE 和版权声明。 |
| PyTorch | 2.9.1 / 2.9.1+cpu | [上游许可证](https://github.com/pytorch/pytorch/blob/v2.9.1/LICENSE) | BSD-3-Clause | 默认发行仅采用 CPU 构建；保留许可证和随 wheel 提供的第三方声明。 |
| TorchVision | 0.24.1 / 0.24.1+cpu | [上游许可证](https://github.com/pytorch/vision/blob/v0.24.1/LICENSE) | BSD-3-Clause | 默认发行仅采用 CPU 构建；保留许可证和第三方声明。 |
| Transformers | 4.57.6 | [PyPI](https://pypi.org/project/transformers/4.57.6/) | Apache-2.0 | 保留许可证、NOTICE 和版权声明。 |

上述表格不是传递依赖的删节许可清单。三套 Python `uv.lock` 和 Flutter `pubspec.lock` 中的全部 374 条环境记录已经逐项核查；以 [dependency-licenses.csv](docs/dependency-licenses.csv) 为完整清单。发行归档必须同时保留各 Python wheel、Dart 包和随附原生库中提供的 `LICENSE`、`COPYING`、`NOTICE` 及版权文件，不能只保留本文件。

## 模型与权重

| 模型 | 固定修订与摘要 | 官方来源 | 许可证 | 发行决定与义务 |
|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | 修订 `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`；目录摘要 `cb32ef7aa7e749a5e9727968fb86fdcf2a8752e6063276ba4de675ce2696e37c` | [Hugging Face 模型页](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/tree/e8f8c211226b894fcb81acc59f3b34ba3efd5f42) | Apache-2.0 | 可按许可证再分发；保存模型卡、许可证、修订号和摘要。仍需自行评估模型输出和适用场景。 |
| `MobileCLIP-S0` 预训练权重 | 修订 `71aa3e13dda93115871afbd017336535ba29886c`；SHA-256 `809b408eff74f8058843e86a1f92967097d42ba782450e85b8f4867b7f0ca0b7` | [Apple 模型仓库](https://huggingface.co/apple/MobileCLIP-S0/tree/71aa3e13dda93115871afbd017336535ba29886c)；[许可原文](https://github.com/apple/ml-mobileclip/blob/aecfb5453d022e9deff12f81a150ea8f35194baa/LICENSE_MODELS) | Apple Machine Learning Research Model License | **限制项：仅限非商业研究用途。** 不得把含该权重的归档描述为不受限制的 Apache-2.0 开源发行或商用发行。公开默认包不包含该权重；研究用途包必须显式确认用途并随附许可和模型卡。 |

模型代码、模型权重和训练数据是三个独立的许可对象。MobileCLIP 源代码采用 MIT，不代表其预训练权重或 DataComp 训练数据采用 MIT；本项目不再分发其训练数据。

## 工具链与运行时

| 工具或运行时 | 核查版本 | 官方来源 | 许可证或条款 | 使用与发行决定 |
|---|---:|---|---|---|
| Apache Tika Server | 3.3.1 | [Apache Tika](https://tika.apache.org/3.3.1/) | Apache-2.0 | 若随包分发 JAR，保留其 `LICENSE`、`NOTICE` 和依赖声明。 |
| Flutter SDK | 3.44.6；修订 `ee80f08bbf97172ec030b8751ceab557177a34a6` | [Flutter 源码](https://github.com/flutter/flutter/tree/ee80f08bbf97172ec030b8751ceab557177a34a6) | BSD-3-Clause | 应用模板与 SDK 组件保留上游许可证；SDK 本身默认不打包。 |
| Dart SDK | 3.12.2 | [Dart SDK](https://github.com/dart-lang/sdk) | BSD-3-Clause | 通过 Flutter 使用；若另行分发运行时，保留其许可证和第三方声明。 |
| Gradle | 9.1.0 | [Gradle 9.1.0](https://github.com/gradle/gradle/tree/v9.1.0) | Apache-2.0 | wrapper 负责下载；不把本地缓存纳入发行包。 |
| Android Gradle Plugin | 9.0.1 | [Google Maven](https://maven.google.com/web/index.html#com.android.tools.build:gradle:9.0.1) | Apache-2.0 | 仅构建时使用；保留 Maven 工件内声明。 |
| Kotlin Gradle Plugin | 2.3.20 | [Kotlin](https://github.com/JetBrains/kotlin/releases/tag/v2.3.20) | Apache-2.0 | 仅构建时使用；保留 Maven 工件内声明。 |
| Python | 3.10.18 | [Python 3.10.18](https://www.python.org/downloads/release/python-31018/) | PSF License | 便携运行时发行时保留 Python 许可证和 `LICENSE.txt`。 |
| uv | 0.8.2 | [astral-sh/uv](https://github.com/astral-sh/uv/tree/0.8.2) | Apache-2.0 OR MIT | 依赖管理工具，默认不随应用分发；如分发则保留所选许可文本。 |
| Java（当前审查机） | Oracle JDK 23.0.2 | [Oracle JDK 23](https://www.oracle.com/java/technologies/javase/jdk23-archive-downloads.html) | Oracle 单独条款 | 本机安装不属于项目 Apache 授权。公开便携发行优先使用许可已单独核准的 OpenJDK 发行版，并原样保留运行时 `legal/` 目录。 |
| PowerShell | 发行脚本所用本机版本 | [PowerShell](https://github.com/PowerShell/PowerShell) | MIT | 作为构建/启动工具使用，默认不随应用分发。 |
| .NET SDK/Runtime | Flutter Windows 启动器所用版本 | [.NET](https://github.com/dotnet/runtime) | MIT（另含第三方声明） | 仅在实际打包运行时时保存对应版本的 LICENSE 与 THIRD-PARTY-NOTICES。 |

WAVE、NVDA（GPL）、VoiceOver（Apple 专有）和 Android Accessibility Scanner 仅用于人工质量验证；项目不复制其源代码，也不在默认应用归档中分发这些工具。验证记录中的工具名称不构成再分发授权。

## 数据集与内容来源

| 材料 | 固定来源或范围 | 许可证/权利状态 | 发行决定与义务 |
|---|---|---|---|
| 本地烟测文本 | `datasets/smoke/text/` 中项目创建的样本 | 项目可控内容 | 可随项目发布，但不代表任何用户导入内容。 |
| 用户 PDF、DOCX 和索引内容 | 项目根目录或用户选择目录中的本地文件 | 用户或第三方权利；未核准 | 不进入公开源码或发行归档。未取得传播权限前不得上传或再分发。 |
| Natural Questions 检索子集 | [sentence-transformers/NQ-retrieval](https://huggingface.co/datasets/sentence-transformers/NQ-retrieval)，`dev.jsonl.gz` SHA-256 `ad23b7e4f50b0f02c9395a4f8fe39946e3e1242edea7c826aaf7ac378f3e8779`；衍生自 [Google Natural Questions](https://ai.google.com/research/NaturalQuestions/download) | 保守按 CC BY-SA 3.0 处理 | 不纳入默认公开包。若另行分发，重新核查两级来源，提供署名、许可证链接、修改说明，并对衍生数据履行相同方式共享。 |
| COCO 2017 验证图片子集 | [COCO](https://cocodataset.org/)；200 张（validation 160、benchmark 40） | 图片逐项采用 CC 2.0 系列许可 | 不纳入默认公开包。逐图保留 Flickr/COCO URL、作者与许可；禁止演绎、非商业和相同方式共享限制必须逐图执行。许可分布：CC BY-NC-SA 59、BY-NC 33、BY-NC-ND 51、BY 27、BY-SA 17、BY-ND 13。 |
| COCO 标注 | [annotations_trainval2017.zip](http://images.cocodataset.org/annotations/annotations_trainval2017.zip) | 以 COCO 官方数据条款和包内声明为准 | 默认包不含下载的标注二进制；重建时记录来源和摘要，并与图片权利分开审查。 |
| RVL-CDIP | [原候选来源](https://www.cs.cmu.edu/~aharley/rvl-cdip/) | 未完成许可和隐私核准 | 未下载、未使用、不得纳入发行。 |
| Wikipedia dumps | [Wikimedia dumps](https://dumps.wikimedia.org/) | 通常为 CC BY-SA 4.0/GFDL，例外内容另行核查 | 未下载、未使用。采用前按 [Wikimedia 数据许可说明](https://dumps.wikimedia.org/legal.html) 重新审查。 |

数据集的详细哈希、选样方法和逐图记录见 [datasets/licenses/NOTICE.md](datasets/licenses/NOTICE.md) 及 `datasets/processed/*/metadata.json`。这些数据许可不属于根目录 Apache-2.0 授权。

## 再分发者须知

1. 发布前运行 [合规审查命令和检查表](docs/OPEN_SOURCE_COMPLIANCE.md)，并确保锁文件与清单一致。
2. 默认公开源码和 CPU 发行包不得包含 MobileCLIP-S0 权重、NQ/COCO 二进制、用户文件、Oracle JDK 或 NVIDIA/CUDA 专有组件。
3. 保留本项目 `LICENSE`、`NOTICE`、本文件，以及所有实际分发依赖自身的许可证/NOTICE。若修改第三方文件，按其许可证标记修改。
4. 含 MobileCLIP 权重的研究包必须使用专门的研究用途发行流程，明确显示非商业限制并随包附上 Apple 模型许可；它不能被标为通用 Apache-2.0 包。
5. 本声明是工程合规记录，不构成法律意见。对外商业发行、面向特定司法辖区的发行或数据再分发，应由具备权限的法务人员复核。
