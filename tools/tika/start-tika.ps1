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
$actual = (Get-FileHash -LiteralPath $jar -Algorithm SHA512).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
    throw "Tika server JAR SHA-512 mismatch: expected $expected, got $actual"
}

& java -jar $jar -p $Port
exit $LASTEXITCODE
