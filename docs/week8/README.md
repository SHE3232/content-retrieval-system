# 第八周结项入口

第八周把前七周成果收束为同一提交、同一事实清单下的公开源码、平台候选、课程研究包、演示视频、作品集和结项文档。任何单项产物都不能脱离 `DELIVERY_MANIFEST.json` 单独声称最终完成。

## 事实来源

- `evidence/manifest.json`：构建前的门禁声明，记录测试、平台、发行类别和待生成产物。
- `output/week8/第八周最终交付/DELIVERY_MANIFEST.json`：最终文件事实，包括字节数和 SHA-256。
- `CLEAN_ENGINEERING_AUDIT.md`：源码清理、白名单和独立目录回归。
- `evidence/source-audit/report.json`：Vulture 2.16 结果和框架回调复核。
- `evidence/platform/`：Windows、Linux、macOS 原始状态与构建证据。
- `validate_rehearsals.py`：要求两轮带时区时间戳、产物哈希和完整操作步骤的真实预演记录。
- `validate_video.py`：用 `ffprobe` 验证五分钟、1080p、30 fps、H.264/AAC 和非零音轨。
- `validate_github_evidence.py`：核验公开仓库、CI、标签、Release、匿名下载与交付哈希。

Windows 构建器要求分别传入公开 Python 运行时与可直接导入 `mobileclip` 的研究 Python 运行时，且两者路径不得相同。验证器同时拒绝公开包内的 MobileCLIP 模块和缺少该模块的研究包，避免只复制权重却无法实际运行。

## 发行边界

公开源码和默认公开发行包不得包含 MobileCLIP 权重。课程演示研究包可以包含已核验权重，但必须同时包含研究许可证、模型卡、模型清单、来源修订和哈希，并明确标记为 `research-only`。研究包不进入默认 GitHub Release 资产列表。

## 完成判定

`verify_delivery.py` 默认允许证据充分的 `BLOCKED` 状态，以便在构建过程中持续审计；正式结项必须增加 `--require-all-platforms`，并同时通过 GitHub 匿名访问、两轮预演、严格五分钟视频、作品集、报告结构与逐页视觉检查。缺少直接证据的门禁不得从 `BLOCKED` 改为 `PASS`。
