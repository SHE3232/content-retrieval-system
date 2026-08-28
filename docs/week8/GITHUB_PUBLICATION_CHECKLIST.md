# GitHub 公开发布检查表

## 本地冻结

- [ ] 工作树无跟踪或未跟踪改动，`SOURCE_VERSION.txt` 等于 `git rev-parse HEAD`。
- [ ] 公开源码白名单导出通过，两个 Python 项目不引用本机 MobileCLIP 路径。
- [ ] 后端、工具、合规、演示与 Flutter 测试均来自冻结提交的 fresh run。
- [ ] 默认公开资产不含研究权重、用户数据、缓存、数据库、密钥或本机源码副本。
- [ ] Windows/Linux 只在目标平台 Release 构建与归档验证后标记 PASS；macOS 需要真实 Darwin 与 VoiceOver。

## 远程发布

- [ ] 获得目标仓库写入权限并配置 HTTPS remote；仓库名称为 `offline-accessible-multimodal-retrieval`。
- [ ] 推送冻结提交，等待 CI 在 Ubuntu 与 Windows 上通过。
- [ ] 创建指向同一提交的注释标签 `v1.0.0` 并推送。
- [ ] GitHub Release 只上传公开源码、默认公开平台资产和 `SHA256SUMS.txt`；不上传课程研究包。
- [ ] 在未登录浏览器中验证 README、许可证、标签、Release 和每个公开资产可访问。
- [ ] 下载公开资产重新计算 SHA-256，与统一交付清单逐项一致。

没有远程仓库、账号权限或匿名访问证据时，公开发布状态必须为 `BLOCKED`，不得编造 URL、CI 结果或 Release。
