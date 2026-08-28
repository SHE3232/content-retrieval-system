# Changelog

本文件记录面向用户的主要变化。版本提交、平台状态和产物 SHA-256 以最终交付目录中的 `SOURCE_VERSION.txt`、`DELIVERY_MANIFEST.json` 与 `SHA256SUMS.txt` 为准。

## 1.0.0

- 完成本机 TXT、PDF、DOCX、JPEG、PNG 发现、解析、增量索引与检索闭环。
- 提供关键词 BM25、文本语义和加权 RRF；非商业研究配置另提供 MobileCLIP 图文语义。
- 提供 Flutter 搜索、索引库和设置界面，以及键盘、语义、高对比度、文本缩放和减少动态效果支持。
- 增加回环地址、本地模型清单、摘要校验、离线恢复、归档安全和许可证门禁。
- 拆分公开源码、默认公开发行包和课程研究包；公开依赖不再引用未跟踪的本机 MobileCLIP 路径。
- 增加 Windows、Linux 和真实 macOS 主机发布管线、公开 CI、源代码白名单、结项报告和统一交付清单。
