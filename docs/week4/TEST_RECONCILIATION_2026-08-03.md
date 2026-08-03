# 第四周 337 项测试证据整改审计

- 整改日期：2026-08-03
- 原始基线：`537e06239717494dfca3bedd70cb1e2d16c14dce`
- 受测提交：`199ecec74577fc0f6a92e92c104e7d93a5165aa0`

## 1. 整改原因

原始提交在干净 detached worktree 中只能收集并通过 162 项测试。历史工作区的
337 项结果还依赖 12 个未跟踪测试文件、未提交的本地 PDF/DOCX、未跟踪的
Flutter 图标以及未启动时会跳过的 Tika 服务，因此不能作为原始提交的提交级证据。

## 2. 整改内容

1. 将 12 个扩展测试文件、共 175 项测试纳入 Git。
2. 将扩展测试使用的 TXT、PDF、DOCX、JPEG 和 PNG 改为在 pytest 临时目录中
   确定性生成，不再读取个人文件、`datasets/manifest.csv` 或未跟踪的前端资源。
3. 保留一项真实 Tika DOCX 解析测试，并提交 Tika 3.3.1 的 SHA-512、启动脚本和
   使用说明；第三方 JAR 本身继续排除在 Git 之外。
4. 修复后台 Windows PowerShell 未加载 `Get-FileHash` 时启动脚本无法验哈希的
   问题，改用 .NET SHA-512 实现。

对应提交：

- `578c7da40129754f56364638b2f2d7669163b6ea`：纳入扩展回归测试和 Tika 约束。
- `199ecec74577fc0f6a92e92c104e7d93a5165aa0`：修复后台启动脚本的哈希验证兼容性。

## 3. 干净提交验证

从受测提交创建新的 detached worktree：

`F:/contentretrivalsystem/.worktrees/week4-evidence-verify-final`

验证过程：

1. 验证 worktree 在外部依赖 provision 前、provision 后和测试后均为 Git clean。
2. 验证 MobileCLIP 源码归档 SHA-256 为
   `dc4396cada8b3473dff1957541ef6f277521e3757bfcea698da1faeface54b35`。
3. 验证 Tika 3.3.1 JAR SHA-512 为
   `2ca66e2445f8463aefad6a6396725cdb64eb23f94d3948a295daf83bba2b5c3bd51b6e29cc52cf6dce8a71948d6a8431dc39efc56500f9bfe30fdbe0a3ee1d48`。
4. 执行 `uv sync --project backend --frozen`，独立安装 129 个锁定依赖包。
5. 通过提交内脚本启动 Tika，并确认 `127.0.0.1:9998` 正常监听。

结果：

- 测试收集：337 tests collected。
- 全量回归：337 passed，0 failed，0 skipped。
- 核心覆盖率门：313 passed，总覆盖率 87.91%，通过 85% 门槛。

机器可读证据：`docs/week4/evidence/test-reconciliation-2026-08-03.json`。

## 4. 正式口径

第四周测试证据应按提交分别陈述：

- 原始提交 `537e06239717494dfca3bedd70cb1e2d16c14dce`：162 passed。
- 整改提交 `199ecec74577fc0f6a92e92c104e7d93a5165aa0`：337 passed，0 skipped；
  核心覆盖率 87.91%。

不得把整改后的 337 项结果追溯写成原始提交的测试数量。模型权重和真实模型清单
仍属于独立的运行资源门，本次测试证据整改不代表第五周真实模型 E2E 已完成。
