# Flutter 桌面工程脚手架重建设计

## 目标

在 `frontend/` 中恢复一个可分析、可测试、可构建且受 Git 版本控制的默认 Flutter 桌面应用工程。项目继续使用已有身份 `content_retrieval_app`，本次不实现检索、索引管理或其他业务 UI。

## 现状

- `frontend/` 当前只保留 `.dart_tool/`、`build/`、`.idea/`、平台临时目录和空的源码目录。
- `pubspec.yaml`、`lib/` 源码、`test/` 测试以及三个桌面平台的正式工程文件均未进入 Git 历史。
- 本机可用 Flutter 3.44.6、Dart 3.12.2。
- 旧工作树表明原项目名为 `content_retrieval_app`，内容是 Flutter 默认计数器模板。

## 方案

在 `frontend/` 目录内使用当前稳定版 Flutter 官方生成器重建工程：

```powershell
flutter create --platforms=windows,macos,linux --project-name content_retrieval_app .
```

选择官方生成器而不复制旧工作树或手工拼装平台文件，以保证 Dart 约束、CMake、Windows Runner、macOS Xcode 工程和 Linux Runner 与当前 SDK 一致。

## 文件范围

纳入 Git 的内容包括：

- `frontend/pubspec.yaml` 与应用级 `pubspec.lock`；
- `frontend/lib/` 默认计数器应用；
- `frontend/test/` 默认 widget 测试；
- `frontend/windows/`、`frontend/macos/`、`frontend/linux/` 的正式工程文件；
- Flutter 标准的 `.metadata`、`.gitignore`、`analysis_options.yaml` 与 `README.md` 等可复现配置。

不纳入 Git 的内容包括 `.dart_tool/`、`build/`、`.idea/`、平台 `ephemeral/`、插件符号链接和编译产物。不会修改 `backend/`、仓库根目录的现有未跟踪输出或业务文档。

## 测试与验收

1. 运行 `flutter pub get`，确认依赖解析成功。
2. 运行 `dart format --output=none --set-exit-if-changed lib test`，确认源码格式稳定。
3. 运行 `flutter analyze`，要求零分析错误。
4. 运行 `flutter test`，要求默认 widget 测试通过。
5. 在当前 Windows 主机运行 `flutter build windows --debug`；macOS 与 Linux 仅验证官方工程文件完整性，因为当前主机不能原生构建这两个平台。
6. 用 `git status`、`git ls-files` 和忽略规则审计，确认要求的文件已进入索引，缓存及产物仍被排除。

本次生产代码与平台配置均由 Flutter 官方生成器生成，属于生成代码/配置场景，不新增需要先写失败测试的手写业务行为；生成的 widget 测试及上述命令共同承担回归验证。

## Git 交付

设计文档和工程重建分别形成提交，便于审阅与回退。实施提交仅包含 `frontend/` 的脚手架文件，不夹带当前工作树中已有的 PDF、`output/` 或 `tmp/` 未跟踪内容。
