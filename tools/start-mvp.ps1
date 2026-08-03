param(
    [string]$PythonExecutable = "",
    [string]$JavaExecutable = "",
    [string]$ModelRoot = "models",
    [string]$ManifestPath = "models/model-manifest.json",
    [string]$DataDir = "data/mvp",
    [string]$TikaJar = "tools/tika/tika-server-standard-3.3.1.jar",
    [string]$TikaChecksumFile = "tools/tika/tika-server-standard-3.3.1.jar.sha512",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Add-Type -AssemblyName System.Net.Http

function Resolve-RepositoryPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $Path))
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TcpPort
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connectTask = $client.ConnectAsync("127.0.0.1", $TcpPort)
        return $connectTask.Wait(250) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-TikaReady {
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [System.TimeSpan]::FromSeconds(1)
    $response = $null
    try {
        $response = $client.GetAsync("http://127.0.0.1:9998/version").GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            return $false
        }
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return $body.Contains("Apache Tika")
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $response) {
            $response.Dispose()
        }
        $client.Dispose()
        $handler.Dispose()
    }
}

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = "backend/.venv/Scripts/python.exe"
}
$pythonPath = Resolve-RepositoryPath $PythonExecutable

if ([string]::IsNullOrWhiteSpace($JavaExecutable)) {
    $javaCommand = Get-Command java -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $javaPath = [System.IO.Path]::GetFullPath($javaCommand.Source)
}
else {
    $javaPath = Resolve-RepositoryPath $JavaExecutable
}

$modelRootPath = Resolve-RepositoryPath $ModelRoot
$manifestPathResolved = Resolve-RepositoryPath $ManifestPath
$dataDirPath = Resolve-RepositoryPath $DataDir
$tikaJarPath = Resolve-RepositoryPath $TikaJar
$tikaChecksumPath = Resolve-RepositoryPath $TikaChecksumFile

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python executable not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath $javaPath -PathType Leaf)) {
    throw "Java executable not found: $javaPath"
}
if (-not (Test-Path -LiteralPath $modelRootPath -PathType Container)) {
    throw "Model root directory not found: $modelRootPath"
}
if (-not (Test-Path -LiteralPath $manifestPathResolved -PathType Leaf)) {
    throw "Model manifest not found: $manifestPathResolved"
}
if (-not (Test-Path -LiteralPath $tikaJarPath -PathType Leaf)) {
    throw "Tika server JAR not found: $tikaJarPath"
}
if (-not (Test-Path -LiteralPath $tikaChecksumPath -PathType Leaf)) {
    throw "Tika checksum file not found: $tikaChecksumPath"
}
if (Test-TcpPort $Port) {
    throw "MVP API port is already in use: $Port"
}

$expectedChecksum = [System.IO.File]::ReadAllText($tikaChecksumPath).Trim().ToLowerInvariant()
if ($expectedChecksum -notmatch '^[0-9a-f]{128}$') {
    throw "Tika checksum file must contain one SHA-512 digest"
}

$jarStream = [System.IO.File]::OpenRead($tikaJarPath)
$sha512 = [System.Security.Cryptography.SHA512]::Create()
try {
    $hashBytes = $sha512.ComputeHash($jarStream)
    $actualChecksum = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant()
}
finally {
    $sha512.Dispose()
    $jarStream.Dispose()
}
if ($actualChecksum -ne $expectedChecksum) {
    throw "Tika server JAR SHA-512 mismatch"
}

[System.IO.Directory]::CreateDirectory($dataDirPath) | Out-Null
$writeProbe = Join-Path $dataDirPath (".mvp-write-probe-{0}" -f [System.Guid]::NewGuid().ToString("N"))
try {
    [System.IO.File]::WriteAllText($writeProbe, "ok")
}
finally {
    if ([System.IO.File]::Exists($writeProbe)) {
        [System.IO.File]::Delete($writeProbe)
    }
}

if ($CheckOnly) {
    Write-Output "MVP preflight passed"
    exit 0
}

$startedTika = $null
try {
    if (-not (Test-TikaReady)) {
        $tikaArguments = "-jar `"$tikaJarPath`" -p 9998"
        $startedTika = Start-Process `
            -FilePath $javaPath `
            -ArgumentList $tikaArguments `
            -PassThru `
            -WindowStyle Hidden

        $readyDeadline = [System.Diagnostics.Stopwatch]::StartNew()
        $tikaReady = $false
        while ($readyDeadline.Elapsed -lt [System.TimeSpan]::FromSeconds(30)) {
            if (Test-TikaReady) {
                $tikaReady = $true
                break
            }
            $startedTika.Refresh()
            if ($startedTika.HasExited) {
                throw "Tika server exited before becoming ready"
            }
            Start-Sleep -Milliseconds 250
        }
        if (-not $tikaReady) {
            throw "Tika server did not become ready within 30 seconds"
        }
    }

    $env:CONTENT_RETRIEVAL_MODEL_ROOT = $modelRootPath
    $env:CONTENT_RETRIEVAL_MANIFEST_PATH = $manifestPathResolved
    $env:CONTENT_RETRIEVAL_DATA_DIR = $dataDirPath
    $env:CONTENT_RETRIEVAL_TIKA_URL = "http://127.0.0.1:9998"
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"

    $appDir = Join-Path $repositoryRoot "backend/src"
    & $pythonPath `
        -m uvicorn `
        "content_retrieval.mvp:create_mvp_app" `
        --factory `
        --app-dir $appDir `
        --host "127.0.0.1" `
        --port $Port
    $uvicornExitCode = $LASTEXITCODE
    if ($uvicornExitCode -ne 0) {
        throw "MVP API exited with code $uvicornExitCode"
    }
}
finally {
    if ($null -ne $startedTika) {
        $startedTika.Refresh()
        if (-not $startedTika.HasExited) {
            Stop-Process -Id $startedTika.Id -Force
            $startedTika.WaitForExit()
        }
    }
}
