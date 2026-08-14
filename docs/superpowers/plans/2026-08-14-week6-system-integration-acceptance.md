# 第六周系统集成、全量测试与性能优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将解析、嵌入、检索、Flutter UI 和本地运行资源整合为可复现的稳定应用，并以可自动判定的证据完成全量测试、性能优化、缺陷关闭和离线数据安全验收。

**Architecture:** 以一个精确 Git 提交作为唯一候选版本，在干净 detached worktree 中执行全部门禁。`docs/week6/evidence/manifest.json` 只引用工具真实生成的原始证据，严格验证器负责汇总 PASS/FAIL/BLOCKED；三份报告和稳定版压缩包只能从全部必需门禁为 PASS 的同一提交生成。

**Tech Stack:** Python 3.10、pytest、pytest-cov、FastAPI、ChromaDB、Sentence Transformers、MobileCLIP、Apache Tika、Flutter/Dart、PowerShell、Windows release build、JSON、DOCX、SHA-256

---

## 1. 原始任务要求与解释边界

权威来源：仓库根目录 `Software Engineering Project Offline Accessible Multimodal Local Content Retrieval System.pdf` 第 4 页。

### 核心目标

稳定完整应用，达到面向普通消费级硬件的生产级可靠性，并完成性能优化。

### 五项关键任务

1. 完成解析、嵌入、检索和 UI 的全链路集成。
2. 执行单元、集成、端到端和大文件库压力测试。
3. 降低嵌入推理延迟、加快向量检索并降低内存占用。
4. 修复测试中发现的全部严重和高优先级缺陷。
5. 审查本地数据安全，确认系统仅离线运行且不发生数据泄露。

### 四项正式交付物

1. 完整集成的稳定应用构建。
2. 完整测试与覆盖率报告；核心模块单元测试语句覆盖率不低于 90%。
3. 性能优化基准报告。
4. 缺陷修复与安全审查报告。

若课程平台延续前五周的提交习惯，可额外提交《第六周工作周报》，但周报不是上述四项技术交付物，不能替代其中任一项。

## 2. 当前基线与第六周缺口

候选开发基线为提交 `25f7cf232cbb87c21a32049e966ed3f9aad51cf6`。开始第六周实现时必须重新记录实际基线提交；若基线已经前移，不得沿用这里的哈希或旧证据。

| 现有能力/证据 | 当前状态 | 为什么不能直接作为第六周验收 |
|---|---|---|
| Flutter UI | Week 5 README 记录 195 项自动化测试通过 | 只证明当时的 UI 基线，未覆盖 Week 6 候选提交和完整后端集成 |
| 五格式索引与检索 | TXT、PDF、DOCX、JPG、PNG 真实 E2E 与重启持久化已有证据 | 尚未覆盖打包后的 UI→API→解析→嵌入→Chroma→结果打开全链路 |
| 覆盖率 | Week 4 证据为 538/612，87.91%，且只统计 retrieval、indexing、storage 的 7 个文件 | 低于 90%，统计边界也不等于当前“全部核心模块” |
| 向量检索性能 | 旧证据为 10,000 条记录、50 次查询、p95 62.76 ms | 没有在同机同数据上比较 Week 6 优化前后，也未证明嵌入延迟与内存降低 |
| 检索准确率 | NQ 与 COCO 基准已有旧结果 | 性能优化后仍需复跑，确认准确率未被速度优化破坏 |
| 离线运行 | 启动器设置离线环境变量并只监听 `127.0.0.1` | 仍需以断网运行和进程连接快照证明无非环回网络访问 |
| Week 5 外部门禁 | 10/19 PASS、9/19 BLOCKED | 不得静默改写为已完成；Week 6 报告须继承为残余风险或补齐证据 |

## 3. 修订后的验收原则

