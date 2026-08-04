# 离线 FastAPI MVP 运行手册

本手册用于在 Windows 本机运行第四周检索 MVP。资源准备完成后，系统在无网络条件下完成
TXT、PDF、DOCX、JPG、PNG 批量解析、真实文本/图片嵌入、Chroma 持久化、关键词与
向量混合检索、排序过滤和 JSON 返回。

本次交付只包含后端。Flutter UI、键盘导航、屏幕阅读器、高对比度和动态字体缩放属于
第五周范围。

## 运行边界

- 正常服务只监听 `127.0.0.1`，默认端口为 `8000`。
- 启动时不联网、不下载资源，也不在资源缺失时退回伪嵌入。
- 文本推理使用 Sentence Transformers Python 适配器；图片与图文查询使用 PyTorch
  MobileCLIP Python 适配器。当前服务运行时不是 TensorFlow Lite。
- DOCX 解析依赖本机 Apache Tika 3.3.1，默认地址为
  `http://127.0.0.1:9998`。
- 默认 Chroma 数据目录为 `data/mvp/`。重新启动不会清空索引。
- 索引请求必须同时声明 `paths` 和 `authorized_roots`。服务只处理授权根目录内的路径。

## 1. 一次性准备运行资源

以下命令均从仓库根目录运行。准备阶段需要网络，只执行一次；后续预检、启动、索引和
检索不需要网络。

先确认本机具备 PowerShell、`uv`、Java，以及可供 `uv` 使用的 64 位 Python 3.10：

```powershell
uv --version
java -version
```

### 1.1 恢复固定版本的 MobileCLIP 源码

后端锁定 Apple MobileCLIP 源码提交
`aecfb5453d022e9deff12f81a150ea8f35194baa`。解压后的目录名与
`backend/pyproject.toml` 和 `model-tools/pyproject.toml` 中的本地依赖一致。

```powershell
New-Item -ItemType Directory -Force `
  -Path 'third_party/mobileclip-src' | Out-Null

Invoke-WebRequest `
  -Uri 'https://github.com/apple/ml-mobileclip/archive/aecfb5453d022e9deff12f81a150ea8f35194baa.zip' `
  -OutFile 'third_party/ml-mobileclip-aecfb545.zip' `
  -UseBasicParsing

Expand-Archive `
  -LiteralPath 'third_party/ml-mobileclip-aecfb545.zip' `
  -DestinationPath 'third_party/mobileclip-src' `
  -Force

$mobileClipSource = `
  'third_party/mobileclip-src/ml-mobileclip-aecfb5453d022e9deff12f81a150ea8f35194baa'
if (-not (Test-Path -LiteralPath "$mobileClipSource/pyproject.toml" -PathType Leaf)) {
  throw '固定版本的 MobileCLIP 源码未正确解压'
}
```

### 1.2 同步锁定的 Python 依赖

```powershell
uv sync --project backend --locked
```

该命令应生成 `backend/.venv/Scripts/python.exe`。启动器要求解释器版本严格为 Python
3.10，并验证 `uvicorn` 可以导入。

### 1.3 下载固定 revision 的文本模型

文本模型为
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，固定 revision 为
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`。下载脚本会离线加载一次模型、计算目录
SHA-256，并写入 `models/model-manifest.json`。

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  'model-tools/download_models.py' `
  --revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42
```

### 1.4 下载并校验固定 MobileCLIP-S0 权重

脚本内固定 Hugging Face revision
`71aa3e13dda93115871afbd017336535ba29886c`，并要求权重 SHA-256 为
`809b408eff74f8058843e86a1f92967097d42ba782450e85b8f4867b7f0ca0b7`。成功后，它会
在同一清单中写入 `mobileclip-s0-v1`。

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  'model-tools/download_mobileclip.py'
```

### 1.5 下载 Apache Tika 3.3.1

```powershell
Invoke-WebRequest `
  -Uri 'https://archive.apache.org/dist/tika/3.3.1/tika-server-standard-3.3.1.jar' `
  -OutFile 'tools/tika/tika-server-standard-3.3.1.jar' `
  -UseBasicParsing
