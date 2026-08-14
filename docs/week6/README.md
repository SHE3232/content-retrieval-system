# 第六周执行与证据入口

第六周目标是将解析、嵌入、检索、Flutter UI 和本地运行资源整合为 Windows 完整集成稳定版，并以 G0-G9 十道门禁完成测试、性能、缺陷和离线安全验收。

## 当前状态

`docs/week6/evidence/manifest.json` 初始状态为 `NOT_RUN`。只有严格验证器确认 G0-G9 全部为 `PASS`，四项交付物才可标记为最终版。

## 严格验证

开发阶段允许查看未完成清单：

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  tools/week6/validate_evidence.py docs/week6/evidence --allow-incomplete
```

最终验收不得带 `--allow-incomplete`：

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  tools/week6/validate_evidence.py docs/week6/evidence
```

完整门禁、阈值和正式输出结构见 `docs/superpowers/plans/2026-08-14-week6-system-integration-acceptance.md`。
