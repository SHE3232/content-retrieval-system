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

function Stop-StartedTika {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    try {
        $hasExited = $true
        try {
            $Process.Refresh()
            $hasExited = $Process.HasExited
        }
        catch [System.InvalidOperationException] {
            $hasExited = $true
        }

        if (-not $hasExited) {
            try {
                Stop-Process -Id $Process.Id -Force -ErrorAction Stop
            }
            catch {
                try {
                    $Process.Refresh()
                    if (-not $Process.HasExited) {
                        throw
                    }
                }
                catch [System.InvalidOperationException] {
                    # The process exited between inspection and termination.
                }
            }
        }

        try {
            if (-not $Process.WaitForExit(5000)) {
                throw "Tika server process did not exit within 5 seconds"
            }
        }
        catch [System.InvalidOperationException] {
            # No associated live process remains to wait for.
        }
    }
    finally {
        $Process.Dispose()
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

try {
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $javaPath -version 2>&1 | Out-Null
        $javaCheckExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}
catch {
    throw "Java runtime check failed"
}
if ($javaCheckExitCode -ne 0) {
    throw "Java runtime check failed"
}

try {
    $pythonVersionOutput = @(
        & $pythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    )
    $pythonVersionExitCode = $LASTEXITCODE
}
catch {
    throw "Python 3.10 is required"
}
$pythonVersion = (
    $pythonVersionOutput | ForEach-Object { $_.ToString() }
) -join "`n"
if ($pythonVersionExitCode -ne 0 -or $pythonVersion.Trim() -ne "3.10") {
    throw "Python 3.10 is required"
}

try {
    & $pythonPath -c "import uvicorn" 2>&1 | Out-Null
    $uvicornImportExitCode = $LASTEXITCODE
}
catch {
    throw "Uvicorn import failed"
}
if ($uvicornImportExitCode -ne 0) {
    throw "Uvicorn import failed"
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

$appDir = Join-Path $repositoryRoot "backend/src"
$manifestVerificationCode = @'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from content_retrieval.embeddings.manifest import ModelManifest
from content_retrieval.runtime import IMAGE_MODEL_ID, TEXT_MODEL_ID

manifest = ModelManifest.load(Path(sys.argv[2]), model_root=Path(sys.argv[3]))
text_entry = manifest.require(TEXT_MODEL_ID)
image_entry = manifest.require(IMAGE_MODEL_ID)
text_entry.verify()
image_entry.verify()
'@
try {
    & $pythonPath `
        -c $manifestVerificationCode `
        $appDir `
        $manifestPathResolved `
        $modelRootPath `
        2>&1 | Out-Null
    $manifestVerificationExitCode = $LASTEXITCODE
}
catch {
    throw "Model manifest verification failed"
}
if ($manifestVerificationExitCode -ne 0) {
    throw "Model manifest verification failed"
}

$dataDirCreatedByLauncher = $false
if (-not [System.IO.Directory]::Exists($dataDirPath)) {
    [System.IO.Directory]::CreateDirectory($dataDirPath) | Out-Null
    $dataDirCreatedByLauncher = $true
}
$writeProbe = Join-Path $dataDirPath (".mvp-write-probe-{0}" -f [System.Guid]::NewGuid().ToString("N"))
try {
    [System.IO.File]::WriteAllText($writeProbe, "ok")
}
finally {
    try {
        if ([System.IO.File]::Exists($writeProbe)) {
            [System.IO.File]::Delete($writeProbe)
        }
    }
    finally {
        if (
            $CheckOnly -and
            $dataDirCreatedByLauncher -and
            [System.IO.Directory]::Exists($dataDirPath) -and
            [System.IO.Directory]::GetFileSystemEntries($dataDirPath).Length -eq 0
        ) {
            [System.IO.Directory]::Delete($dataDirPath, $false)
        }
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
        Stop-StartedTika $startedTika
    }
}
