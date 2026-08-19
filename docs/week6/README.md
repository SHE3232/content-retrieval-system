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

## 轻量稳定包构建与验收约定

原有 `01_Windows完整集成稳定版.zip` 必须保留，作为完整集成稳定版的权威交付物；轻量流程不得覆盖或改写它。新增轻量交付物的文件名必须精确为 `01_Windows轻量集成稳定版.zip`。本节是构建与验收约定，不表示该 ZIP 已经生成或已经通过验收。

轻量包的严格体积门禁为十进制字节数 `< 1,000,000,000`，不能用 `< 1 GiB` 代替。包内仍须嵌入 `text-multilingual-v1` 与 `mobileclip-s0-v1`，不允许首次运行下载模型，断网运行能力保持不变。轻量化按策略裁剪 Python 运行时中评测、开发、缓存、静态链接等非运行必需内容；Tika JAR 及其校验文件必须保留，不得作为轻量化对象删除。轻量化使用 `jlink` Java 运行时，但不改变检索、模型或数据格式。`PACKAGE_MANIFEST.json` 必须记录应用源码提交；当前真实候选包应从 `b8180477ade5829f551e2c55922a54500f142c1e` 构建。

候选包生成后，可在只读副本中执行以下 PowerShell 检查（将 `$zip` 改为实际路径）；检查失败即不得标记为通过：

```powershell
$zip = '.\01_Windows轻量集成稳定版.zip'
$f = Get-Item -LiteralPath $zip
if ($f.Length -ge 1000000000) { throw "ZIP exceeds strict decimal limit: $($f.Length) bytes" }
Get-FileHash -LiteralPath $zip -Algorithm SHA256

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($f.FullName)
try {
    $entry = @($archive.Entries | Where-Object { $_.FullName -eq 'app/PACKAGE_MANIFEST.json' })
    if ($entry.Count -ne 1) { throw "Expected exactly one app/PACKAGE_MANIFEST.json entry" }
    $stream = $entry[0].Open()
    $reader = New-Object -TypeName System.IO.StreamReader -ArgumentList $stream
    try { $manifest = ( $reader.ReadToEnd() | ConvertFrom-Json ) }
    finally { $reader.Dispose() }
}
finally { $archive.Dispose() }

if ($manifest.package_profile -ne 'lightweight') { throw 'Unexpected package_profile' }
if ($manifest.archive_size_limit_bytes -ne 1000000000) { throw 'Unexpected archive_size_limit_bytes' }
if ($manifest.java_runtime_mode -ne 'jlink') { throw 'Unexpected java_runtime_mode' }
if ($manifest.source_commit -ne 'b8180477ade5829f551e2c55922a54500f142c1e') { throw 'Unexpected source_commit' }
if ($manifest.first_run_downloads -ne $false) { throw 'first_run_downloads must be false' }
```
