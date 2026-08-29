# 第八周干净工程审计

## 审计结论

本轮在隔离工作树 `codex/week8-finalization` 中实施清理，原始主工作区及其未提交内容不参与编辑。本文记录清理策略与冻结前门禁；最终公开工程的提交号、文件数、总字节数和逐文件 SHA-256 由独立目录内的 `CLEAN_SOURCE_MANIFEST.json` 给出，并由统一 `DELIVERY_MANIFEST.json` 二次绑定，避免在冻结提交前写入会自我循环的版本号。

## 源码级清理

| 项目 | 证据 | 处理 | 回归结果 |
|---|---|---|---|
| Week 5 报告生成器的 `WD_SECTION` | Vulture 2.16，置信度 90% | 删除未使用导入 | 报告测试通过 |
| Week 6 报告生成器的 `WD_SECTION` | Vulture 2.16，置信度 90% | 删除未使用导入 | 报告测试通过 |
| `tmp/docx/build_week2_reports.py` | 仅历史计划引用；依赖未入库且不存在的 `build_architecture_docx.py` | 删除不可复现脚本 | 仓库布局测试通过 |
| `tmp/docx/test_week2_sequence_diagram.py` | 导入上述不可复现脚本，在干净检出中收集失败 | 删除失效测试 | 仓库布局测试通过 |
| `tmp/docx/build_week3_reports.py` | 仅历史计划引用；硬依赖缺失且被忽略的 `output/week3/embedding-coverage.json` | 删除不可复现脚本 | 仓库布局测试通过 |
| Week 2 摄取时序图 | 已完成报告所用的可读图证据 | 迁入 `docs/week2/assets/` | 文件哈希进入公开工程清单 |
| 后端与模型工具的本机 MobileCLIP 路径依赖 | 公开环境在缺少 `third_party/mobileclip-src` 时不能安装 | 从默认锁文件移除，仅在研究流程中显式安装 | 独立公开环境可安装，`mobileclip=NOT_INSTALLED` |
| Week 8 Python 工具的导入、异常类型与重复后缀判断 | Ruff 全目录检查 | 机械整理导入并明确类型错误 | Ruff 0 issue，Week 8 回归通过 |

最终 Vulture 审计为 0 个未解释发现，并记录 15 个由 FastAPI/Pydantic 框架调用、不可按文本引用数删除的路由或校验器。Flutter `analyze` 为 0 issue，因此未删除任何 Dart 变量、函数或部件。

## 白名单边界

公开工程仅从 `git ls-files -z` 的结果中选择根法律文件、后端、Flutter 前端、模型/转换工具、数据集脚本、演示数据、必要工具和公开技术文档。以下内容不进入公开工程：

- `.git`、worktree、虚拟环境、缓存、构建目录、覆盖率输出、临时目录和录制目录；
- 历史周提交 ZIP、历史 DOCX 交付副本和内部 Superpowers 计划；
- 真实模型权重、MobileCLIP 源码副本、ONNX/TFLite、数据库、日志、密钥和证书；
- 不在根文件或根目录白名单中的项目内部文件。

`models/model-manifest.example.json` 是模型目录的唯一公开例外。课程演示研究包在后续发布步骤独立生成，不与公开源码或默认发行包混合。

导出器拒绝脏工作树、缺失必需文件、越界路径、符号链接/Windows 重解析点、非自有非空目标目录和策略不匹配的旧目录。每个复制文件记录相对路径、字节数和 SHA-256；导出器自身的策略文件也记录 SHA-256。

## 独立目录验证结果

验证时设置 `PYTHONDONTWRITEBYTECODE=1` 并禁用 pytest 缓存，Flutter 在一次性副本中运行，待交付目录保持只读文件集合不变。

| 门禁 | 结果 |
|---|---:|
| 后端测试 | 445 passed，1 deselected（需要真实模型/服务的标记项未纳入本轮 CPU 快速回归） |
| 数据集、模型工具、转换工具 | 24 passed |
| Python 主套件合计 | 469 passed，1 deselected |
| Week 5 工具测试 | 7 passed |
| Week 6 启动器/打包/验收测试 | 116 passed |
| 开源合规测试 | 8 passed |
| 演示材料测试 | 33 passed |
| Week 8 清理、发行、报告、作品集与外部门禁测试 | 94 passed，1 skipped（当前 Windows 主机不允许创建真实符号链接；等价 fail-closed 路径用例已通过） |
| Flutter 静态分析 | 0 issues |
| Flutter 测试 | 249 passed |
| 锁定依赖许可证清单 | 312 rows verified |
| 白名单文件复核 | 由冻结提交生成后要求 manifest files = actual files，extras = 0 |
| 禁止内容扫描 | 由冻结提交导出后要求 0 findings |

Python 主套件由 `backend/tests` 的 445 项和 `datasets`、`model-tools`、`conversion-tools` 的 24 项组成。Week 5、Week 6 与合规目录因存在同名测试模块，分别运行并分别核对退出码，避免 pytest 默认导入模式造成收集冲突。

## 复现命令

```powershell
$env:TEMP='F:\contentretrivalsystem\.tmp'
$env:TMP='F:\contentretrivalsystem\.tmp'
$env:UV_CACHE_DIR='F:\contentretrivalsystem\.tmp\uv-cache'

uv run --project tools/week8 --locked python tools/week8/source_audit.py `
  --output docs/week8/evidence/source-audit/report.json

uv run --project tools/week8 --locked python tools/week8/build_clean_source.py `
  --repository . `
  --destination F:\contentretrivalsystem\.tmp\week8\clean-source
```

产品测试应在干净目录或其一次性验证副本中执行。最终对外 ZIP、平台候选、作品集、演示视频和结项报告必须在最终冻结提交后重新导出并重新计算清单，不能直接把本阶段提交号当作最终发布提交。
