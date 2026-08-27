# macOS 真实主机发布与 VoiceOver 验收手册

本手册是 macOS 发布门禁，不是“在 Windows 上生成一个同名 ZIP”的替代方案。只有真实 Mac 上的 Release 构建、启动、健康检查、五格式流程和 VoiceOver 人工验收全部通过后，macOS 状态才允许从 `BLOCKED` 改为 `PASS`。

## 1. 前置条件

- Apple Silicon 或 Intel Mac，记录具体机型、`sw_vers` 与 `uname -a`；不得使用模拟器证据。
- 检出最终冻结提交，工作树必须干净；提交号必须是 40 位小写哈希。
- Flutter 3.44.6、Dart 3.12.2、Python 3.10、可再分发 OpenJDK 21、项目锁定依赖均已准备。
- 公开候选只使用 Apache-2.0 文本模型；MobileCLIP 权重仅能在课程非商业研究验证环境中使用，并随附 Apple 研究模型许可证与 SHA-256。
- 在独立空目录准备输出和证据目录，不复用历史构建物。

## 2. 自动化构建与回归

```bash
export REPOSITORY_ROOT=/absolute/path/offline-accessible-multimodal-retrieval
export SOURCE_COMMIT=$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)
export OUTPUT_DIR=/absolute/path/week8-macos-output
export EVIDENCE_DIR=/absolute/path/week8-macos-evidence
export E2E_BASE_URL=http://127.0.0.1:8000

git -C "$REPOSITORY_ROOT" status --porcelain=v1 --untracked-files=all
bash "$REPOSITORY_ROOT/tools/week8/build_macos_release.sh"
```

脚本必须完成后端与工具测试、Flutter analyze/test、`flutter build macos --release --no-pub`、`.app` 归档和 SHA-256。五格式脚本需要一个已经启动、使用完整研究模型的本地 API；运行前设置并记录该服务的地址，确保验证 TXT、PDF、DOCX、JPG、PNG，而不是仅验证前端窗口出现。

## 3. 启动与运行检查

在全新解压目录执行以下项目，并把命令、时间、退出码、日志路径写入最终证据 JSON：

1. 断开非必要网络或设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，确认首次运行不下载模型。
2. 启动打包后的后端与 Tika，确认只终止本次启动的进程。
3. 请求 `/health/live` 与 `/health/ready`，两者均返回成功。
4. 启动 `.app`，完成导入、索引、搜索、复制路径、打开文件。
5. 运行 `tools/week5/run_real_five_format_e2e.py`；要求五个文件全部索引成功，关键词检索命中三种文本格式，图像语义检索正确排序 JPG 与 PNG。
6. 退出应用、停止本次启动的后端/Tika，再次离线重启并重复健康检查。

## 4. VoiceOver 与可访问性人工验收

启动 VoiceOver（Command+F5），逐项完成并截图。每张截图或录屏片段都要记录相对路径与 SHA-256。

- `navigation`：仅用键盘和 VoiceOver 在导入区、搜索框、筛选器、结果列表、分页与设置之间移动，焦点顺序符合视觉顺序。
- `labels`：按钮、输入框、状态、错误、进度和结果项都有明确可读名称；不存在只播报“按钮”或文件内部 ID 的控件。
- `search_results`：播报文件名、类型、匹配原因和可执行操作；结果更新后有状态反馈，不强制抢走用户焦点。
- `high_contrast`：启用“增强对比度”，文本、边框、焦点环和状态图标仍清晰，不能仅依赖颜色表达状态。
- `text_150_percent`：将系统显示/文字放大到至少 150%，无正文截断、按钮遮挡、横向溢出或不可达操作。
- `reduced_motion`：启用“减弱动态效果”，页面切换和加载反馈不依赖大幅动画，功能完整。
- `copy_path`：用 VoiceOver 触发“复制路径”，核对剪贴板内容与目标文件绝对路径一致。
- `open_file`：用 VoiceOver 触发“打开文件”，确认由系统默认应用打开正确文件，并返回检索应用继续操作。

只有八项全部为 `true` 才允许写入最终证据。任何一项失败都应保留 `FAIL` 和复现步骤，不得删掉失败截图后改成通过。

## 5. 最终证据与门禁

在 `$EVIDENCE_DIR` 内准备 `final-evidence.json`，其中应用归档和截图使用相对于证据目录的路径；包含真实 Darwin 主机信息、构建日志、启动/健康/五格式结果、八项 VoiceOver 布尔值及每个文件的 SHA-256。然后执行：

```bash
python3.10 "$REPOSITORY_ROOT/tools/week8/validate_macos_evidence.py" \
  "$EVIDENCE_DIR/final-evidence.json" \
  --expected-commit "$SOURCE_COMMIT"
```

验证器返回 `PASS` 后，才可把归档复制到 `01_平台发布/macOS`，并更新统一交付清单。验证器会拒绝非 Darwin、模拟器、提交不一致、非 Release 构建、缺失归档/哈希、启动/健康/五格式未通过、VoiceOver 未完成和无哈希截图。

## 6. 当前状态

当前 Windows 主机无法生成真实 macOS `.app` 或 VoiceOver 证据，因此 macOS 门禁保持 `BLOCKED`。这不影响继续完善脚本、清单和交接材料，但不能声称 macOS 候选已验证。
