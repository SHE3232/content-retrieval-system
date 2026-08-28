# v1.0.0 发布说明

`offline-accessible-multimodal-retrieval` 1.0.0 是八周课程项目的首个可审计发布版本。最终源码提交、平台状态和产物摘要不在本文中手工维护，而由交付目录的 `SOURCE_VERSION.txt`、`DELIVERY_MANIFEST.json` 与 `SHA256SUMS.txt` 生成并交叉验证。

## 主要能力

- 在本机发现、解析和索引 TXT、PDF、DOCX、JPEG、PNG；后端暂不支持 WebP。
- 提供字段加权 BM25、三百八十四维文本语义和加权倒数排名融合。
- 课程非商业研究配置可启用 MobileCLIP-S0 图文语义；默认公开包不会静默下载或包含其权重。
- Windows 课程研究包使用独立研究 Python 运行时；归档验收会直接检查 `mobileclip` 模块，公开运行时明确不得包含该模块。
- Flutter 客户端提供搜索、过滤、索引库管理、复制/打开文件和本地设置。
- 支持键盘操作、语义标签、高对比度、200% 文本缩放和减少动态效果。
- 通过模型清单、来源修订、哈希、锁文件、启动器预检与归档验证保持离线可复现。

## 安装与启动

源码开发环境使用 64 位 Python 3.10 与 uv：

```powershell
uv sync --project backend --locked
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

默认公开发行归档包含所需运行时、文本模型、Tika 和一键启动器，不要求首次运行下载。研究配置的源码与权重准备方法见 `docs/week4/MVP_RUNBOOK.md`。

## 隐私与安全边界

服务只面向本机单用户并绑定 `127.0.0.1`；当前没有身份认证、授权或多租户隔离，不应暴露到局域网或互联网。用户文件、索引和查询留在本机。模型、Tika、运行时和归档必须通过清单与摘要验证。

## 许可证与发行边界

项目自有代码和文档采用 Apache-2.0。第三方代码、模型与数据保持各自许可证。MobileCLIP 源码为 MIT，但预训练权重受 Apple Machine Learning Research Model License 约束，只能进入明确标记的课程研究包；研究包不是通用开源或商业二进制，也不进入公共 GitHub Release 资产。

## 已知限制

- 后端不支持 WebP，任务状态不跨服务重启持久化。
- 默认公开版不提供图片语义；显式请求会返回受控能力不可用错误。
- 检索质量来自有限冻结子集，历史性能基线不代表所有硬件。
- Windows、Linux、macOS、GitHub 与真实五分钟视频分别按直接证据判定；没有指定环境或权限时保持 BLOCKED。
