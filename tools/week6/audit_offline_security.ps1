param(
    [Parameter(Mandatory = $true)]
    [int[]]$ProcessIds,
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [Parameter(Mandatory = $true)]
    [string]$OfflineE2EJson,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [ValidateRange(1, 3600)]
    [int]$SampleSeconds = 30,
    [ValidateRange(0.1, 60)]
    [double]$SampleIntervalSeconds = 1
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-LoopbackAddress {
    param([string]$Address)
    if ([string]::IsNullOrWhiteSpace($Address)) { return $false }
    if ($Address -in @("127.0.0.1", "::1", "0.0.0.0", "::")) { return $true }
    try { return [System.Net.IPAddress]::Parse($Address).IsIPv6LinkLocal }
    catch { return $false }
}

$package = (Resolve-Path -LiteralPath $PackagePath).Path
$offlineEvidence = (Resolve-Path -LiteralPath $OfflineE2EJson).Path
$offline = Get-Content -LiteralPath $offlineEvidence -Raw | ConvertFrom-Json
$connections = New-Object System.Collections.Generic.List[object]
$deadline = [System.Diagnostics.Stopwatch]::StartNew()
while ($deadline.Elapsed.TotalSeconds -lt $SampleSeconds) {
    foreach ($connection in @(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object OwningProcess -In $ProcessIds)) {
        $connections.Add([ordered]@{
            captured_at = [DateTime]::UtcNow.ToString("o")
            process_id = [int]$connection.OwningProcess
            state = [string]$connection.State
            local_address = [string]$connection.LocalAddress
            local_port = [int]$connection.LocalPort
            remote_address = [string]$connection.RemoteAddress
            remote_port = [int]$connection.RemotePort
            remote_is_loopback = Test-LoopbackAddress ([string]$connection.RemoteAddress)
        })
    }
    Start-Sleep -Milliseconds ([int]($SampleIntervalSeconds * 1000))
}

$nonLoopback = @($connections | Where-Object {
    $_.state -eq "Established" -and -not $_.remote_is_loopback
})
$forbiddenEntries = New-Object System.Collections.Generic.List[string]
$absolutePathMatches = New-Object System.Collections.Generic.List[string]
$archive = [System.IO.Compression.ZipFile]::OpenRead($package)
try {
    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName.Replace("\", "/")
        if ($name -match '(^|/)(\.git|\.venv|data|mvp-input|logs?)(/|$)' -or
            $name -match '(?i)(credentials?|secrets?|\.env|\.pem|\.key)$') {
            $forbiddenEntries.Add($name)
        }
        if ($entry.Length -gt 0 -and $entry.Length -le 10MB -and
            $name -match '(?i)\.(txt|json|yaml|yml|ps1|py|dart|md|ini|cfg)$') {
            $reader = New-Object System.IO.StreamReader($entry.Open())
            try {
                $text = $reader.ReadToEnd()
                if ($text -match '(?i)[A-Z]:\\contentretrivalsystem\\\.worktrees\\' -or
                    $text -match '(?i)(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*["''][^"'']+["'']') {
                    $absolutePathMatches.Add($name)
                }
            }
            finally { $reader.Dispose() }
        }
    }
}
finally { $archive.Dispose() }

$checks = @(
    [ordered]@{ id = "offline_e2e"; status = $(if ($offline.status -eq "PASS") { "PASS" } else { "FAIL" }); actual = [string]$offline.status; expected = "PASS" },
    [ordered]@{ id = "non_loopback_connections"; status = $(if ($nonLoopback.Count -eq 0) { "PASS" } else { "FAIL" }); actual = $nonLoopback.Count; expected = 0 },
    [ordered]@{ id = "forbidden_package_entries"; status = $(if ($forbiddenEntries.Count -eq 0) { "PASS" } else { "FAIL" }); actual = @($forbiddenEntries); expected = @() },
    [ordered]@{ id = "package_sensitive_content"; status = $(if ($absolutePathMatches.Count -eq 0) { "PASS" } else { "FAIL" }); actual = @($absolutePathMatches); expected = @() }
)
$status = if (@($checks | Where-Object status -ne "PASS").Count -eq 0) { "PASS" } else { "FAIL" }
$result = [ordered]@{
    status = $status
    generated_at = [DateTime]::UtcNow.ToString("o")
    sample_seconds = $SampleSeconds
    process_ids = $ProcessIds
    checks = $checks
    connections = @($connections)
}
$destination = [System.IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $destination
[System.IO.Directory]::CreateDirectory($parent) | Out-Null
$temporary = Join-Path $parent (".{0}.{1}.tmp" -f [System.IO.Path]::GetFileName($destination), [Guid]::NewGuid().ToString("N"))
try {
    $result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $temporary -Encoding utf8NoBOM
    Move-Item -LiteralPath $temporary -Destination $destination -Force
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
Write-Output $destination
if ($status -ne "PASS") { exit 1 }
