[CmdletBinding()]
param(
    [string]$PackageRoot = $PSScriptRoot,
    [int]$Port = 8000,
    [int]$ReadyTimeoutSeconds = 180,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredFile {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-RequiredDirectory {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-JavaProcessIds {
    return @(
        Get-Process -Name java -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Id }
    )
}

function Test-BackendReady {
    param([string]$Uri)
    try {
        $request = [System.Net.WebRequest]::Create($Uri)
        $request.Proxy = $null
        $request.Timeout = 3000
        $response = $request.GetResponse()
        try {
            $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
            try {
                $payload = $reader.ReadToEnd() | ConvertFrom-Json
                return $payload.status -eq 'ready'
            } finally {
                $reader.Dispose()
            }
        } finally {
            $response.Dispose()
        }
    } catch {
        return $false
    }
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw 'Port must be between 1 and 65535'
}
$root = Resolve-RequiredDirectory -Path $PackageRoot -Label 'Package root'
$frontendRoot = Resolve-RequiredDirectory -Path (Join-Path $root 'frontend') -Label 'Frontend directory'
$frontendExecutable = Join-Path $frontendRoot 'content_retrieval_app.exe'
if (-not (Test-Path -LiteralPath $frontendExecutable -PathType Leaf)) {
    $frontendExecutable = Get-ChildItem -LiteralPath $frontendRoot -Filter '*.exe' -File |
        Sort-Object Name |
        Select-Object -First 1 -ExpandProperty FullName
}
$frontendExecutable = Resolve-RequiredFile -Path $frontendExecutable -Label 'Flutter executable'

$pythonCandidates = @(
    (Join-Path $root 'runtime/python/Scripts/python.exe'),
    (Join-Path $root 'runtime/python/python.exe')
)
$pythonExecutable = $pythonCandidates | Where-Object {
    Test-Path -LiteralPath $_ -PathType Leaf
} | Select-Object -First 1
$pythonExecutable = Resolve-RequiredFile -Path $pythonExecutable -Label 'Packaged Python executable'
$javaExecutable = Resolve-RequiredFile -Path (Join-Path $root 'runtime/java/bin/java.exe') -Label 'Packaged Java executable'
$mvpLauncher = Resolve-RequiredFile -Path (Join-Path $root 'tools/start-mvp.ps1') -Label 'MVP launcher'
$modelRoot = Resolve-RequiredDirectory -Path (Join-Path $root 'models') -Label 'Model root'
$modelManifest = Resolve-RequiredFile -Path (Join-Path $modelRoot 'model-manifest.json') -Label 'Model manifest'
$tikaJar = Resolve-RequiredFile -Path (Join-Path $root 'tools/tika/tika-server-standard-3.3.1.jar') -Label 'Tika JAR'
$tikaChecksum = Resolve-RequiredFile -Path (Join-Path $root 'tools/tika/tika-server-standard-3.3.1.jar.sha512') -Label 'Tika checksum'
$dataDir = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

if ($CheckOnly) {
    Write-Output 'Integrated package preflight passed'
    Write-Output "Frontend: $frontendExecutable"
    Write-Output "Python: $pythonExecutable"
    Write-Output "Java: $javaExecutable"
    Write-Output "Models: $modelRoot"
    exit 0
}

$beforeJava = Get-JavaProcessIds
$backendProcess = $null
$frontendProcess = $null
try {
    $backendArguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"' + $mvpLauncher + '"'),
        '-PythonExecutable', ('"' + $pythonExecutable + '"'),
        '-JavaExecutable', ('"' + $javaExecutable + '"'),
        '-ModelRoot', ('"' + $modelRoot + '"'),
        '-ManifestPath', ('"' + $modelManifest + '"'),
        '-DataDir', ('"' + $dataDir + '"'),
        '-TikaJar', ('"' + $tikaJar + '"'),
        '-TikaChecksumFile', ('"' + $tikaChecksum + '"'),
        '-Port', "$Port"
    )
    $backendProcess = Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList $backendArguments `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -PassThru

    $deadline = [DateTime]::UtcNow.AddSeconds($ReadyTimeoutSeconds)
    $readyUri = "http://127.0.0.1:$Port/health/ready"
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($backendProcess.HasExited) {
            throw "Backend exited before becoming ready with code $($backendProcess.ExitCode)"
        }
        if (Test-BackendReady -Uri $readyUri) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-BackendReady -Uri $readyUri)) {
        throw "Backend did not become ready within $ReadyTimeoutSeconds seconds"
    }

    $frontendProcess = Start-Process `
        -FilePath $frontendExecutable `
        -WorkingDirectory $frontendRoot `
        -PassThru
    $frontendProcess.WaitForExit()
} finally {
    if ($null -ne $frontendProcess) {
        $frontendProcess.Dispose()
    }
    if ($null -ne $backendProcess) {
        if (-not $backendProcess.HasExited) {
            Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
            $backendProcess.WaitForExit(5000) | Out-Null
        }
        $backendProcess.Dispose()
    }
    $afterJava = Get-JavaProcessIds
    $ownedJava = @($afterJava | Where-Object { $_ -notin $beforeJava })
    foreach ($processId in $ownedJava) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}