```

仓库内的 `tools/tika/tika-server-standard-3.3.1.jar.sha512` 固定期望摘要为：

```text
2ca66e2445f8463aefad6a6396725cdb64eb23f94d3948a295daf83bba2b5c3bd51b6e29cc52cf6dce8a71948d6a8431dc39efc56500f9bfe30fdbe0a3ee1d48
```

启动器使用 .NET SHA-512 实现核对 JAR；摘要不匹配时不会启动服务。单独运行 Tika 的
方法见 [Tika 本地测试服务说明](../../tools/tika/README.md)。

### 1.6 执行完整预检

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -CheckOnly
```

成功输出为：

```text
MVP preflight passed
```

`-CheckOnly` 会验证 Python 3.10、Java、Uvicorn、模型目录、模型清单中的两个模型 ID 与
SHA-256、Tika JAR 与 SHA-512、API 端口和数据目录写权限；它不会启动 Tika 或 FastAPI。

### 1.7 生成受控五格式样本

在调用任何 API 前，从仓库根目录运行以下命令。命令只创建全新的 `mvp-input/`；如果
目录已经存在，会立即停止，不删除或覆盖其中的用户数据。样本内容固定，并覆盖后续三条
默认查询。

```powershell
$sampleRoot = [System.IO.Path]::GetFullPath('mvp-input')
if (Test-Path -LiteralPath $sampleRoot) {
  throw "受控输入目录已存在，拒绝覆盖：$sampleRoot"
}

$sampleGenerator = @'
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image, ImageDraw


root = Path(sys.argv[1])
if root.exists():
    raise SystemExit(f"refusing to overwrite existing input root: {root}")
root.mkdir(parents=False)

keyword_query = "没有互联网连接"
text_query = "offline system for searching private documents"
image_query = "a blue geometric logo on a white rounded square"

(root / "offline-notes.txt").write_text(
    (
        f"{keyword_query}时，仍可在本机检索私人文档。\n"
        f"{text_query}\n{image_query}\n"
    ),
    encoding="utf-8",
)


def write_pdf(path: Path, text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 14 Tf\n72 720 Td\n({escaped}) Tj\nET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(payload)


write_pdf(root / "private-search.pdf", text_query)


def write_zip_text(archive: ZipFile, name: str, text: str) -> None:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, text.encode("utf-8"))


with ZipFile(root / "local-guide.docx", "w") as archive:
    write_zip_text(
        archive,
        "[Content_Types].xml",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
    )
    write_zip_text(
        archive,
        "_rels/.rels",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
    )
    write_zip_text(
        archive,
        "word/document.xml",
        f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{keyword_query}；{text_query}；{image_query}</w:t></w:r></w:p><w:sectPr/></w:body>
</w:document>""",
    )


def write_logo(path: Path, image_format: str) -> None:
    image = Image.new("RGB", (256, 256), (232, 238, 248))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (24, 24, 232, 232),
        radius=36,
        fill=(255, 255, 255),
        outline=(37, 99, 235),
        width=5,
    )
    draw.polygon(
        ((128, 58), (198, 128), (128, 198), (58, 128)),
        fill=(37, 99, 235),
    )
    draw.ellipse((105, 105, 151, 151), fill=(255, 255, 255))
    if image_format == "JPEG":
        image.save(path, format=image_format, quality=95, subsampling=0, optimize=False)
    else:
        image.save(path, format=image_format, optimize=False)


write_logo(root / "blue-logo.jpg", "JPEG")
write_logo(root / "blue-logo.png", "PNG")

expected = {".txt", ".pdf", ".docx", ".jpg", ".png"}
actual = {path.suffix.lower() for path in root.iterdir() if path.is_file()}
if actual != expected or len(list(root.iterdir())) != 5:
    raise SystemExit(f"unexpected generated files: {sorted(actual)}")
with ZipFile(root / "local-guide.docx") as archive:
    if archive.testzip() is not None or "word/document.xml" not in archive.namelist():
        raise SystemExit("generated DOCX package is invalid")
for name in ("blue-logo.jpg", "blue-logo.png"):
    with Image.open(root / name) as image:
        image.verify()
print(f"created five controlled files in {root}")
'@

$sampleGeneratorBase64 = [System.Convert]::ToBase64String(
  [System.Text.Encoding]::UTF8.GetBytes($sampleGenerator)
)
$pythonBootstrap = `
  "import base64,sys;source=sys.argv.pop(1);exec(compile(base64.b64decode(source),'<mvp-fixture-generator>','exec'))"
