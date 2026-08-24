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

只有本生成器生成并拥有的目录才可使用 `--force` 重建。不要对个人资料目录、共享目录或来源不明的非空目录使用该参数。首录分别使用 `rehearsal-01` 和 `recording-01`；重录默认改用新的 `fixtures-02`、`rehearsal-02` 和 `recording-02`，不要删除旧目录。

## 验证材料

先运行专项测试，再运行 `tools/demo` 的全部 unittest：

```powershell
$env:TEMP = 'F:\contentretrieval-demo\temp'
$env:TMP = 'F:\contentretrieval-demo\temp'
$env:UV_CACHE_DIR = 'F:\contentretrieval-demo\uv-cache'
uv run --project tools/demo --locked python -m unittest tools.demo.tests.test_demo_materials -v
uv run --project tools/demo --locked python -m unittest discover -s tools/demo/tests -v
```

## 启动预演实例

先做只读预检，也就是运行 `tools/start-mvp.ps1 -CheckOnly`，再显式传入预演专用 `-DataDir` 启动 MVP：

```powershell
Set-Location F:\contentretrivalsystem
& .\tools\start-mvp.ps1 -CheckOnly -DataDir 'F:\contentretrieval-demo\rehearsal-01'
& .\tools\start-mvp.ps1 -DataDir 'F:\contentretrieval-demo\rehearsal-01'
```

另开一个 PowerShell 窗口确认服务就绪并启动 Flutter：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
Set-Location F:\contentretrivalsystem\frontend
flutter run -d windows
```

在 `rehearsal-01` 中索引 fixtures-01，并严格按[五分钟项目演示成片脚本](./PROJECT_DEMO_VIDEO_SCRIPT.md)完成两遍完整预演。

## 预录离线异常

离线时搜索按钮受服务在线状态门控，因此不要用搜索按钮触发错误。按以下真实可点击路径预录：

1. 按 `Ctrl+3` 到设置，将地址改为 `http://127.0.0.1:65534`，点击“保存设置”。
2. 按 `Ctrl+2` 到索引库，按 `F5` 刷新，保留完整错误“无法连接本地检索服务，请检查服务地址和运行状态。”3 秒。
3. 按 `Ctrl+3` 恢复 `http://127.0.0.1:8000` 并“保存设置”。
4. 按 `Ctrl+2` 回索引库并按 `F5` 验证恢复，最后按 `Ctrl+1` 回到搜索。

## 停止预演并启动正式实例

预演和异常片段完成后，回到启动 MVP 的终端按 `Ctrl+C` 停止预演实例，确认进程退出且 8000 端口已释放。不要删除 `rehearsal-01`，也不要同时运行两个实例。停止预演实例后再预检并启动正式实例；`recording-01` 必须是全新目录，正式录制从空白索引状态开始。

```powershell
Set-Location F:\contentretrivalsystem
& .\tools\start-mvp.ps1 -CheckOnly -DataDir 'F:\contentretrieval-demo\recording-01'
& .\tools\start-mvp.ps1 -DataDir 'F:\contentretrieval-demo\recording-01'
```

正式实例启动后，再次确认就绪：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

此后才开始正式录制，并在 `recording-01` 中重新执行“添加资料文件夹”。重录使用一组同编号的新目录，例如 `rehearsal-02` 与 `recording-02`；不要删除旧目录，也不要让两个实例同时占用 8000 端口。
