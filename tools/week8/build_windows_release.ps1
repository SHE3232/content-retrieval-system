[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [string]$SourceCommit,
    [string]$SourceModelRoot,
    [string]$SourceModelManifestPath,
    [string]$FrontendReleaseDir,
    [string]$PythonRuntimeDir,
    [string]$ResearchPythonRuntimeDir,
    [string]$JavaRuntimeDir,
    [string]$ResearchThirdPartySourceDir,
    [string]$TikaJar,
    [string]$TikaChecksumFile,
    [string]$OutputRoot,
    [string]$WorkingRoot = 'F:\contentretrivalsystem\.tmp\week8\windows-release',
    [string]$EvidenceDirectory,
    [long]$ArchiveSizeLimitBytes = 1000000000,
    [switch]$SkipFlutterBuild,
    [switch]$SkipPreflight,
    [switch]$ValidateOnly,
    [switch]$ReplaceExactTargets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredFile {
    param([string]$Path, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-RequiredDirectory {
    param([string]$Path, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-EmptyOrMissingDirectory {
    param([string]$Path, [string]$AllowedParent)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullParent = [System.IO.Path]::GetFullPath($AllowedParent).TrimEnd('\')
    if (-not $fullPath.StartsWith(
        $fullParent + '\',
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing working path outside the approved root: $fullPath"
    }
    if ([System.IO.Directory]::Exists($fullPath) -and
        [System.IO.Directory]::GetFileSystemEntries($fullPath).Length -gt 0) {
        throw "Working directory is not empty: $fullPath"
    }
    return $fullPath
}

if ($SourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'SourceCommit must be a full 40-character lowercase hexadecimal hash'
}
if ($ArchiveSizeLimitBytes -le 0) {
    throw 'ArchiveSizeLimitBytes must be positive'
}

$repository = Resolve-RequiredDirectory -Path $RepositoryRoot -Label 'Repository root'
$head = (& git -C $repository rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $SourceCommit) {
    throw "SourceCommit does not match repository HEAD: expected $head, got $SourceCommit"
}
$dirty = (& git -C $repository status --porcelain=v1 --untracked-files=all 2>&1 |
    Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace($dirty)) {
    throw "Worktree is not clean:`n$dirty"
}

foreach ($legalName in @('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md')) {
    Resolve-RequiredFile -Path (Join-Path $repository $legalName) `
        -Label "Required legal file $legalName" | Out-Null
}

if ([string]::IsNullOrWhiteSpace($SourceModelRoot)) {
    $SourceModelRoot = Join-Path $repository 'models'
}
$sourceModels = Resolve-RequiredDirectory `
    -Path $SourceModelRoot `
    -Label 'Source model root'
if ([string]::IsNullOrWhiteSpace($SourceModelManifestPath)) {
    $SourceModelManifestPath = Join-Path $sourceModels 'model-manifest.json'
}
$sourceModelManifest = Resolve-RequiredFile `
    -Path $SourceModelManifestPath `
    -Label 'Source model manifest'

if ([string]::IsNullOrWhiteSpace($PythonRuntimeDir)) {
    $PythonRuntimeDir = Join-Path $repository 'backend/.venv'
}
$pythonRuntime = Resolve-RequiredDirectory `
    -Path $PythonRuntimeDir `
    -Label 'Python runtime'
$pythonExecutable = Resolve-RequiredFile `
    -Path (Join-Path $pythonRuntime 'Scripts/python.exe') `
    -Label 'Python executable'

if ([string]::IsNullOrWhiteSpace($ResearchPythonRuntimeDir)) {
    throw 'ResearchPythonRuntimeDir must identify a separate research-only Python runtime'
}
$researchPythonRuntime = Resolve-RequiredDirectory `
    -Path $ResearchPythonRuntimeDir `
    -Label 'Research-only Python runtime'
$researchPythonExecutable = Resolve-RequiredFile `
    -Path (Join-Path $researchPythonRuntime 'Scripts/python.exe') `
    -Label 'Research-only Python executable'
if ($researchPythonRuntime -eq $pythonRuntime) {
    throw 'Research-only Python runtime must differ from the public Python runtime'
}
& $researchPythonExecutable -c 'import mobileclip; print(mobileclip.__file__)'
if ($LASTEXITCODE -ne 0) {
    throw 'Research-only Python runtime cannot import mobileclip'
}

if ([string]::IsNullOrWhiteSpace($JavaRuntimeDir)) {
    throw 'JavaRuntimeDir must identify a redistributable OpenJDK runtime'
}
$javaRuntime = Resolve-RequiredDirectory -Path $JavaRuntimeDir -Label 'Java runtime'
$javaExecutable = Resolve-RequiredFile `
    -Path (Join-Path $javaRuntime 'bin/java.exe') `
    -Label 'Java executable'
Resolve-RequiredFile -Path (Join-Path $javaRuntime 'bin/jlink.exe') `
    -Label 'jlink executable' | Out-Null
$javaReleaseFile = Resolve-RequiredFile `
    -Path (Join-Path $javaRuntime 'release') `
    -Label 'OpenJDK release metadata'
$javaRelease = Get-Content -LiteralPath $javaReleaseFile -Raw
if ($javaRelease -match '(?im)^IMPLEMENTOR="?Oracle Corporation"?') {
    throw 'Oracle Java runtime is not permitted in the default public package'
}

if ([string]::IsNullOrWhiteSpace($TikaJar)) {
    $TikaJar = Join-Path $repository 'tools/tika/tika-server-standard-3.3.1.jar'
}
$resolvedTikaJar = Resolve-RequiredFile -Path $TikaJar -Label 'Tika server JAR'
if ([string]::IsNullOrWhiteSpace($TikaChecksumFile)) {
    $TikaChecksumFile = "$resolvedTikaJar.sha512"
}
$resolvedTikaChecksum = Resolve-RequiredFile `
    -Path $TikaChecksumFile `
    -Label 'Tika checksum file'

if ([string]::IsNullOrWhiteSpace($ResearchThirdPartySourceDir)) {
    $ResearchThirdPartySourceDir = Join-Path $repository 'third_party/mobileclip-src'
}
$researchThirdPartySource = Resolve-RequiredDirectory `
    -Path $ResearchThirdPartySourceDir `
    -Label 'Curated MobileCLIP source'

if (-not $SkipFlutterBuild) {
    Push-Location (Join-Path $repository 'frontend')
    try {
        & flutter build windows --release --no-pub
        if ($LASTEXITCODE -ne 0) {
            throw "Flutter Windows release build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
if ([string]::IsNullOrWhiteSpace($FrontendReleaseDir)) {
    $FrontendReleaseDir = Join-Path $repository 'frontend/build/windows/x64/runner/Release'
}
$frontendRelease = Resolve-RequiredDirectory `
    -Path $FrontendReleaseDir `
    -Label 'Flutter Windows release directory'
Resolve-RequiredFile `
    -Path (Join-Path $frontendRelease 'content_retrieval_app.exe') `
    -Label 'Flutter release executable' | Out-Null

if ($ValidateOnly) {
    Write-Output "Windows release inputs validated for $SourceCommit"
    exit 0
}

$workingParent = [System.IO.Path]::GetFullPath($WorkingRoot)
New-Item -ItemType Directory -Force -Path $workingParent | Out-Null
$runRootCandidate = Join-Path $workingParent $SourceCommit
$runRoot = Assert-EmptyOrMissingDirectory `
    -Path $runRootCandidate `
    -AllowedParent $workingParent
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$publicThirdPartySource = Join-Path $runRoot 'public-third-party-omitted'
$publicModelRoot = Join-Path $runRoot 'public-models'
$researchModelRoot = Join-Path $runRoot 'research-models'

& $pythonExecutable (Join-Path $repository 'tools/week8/build_public_model_root.py') `
    --source-model-root $sourceModels `
    --source-manifest $sourceModelManifest `
    --destination $publicModelRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Public model staging failed'
}
& $pythonExecutable (Join-Path $repository 'tools/week8/build_public_model_root.py') `
    --source-model-root $sourceModels `
    --source-manifest $sourceModelManifest `
    --destination $researchModelRoot `
    --distribution research-only
if ($LASTEXITCODE -ne 0) {
    throw 'Research model staging failed'
}

if (-not $SkipPreflight) {
    $preflightData = Join-Path $runRoot 'preflight-data'
    & (Join-Path $repository 'tools/start-mvp.ps1') `
        -PythonExecutable $pythonExecutable `
        -JavaExecutable $javaExecutable `
        -ModelRoot $publicModelRoot `
        -ManifestPath (Join-Path $publicModelRoot 'model-manifest.json') `
        -DataDir $preflightData `
        -TikaJar $resolvedTikaJar `
        -TikaChecksumFile $resolvedTikaChecksum `
        -CheckOnly
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $defaultOutputRelative = [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String(
            'b3V0cHV0L3dlZWs4L+esrOWFq+WRqOacgOe7iOS6pOS7mA=='
        )
    )
    $OutputRoot = Join-Path $repository $defaultOutputRelative
}
$deliveryRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$allowedDeliveryParent = [System.IO.Path]::GetFullPath(
    (Join-Path $repository 'output/week8')
).TrimEnd('\')
if (-not $deliveryRoot.StartsWith(
    $allowedDeliveryParent + '\',
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "OutputRoot must be inside repository output/week8: $deliveryRoot"
}

$windowsRelative = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('MDFf5bmz5Y+w5Y+R5biDL1dpbmRvd3M=')
)
$researchRelative = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('MDNf6K++56iL5ryU56S656CU56m25YyF')
)
$researchArchiveName = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String(
        '6K++56iL5ryU56S656CU56m25YyFLXYxLjAuMC13aW5kb3dzLXg2NC56aXA='
    )
)
$windowsOutput = Join-Path $deliveryRoot $windowsRelative
$researchOutput = Join-Path $deliveryRoot $researchRelative
New-Item -ItemType Directory -Force -Path $windowsOutput | Out-Null
New-Item -ItemType Directory -Force -Path $researchOutput | Out-Null
$publicFinal = Join-Path $windowsOutput 'offline-retrieval-v1.0.0-windows-x64.zip'
$researchFinal = Join-Path $researchOutput $researchArchiveName
foreach ($target in @($publicFinal, $researchFinal)) {
    if ([System.IO.File]::Exists($target) -and -not $ReplaceExactTargets) {
        throw "Output archive already exists: $target"
    }
}

$week6Output = Join-Path $repository 'output/week6/.week8-build'
$week6Stage = Join-Path $repository 'output/week6/.week8-staging'
New-Item -ItemType Directory -Force -Path $week6Output | Out-Null
New-Item -ItemType Directory -Force -Path $week6Stage | Out-Null
$publicIntermediate = Join-Path $week6Output ("public-$SourceCommit.zip")
$researchIntermediate = Join-Path $week6Output ("research-$SourceCommit.zip")

$packageCommon = @{
    RepositoryRoot = $repository
    SourceCommit = $SourceCommit
    FrontendReleaseDir = $frontendRelease
    PythonRuntimeDir = $pythonRuntime
    JavaRuntimeDir = $javaRuntime
    TikaJar = $resolvedTikaJar
    TikaChecksumFile = $resolvedTikaChecksum
    MvpLauncher = (Join-Path $repository 'tools/start-mvp.ps1')
    IntegratedLauncher = (Join-Path $repository 'tools/week6/start-integrated.ps1')
    StagingRoot = $week6Stage
    PackageProfile = 'lightweight'
    ArchiveSizeLimitBytes = $ArchiveSizeLimitBytes
    LightweightProfilePath = (Join-Path $repository 'tools/week6/lightweight_package_profile.json')
    JlinkExecutable = (Join-Path $javaRuntime 'bin/jlink.exe')
}

& (Join-Path $repository 'tools/week6/package_stable_build.ps1') `
    @packageCommon `
    -ModelRoot $publicModelRoot `
    -ModelManifestPath (Join-Path $publicModelRoot 'model-manifest.json') `
    -ThirdPartySourceDir $publicThirdPartySource `
    -OutputZip $publicIntermediate `
    -ReplaceExactTarget

$researchPackageCommon = $packageCommon.Clone()
$researchPackageCommon['PythonRuntimeDir'] = $researchPythonRuntime
& (Join-Path $repository 'tools/week6/package_stable_build.ps1') `
    @researchPackageCommon `
    -ModelRoot $researchModelRoot `
    -ModelManifestPath (Join-Path $researchModelRoot 'model-manifest.json') `
    -ThirdPartySourceDir $researchThirdPartySource `
    -OutputZip $researchIntermediate `
    -ResearchOnlyDistribution `
    -ReplaceExactTarget

foreach ($pair in @(
    [pscustomobject]@{ Source = $publicIntermediate; Target = $publicFinal },
    [pscustomobject]@{ Source = $researchIntermediate; Target = $researchFinal }
)) {
    $source = $pair.Source
    $target = $pair.Target
    if ([System.IO.File]::Exists($target)) {
        [System.IO.File]::Delete($target)
    }
    [System.IO.File]::Copy($source, $target, $false)
}

if ([string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
    $EvidenceDirectory = Join-Path $repository 'docs/week8/evidence/platform/windows'
}
New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
$validator = Join-Path $repository 'tools/week8/validate_windows_release.py'
& $pythonExecutable $validator $publicFinal `
    --expected-commit $SourceCommit `
    --distribution default-public `
    --size-limit-bytes $ArchiveSizeLimitBytes `
    --output (Join-Path $EvidenceDirectory 'public-archive.json')
if ($LASTEXITCODE -ne 0) {
    throw 'Default public archive validation failed'
}
& $pythonExecutable $validator $researchFinal `
    --expected-commit $SourceCommit `
    --distribution research-only `
    --size-limit-bytes $ArchiveSizeLimitBytes `
    --output (Join-Path $EvidenceDirectory 'research-archive.json')
if ($LASTEXITCODE -ne 0) {
    throw 'Research archive validation failed'
}

Write-Output "Windows public candidate: $publicFinal"
Write-Output "Windows research package: $researchFinal"
