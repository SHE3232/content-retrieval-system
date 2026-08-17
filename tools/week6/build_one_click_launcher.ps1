[CmdletBinding()]
param(
    [string]$OutputPath,
    [string]$SourcePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $launcherName = [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String('5YaF5a655qOA57Si57O757ufLmV4ZQ==')
    )
    $OutputPath = Join-Path (Join-Path $PSScriptRoot 'bin') $launcherName
}
if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    $SourcePath = Join-Path $PSScriptRoot 'launcher\Program.cs'
}

$source = (Resolve-Path -LiteralPath $SourcePath).Path
$output = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$compilerCandidates = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$compiler = $compilerCandidates | Where-Object {
    Test-Path -LiteralPath $_ -PathType Leaf
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($compiler)) {
    throw 'C# compiler was not found in the Windows .NET Framework directories'
}

& $compiler /nologo /target:winexe /platform:x64 "/out:$output" $source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "One-click launcher build failed with exit code $LASTEXITCODE"
}
Write-Output "One-click launcher created: $output"
