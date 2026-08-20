[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$JavaHome,
    [string]$JlinkExecutable,
    [string[]]$Modules = @('ALL-MODULE-PATH')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($JavaHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:JAVA_HOME)) {
        $JavaHome = $env:JAVA_HOME
    } else {
        $javaCommand = Get-Command java -CommandType Application -ErrorAction Stop | Select-Object -First 1
        $JavaHome = Split-Path -Parent (Split-Path -Parent $javaCommand.Source)
    }
}
$javaRoot = (Resolve-Path -LiteralPath $JavaHome).Path
$jmods = (Resolve-Path -LiteralPath (Join-Path $javaRoot 'jmods')).Path
if ([string]::IsNullOrWhiteSpace($JlinkExecutable)) {
    $JlinkExecutable = Join-Path $javaRoot 'bin\jlink.exe'
}
$jlink = (Resolve-Path -LiteralPath $JlinkExecutable).Path
$selectedModules = @(
    $Modules | ForEach-Object { ([string]$_).Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
)
if ($selectedModules.Count -eq 0) {
    throw 'At least one Java module is required'
}
$moduleList = [string]::Join(',', $selectedModules)
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {
    throw "Portable Java output already exists: $output"
}
$parent = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $parent | Out-Null

$arguments = @(
    '--module-path', $jmods,
    '--add-modules', $moduleList,
    '--strip-debug',
    '--no-header-files',
    '--no-man-pages',
    '--compress=2',
    '--output', $output
)
$portableJavaCreated = $false
try {
    $global:LASTEXITCODE = 0
    & $jlink @arguments
    $jlinkExitCode = if (Test-Path -LiteralPath variable:LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    if ($jlinkExitCode -ne 0) {
        throw "jlink failed with exit code $jlinkExitCode"
    }
    $javaExecutable = Join-Path $output 'bin\java.exe'
    if (-not (Test-Path -LiteralPath $javaExecutable -PathType Leaf)) {
        throw "Portable Java executable was not created: $javaExecutable"
    }
    $portableJavaCreated = $true
} finally {
    if (-not $portableJavaCreated) {
        $extendedOutput = if ($output.StartsWith('\\')) {
            '\\?\UNC\' + $output.Substring(2)
        } else {
            '\\?\' + $output
        }
        if ([System.IO.Directory]::Exists($extendedOutput)) {
            [System.IO.Directory]::Delete($extendedOutput, $true)
        } elseif ([System.IO.File]::Exists($extendedOutput)) {
            [System.IO.File]::Delete($extendedOutput)
        }
    }
}
Write-Output "Portable Java runtime created: $output"