& '.\backend\.venv\Scripts\python.exe' `
  -c $pythonBootstrap `
  $sampleGeneratorBase64 `
  $sampleRoot
if ($LASTEXITCODE -ne 0) {
  throw '五格式受控样本生成失败'
}
```

生成结果固定为 `offline-notes.txt`、`private-search.pdf`、`local-guide.docx`、
`blue-logo.jpg` 和 `blue-logo.png`。PDF 是含可提取英文文本的有效 PDF 1.4；DOCX 是
包含内容类型、包关系和主文档的最小 Open XML 包。Base64 只负责把 UTF-8 Python 源码
安全穿过 Windows PowerShell 5.1 的原生命令参数边界，不写入临时 `.py` 文件。

## 2. 一键启动

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1
```

启动器先复用 `127.0.0.1:9998` 上健康的 Tika；若不存在，则从已校验的本地 JAR 启动
隐藏子进程。随后它设置 `HF_HUB_OFFLINE=1` 和 `TRANSFORMERS_OFFLINE=1`，加载两个
真实模型与 `data/mvp/` 中的 Chroma 索引，并启动 Uvicorn。

启动后访问：

- OpenAPI：<http://127.0.0.1:8000/docs>
- 存活检查：<http://127.0.0.1:8000/health/live>
- 就绪检查：<http://127.0.0.1:8000/health/ready>

存活响应为 `{"status":"ok"}`；模型、Chroma 与 Tika 均可用时，就绪响应为
`{"status":"ready"}`。

### 启动参数参考

所有相对路径都基于仓库根目录解析，不受当前 PowerShell 工作目录影响。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `-PythonExecutable` | `backend/.venv/Scripts/python.exe` | 严格使用 Python 3.10 的后端解释器 |
| `-JavaExecutable` | `PATH` 中的 `java` | 启动或检查本地 Tika |
| `-ModelRoot` | `models` | 两个本地模型的根目录 |
| `-ManifestPath` | `models/model-manifest.json` | 模型 ID、空间、维度和摘要清单 |
| `-DataDir` | `data/mvp` | Chroma 持久化目录 |
| `-TikaJar` | `tools/tika/tika-server-standard-3.3.1.jar` | Tika 3.3.1 JAR |
| `-TikaChecksumFile` | `tools/tika/tika-server-standard-3.3.1.jar.sha512` | JAR 的 SHA-512 |
| `-Port` | `8000` | 本机 FastAPI 端口，允许范围为 1–65535 |
| `-CheckOnly` | 关闭 | 只预检，不启动进程 |

例如，端口 `8000` 被占用时改用：

```powershell
powershell -ExecutionPolicy Bypass -File tools/start-mvp.ps1 -Port 8001
```

此时后续命令中的基础地址应改为 `http://127.0.0.1:8001`，烟测命令还需增加
`--base-url http://127.0.0.1:8001`。

## 3. 调用索引与检索 API

保持启动终端运行，在第二个 PowerShell 终端从仓库根目录执行本节命令。

### 3.1 定义 JSON 请求助手

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$inputRoot = (Resolve-Path -LiteralPath 'mvp-input').Path

function Invoke-MvpPost {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [hashtable]$Payload
  )

  $json = $Payload | ConvertTo-Json -Depth 10 -Compress
  Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl$Path" `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) `
    -TimeoutSec 30
}
```

### 3.2 提交批量索引任务并轮询

`authorized_roots` 是允许访问的根目录。示例将它限制为与输入目录相同的绝对路径，
并递归处理目录。

```powershell
$createdJob = Invoke-MvpPost `
  -Path '/v1/indexing/jobs' `
  -Payload @{
    paths = @($inputRoot)
    authorized_roots = @($inputRoot)
    recursive = $true
  }

$createdJob | ConvertTo-Json -Depth 10