1. **提交一致性：** 构建、测试、性能、安全、报告和压缩包必须指向同一个 40 位 Git 提交。
2. **干净环境：** 最终门禁只能在该提交的干净 detached worktree 中执行；当前脏工作树的结果只可用于开发诊断。
3. **真实全链路：** 最终 E2E 不允许用 mock 嵌入、内存假仓库或伪造 API 响应替代真实模型、Tika 和 Chroma。
4. **平台限定：** 若只有 Windows 完成真实集成验收，交付名称必须写“Windows 完整集成稳定版”，不得宣称全部桌面/移动平台均为稳定版。
5. **覆盖率限定：** 90% 只以显式核心模块清单和 `unit` 测试标记计算；集成、E2E 与压力测试不得混入单元覆盖率抬高数字。
6. **性能可比：** 优化前后使用同一硬件、同一电源模式、同一数据集、同一模型、相同预热和至少 3 轮独立运行；旧报告数字只能作历史参考。
7. **安全实证：** “离线”不能只看配置项，必须在禁用外网后运行全链路，并检查候选进程没有非环回连接。
8. **缺陷零豁免：** 最终候选版本不得存在未关闭的 Critical 或 High 缺陷；Medium/Low 必须记录影响、规避方式和后续安排。
9. **证据先于报告：** 报告中的每个数值与状态都由原始 JSON/XML/日志计算；报告生成器不得把 BLOCKED 或 FAIL 写成 PASS。
10. **一票否决：** 任一必需门禁为 FAIL/BLOCKED，四项正式交付不得标为“验收通过”。

## 4. 核心模块与正式输出

### 4.1 覆盖率统计边界

以下目录合并计算单元测试语句覆盖率，合计必须 `>=90.00%`：

```text
backend/src/content_retrieval/api/
backend/src/content_retrieval/domain/
backend/src/content_retrieval/embeddings/
backend/src/content_retrieval/parsers/
backend/src/content_retrieval/retrieval/
backend/src/content_retrieval/services/
backend/src/content_retrieval/storage/
backend/src/content_retrieval/mvp.py
backend/src/content_retrieval/runtime.py
```

Flutter 不套用任务书的 90% 数字，但 `flutter analyze`、全部 Flutter 自动化测试和关键页面集成测试必须全部通过。

### 4.2 正式提交结构

```text
output/week6/第六周最终提交_请上传这4项/
  01_Windows完整集成稳定版.zip
  02_完整测试与覆盖率报告.docx
  03_性能优化基准报告.docx
  04_缺陷修复与本地数据安全审查报告.docx
  SHA256SUMS.txt
  SOURCE_VERSION.txt
```

若最终取得其他平台的完整集成证据，可在证据清单通过后去掉文件名中的 `Windows`，不能只凭 Week 5 的构建成功记录扩大声明范围。

## 5. 验收门禁总表

| 门禁 | 通过条件 | 必需证据 |
|---|---|---|
| G0 候选冻结 | 干净 worktree；40 位提交一致；依赖锁和模型摘要通过 | `candidate.json`、预检日志 |
| G1 稳定构建 | Flutter analyze/test/release build 和后端测试全部退出 0；压缩包在新目录可启动 | 构建 JSON、日志、哈希 |
| G2 全链路集成 | UI 发起五格式索引与三通道检索；结果打开/复制；删除/重建；重启持久化；离线恢复全部通过 | E2E JSON、截图/录屏索引、运行日志 |
| G3 单元覆盖率 | 显式核心模块、仅 `unit` 标记，合计语句覆盖率 `>=90.00%`；无失败/跳过的必需单测 | coverage JSON/XML/HTML、pytest 日志 |
| G4 集成/E2E | API、Tika、真实模型、Chroma 和 Flutter 集成测试全部通过 | JUnit XML、E2E JSON |
| G5 大库压力 | 至少 10,000 条索引记录、500 次混合查询、30 分钟 soak；0 崩溃/死锁/未处理异常；末 5 分钟 RSS 中位数不超过首 5 分钟的 110% | stress JSON、资源采样 CSV |
| G6 性能优化 | 同机三轮中位数：嵌入综合 p95、向量检索 p95、峰值 RSS 均较基线改善至少 5%；10k 检索 p95 `<=2000 ms`；NQ/COCO 主要指标下降不超过 1 个百分点 | baseline/candidate 原始结果、比较 JSON |
| G7 缺陷关闭 | 0 个 Open Critical、0 个 Open High；每个已关闭项有复现、回归测试、修复提交和复测证据 | bug ledger、测试日志 |
| G8 离线安全 | 断网全链路通过；应用/Tika/FastAPI 仅环回通信；0 个非环回连接；路径越权、重解析点绕过、敏感文件误打包测试通过 | 连接快照、安全测试 JSON、包审计 |
| G9 报告与包 | 四项交付来自同一候选提交；证据清单严格校验通过；哈希复算一致 | manifest、SHA256SUMS、最终验证日志 |

