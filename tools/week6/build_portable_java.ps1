[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$JavaHome,
    [string]$JlinkExecutable
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
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {
    throw "Portable Java output already exists: $output"
}
$parent = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $parent | Out-Null

$arguments = @(
    '--module-path', $jmods,
    '--add-modules', 'ALL-MODULE-PATH',
    '--strip-debug',
    '--no-header-files',
    '--no-man-pages',
    '--compress=2',
    '--output', $output
)
& $jlink @arguments
$jlinkExitCode = if (Test-Path -LiteralPath variable:LASTEXITCODE) { $LASTEXITCODE } else { 0 }
if ($jlinkExitCode -ne 0) {
    throw "jlink failed with exit code $jlinkExitCode"
}
$javaExecutable = Join-Path $output 'bin\java.exe'
if (-not (Test-Path -LiteralPath $javaExecutable -PathType Leaf)) {
    throw "Portable Java executable was not created: $javaExecutable"
}
Write-Output "Portable Java runtime created: $output"