$pollDeadline = [System.DateTime]::UtcNow.AddSeconds(180)
do {
  if ([System.DateTime]::UtcNow -ge $pollDeadline) {
    throw "索引任务在 180 秒内未完成，job_id=$($createdJob.job_id)"
  }
  $jobState = Invoke-RestMethod `
    -Method Get `
    -Uri "$baseUrl/v1/indexing/jobs/$($createdJob.job_id)" `
    -TimeoutSec 10
  if ($jobState.status -in @('queued', 'running')) {
    Start-Sleep -Milliseconds 250
  }
} while ($jobState.status -in @('queued', 'running'))

$jobState | ConvertTo-Json -Depth 10
if ($jobState.status -ne 'completed') {
  throw "索引任务未完整成功：$($jobState.status)"
}
```

返回结果应满足 `result.failed_files=0`、`result.partial_files=0` 和
`result.skipped_files=0`。重复索引未变化文件时，`result.unchanged_files` 会增加，既有
Chroma 记录不会被重复插入。

### 3.3 查看索引统计

```powershell
$stats = Invoke-RestMethod -Method Get -Uri "$baseUrl/v1/index/stats"
$stats | ConvertTo-Json -Depth 10
```

### 3.4 普通文本语义检索

```powershell
$textSearch = Invoke-MvpPost `
  -Path '/v1/search' `
  -Payload @{
    query = 'offline system for searching private documents'
    top_k = 5
    channels = @('text_semantic')
  }

$textSearch | ConvertTo-Json -Depth 10
```

### 3.5 关键词检索

```powershell
$keywordSearch = Invoke-MvpPost `
  -Path '/v1/search' `
  -Payload @{
    query = '没有互联网连接'
    top_k = 5
    channels = @('keyword')
  }

$keywordSearch | ConvertTo-Json -Depth 10
```

### 3.6 三通道混合检索与排序权重

```powershell
$hybridSearch = Invoke-MvpPost `
  -Path '/v1/search' `
  -Payload @{
    query = 'offline system for searching private documents'
    top_k = 5
    channels = @('keyword', 'text_semantic', 'image_semantic')
    weights = @{
      keyword = 0.35
      text_semantic = 1.0
      image_semantic = 0.85
    }
  }

$hybridSearch | ConvertTo-Json -Depth 10
```

`hits` 已按融合得分排序；每项命中的 `match_reasons` 说明参与排名的检索通道。
`top_k` 允许 1–100，所有权重必须为正数。

### 3.7 图片模态过滤检索

```powershell
$filteredImageSearch = Invoke-MvpPost `
  -Path '/v1/search' `
  -Payload @{
    query = 'a blue geometric logo on a white rounded square'
    top_k = 5
    channels = @('image_semantic')
    filters = @{
      modalities = @('image')
    }
  }

$filteredImageSearch | ConvertTo-Json -Depth 10
if ($filteredImageSearch.hits.modality -contains 'text') {
  throw '图片模态过滤未生效'
}
```

过滤器还支持 `mime_types`、`path_prefix`、`modified_after` 和 `modified_before`。

## 4. 五格式真实 HTTP 烟测

### 4.1 核对受控输入与 Git 边界

使用 1.7 生成的 `mvp-input/`。它恰好包含五个文件、每种支持扩展名各一个，目录及其
子目录没有符号链接或 Windows 重解析点。不要向该目录混入其他文件；烟测会递归检查
五种扩展名，并要求所有文件均被完整处理，没有失败、部分成功或跳过项。

`mvp-input/` 是本机输入，不属于提交内容。`models/*`、`data/*`、MobileCLIP 源码、Tika
JAR 和虚拟环境也只保留在本机。提交前运行以下命令确认模型、数据库和输入文件均未被
Git 跟踪：

```powershell
git ls-files -- models data mvp-input tools/tika backend/.venv
git status --short -- models data mvp-input tools/tika backend/.venv
```

第一条不应显示模型权重、数据库、`mvp-input`、JAR 或虚拟环境。第二条若显示
`mvp-input/`，不要暂存或提交它。

### 4.2 用全新专用数据目录首次启动

先停止用于手工 API 演示的服务。在启动终端从仓库根目录运行以下命令。专用目录
`data/mvp-http-smoke/` 必须尚不存在；命令发现任何同名文件或目录时会停止，不会删除
既有数据。

```powershell
$smokeDataDir = [System.IO.Path]::GetFullPath('data/mvp-http-smoke')
if (Test-Path -LiteralPath $smokeDataDir) {
  throw "烟测数据路径已经存在；为保护既有数据，拒绝复用：$smokeDataDir"
}

powershell -ExecutionPolicy Bypass `
  -File tools/start-mvp.ps1 `
  -DataDir $smokeDataDir
```

此流程始终使用默认端口 `8000`。若必须改端口，应在首次与重启两条启动命令中使用相同
`-Port`，并在两条烟测命令中使用相同的 `--base-url`。

### 4.3 保存并断言首次烟测结果

服务启动后，在第二个 PowerShell 终端运行：

```powershell
$firstEvidence = [System.IO.Path]::GetFullPath(
  'data/mvp-http-smoke-evidence/first-pass-summary.json'
)
if (Test-Path -LiteralPath $firstEvidence) {
  throw "首次烟测证据已经存在，拒绝覆盖：$firstEvidence"
}

& '.\backend\.venv\Scripts\python.exe' `
  'backend/tools/smoke_mvp.py' `
  --input-root mvp-input `
  --keyword-query '没有互联网连接' `
  --text-query 'offline system for searching private documents' `
  --image-query 'a blue geometric logo on a white rounded square' `
  --output $firstEvidence
if ($LASTEXITCODE -ne 0) {
  throw '首次 MVP HTTP 烟测失败'
}

$first = Get-Content -Raw -LiteralPath $firstEvidence | ConvertFrom-Json
if ($first.status -ne 'passed') { throw '首次烟测状态不是 passed' }
if ($first.pre_index_record_count -ne 0) {
  throw '首次烟测没有从空索引开始'
}
if ($first.expected_input_file_count -ne 5) {
  throw '首次烟测没有使用恰好五个受控输入文件'
}
if ($first.indexing.failed_files -ne 0) {
  throw '首次烟测存在索引失败文件'
}
if ($first.indexing.indexed_files -ne $first.expected_input_file_count) {
  throw '首次烟测没有把全部受控文件写入新索引'
}
if ($first.indexing.unchanged_files -ne 0) {
  throw '全新索引的首次烟测不应出现 unchanged_files'
}
if ($first.stats.record_count -le 0) {
  throw '首次烟测完成后索引仍为空'
}

$firstRecordCount = [int]$first.stats.record_count
$controlledInputCount = [int]$first.expected_input_file_count
```

脚本依次检查索引前统计、索引提交与轮询、关键词、文本语义、图片语义、三通道混合检索、
图片模态过滤和索引后统计。只有所有检查通过时才以 UTF-8 原子写入证据文件。

首次结果保存在被 Git 忽略的 `data/mvp-http-smoke-evidence/`，不会被第二轮覆盖。预期
JSON 包含 `status="passed"`、五种 `formats`、`indexing.failed_files=0`、五项
`searches[*].passed=true`，且 `persistent_restart.required=false`。

### 4.4 使用同一绝对数据目录重启

1. 在启动终端按 `Ctrl+C`，等待后台索引结束且运行时关闭。
2. 在同一启动终端运行以下命令。它只检查目录存在且含持久化文件，不会删除或清空它。

```powershell
$smokeDataDir = [System.IO.Path]::GetFullPath('data/mvp-http-smoke')
if (-not (Test-Path -LiteralPath $smokeDataDir -PathType Container)) {
  throw "首次烟测数据目录不存在：$smokeDataDir"
}
if ($null -eq (Get-ChildItem -LiteralPath $smokeDataDir -Force | Select-Object -First 1)) {
  throw "首次烟测数据目录为空：$smokeDataDir"
}

powershell -ExecutionPolicy Bypass `
  -File tools/start-mvp.ps1 `
  -DataDir $smokeDataDir
```

### 4.5 生成最终重启持久化证据

保持第二个 PowerShell 终端不关闭，以保留 `$firstRecordCount` 和
`$controlledInputCount`。服务重启就绪后运行：

```powershell
$restartEvidence = [System.IO.Path]::GetFullPath(
  'data/mvp-http-smoke-evidence/restart-pass-summary.json'
)
if (Test-Path -LiteralPath $restartEvidence) {
  throw "重启烟测证据已经存在，拒绝覆盖：$restartEvidence"
}

& '.\backend\.venv\Scripts\python.exe' `
  'backend/tools/smoke_mvp.py' `
  --input-root mvp-input `
  --keyword-query '没有互联网连接' `
  --text-query 'offline system for searching private documents' `
  --image-query 'a blue geometric logo on a white rounded square' `
  --require-existing-index `
  --output $restartEvidence
if ($LASTEXITCODE -ne 0) {
  throw '重启后的 MVP HTTP 烟测失败'
}

$second = Get-Content -Raw -LiteralPath $restartEvidence | ConvertFrom-Json
if ($second.status -ne 'passed') { throw '重启烟测状态不是 passed' }
if ($second.pre_index_record_count -ne $firstRecordCount) {
  throw '重启前记录数与首次烟测完成后的记录数不一致'
}
if ($second.indexing.failed_files -ne 0) {
  throw '重启烟测存在索引失败文件'
}
if ($second.indexing.indexed_files -ne 0) {
  throw '未变化文件在重启烟测中不应重新写入'
}
if ($second.indexing.unchanged_files -ne $controlledInputCount) {
  throw '重启烟测没有把全部受控输入识别为 unchanged'
}
if (-not $second.persistent_restart.required) {
  throw '重启烟测没有启用持久化前置条件'
}
if (-not $second.persistent_restart.passed) {
  throw '重启持久化检查未通过'
}

$finalEvidence = [System.IO.Path]::GetFullPath(
  'docs/week4/evidence/mvp-api-smoke-summary.json'
)
$finalEvidenceDirectory = Split-Path -Parent $finalEvidence
New-Item -ItemType Directory -Force -Path $finalEvidenceDirectory | Out-Null
$finalEvidenceTemporary = Join-Path $finalEvidenceDirectory (
  '.mvp-api-smoke-summary.' + [guid]::NewGuid().ToString('N') + '.tmp'
)
$finalEvidenceBackup = Join-Path $finalEvidenceDirectory (
  '.mvp-api-smoke-summary.' + [guid]::NewGuid().ToString('N') + '.bak'
)
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
try {
  $finalJson = $second | ConvertTo-Json -Depth 20
  [System.IO.File]::WriteAllText(
    $finalEvidenceTemporary,
    $finalJson + "`n",
    $utf8WithoutBom
  )
  if ([System.IO.File]::Exists($finalEvidence)) {
    [System.IO.File]::Replace(
      $finalEvidenceTemporary,
      $finalEvidence,
      $finalEvidenceBackup
    )
  } else {
    [System.IO.File]::Move($finalEvidenceTemporary, $finalEvidence)
  }
} finally {
  if ([System.IO.File]::Exists($finalEvidenceTemporary)) {
    [System.IO.File]::Delete($finalEvidenceTemporary)
  }
  if ([System.IO.File]::Exists($finalEvidenceBackup)) {
    [System.IO.File]::Delete($finalEvidenceBackup)
  }
}
```

第二轮会再次提交相同目录，但增量索引应报告 `indexed_files=0`、
`unchanged_files=5`。最终证据同时证明重启前已有记录、记录数与首轮完成值一致，以及
持久化检查通过。重启烟测先写入被 Git 忽略的本地 JSON；只有所有跨轮断言通过后，才在
同一目录内原子生成或替换正式证据。失败不会留下本轮的伪通过证据，首轮与重启上下文也
始终保留在两个单独的本地 JSON 中。

`docs/week4/evidence/mvp-api-smoke-summary.json` 由上述两轮真实烟测生成，本任务不提供
预制结果。最终证据将在第四周提交级验证阶段产生。

## 5. 安全退出与进程所有权

在启动终端按 `Ctrl+C` 退出。若仍有索引任务运行，应用会先等待后台索引工作安全结束，
再关闭 Chroma，避免并发关闭破坏索引。

启动器只停止自己本次创建的 Tika 子进程：

- 如果启动前已有健康 Tika，启动器复用它，退出时不会终止它；
- 如果启动器自己创建了 Tika，退出或启动失败时会终止该进程并等待最多 5 秒；
- 启动器不会按名称批量结束其他 Java 进程。

## 6. 故障排查

| 稳定错误或现象 | 处理动作 |
|---|---|
| `Python executable not found` | 运行 `uv sync --project backend --locked`，确认 `backend/.venv/Scripts/python.exe` 存在。 |
| `Python 3.10 is required` | 为 `uv` 配置 64 位 Python 3.10 后重新同步；不要使用 3.11 或 3.12。 |
| `Uvicorn import failed` | 重新执行锁定依赖同步，且不要用只有测试依赖的临时虚拟环境。 |
| `Java runtime check failed` | 安装可运行的 Java，并确保 `java -version` 成功；或通过 `-JavaExecutable` 指定绝对路径。 |
| `Model root directory not found` | 重新执行两个模型下载脚本，或用 `-ModelRoot` 指向实际目录。 |
| `Model manifest not found` | 重新执行两个模型下载脚本，确认它们共同写入 `models/model-manifest.json`。 |
| `Model manifest verification failed:` | 阅读冒号后的异常详情；补齐缺失模型 ID，或重新下载摘要不匹配的文本模型/MobileCLIP 权重。 |
| `Tika server JAR not found` | 按本手册 1.5 或 [Tika 说明](../../tools/tika/README.md) 下载 3.3.1 JAR。 |
| `Tika server JAR SHA-512 mismatch` | 删除错误 JAR，重新从 Apache 官方归档下载；不要修改仓库摘要文件。 |
| `MVP API port is already in use` | 使用 `-Port 8001`，并同步修改 API 地址和烟测 `--base-url`。 |
| `Tika server exited before becoming ready` | 按下方命令在前台启动同一个 JAR，直接读取 Java/Tika 错误。 |
| `Tika server did not become ready within 30 seconds` | 确认 `http://127.0.0.1:9998/version` 返回包含 `Apache Tika`，并排除代理或防火墙干扰。 |
| `{"status":"not_ready"}` | 检查 Tika、模型/清单摘要和 `data/mvp/` 写权限；查看启动终端中的首个异常。 |
| `Tika dependency is not ready at` | Tika 在 FastAPI 生命周期启动时不可用；先恢复 9998 服务，再重启 MVP。 |
| 烟测报 `input root is missing formats` | 为列出的缺失扩展名补充真实文件，五种格式必须全部存在。 |
| 烟测报 `no records existed before indexing after restart` | 复用首次烟测的同一 `data/mvp-http-smoke/`，确认首次索引成功后再带 `--require-existing-index` 重跑。 |

排查 Tika 早退时，先确认 9998 没有监听者，再在单独终端以前台方式运行精确的启动命令：

```powershell
$existingTikaPort = Get-NetTCPConnection `
  -LocalPort 9998 `
  -State Listen `
  -ErrorAction SilentlyContinue
if ($null -ne $existingTikaPort) {
  throw '9998 端口已被占用；先识别并安全停止该监听者'
}

java -jar tools/tika/tika-server-standard-3.3.1.jar -p 9998
```

观察前台错误；若服务成功启动，可访问 `http://127.0.0.1:9998/version`。检查完成后在该
终端按 `Ctrl+C` 停止，不要用进程名批量结束 Java。

就绪检查使用直连本机、禁用系统代理。若浏览器能打开但检查仍失败，优先核对实际
`/version` 响应内容，而不是只确认 9998 端口处于监听状态。

## 7. 交付与已知差距

- [端到端功能测试报告](reports/端到端功能测试报告.docx)
- [检索准确率基准报告](reports/检索准确率基准报告.docx)
- [MVP HTTP 烟测证据](evidence/mvp-api-smoke-summary.json)：完成首次与重启烟测后生成
- [第四周交付入口](README.md)

本 MVP 使用现有真实 Python 推理适配器，不宣称服务运行时已经迁移到 TensorFlow Lite。
仓库中的 TFLite 转换产物仍用于一致性验证。Flutter UI 与无障碍验收属于第五周，未纳入
本次后端运行、烟测或报告结论。
