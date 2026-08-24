# 项目演示材料

本目录提供 Windows 桌面端五分钟项目演示的单一执行入口。开始录制前先通读脚本，再按下方命令生成数据、测试材料并启动专用 MVP 实例。

## 导航

- [五分钟项目演示成片脚本](./PROJECT_DEMO_VIDEO_SCRIPT.md)
- [演示数据生成器](../../tools/demo/generate_demo_data.py)
- [演示材料契约测试](../../tools/demo/tests/test_demo_materials.py)

## 首次生成

在仓库根目录打开 Windows PowerShell。命令使用 `tools/demo/uv.lock` 中的锁定依赖；不需要另外安装包。输出目录必须是新的或空的。

```powershell
Set-Location F:\contentretrivalsystem
New-Item -ItemType Directory -Force F:\contentretrieval-demo\temp | Out-Null
$env:TEMP = 'F:\contentretrieval-demo\temp'
$env:TMP = 'F:\contentretrieval-demo\temp'
$env:UV_CACHE_DIR = 'F:\contentretrieval-demo\uv-cache'
uv run --project tools/demo --locked python tools/demo/generate_demo_data.py F:\contentretrieval-demo\fixtures-01
```

## 安全重建

只有本生成器生成并拥有的目录才可使用 `--force` 重建。不要对个人资料目录、共享目录或来源不明的非空目录使用该参数。重录默认改用新的 `fixtures-02` 和 `recording-02`，不要删除旧目录。

## 验证材料

先运行专项测试，再运行 `tools/demo` 的全部 unittest：

```powershell
$env:TEMP = 'F:\contentretrieval-demo\temp'
$env:TMP = 'F:\contentretrieval-demo\temp'
$env:UV_CACHE_DIR = 'F:\contentretrieval-demo\uv-cache'
uv run --project tools/demo --locked python -m unittest tools.demo.tests.test_demo_materials -v
uv run --project tools/demo --locked python -m unittest discover -s tools/demo/tests -v
```

## 启动录制实例

先做只读预检，也就是运行 `tools/start-mvp.ps1 -CheckOnly`，再显式传入录制专用 `-DataDir` 启动 MVP。以下命令使用 `recording-01`；重录时将两处都改为 `recording-02`。

```powershell
Set-Location F:\contentretrivalsystem
& .\tools\start-mvp.ps1 -CheckOnly -DataDir 'F:\contentretrieval-demo\recording-01'
& .\tools\start-mvp.ps1 -DataDir 'F:\contentretrieval-demo\recording-01'
```

另开一个 PowerShell 窗口确认服务就绪并启动 Flutter：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
Set-Location F:\contentretrivalsystem\frontend
flutter run -d windows
```

随后严格按[五分钟项目演示成片脚本](./PROJECT_DEMO_VIDEO_SCRIPT.md)完成两遍预演、异常片段预录和正式录制。异常片段结束后，务必将 Flutter 设置中的服务地址恢复为 `http://127.0.0.1:8000` 并保存。