## Task 1: 建立 Week 6 证据模型和严格验证器

**Files:**

- Create: `docs/week6/README.md`
- Create: `docs/week6/evidence/manifest.json`
- Create: `tools/week6/validate_evidence.py`
- Create: `tools/week6/tests/test_validate_evidence.py`

- [ ] **Step 1: 固定证据状态和门禁 ID**

在验证器中只允许 `PASS`、`FAIL`、`BLOCKED`、`NOT_RUN` 四种状态，固定 G0-G9 十个门禁。`PASS` 必须包含 `source_commit`、`generated_at`、`command`、`exit_code` 和至少一个可读取的相对证据路径。

- [ ] **Step 2: 先写失败测试**

覆盖以下场景：缺门禁、重复门禁、短提交哈希、证据文件不存在、哈希不一致、四项交付提交不一致、BLOCKED 被汇总为 PASS、覆盖率 89.99 被舍入为 90、性能只给候选值而无基线值。

- [ ] **Step 3: 运行 RED**

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest `
  tools/week6/tests/test_validate_evidence.py -q
```

Expected: FAIL because `tools/week6/validate_evidence.py` does not exist.

- [ ] **Step 4: 实现严格验证**

最终模式仅当 G0-G9 全部 PASS 时退出 0；开发模式可输出未完成汇总，但退出码仍不能被报告生成器当作最终通过。所有覆盖率比较使用未四舍五入浮点值。

- [ ] **Step 5: 运行 GREEN 并提交**

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest `
  tools/week6/tests/test_validate_evidence.py -q
git add docs/week6 tools/week6
git commit -m "test: define Week 6 acceptance gates"
```

## Task 2: 冻结候选版本并构建完整稳定应用

**Files:**

- Create: `tools/week6/capture_candidate.ps1`
- Create: `tools/week6/package_stable_build.ps1`
- Create after execution: `docs/week6/evidence/candidate.json`
- Create after execution: `docs/week6/evidence/build/`

- [ ] **Step 1: 捕获候选身份**

脚本拒绝脏 worktree、非 40 位提交、未锁定 Python 依赖、缺失模型清单或摘要不一致。记录 Git 提交、分支/ detached 状态、Python/Flutter/Dart/Java/Tika/模型版本、CPU、内存和 Windows 版本。

- [ ] **Step 2: 在精确提交的干净 worktree 预检**

```powershell
uv sync --project backend --locked
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
Set-Location frontend
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build windows --release
```

Expected: every command exits 0; preflight prints `MVP preflight passed`; analyzer reports no issues.

- [ ] **Step 3: 打包离线运行所需资源**

稳定版必须包含 Flutter Windows release、后端源/锁定运行时、启动脚本、Tika、模型清单，以及经摘要校验的离线模型资源或同一交付项内的分卷资源包。首次启动不得下载资源。不得包含 `.git`、`.venv` 开发缓存、`data/` 用户索引、`mvp-input/`、用户设置、日志、凭据或本机绝对路径。

- [ ] **Step 4: 在全新目录解压复验**

从正式 ZIP 解压到新的空目录，在禁用外网条件下启动后端与 UI，确认 `/health/ready` 返回 ready，UI 显示已连接。验证结束后只停止本次启动器拥有的进程。

- [ ] **Step 5: 保存构建证据**

记录每条命令、退出码、开始/结束时间、产物大小、SHA-256 和候选提交。若拆分模型资源包，主包清单必须列出所有分卷及其 SHA-256。

## Task 3: 将测试分层并达到核心模块 90% 单元覆盖率

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `pytest.ini`
- Modify: `backend/tests/test_*.py`
- Create after execution: `docs/week6/evidence/tests/`

- [ ] **Step 1: 为测试添加明确标记**

注册 `unit`、`integration`、`e2e`、`stress`、`requires_models`、`requires_tika` 标记。一个测试可以同时属于功能域和外部依赖标记，但最终单元覆盖率命令只选择 `unit`，且 unit 测试不得启动真实网络服务或依赖持久化外部进程。

