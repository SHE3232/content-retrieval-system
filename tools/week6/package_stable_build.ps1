[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [string]$SourceCommit,
    [string]$FrontendReleaseDir,
    [string]$PythonRuntimeDir,
    [string]$ModelRoot,
    [string]$ModelManifestPath,
    [string]$TikaJar,
    [string]$TikaChecksumFile,
    [string]$MvpLauncher,
    [string]$IntegratedLauncher,
    [string]$OutputZip,
    [string]$ThirdPartySourceDir,
    [switch]$ReplaceExactTarget
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredFile {
    param([string]$Path, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-RequiredDirectory {
    param([string]$Path, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Copy-DirectoryContents {
    param([string]$Source, [string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Get-Sha256 {
    param([string]$Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        } finally {
            $stream.Dispose()
        }
    } finally {
        $algorithm.Dispose()
    }
}

function Get-RelativeFileManifest {
    param([string]$Root)
    $rootPath = [System.IO.Path]::GetFullPath($Root)
    return @(
        Get-ChildItem -LiteralPath $rootPath -Recurse -File | Sort-Object FullName | ForEach-Object {
            [ordered]@{
                path = $_.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
                bytes = $_.Length
                sha256 = Get-Sha256 -Path $_.FullName
            }
        }
    )
}

$repository = Resolve-RequiredDirectory -Path $RepositoryRoot -Label 'Repository root'
if ([string]::IsNullOrWhiteSpace($OutputZip)) {
    $OutputZip = Join-Path $repository 'output/week6/第六周最终提交_请上传这4项/01_Windows完整集成稳定版.zip'
}
$absoluteOutput = [System.IO.Path]::GetFullPath($OutputZip)
$allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $repository 'output/week6'))
if (-not $absoluteOutput.StartsWith(
    $allowedRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Output ZIP must be inside output/week6: $absoluteOutput"
}

if ($SourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'SourceCommit must be a full 40-character lowercase hexadecimal hash'
}
$head = (& git -C $repository rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $SourceCommit) {
    throw "SourceCommit does not match repository HEAD: expected $head, got $SourceCommit"
}
$dirty = (& git -C $repository status --porcelain=v1 --untracked-files=all 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace($dirty)) {
    throw "Worktree is not clean:`n$dirty"
}

if ([string]::IsNullOrWhiteSpace($FrontendReleaseDir)) {
    $FrontendReleaseDir = Join-Path $repository 'frontend/build/windows/x64/runner/Release'
}
if ([string]::IsNullOrWhiteSpace($PythonRuntimeDir)) {
    $PythonRuntimeDir = Join-Path $repository 'backend/.venv'
}
if ([string]::IsNullOrWhiteSpace($ModelRoot)) {
    $ModelRoot = Join-Path $repository 'models'
}
if ([string]::IsNullOrWhiteSpace($ModelManifestPath)) {
    $ModelManifestPath = Join-Path $ModelRoot 'model-manifest.json'
}
if ([string]::IsNullOrWhiteSpace($TikaJar)) {
    $TikaJar = Join-Path $repository 'tools/tika/tika-server-standard-3.3.1.jar'
}
if ([string]::IsNullOrWhiteSpace($TikaChecksumFile)) {
    $TikaChecksumFile = "$TikaJar.sha512"
}
if ([string]::IsNullOrWhiteSpace($MvpLauncher)) {
    $MvpLauncher = Join-Path $repository 'tools/start-mvp.ps1'
}
if ([string]::IsNullOrWhiteSpace($IntegratedLauncher)) {
    $IntegratedLauncher = Join-Path $repository 'tools/week6/start-integrated.ps1'
}
if ([string]::IsNullOrWhiteSpace($ThirdPartySourceDir)) {
    $ThirdPartySourceDir = Join-Path $repository 'third_party/mobileclip-src'
}

$frontend = Resolve-RequiredDirectory -Path $FrontendReleaseDir -Label 'Flutter release directory'
$pythonRuntime = Resolve-RequiredDirectory -Path $PythonRuntimeDir -Label 'Python runtime directory'
$models = Resolve-RequiredDirectory -Path $ModelRoot -Label 'Model root'
$modelManifest = Resolve-RequiredFile -Path $ModelManifestPath -Label 'Model manifest'
$tikaPath = Resolve-RequiredFile -Path $TikaJar -Label 'Tika JAR'
$tikaChecksum = Resolve-RequiredFile -Path $TikaChecksumFile -Label 'Tika checksum'
$mvpScript = Resolve-RequiredFile -Path $MvpLauncher -Label 'MVP launcher'
$integratedScript = Resolve-RequiredFile -Path $IntegratedLauncher -Label 'Integrated launcher'

if (Test-Path -LiteralPath $absoluteOutput) {
    if (-not $ReplaceExactTarget) {
        throw "Output ZIP already exists; pass -ReplaceExactTarget to replace this exact file: $absoluteOutput"
    }
    Remove-Item -LiteralPath $absoluteOutput -Force
}
$outputDirectory = Split-Path -Parent $absoluteOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('week6-package-' + [Guid]::NewGuid().ToString('N'))
$stageRoot = [System.IO.Path]::GetFullPath($stageRoot)
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
if (-not $stageRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing unsafe staging path: $stageRoot"
}
$appRoot = Join-Path $stageRoot 'app'
$temporaryZip = Join-Path $outputDirectory ('.week6-' + [Guid]::NewGuid().ToString('N') + '.zip')

try {
    New-Item -ItemType Directory -Force -Path $appRoot | Out-Null
    Copy-DirectoryContents -Source $frontend -Destination (Join-Path $appRoot 'frontend')
    Copy-DirectoryContents -Source (Join-Path $repository 'backend/src') -Destination (Join-Path $appRoot 'backend/src')
    Copy-Item -LiteralPath (Resolve-RequiredFile (Join-Path $repository 'backend/pyproject.toml') 'Backend pyproject') -Destination (Join-Path $appRoot 'backend/pyproject.toml')
    Copy-Item -LiteralPath (Resolve-RequiredFile (Join-Path $repository 'backend/uv.lock') 'Backend lockfile') -Destination (Join-Path $appRoot 'backend/uv.lock')
    Copy-DirectoryContents -Source $pythonRuntime -Destination (Join-Path $appRoot 'runtime/python')
    Copy-DirectoryContents -Source $models -Destination (Join-Path $appRoot 'models')
    Copy-Item -LiteralPath $modelManifest -Destination (Join-Path $appRoot 'models/model-manifest.json') -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $appRoot 'tools/tika') | Out-Null
    Copy-Item -LiteralPath $tikaPath -Destination (Join-Path $appRoot 'tools/tika/tika-server-standard-3.3.1.jar')
    Copy-Item -LiteralPath $tikaChecksum -Destination (Join-Path $appRoot 'tools/tika/tika-server-standard-3.3.1.jar.sha512')
    Copy-Item -LiteralPath $mvpScript -Destination (Join-Path $appRoot 'tools/start-mvp.ps1')
    Copy-Item -LiteralPath $integratedScript -Destination (Join-Path $appRoot '启动应用.ps1')
    if (Test-Path -LiteralPath $ThirdPartySourceDir -PathType Container) {
        Copy-DirectoryContents -Source $ThirdPartySourceDir -Destination (Join-Path $appRoot 'third_party/mobileclip-src')
    }

    $manifest = [ordered]@{
        schema_version = 1
        source_commit = $SourceCommit
        generated_at = [DateTimeOffset]::Now.ToString('o')
        platform_claim = 'Windows complete integrated stable build'
        first_run_downloads = $false
        excluded = @('.git', '.venv development cache', 'data', 'mvp-input', 'user settings', 'logs', 'credentials')
        files = Get-RelativeFileManifest -Root $appRoot
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $appRoot 'PACKAGE_MANIFEST.json'),
        ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $stageRoot,
        $temporaryZip,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    Move-Item -LiteralPath $temporaryZip -Destination $absoluteOutput
} finally {
    if (Test-Path -LiteralPath $temporaryZip -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryZip -Force
    }
    if (Test-Path -LiteralPath $stageRoot -PathType Container) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}

$hash = Get-Sha256 -Path $absoluteOutput
Write-Output "Stable package created: $absoluteOutput"
Write-Output "SHA256: $hash"
