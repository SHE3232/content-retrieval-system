# 贡献指南

感谢参与离线可访问多模态内容检索系统。提交应保持离线优先、可访问、可复现，并遵守仓库中的许可证边界。

## 开发环境

后端使用 64 位 Python 3.10 和 `uv`：

```powershell
uv sync --project backend --locked
uv run --project backend python -m pytest backend/tests `
  -m 'not requires_models and not requires_tika and not stress'
```

默认公开依赖不安装 MobileCLIP。只有开展非商业研究验证时，才按照
`docs/week4/MVP_RUNBOOK.md` 单独安装固定源码和准备受限权重。

前端使用仓库支持的 Flutter stable SDK：

```powershell
Set-Location frontend
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
```

## 变更要求

1. 功能或缺陷修复先补充能失败的测试，再实现最小修复。
2. 不提交模型权重、数据集二进制、用户文件、数据库、日志、缓存、虚拟环境、构建目录或密钥。
3. 新增依赖时更新锁文件、`docs/dependency-licenses.csv`、第三方声明和必要的许可证副本。
4. 修改 API、配置、模型清单或发布流程时同步更新对应文档。
5. 保留解释安全边界、兼容性取舍和非显然算法的注释；删除失效注释、死代码和未使用符号。

提交前请运行与变更范围相称的后端测试、Flutter 静态检查和 Flutter 测试。Pull Request 应说明目的、验证命令、结果以及许可证或数据边界影响。