- [ ] **Step 2: 生成当前核心模块单元覆盖率**

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests `
  -m unit `
  --cov=content_retrieval.api `
  --cov=content_retrieval.domain `
  --cov=content_retrieval.embeddings `
  --cov=content_retrieval.parsers `
  --cov=content_retrieval.retrieval `
  --cov=content_retrieval.services `
  --cov=content_retrieval.storage `
  --cov=content_retrieval.mvp `
  --cov=content_retrieval.runtime `
  --cov-report=json:docs/week6/evidence/tests/unit-coverage.json `
  --cov-report=xml:docs/week6/evidence/tests/unit-coverage.xml `
  --cov-report=html:docs/week6/evidence/tests/htmlcov `
  --cov-fail-under=90 `
  --junitxml=docs/week6/evidence/tests/unit-junit.xml
```

Expected: all selected tests pass and the unrounded combined statement coverage is at least 90.00%. 如需分支覆盖率诊断，应另起一次不带 `--cov-fail-under` 的运行；不得让分支覆盖率改变任务书规定的语句覆盖率判定。

- [ ] **Step 3: 对未覆盖的真实分支补测试**

优先补齐路径授权、索引增量/删除、Chroma 异常转换、模型清单校验、解析失败、过滤边界、启动/关闭和 UI API 错误恢复；不得通过 `# pragma: no cover`、删除代码或缩小核心模块清单制造 90%。

- [ ] **Step 4: 分别运行集成与 E2E 测试**

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests `
  -m integration --junitxml=docs/week6/evidence/tests/integration-junit.xml
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests `
  -m e2e --junitxml=docs/week6/evidence/tests/e2e-junit.xml
