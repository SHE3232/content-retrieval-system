param(
    [Parameter(Mandatory = $true)]
    [int[]]$ProcessIds,
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [Parameter(Mandatory = $true)]
    [string]$OfflineE2EJson,
    [Parameter(Mandatory = $true)]
    [string]$SecurityTestJson,
    [Parameter(Mandatory = $true)]
    [string]$NetworkProbeJson,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [ValidateSet("host-network-disabled", "firewall-outbound-block", "process-network-deny")]
    [string]$IsolationMethod = "process-network-deny",
    [switch]$NetworkIsolationEnforced,
    [ValidateRange(1, 3600)]
    [int]$SampleSeconds = 1800,
    [ValidateRange(1, 1800)]
    [int]$MinimumSampleSeconds = 1800,
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
$securityTestEvidence = (Resolve-Path -LiteralPath $SecurityTestJson).Path
$networkProbeEvidence = (Resolve-Path -LiteralPath $NetworkProbeJson).Path
$offline = Get-Content -LiteralPath $offlineEvidence -Raw | ConvertFrom-Json
$securityTests = Get-Content -LiteralPath $securityTestEvidence -Raw | ConvertFrom-Json
$networkProbe = Get-Content -LiteralPath $networkProbeEvidence -Raw | ConvertFrom-Json
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
        if ($name -match '(?i)(^|/)(\.git|\.venv|data|mvp-input|logs?|xcuserdata|[^/]+\.xcuserdatad|\.idea|\.vscode)(/|$)' -or
            $name -match '(?i)(credentials?|secrets?|\.env|\.pem|\.key|\.xcuserstate|\.DS_Store)$') {
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

$isolationPassed = (
    $NetworkIsolationEnforced.IsPresent -and
    $SampleSeconds -ge $MinimumSampleSeconds -and
    $networkProbe.status -eq "PASS" -and
    $networkProbe.blocked -eq $true
)
$packageAuditPassed = $forbiddenEntries.Count -eq 0 -and $absolutePathMatches.Count -eq 0
$checks = [ordered]@{
    network_isolation = $(if ($isolationPassed) { "PASS" } else { "FAIL" })
    offline_e2e = $(if ($offline.status -eq "PASS") { "PASS" } else { "FAIL" })
    non_loopback_connections = $(if ($nonLoopback.Count -eq 0) { "PASS" } else { "FAIL" })
    path_traversal = $(if ($securityTests.status -eq "PASS" -and $securityTests.checks.path_traversal -eq "PASS") { "PASS" } else { "FAIL" })
    reparse_point_escape = $(if ($securityTests.status -eq "PASS" -and $securityTests.checks.reparse_point_escape -eq "PASS") { "PASS" } else { "FAIL" })
    package_audit = $(if ($packageAuditPassed) { "PASS" } else { "FAIL" })
}
$checkDetails = @(
    [ordered]@{ id = "network_isolation"; status = $checks.network_isolation; actual = [ordered]@{ enforced = $NetworkIsolationEnforced.IsPresent; method = $IsolationMethod; sample_seconds = $SampleSeconds; probe_blocked = ($networkProbe.blocked -eq $true) }; expected = [ordered]@{ enforced = $true; minimum_sample_seconds = $MinimumSampleSeconds; probe_blocked = $true } },
    [ordered]@{ id = "offline_e2e"; status = $checks.offline_e2e; actual = [string]$offline.status; expected = "PASS" },
    [ordered]@{ id = "non_loopback_connections"; status = $checks.non_loopback_connections; actual = $nonLoopback.Count; expected = 0 },
    [ordered]@{ id = "path_traversal"; status = $checks.path_traversal; actual = [string]$securityTests.checks.path_traversal; expected = "PASS" },
    [ordered]@{ id = "reparse_point_escape"; status = $checks.reparse_point_escape; actual = [string]$securityTests.checks.reparse_point_escape; expected = "PASS" },
    [ordered]@{ id = "forbidden_package_entries"; status = $(if ($forbiddenEntries.Count -eq 0) { "PASS" } else { "FAIL" }); actual = @($forbiddenEntries); expected = @() },
    [ordered]@{ id = "package_sensitive_content"; status = $(if ($absolutePathMatches.Count -eq 0) { "PASS" } else { "FAIL" }); actual = @($absolutePathMatches); expected = @() }
)
$status = if (@($checks.Values | Where-Object { $_ -ne "PASS" }).Count -eq 0) { "PASS" } else { "FAIL" }
$result = [ordered]@{
    status = $status
    generated_at = [DateTime]::UtcNow.ToString("o")
    network_isolation = [ordered]@{
        enforced = $NetworkIsolationEnforced.IsPresent
        method = $IsolationMethod
        sample_seconds = $SampleSeconds
        probe_blocked = ($networkProbe.blocked -eq $true)
    }
    process_ids = $ProcessIds
    checks = $checks
    check_details = $checkDetails
    connections = [object[]]$connections
}
$destination = [System.IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $destination
[System.IO.Directory]::CreateDirectory($parent) | Out-Null
$temporary = Join-Path $parent (".{0}.{1}.tmp" -f [System.IO.Path]::GetFileName($destination), [Guid]::NewGuid().ToString("N"))
try {
    $json = $result | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText(
        $temporary,
        $json,
        (New-Object System.Text.UTF8Encoding($false))
    )
    Move-Item -LiteralPath $temporary -Destination $destination -Force
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
Write-Output $destination
if ($status -ne "PASS") { exit 1 }
