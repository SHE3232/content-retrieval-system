# 开源合规审查报告

审查日期：2026-08-22  
审查对象：Content Retrieval System 源代码、锁定依赖、随附第三方源代码、模型、构建/运行工具与验证数据集。

## 结论

项目贡献者有权授权的自有代码和文档已准备采用 [Apache License 2.0](../LICENSE)，并通过根目录 [NOTICE](../NOTICE) 明确授权边界。第三方材料仍受原许可证约束，详细来源和义务见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

本次扫描覆盖三套 Python `uv.lock` 和一套 Flutter `pubspec.lock`：

- 246 个唯一的“生态 + 名称 + 版本”审核项；
- 374 条按环境保留的依赖记录，其中 337 条 `approved`、34 条 `restricted`、3 条 `project-owned`；
- 0 条缺失许可证、0 条缺失证据、0 条 `review-required`；
- 17 个唯一受限组件，均为 Linux CUDA 路径下的 NVIDIA 专有传递依赖。

源代码公开发行在排除受限模型、数据和专有运行时后可以采用 Apache-2.0。当前 MobileCLIP-S0 预训练权重仅获准用于非商业研究，因此任何包含该权重的归档都不是不受限制的开源/商业发行；默认发行包必须排除它，或者使用显式的研究用途门禁和独立声明。

## 审查范围与方法

### 依赖范围

| 环境 | 锁文件 | 记录数 |
|---|---|---:|
| 后端 Python | `backend/uv.lock` | 152 |
| 模型工具 Python | `model-tools/uv.lock` | 84 |
| 转换工具 Python | `conversion-tools/uv.lock` | 99 |
| Flutter/Dart | `frontend/pubspec.lock` | 39 |
| **合计** |  | **374** |

同一组件出现在多个环境时保留多行，以便判断它在何处被直接或传递引入；审核基线按唯一名称和版本去重。项目自身的三个 Python 包标记为 `project-owned`。

### 证据优先级

许可证判断采用以下优先级，并固定到精确版本或源代码修订：

1. 发布工件内的 `LICENSE`、`COPYING`、`NOTICE` 和第三方声明；
2. 对应 Git 标签/提交中的上游许可证文件；
3. PyPI、pub.dev、Hugging Face 等官方发布页的结构化元数据；
4. 分类器或项目描述仅作交叉检查，不在与许可证正文冲突时覆盖正文。

机器可读审核记录在 [`tools/compliance/approved-licenses.json`](../tools/compliance/approved-licenses.json)，生成结果在 [`docs/dependency-licenses.csv`](dependency-licenses.csv)。生成器对名称按生态规范化，并在任何锁定组件未获审核时失败。

## 重点义务与风险

### 1. 受限 NVIDIA/CUDA 传递依赖

以下 17 个唯一包在锁文件中产生 34 条 `restricted` 环境记录：

`cuda-bindings`、`cuda-toolkit`、`nvidia-cublas`、`nvidia-cuda-cupti`、`nvidia-cuda-nvrtc`、`nvidia-cuda-runtime`、`nvidia-cudnn-cu13`、`nvidia-cufft`、`nvidia-cufile`、`nvidia-curand`、`nvidia-cusolver`、`nvidia-cusparse`、`nvidia-cusparselt-cu13`、`nvidia-nccl-cu13`、`nvidia-nvjitlink`、`nvidia-nvshmem-cu13`、`nvidia-nvtx`。

它们是 PyTorch/LiteRT 在 Linux CUDA 平台上的条件传递依赖，采用 NVIDIA 专有软件条款而不是 Apache-2.0。项目默认 Windows CPU 发行不得解析或捆绑这些组件；如以后提供 GPU/Linux 构建，必须逐项接受对应 NVIDIA 条款、确认再分发权，并为该发行物生成平台实测 SBOM/许可证归档。

### 2. 模型代码与权重许可分离

- `ml-mobileclip` 源代码固定到 `aecfb5453d022e9deff12f81a150ea8f35194baa`，采用 MIT；保留上游 LICENSE 和 ACKNOWLEDGEMENTS。
- `MobileCLIP-S0` 权重固定到 `71aa3e13dda93115871afbd017336535ba29886c`，采用 Apple Machine Learning Research Model License，仅限非商业研究。
- `paraphrase-multilingual-MiniLM-L12-v2` 固定到 `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`，模型页声明 Apache-2.0。

根目录 Apache-2.0 不能覆盖或放宽 MobileCLIP 权重条款。模型清单中的 `license_name`、来源修订和 SHA-256 是打包前的必检字段。

