# 开源合规审查与 Apache 2.0 发布设计

## 目标

为离线可访问多模态本地内容检索系统建立可复核、可持续更新的开源合规基线：项目自有代码采用 Apache License 2.0；全部锁定的软件依赖逐项记录许可证；第三方代码、模型、工具和数据集按各自条款单独说明；发行包携带必要的许可证和署名材料。

## 审查边界

审查覆盖仓库和发行流程能够引用、下载、构建或打包的下列内容：

- `backend/uv.lock`、`conversion-tools/uv.lock`、`model-tools/uv.lock` 中的运行、开发、测试和转换依赖；
- `frontend/pubspec.lock` 中的 Dart、Flutter SDK、运行和测试依赖；
- Flutter 生成的平台模板，以及 Gradle、Android Gradle Plugin、Kotlin、Python、Java 和 `uv` 等构建或运行工具；
- Apache Tika 服务器 JAR 及其内部第三方组件声明；
- MobileCLIP 源码与权重、Sentence Transformers 多语言 MiniLM 权重；
- Natural Questions、COCO 和仓库内项目自建或用户提供的测试材料；
- 打包脚本复制进发行物的 Python、Java、Flutter、模型和数据资产。

仅被文档列为候选、尚未下载且未进入构建或发行流程的 RVL-CDIP 和 Wikipedia Dumps 记录为“未使用”，不计入当前发行物依赖。

## 许可证分层

根目录 `LICENSE` 只授权项目贡献者有权许可的自有代码和文档，不改变任何第三方材料的许可证。根目录 `NOTICE` 给出项目署名并指向完整第三方声明。具体分层如下：

| 材料 | 项目许可证关系 | 处理方式 |
|---|---|---|
| 项目自有代码与文档 | Apache-2.0 | 由根目录 `LICENSE` 授权 |
| 常规软件依赖 | 独立许可证 | 在依赖清单中逐版本记录，发行时保留适用文本和署名 |
| MobileCLIP 源码 | MIT，并包含单独的上游致谢 | 保留源码许可证和上游致谢 |
| MobileCLIP 权重 | Apple Machine Learning Research Model License | 明确排除在 Apache-2.0 外；仅限非商业研究；默认不进入通用开源发行包 |
| 多语言 MiniLM 权重 | Apache-2.0 | 固定仓库、修订和摘要，随模型许可证分发 |
| NQ 衍生数据 | 按 CC BY-SA 3.0 保守处理 | 单独署名和同方式共享；默认不随代码发行 |
| COCO 图片 | 逐图 CC 条款，包含 NC、ND、SA 等限制 | 逐图保留来源和许可证；默认不随代码发行 |
| 用户提供的 PDF/DOCX | 未取得公开再分发授权 | 只用于本地验证，不进入公开发行物 |

`Copyright 2026 Content Retrieval System contributors` 作为项目默认署名。该署名不声称拥有第三方组件、模型或数据的版权。

## 交付文件

### 根目录发布文件

- `LICENSE`：Apache License 2.0 官方标准文本，不增加或修改条款。
- `NOTICE`：项目名称、默认署名、第三方边界和 `THIRD_PARTY_NOTICES.md` 指引。
- `THIRD_PARTY_NOTICES.md`：面向发布者和使用者的高层第三方声明，按代码、模型、工具和数据集分类，包含固定版本或修订、来源、许可证、使用方式、再分发义务和发行决策。

### 审查证据

- `docs/OPEN_SOURCE_COMPLIANCE.md`：审查范围、方法、结论、风险、许可证兼容性边界和发布检查表。
- `docs/dependency-licenses.csv`：逐环境列出生态、环境、包名、版本、直接性、用途、来源、许可证表达式、证据 URL、审查状态和备注。相同包在不同锁文件中保留独立记录，以便与实际构建环境对账。

### 可重复校验

- `tools/compliance/generate_license_inventory.py`：仅使用 Python 标准库解析三份 `uv.lock` 和 `pubspec.lock`，将锁定依赖与已审核基线对账，并检查缺失、重复和未审查记录。
- `tools/compliance/approved-licenses.json`：保存逐“生态/包名/版本”的人工核验结果、证据来源和状态；不把不明确的包自动归类为宽松许可证。
- `tools/compliance/tests/test_generate_license_inventory.py`：验证所有锁定项均进入 CSV、项目自身包不会被误报为第三方、受限和未知条款会阻止发布模式校验。

生成器不把 PyPI、pub.dev 或包元数据中的自由文本当作唯一证据。自动元数据用于发现，最终许可证表达式应优先来自随精确版本发布的 `LICENSE`、包仓库固定标签或官方项目页面。

## 审查状态与发布门禁

每个清单项只能使用以下状态：

- `approved`：许可证已由精确版本或固定修订的官方材料确认，义务已记录；
- `restricted`：允许特定用途但存在非商业、研究限定、禁止演绎、专有或其他限制；
- `review-required`：来源可确认，但许可证表达式或二进制再分发义务仍不充分；
- `not-distributed`：开发或本地验证可用，但被明确排除在发行物之外；
- `project-owned`：项目自身包，不属于第三方依赖。

发布模式校验在以下任一条件出现时失败：

1. 锁文件中出现清单未覆盖的包名和版本；
2. 发行集合中包含 `restricted` 或 `review-required` 项；
3. 模型或数据没有固定来源、修订/摘要和许可证；
4. 发行包缺少 `LICENSE`、`NOTICE` 或 `THIRD_PARTY_NOTICES.md`；
5. Python、Java、Tika 或 Flutter 二进制的随附法律文件未被保留。

## 发行流程调整

`tools/week6/package_stable_build.ps1` 在构建发行候选时复制根目录三份合规文件。运行时组件的法律材料按来源保留：Python 运行时保留其 `LICENSE`；`jlink` 生成的 Java 运行时保留 `legal/`；Tika JAR 保留原始 JAR 内的 `META-INF/LICENSE` 和 `META-INF/NOTICE`；Flutter 构建产物使用 Flutter 生成的第三方许可证清单，并与项目声明一同交付。

MobileCLIP 权重和受限 COCO 图片默认不进入通用开源发行包。若研究交付明确包含 MobileCLIP 权重，则必须同时分发 Apple 模型许可证和指定署名，并在交付名称和说明中标记“仅限非商业研究”。

## 验证

完成实施后执行以下验证：

1. 解析全部锁文件并核对清单记录数及唯一键；
2. 对每个 `approved` 项检查非空许可证表达式和官方证据 URL；
3. 对所有 `restricted`、`review-required` 和 `not-distributed` 项检查明确发行决策；
4. 扫描仓库内版权、SPDX、来源 URL 和许可证标记，确认不存在未登记的第三方材料；
5. 运行合规工具单元测试；
6. 构建或审计一个发行候选，确认合规文件和运行时法律目录实际存在；
7. 检查 README 到合规文档的链接以及合规文档内部链接。

## 非目标与法律边界

本次工作不替代律师意见，不判断合理使用、数据库权利或跨法域可执行性，也不授予项目方尚未取得的第三方权利。审查结论只描述本仓库在固定依赖和固定资产版本下的技术事实、已发现条款和建议的发行控制。依赖、模型、数据或工具版本变化后必须重新生成并复核清单。
