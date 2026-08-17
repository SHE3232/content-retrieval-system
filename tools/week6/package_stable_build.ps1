[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [string]$SourceCommit,
    [string]$FrontendReleaseDir,
    [string]$PythonRuntimeDir,
    [string]$JavaRuntimeDir,
    [string]$ModelRoot,
    [string]$ModelManifestPath,
    [string]$TikaJar,
    [string]$TikaChecksumFile,
    [string]$MvpLauncher,
    [string]$IntegratedLauncher,
    [string]$OutputZip,
    [string]$ThirdPartySourceDir,
    [string]$StagingRoot,
    [switch]$ReplaceExactTarget
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$oneClickLauncherName = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('5YaF5a655qOA57Si57O757ufLmV4ZQ==')
)
$integratedLauncherName = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('5ZCv5Yqo5bqU55SoLnBzMQ==')
)

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
    & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS /NP | Out-Null
    $robocopyExitCode = $LASTEXITCODE
    if ($robocopyExitCode -gt 7) {
        throw "Robocopy failed with exit code $robocopyExitCode while copying $Source"
    }
}

function Copy-PythonRuntime {
    param([string]$Source, [string]$Destination)

    $venvConfig = Join-Path $Source 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $venvConfig -PathType Leaf)) {
        Copy-DirectoryContents -Source $Source -Destination $Destination
        return 'standalone'
    }

    $homeLine = Get-Content -LiteralPath $venvConfig | Where-Object {
        $_ -match '^\s*home\s*='
    } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($homeLine)) {
        throw "Virtual environment pyvenv.cfg does not define home: $venvConfig"
    }
    $baseHome = ($homeLine -split '=', 2)[1].Trim().Trim('"')
    $baseRuntime = Resolve-RequiredDirectory -Path $baseHome -Label 'Base Python runtime from pyvenv.cfg'
    $basePython = Join-Path $baseRuntime 'python.exe'
    if (-not (Test-Path -LiteralPath $basePython -PathType Leaf)) {
        throw "Base Python runtime is not portable: python.exe not found in $baseRuntime"
    }
    $sitePackages = Resolve-RequiredDirectory -Path (Join-Path $Source 'Lib/site-packages') -Label 'Virtual environment site-packages'

    Copy-DirectoryContents -Source $baseRuntime -Destination $Destination
    Copy-DirectoryContents -Source $sitePackages -Destination (Join-Path $Destination 'Lib/site-packages')
    return 'expanded-venv'
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
    $extendedRoot = if ($rootPath.StartsWith('\\')) {
        '\\?\UNC\' + $rootPath.Substring(2)
    } else {
        '\\?\' + $rootPath
    }
    return @(
        [System.IO.Directory]::EnumerateFiles(
            $extendedRoot,
            '*',
            [System.IO.SearchOption]::AllDirectories
        ) | Sort-Object | ForEach-Object {
            $fileInfo = [System.IO.FileInfo]::new($_)
            [ordered]@{
                path = $_.Substring($extendedRoot.Length + 1).Replace('\', '/')
                bytes = $fileInfo.Length
                sha256 = Get-Sha256 -Path $_
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

function Remove-DirectoryTree {
    param([string]$Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $extendedPath = if ($fullPath.StartsWith('\\')) {
        '\\?\UNC\' + $fullPath.Substring(2)
    } else {
        '\\?\' + $fullPath
    }
    if ([System.IO.Directory]::Exists($extendedPath)) {
        [System.IO.Directory]::Delete($extendedPath, $true)
    }
}

function New-ZipFromDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationArchive
    )

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $sourcePath = [System.IO.Path]::GetFullPath($SourceDirectory).TrimEnd('\')
    $extendedSource = if ($sourcePath.StartsWith('\\')) {
        '\\?\UNC\' + $sourcePath.Substring(2)
    } else {
        '\\?\' + $sourcePath
    }
    $archiveStream = [System.IO.File]::Open(
        $DestinationArchive,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipArchive]::new(
            $archiveStream,
            [System.IO.Compression.ZipArchiveMode]::Create,
            $false,
            [System.Text.Encoding]::UTF8
        )
        foreach ($file in [System.IO.Directory]::EnumerateFiles(
            $extendedSource,
            '*',
            [System.IO.SearchOption]::AllDirectories
        )) {
            $relativePath = $file.Substring($extendedSource.Length + 1).Replace('\', '/')
            $entry = $archive.CreateEntry(
                $relativePath,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $inputStream = [System.IO.File]::Open(
                $file,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::ReadWrite
            )
            try {
                $entryStream = $entry.Open()
                try {
                    $inputStream.CopyTo($entryStream)
                } finally {
                    $entryStream.Dispose()
                }
            } finally {
                $inputStream.Dispose()
            }
        }
    } finally {
        if ($null -ne $archive) {
            $archive.Dispose()
        } else {
            $archiveStream.Dispose()
        }
    }
}
if ([string]::IsNullOrWhiteSpace($JavaRuntimeDir)) {
    $javaCommand = Get-Command java -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $JavaRuntimeDir = Split-Path -Parent (Split-Path -Parent $javaCommand.Source)
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
$javaRuntime = Resolve-RequiredDirectory -Path $JavaRuntimeDir -Label 'Java runtime directory'
$javaExecutable = Resolve-RequiredFile -Path (Join-Path $javaRuntime 'bin/java.exe') -Label 'Java runtime executable'
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

$stagingBase = if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
    Join-Path $allowedRoot '.staging'
} else {
    [System.IO.Path]::GetFullPath($StagingRoot)
}
$stagingBase = [System.IO.Path]::GetFullPath($stagingBase)
if (-not $stagingBase.StartsWith(
    $allowedRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "StagingRoot must be inside output/week6 on the repository drive: $stagingBase"
}
New-Item -ItemType Directory -Force -Path $stagingBase | Out-Null
$stageRoot = Join-Path $stagingBase ('week6-package-' + [Guid]::NewGuid().ToString('N'))
$stageRoot = [System.IO.Path]::GetFullPath($stageRoot)
if (-not $stageRoot.StartsWith(
    $stagingBase + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
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
    $pythonRuntimeMode = Copy-PythonRuntime -Source $pythonRuntime -Destination (Join-Path $appRoot 'runtime/python')
    Copy-DirectoryContents -Source $javaRuntime -Destination (Join-Path $appRoot 'runtime/java')
    Copy-DirectoryContents -Source $models -Destination (Join-Path $appRoot 'models')
    Copy-Item -LiteralPath $modelManifest -Destination (Join-Path $appRoot 'models/model-manifest.json') -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $appRoot 'tools/tika') | Out-Null
    Copy-Item -LiteralPath $tikaPath -Destination (Join-Path $appRoot 'tools/tika/tika-server-standard-3.3.1.jar')
    Copy-Item -LiteralPath $tikaChecksum -Destination (Join-Path $appRoot 'tools/tika/tika-server-standard-3.3.1.jar.sha512')
    Copy-Item -LiteralPath $mvpScript -Destination (Join-Path $appRoot 'tools/start-mvp.ps1')
    Copy-Item -LiteralPath $integratedScript -Destination (Join-Path $appRoot $integratedLauncherName)
    $oneClickLauncherPath = Join-Path $appRoot $oneClickLauncherName
    & (Join-Path $PSScriptRoot 'build_one_click_launcher.ps1') -OutputPath $oneClickLauncherPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $oneClickLauncherPath -PathType Leaf)) {
        throw 'One-click launcher build failed during stable package creation'
    }
    if (Test-Path -LiteralPath $ThirdPartySourceDir -PathType Container) {
        Copy-DirectoryContents -Source $ThirdPartySourceDir -Destination (Join-Path $appRoot 'third_party/mobileclip-src')
    }

    $manifest = [ordered]@{
        schema_version = 1
        source_commit = $SourceCommit
        generated_at = [DateTimeOffset]::Now.ToString('o')
        platform_claim = 'Windows complete integrated stable build'
        first_run_downloads = $false
        python_runtime_mode = $pythonRuntimeMode
        java_runtime_mode = 'bundled'
        one_click_launcher = $oneClickLauncherName
        excluded = @('.git', '.venv development cache', 'data', 'mvp-input', 'user settings', 'logs', 'credentials')
        files = Get-RelativeFileManifest -Root $appRoot
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $appRoot 'PACKAGE_MANIFEST.json'),
        ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )

    New-ZipFromDirectory -SourceDirectory $stageRoot -DestinationArchive $temporaryZip
    Move-Item -LiteralPath $temporaryZip -Destination $absoluteOutput
} finally {
    if (Test-Path -LiteralPath $temporaryZip -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryZip -Force
    }
    if (Test-Path -LiteralPath $stageRoot -PathType Container) {
        Remove-DirectoryTree -Path $stageRoot
    }
    if ((Test-Path -LiteralPath $stagingBase -PathType Container) -and -not (Get-ChildItem -LiteralPath $stagingBase -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $stagingBase -Force
    }
}

$hash = Get-Sha256 -Path $absoluteOutput
Write-Output "Stable package created: $absoluteOutput"
Write-Output "SHA256: $hash"