### 3. 弱著佐权和复合许可证

- MPL-2.0 组件（以及 MPL 与 MIT/Apache 的组合表达式）可与项目聚合，但修改并分发其 MPL 覆盖文件时，必须按 MPL-2.0 提供相应源代码并保留声明。
- pypdfium2 wheel 同时涉及 pypdfium2 包装层、PDFium 及 PDFium 第三方代码；发行时必须保留工件自带的完整许可证目录，不能只记录一个 SPDX 标识。
- Apache-2.0、BSD、MIT、ISC、PSF 等宽松许可证仍要求保留相应版权、许可证、NOTICE 或免责声明。CSV 的 `redistribution` 列记录每个精确版本的最低动作。

### 4. 工具和运行时

Tika JAR、便携 Python、Java 运行时、Flutter/Dart 运行时及 .NET 组件若实际进入归档，均应以“实际分发文件”为范围保存它们自带的许可证和第三方声明。本机 Oracle JDK 23.0.2 仅是审查环境工具，不能因项目采用 Apache-2.0 而直接纳入公开便携包；公开发行优先选用单独核准的 OpenJDK 发行版并保留 `legal/`。

### 5. 数据和用户内容

Natural Questions 衍生样本保守按 CC BY-SA 3.0 处理；COCO 子集的 200 张 Flickr 图片具有六类逐图 CC 2.0 条款，其中包含非商业、禁止演绎和相同方式共享限制。两者均排除在默认公开包之外。用户 PDF、DOCX、图片、索引库和查询记录也不是项目可授权内容，未经权利确认不得发布。

## 发行矩阵

| 发行类型 | 可包含 | 必须排除/额外条件 | 结论 |
|---|---|---|---|
| 公开源代码 | 项目代码、文档、锁文件、数据准备脚本、MobileCLIP MIT 源代码及其声明 | 排除模型权重、下载的数据二进制、用户文件和本地缓存 | 可标为“项目自有部分 Apache-2.0”；第三方按各自许可证。 |
| 默认 CPU 二进制 | 上述内容、核准的 CPU wheels、Tika、许可已核准的便携运行时 | 排除 MobileCLIP-S0 权重、NVIDIA/CUDA、Oracle JDK、NQ/COCO、用户内容 | 通过依赖清单和归档内许可证检查后可发布。图片语义功能需由用户自行提供合规权重，或使用另行核准的替代模型。 |
| 非商业研究包 | 默认包内容 + MobileCLIP-S0 权重 | 必须显式确认研究用途；随附 Apple 模型许可和模型卡；不得宣传为通用开源或商业包 | 仅限许可证允许的非商业研究场景。 |

## 可复现核查命令

在仓库根目录使用 Python 3.10 执行：

```powershell
& '.\backend\.venv\Scripts\python.exe' tools/compliance/generate_license_inventory.py `
  --repository . `
  --approvals tools/compliance/approved-licenses.json `
  --output docs/dependency-licenses.csv `
  --check

& '.\backend\.venv\Scripts\python.exe' -m pytest tools/compliance/tests -q
```

更新锁文件后，先审核新出现的精确版本并更新 `approved-licenses.json`，再去掉 `--check` 重新生成 CSV。禁止通过把未知许可证写成宽松许可证来绕过门禁。

## 发布检查表

- [ ] 四个锁文件没有未审核的名称/版本，生成器以 `--check` 成功。
- [ ] `LICENSE`、`NOTICE`、`THIRD_PARTY_NOTICES.md` 和实际分发依赖的许可证文件均进入归档。
- [ ] 包中实际的 Python/Dart/原生组件与 CSV 及包清单一致；没有从开发环境意外复制缓存或未锁定包。
- [ ] 默认包不含 MobileCLIP-S0 权重、NQ/COCO 二进制、用户文件、Oracle JDK 或 NVIDIA/CUDA 包。
- [ ] 若生成研究包，发布者已显式确认非商业研究用途，包清单标为 `research-only`，并随附 Apple 模型许可和模型卡。
- [ ] 便携 Python、Tika、OpenJDK、.NET 或其他运行时的许可证/NOTICE/third-party notices 按实际文件完整保存。
- [ ] 对 MPL 覆盖文件或任何第三方源代码的修改已标记，并提供许可证要求的对应源代码。
- [ ] 对外发布前复核商标、专利、出口管制、隐私和数据权利；这些事项不由开源许可证清单自动解决。

本报告用于工程发布门禁和来源追踪，不构成法律意见。组件版本、打包内容或用途变化时应重新审查。
