param(
    [ValidateRange(1, 65535)]
    [int]$Port = 9998
)

$ErrorActionPreference = "Stop"

$version = "3.3.1"
$jar = Join-Path $PSScriptRoot "tika-server-standard-$version.jar"
$checksumFile = "$jar.sha512"

if (-not (Test-Path -LiteralPath $jar -PathType Leaf)) {
    throw "Tika server JAR not found: $jar"
}
if (-not (Test-Path -LiteralPath $checksumFile -PathType Leaf)) {
    throw "Tika checksum file not found: $checksumFile"
}

$expected = (Get-Content -LiteralPath $checksumFile -Raw).Trim().ToLowerInvariant()
if ($expected -notmatch '^[0-9a-f]{128}$') {
    throw "Tika checksum file must contain one lowercase SHA-512 digest"
}
$stream = [System.IO.File]::OpenRead($jar)
$sha512 = [System.Security.Cryptography.SHA512]::Create()
try {
    $hash = $sha512.ComputeHash($stream)
    $actual = [System.BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant()
}
finally {
    $sha512.Dispose()
    $stream.Dispose()
}
if ($actual -ne $expected) {
    throw "Tika server JAR SHA-512 mismatch: expected $expected, got $actual"
}

& java -jar $jar -p $Port
exit $LASTEXITCODE
