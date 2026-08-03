# 第四周提交内容重新整合记录

- 整合日期：2026-08-03
- 整合基线：`d2bcddcd20b41e12c5c02dca142e80a0be256d25`
- 受测提交：`c920a30a1da6931bb61c070e9d4cf26d0755377f`
- 整合原则：只纳入可归属、可复现、可审计的第四周交付内容，不整包恢复旧工作区。

## 1. 已纳入内容

1. 补录 2026-08-02 的第四周原始审核，并在文件开头标明整改复核状态。
2. 恢复 stash 中四份第四周 DOCX 的发布修订：删除正文末尾的证据文件引用，
   将“证据”类栏目名称改为普通内容名称，不改动接口、指标或实现结论。
3. 在 API 文档、端到端测试报告和第四周周报中统一测试口径：
   “原始提交 162 passed；整改提交 337 passed”。
4. 在第四周 README 中建立原始审核、测试证据整改和本次重新整合记录的入口。

## 2. 明确排除内容

| 候选内容 | 处理 | 原因 |
|---|---|---|
| 备份中的 12 个旧扩展测试副本 | 排除 | 已提交版本已改为 pytest 临时目录生成自包含夹具；旧副本仍依赖本地文件 |
| 备份中的旧 `start-tika.ps1` | 排除 | 已提交版本包含固定版本、SHA-512 校验和后台 PowerShell 兼容修复 |
| stash 中依赖锁文件和工具配置 | 排除 | 混有第二、三周及个人工作区调整，无法整体归属第四周 |
| `frontend/` 和第五周计划 | 排除 | 属于第五周 UI 与无障碍工作，不属于第四周检索核心 |
| 模型权重、真实 `model-manifest.json` 和数据集原文件 | 排除 | 属于独立运行资源，继续按许可证和运行门管理，不进入 Git |
| 缓存、虚拟环境、Chroma 数据库和渲染中间文件 | 排除 | 均为可再生或本地运行产物 |

## 3. 文档验证

- 四份 DOCX 均可由 Microsoft Word 只读打开并导出为 PDF。
- 页数保持不变：API 文档 6 页、准确率报告 4 页、端到端报告 5 页、周报 4 页。
- 所有发生版式变化的页面均完成逐页检查；未发现裁切、重叠、表格溢出或缺字。
- OOXML ZIP 完整性检查通过；四份文档均为 19 个部件。
- 可访问性审计结果均为 0 high、0 medium、0 low。
- 发布修订后四份文档均不再包含 `证据文件:` 正文尾注。

本机没有 LibreOffice，因此未使用 `render_docx.py`；本次采用 Microsoft Word
只读导出作为 Windows 实机渲染证据。

## 4. 提交级测试验证

从受测提交创建新的 clean detached worktree：

`F:/contentretrivalsystem/.worktrees/week4-reintegrate-verify`

启动已校验 SHA-512 的 Apache Tika 3.3.1 后执行：

```powershell
F:\contentretrivalsystem\backend\.venv\Scripts\python.exe -m pytest -q
```

结果：`337 passed in 34.20s`，0 failed，0 skipped。测试结束后已确认 Tika
相关 Java 进程为 0，端口 9998 无监听。

整合基线首次全量运行曾出现一次 Chroma HNSW 临时目录错误：
`Error creating hnsw segment reader: Nothing found on disk`。对应单项连续 12 次、
所在模块连续 8 次（共 96 项执行）均未复现；随后基线全量、提交前全量和受测提交
全量均为 337 passed。本次没有用重试逻辑或业务代码改动掩盖该现象，后续继续按
Chroma 版本升级风险跟踪。

机器可读结果见 `evidence/reintegration-2026-08-03.json`。

## 5. 验收边界

本次重新整合使第四周代码、测试、审核和正式报告形成一致的提交级交付集，但不代表
第五周真实模型端到端验收已经完成。最终真实 E2E 前仍需补齐模型权重和真实
`model-manifest.json`；VoiceOver 仍必须在 macOS 实机执行，只有 Windows 证据时应
记录为 `not_run`。
