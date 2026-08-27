# 平台证据规则

每个平台目录至少保存状态 JSON、构建日志、工具版本、产物哈希、启动日志、健康检查、五格式端到端结果和独立解压复核。`PASS` 必须引用真实文件；`FAIL` 与 `BLOCKED` 必须保留原因。

- Windows：在当前 Windows 主机完成 Release 构建、一键启动、离线恢复和五格式验证。
- Linux：在 Ubuntu 24.04 WSL 或真实 Linux 完成 Release 构建、启动和核心流程验证。
- macOS：只能由真实 Mac 的 Release 构建、启动、五格式流程及 VoiceOver 人工验收转为 PASS；Windows 生成的占位 ZIP 无效。

