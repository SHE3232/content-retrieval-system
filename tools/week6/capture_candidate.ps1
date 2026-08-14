[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [string]$OutputPath,
    [string]$PythonExecutable,
    [string]$FlutterExecutable = 'flutter',
    [string]$DartExecutable = 'dart',
    [string]$JavaExecutable = 'java',
    [string]$PreflightScript,
    [string]$ModelRoot,
    [string]$ManifestPath,
    [string]$TikaJar,
    [string]$TikaChecksumFile,
    [string]$DataDir
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

function Resolve-ExecutableCommand {
    param([string]$Executable, [string]$Label)
    if (-not [string]::IsNullOrWhiteSpace($Executable) -and (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $Executable).Path
    }
    $command = Get-Command $Executable -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        throw "$Label not found: $Executable"
    }
    return $command.Source
}

function Invoke-Version {
    param([string]$Executable, [string[]]$Arguments)
    if ([string]::IsNullOrWhiteSpace($Executable)) {
        throw 'Version executable was not supplied'
    }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "Version command failed: $Executable $($Arguments -join ' ')"
    }
    return $output.Trim()
}

$repository = Resolve-RequiredDirectory -Path $RepositoryRoot -Label 'Repository root'
$inside = (& git -C $repository rev-parse --is-inside-work-tree 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $inside -ne 'true') {
    throw "Not a Git worktree: $repository"
}
$dirty = (& git -C $repository status --porcelain=v1 --untracked-files=all 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect Git worktree'
}
if (-not [string]::IsNullOrWhiteSpace($dirty)) {
    throw "Worktree is not clean:`n$dirty"
}

$sourceCommit = (& git -C $repository rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'Git did not return a full 40-character commit hash'
}
$branch = (& git -C $repository rev-parse --abbrev-ref HEAD 2>&1 | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repository 'docs/week6/evidence/candidate.json'
}
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $repository 'backend/.venv/Scripts/python.exe'
}
if ([string]::IsNullOrWhiteSpace($PreflightScript)) {
    $PreflightScript = Join-Path $repository 'tools/start-mvp.ps1'
}
if ([string]::IsNullOrWhiteSpace($ModelRoot)) {
    $ModelRoot = Join-Path $repository 'models'
}
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $ModelRoot 'model-manifest.json'
}
if ([string]::IsNullOrWhiteSpace($TikaJar)) {
    $TikaJar = Join-Path $repository 'tools/tika/tika-server-standard-3.3.1.jar'
}
if ([string]::IsNullOrWhiteSpace($TikaChecksumFile)) {
    $TikaChecksumFile = "$TikaJar.sha512"
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $DataDir = Join-Path $repository 'data/week6-candidate'
}

$python = Resolve-RequiredFile -Path $PythonExecutable -Label 'Python executable'
$flutterCommand = Resolve-ExecutableCommand -Executable $FlutterExecutable -Label 'Flutter executable'
$dartCommand = Resolve-ExecutableCommand -Executable $DartExecutable -Label 'Dart executable'
$javaCommand = Resolve-ExecutableCommand -Executable $JavaExecutable -Label 'Java executable'
$preflight = Resolve-RequiredFile -Path $PreflightScript -Label 'Preflight script'
$models = Resolve-RequiredDirectory -Path $ModelRoot -Label 'Model root'
$modelManifest = Resolve-RequiredFile -Path $ManifestPath -Label 'Model manifest'
$tikaPath = Resolve-RequiredFile -Path $TikaJar -Label 'Tika JAR'
$tikaChecksum = Resolve-RequiredFile -Path $TikaChecksumFile -Label 'Tika checksum'
$runtimeData = Resolve-RequiredDirectory -Path $DataDir -Label 'Data directory'

$preflightOutput = & $preflight `
    -PythonExecutable $python `
    -JavaExecutable $javaCommand `
    -ModelRoot $models `
    -ManifestPath $modelManifest `
    -TikaJar $tikaPath `
    -TikaChecksumFile $tikaChecksum `
    -DataDir $runtimeData `
    -CheckOnly 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $preflightOutput -notmatch 'MVP preflight passed') {
    throw "MVP preflight failed:`n$preflightOutput"
}

$computer = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem
$record = [ordered]@{
    schema_version = 1
    source_commit = $sourceCommit
    branch = $branch
    worktree_clean = $true
    generated_at = [DateTimeOffset]::Now.ToString('o')
    versions = [ordered]@{
        python = Invoke-Version -Executable $python -Arguments @('--version')
        flutter = Invoke-Version -Executable $flutterCommand -Arguments @('--version')
        dart = Invoke-Version -Executable $dartCommand -Arguments @('--version')
        java = Invoke-Version -Executable $javaCommand -Arguments @('-version')
    }
    system = [ordered]@{
        computer_name = $env:COMPUTERNAME
        os = $os.Caption
        os_version = $os.Version
        cpu = $processor.Name
        logical_processors = [int]$computer.NumberOfLogicalProcessors
        total_memory_bytes = [int64]$computer.TotalPhysicalMemory
    }
    resources = [ordered]@{
        python = $python
        model_root = $models
        model_manifest = $modelManifest
        tika_jar = $tikaPath
        tika_checksum = $tikaChecksum
        data_dir = $runtimeData
    }
    preflight = [ordered]@{
        status = 'PASS'
        output = $preflightOutput.Trim()
    }
}

$absoluteOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $absoluteOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$json = $record | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText(
    $absoluteOutput,
    $json + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Output "Candidate captured: $absoluteOutput"