Set-Location frontend
flutter test --machine > '..\docs\week6\evidence\tests\flutter-test.jsonl'
```

Expected: zero failed tests. 必需测试若因资源缺失而 skipped，G3/G4 为 BLOCKED，而不是 PASS。

## Task 4: 执行真实全链路与大文件库压力测试

**Files:**

- Create: `tools/week6/run_integrated_e2e.py`
- Create: `tools/week6/run_stress.py`
- Create: `tools/week6/tests/test_run_stress.py`
- Create after execution: `docs/week6/evidence/e2e/`
- Create after execution: `docs/week6/evidence/stress/`

- [ ] **Step 1: 扩展五格式 E2E 为 UI 全链路**

从 Flutter UI 完成添加受控目录、轮询索引、关键词/文本语义/图片语义/混合检索、筛选、复制路径、打开文件、删除索引、重新索引和后端断开/恢复。所有 API 必须由真实后端、真实模型、Tika 和 Chroma 处理。

- [ ] **Step 2: 验证重启持久化**

记录首次索引后的记录数，安全关闭并使用同一数据目录重启；重启前记录数必须相等，再次提交未变化目录时 `indexed_files=0` 且 `unchanged_files` 等于受控文件数。

- [ ] **Step 3: 建立可重复的大库压力数据**

使用固定随机种子生成不少于 10,000 条索引记录，记录数据清单哈希。执行 500 次混合查询和 30 分钟 soak，持续采样 RSS、CPU、查询延迟、错误、队列长度与未处理异常。

- [ ] **Step 4: 判定压力门禁**

要求 0 崩溃、0 死锁、0 未处理异常、全部 500 次查询得到结构合法响应；10k 数据集检索 p95 不超过 2000 ms；最后 5 分钟 RSS 中位数不超过最初稳定 5 分钟的 110%。

- [ ] **Step 5: 原子写入证据**

测试未完整通过时不得留下 `status=PASS` 的正式 JSON。原始样本、采样 CSV、摘要 JSON 分开保存，摘要引用精确的源文件哈希。

## Task 5: 建立同机前后对比并完成性能优化

**Files:**

- Create: `tools/week6/benchmark_performance.py`
- Create: `tools/week6/compare_performance.py`
- Create: `tools/week6/tests/test_compare_performance.py`
- Modify as evidence requires: `backend/src/content_retrieval/**/*.py`
- Create after execution: `docs/week6/evidence/performance/`

- [ ] **Step 1: 在 Week 6 开发前提交上复跑基线**

在独立干净 worktree 中记录文本嵌入 p50/p95、图片嵌入 p50/p95、10k 向量检索 p50/p95、完整搜索 p50/p95、索引吞吐、空闲 RSS、峰值 RSS 和 30 分钟稳态 RSS。每轮固定预热 10 次、正式查询至少 100 次，独立运行 3 轮。

- [ ] **Step 2: 写性能比较失败测试**

覆盖：硬件或数据哈希不同、只有一轮结果、缺少 RSS、候选改善小于 5%、检索 p95 超过 2000 ms、准确率下降超过 1 个百分点、报告把负数改善写为通过。

- [ ] **Step 3: 只优化实测瓶颈**

对 profiler 证明的热点做最小改动。每项优化先增加正确性/回归测试，再修改实现；不得以减少检索候选、降低向量维度、跳过文件、关闭模型或改变基准数据来换取速度。

- [ ] **Step 4: 在候选提交上以完全相同条件复跑**

以 3 轮中位数比较，要求：嵌入综合 p95 至少改善 5%，向量检索 p95 至少改善 5%，峰值 RSS 至少改善 5%；任何单项关键延迟不得回退超过 5%。

- [ ] **Step 5: 复跑准确率防回归**

NQ 的 recall@10、MRR@10、NDCG@10 和 COCO 的 recall@10、MRR@10、NDCG@10 相对基线下降均不得超过 0.01。超出即 G6 FAIL。

## Task 6: 建立缺陷台账并关闭 Critical/High

**Files:**

- Create: `docs/week6/evidence/bugs/bug-ledger.json`
- Create: `tools/week6/validate_bug_ledger.py`
- Create: `tools/week6/tests/test_validate_bug_ledger.py`

- [ ] **Step 1: 固定严重度定义**

- Critical：数据丢失/损坏、任意本地文件越权读取、外发用户内容、无法启动或主要安全边界失效。
- High：索引/检索/打开/删除/重启持久化任一核心流程稳定失败、可重复崩溃、结果严重错误或无可用规避方式的无障碍阻断。
- Medium/Low：不阻断核心流程且存在明确规避方式的问题。

- [ ] **Step 2: 每个缺陷保留完整链路**

每条记录包含 ID、标题、严重度、发现门禁、环境、复现步骤、期望/实际、失败证据、回归测试、修复提交、复测命令、复测证据和最终状态。

- [ ] **Step 3: 实施测试先行修复**

先运行最小复现确认失败，再提交回归测试与最小修复，最后运行聚焦测试和受影响的完整门禁。不得仅把严重度从 High 下调来通过验收。

- [ ] **Step 4: 严格验证台账**

最终必须为 `open_critical=0`、`open_high=0`。若确实未发现 Critical/High，台账仍需引用实际执行的测试会话，不能只写“无”。

## Task 7: 执行本地数据安全与离线审查

**Files:**

- Create: `tools/week6/audit_offline_security.ps1`
- Create: `backend/tests/test_week6_security.py`
- Create after execution: `docs/week6/evidence/security/`

- [ ] **Step 1: 检查监听与外连边界**

确认 FastAPI 只监听 `127.0.0.1`，Tika 只通过环回访问。记录后端、Flutter、Java/Tika 子进程在启动、索引、搜索和 30 分钟 soak 期间的 TCP/UDP 连接；除环回外不得存在 ESTABLISHED/发送数据连接。

- [ ] **Step 2: 在禁用外网后复跑完整 E2E**

禁用活动网络适配器或使用等效、可审计的出站阻断后启动正式包，完成五格式索引、三通道检索、结果操作和重启持久化。测试结束后恢复用户原有网络状态。

- [ ] **Step 3: 验证文件访问授权**

测试授权根外路径、`..` 规范化、符号链接/Windows reparse point、大小写与分隔符变体、已删除文件、无权限文件和恶意扩展名。任何授权根逃逸均为 Critical。

- [ ] **Step 4: 审计最终包与运行痕迹**

检查 ZIP 不含用户索引、受控测试输入、用户偏好、日志、绝对工作站路径、密钥/令牌和开发缓存；运行日志不得包含文件正文或嵌入向量。允许显示用户主动检索结果所需的文件名和路径，但不得发送到本机之外。

- [ ] **Step 5: 生成机器可判定结果**

安全 JSON 必须列出每项检查、命令、期望、实际、状态和证据。只要出现非环回连接、越权路径成功或敏感文件入包，G8 直接 FAIL。

## Task 8: 生成三份报告并封装四项交付物

**Files:**

- Create: `tools/week6/build_reports.py`
- Create: `tools/week6/tests/test_build_reports.py`
- Create: `docs/week6/reports/完整测试与覆盖率报告.docx`
- Create: `docs/week6/reports/性能优化基准报告.docx`
- Create: `docs/week6/reports/缺陷修复与本地数据安全审查报告.docx`
- Create after execution: `output/week6/第六周最终提交_请上传这4项/`

- [ ] **Step 1: 只从严格证据清单生成报告**

报告生成前运行最终模式验证器。任何必需门禁不是 PASS 时拒绝生成“最终版”，只允许生成明确标注未完成状态的草稿。

- [ ] **Step 2: 完整测试与覆盖率报告内容**

包含候选提交、环境、测试分层、单元/集成/E2E/压力测试结果、显式核心模块清单、未四舍五入覆盖率、缺失行摘要、Flutter 测试、跳过项、失败项和最终判定。

- [ ] **Step 3: 性能优化基准报告内容**

包含同机基线/候选提交、硬件与电源模式、数据/模型哈希、预热与轮次、各轮原始值、三轮中位数、改善百分比、准确率防回归和内存曲线。不得只展示优化后数字。

- [ ] **Step 4: 缺陷与安全报告内容**

包含严重度定义、发现与关闭统计、每个 Critical/High 的复现-修复-复测链路、残余 Medium/Low、监听/连接审查、断网 E2E、路径授权、包内容和隐私结论。

- [ ] **Step 5: 按项目 DOCX 规范生成与验证**

三份 DOCX 统一使用 Times New Roman，黑色文字与线条，白色页面/表格/强调块背景。使用 Word 只读打开检查无修复提示，更新目录/页码，导出 PDF 并逐页检查标题、表格、分页、页眉页脚和中文字符。

- [ ] **Step 6: 生成最终目录与哈希**

从同一候选提交复制稳定版 ZIP 和三份 DOCX，生成 `SOURCE_VERSION.txt` 与 `SHA256SUMS.txt`。在一个新的临时目录解压 ZIP 并复算全部四项交付物的 SHA-256。

## 6. 修订后的最终验收步骤

以下顺序替代“构建成功、测试通过、报告齐全”这类不可判定的旧式验收描述：

1. **冻结版本：** 记录 40 位候选提交，在指向该提交的干净 detached worktree 中执行；工作树不干净则停止。
2. **验证资源：** 锁定依赖同步成功，Python 3.10、Java、Tika、两个模型及其摘要预检通过；任一缺失则 BLOCKED。
3. **运行静态与自动化门禁：** Dart 格式、Flutter analyze、Flutter 全测、后端 unit/integration/e2e 分层测试全部退出 0；必需测试 skipped 视为 BLOCKED。
4. **核对覆盖率：** 只统计第 4.1 节核心模块且只使用 unit 测试；读取 coverage JSON 原始浮点值，合计语句覆盖率必须 `>=90.00%`。
5. **验证正式构建：** 生成 Windows release 和离线稳定包，在新的空目录解压并启动；不得复用源码目录、开发缓存或现有索引。
6. **执行真实全链路：** 在 UI 中完成五格式索引、关键词/文本语义/图片语义/混合检索、筛选、打开/复制、删除/重建、断连恢复和重启持久化；全部断言通过。
7. **执行压力与性能门禁：** 10k 记录、500 查询、30 分钟 soak 通过；在同机三轮对比中，嵌入 p95、向量检索 p95、峰值 RSS 分别改善至少 5%，检索 p95 不超过 2000 ms，准确率下降不超过 0.01。
8. **关闭缺陷：** 验证台账为 0 Open Critical、0 Open High；逐条抽查回归测试、修复提交与复测证据。
9. **执行离线安全验收：** 禁用外网后重复正式包 E2E；候选进程无非环回连接；路径越权、重解析点绕过和敏感文件误打包测试全部被拒绝/未发现。
10. **严格封装：** G0-G9 全部 PASS 后生成三份报告和稳定包；确认四项交付物提交哈希一致、Word 可正常打开、ZIP 可解压运行、SHA-256 复算一致。

## 7. 最终声明规则

- 只有 G0-G9 全部 PASS，结论才写“第六周验收通过”。
- 仅 Windows 完成真实 E2E 时，结论写“Windows 完整集成稳定版通过”，不能扩大为“跨平台稳定版通过”。
- Week 5 的 macOS/VoiceOver、Android Scanner、NVDA/键盘和真实参与者等未完成项必须在残余风险中保留；若本周补齐，可引用新证据关闭。
- 覆盖率低于 90%、性能任一要求无同机基线、存在 Open Critical/High、或离线外连证据不完整时，结论必须为 FAIL/BLOCKED，不能以“基本完成”代替。
