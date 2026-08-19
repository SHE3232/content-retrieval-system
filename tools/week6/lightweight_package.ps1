Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function ConvertTo-ExtendedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath.StartsWith('\\?\')) {
        return $fullPath
    }
    if ($fullPath.StartsWith('\\')) {
        return '\\?\UNC\' + $fullPath.Substring(2)
    }
    return '\\?\' + $fullPath
}

function ConvertFrom-ExtendedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ($Path.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase)) {
        return '\\' + $Path.Substring(8)
    }
    if ($Path.StartsWith('\\?\', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $Path.Substring(4)
    }
    return $Path
}

function Resolve-StagingChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    $rootPath = [System.IO.Path]::GetFullPath((ConvertFrom-ExtendedPath -Path $Root)).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $candidatePath = [System.IO.Path]::GetFullPath((ConvertFrom-ExtendedPath -Path $Candidate))
    $requiredPrefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidatePath.StartsWith($requiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes staging root '$rootPath': $candidatePath"
    }
    return $candidatePath
}

function Remove-StagingDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $safePath = Resolve-StagingChildPath -Root $Root -Candidate $Path
    $extendedPath = ConvertTo-ExtendedPath -Path $safePath
    if ([System.IO.Directory]::Exists($extendedPath)) {
        [System.IO.Directory]::Delete($extendedPath, $true)
    }
}

function Get-NormalizedPythonPackageName {
    param([Parameter(Mandatory = $true)][string]$Name)
    return ([System.Text.RegularExpressions.Regex]::Replace($Name, '[-_.]+', '-')).ToLowerInvariant()
}

function Get-PackageMetadataDirectories {
    param(
        [Parameter(Mandatory = $true)][string]$SitePackages,
        [Parameter(Mandatory = $true)][string]$PackageName
    )

    $normalizedPackage = Get-NormalizedPythonPackageName -Name $PackageName
    $extendedSitePackages = ConvertTo-ExtendedPath -Path $SitePackages
    if (-not [System.IO.Directory]::Exists($extendedSitePackages)) {
        return @()
    }

    return @(
        [System.IO.Directory]::EnumerateDirectories($extendedSitePackages, '*', [System.IO.SearchOption]::TopDirectoryOnly) |
            Where-Object {
                $directoryName = [System.IO.Path]::GetFileName($_)
                $suffix = if ($directoryName.EndsWith('.dist-info', [System.StringComparison]::OrdinalIgnoreCase)) {
                    '.dist-info'
                } elseif ($directoryName.EndsWith('.egg-info', [System.StringComparison]::OrdinalIgnoreCase)) {
                    '.egg-info'
                } else {
                    $null
                }
                if ($null -eq $suffix) {
                    return $false
                }
                $metadataStem = $directoryName.Substring(0, $directoryName.Length - $suffix.Length)
                $normalizedStem = Get-NormalizedPythonPackageName -Name $metadataStem
                return $normalizedStem -eq $normalizedPackage -or
                    $normalizedStem -match ('^' + [System.Text.RegularExpressions.Regex]::Escape($normalizedPackage) + '-(?=\d)')
            }
    )
}

function Copy-ExcludedPackageLicenses {
    param(
        [Parameter(Mandatory = $true)][string]$AppRoot,
        [Parameter(Mandatory = $true)][string]$SitePackages,
        [Parameter(Mandatory = $true)][string]$PackageName
    )

    $safeSitePackages = Resolve-StagingChildPath -Root $AppRoot -Candidate $SitePackages
    $licenseRoot = Resolve-StagingChildPath -Root $AppRoot -Candidate (
        Join-Path $AppRoot 'licenses/excluded-python-components'
    )
    $licenseDestination = Resolve-StagingChildPath -Root $licenseRoot -Candidate (Join-Path $licenseRoot $PackageName)
    $licenseFilePattern = '^(LICENSE|COPYING|NOTICE)(\..+)?$'
    foreach ($metadataDirectory in (Get-PackageMetadataDirectories -SitePackages $safeSitePackages -PackageName $PackageName)) {
        $safeMetadataDirectory = Resolve-StagingChildPath -Root $AppRoot -Candidate $metadataDirectory
        foreach ($file in [System.IO.Directory]::EnumerateFiles(
            (ConvertTo-ExtendedPath -Path $safeMetadataDirectory),
            '*',
            [System.IO.SearchOption]::AllDirectories
        )) {
            $fileName = [System.IO.Path]::GetFileName($file)
            if ($fileName -notmatch $licenseFilePattern) {
                continue
            }
            $safeFile = Resolve-StagingChildPath -Root $AppRoot -Candidate $file
            [System.IO.Directory]::CreateDirectory((ConvertTo-ExtendedPath -Path $licenseDestination)) | Out-Null
            $destinationFile = Resolve-StagingChildPath -Root $AppRoot -Candidate (Join-Path $licenseDestination $fileName)
            [System.IO.File]::Copy(
                (ConvertTo-ExtendedPath -Path $safeFile),
                (ConvertTo-ExtendedPath -Path $destinationFile),
                $true
            )
        }
    }
}

function Invoke-LightweightPythonPruning {
    param(
        [Parameter(Mandatory = $true)][string]$AppRoot,
        [Parameter(Mandatory = $true)]$Policy
    )

    $canonicalAppRoot = [System.IO.Path]::GetFullPath($AppRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $pythonRoot = Resolve-StagingChildPath -Root $canonicalAppRoot -Candidate (Join-Path $canonicalAppRoot 'runtime/python')
    $sitePackages = Resolve-StagingChildPath -Root $canonicalAppRoot -Candidate (Join-Path $pythonRoot 'Lib/site-packages')

    foreach ($packageNameValue in @($Policy.python_remove_packages)) {
        $packageName = [string]$packageNameValue
        Copy-ExcludedPackageLicenses -AppRoot $canonicalAppRoot -SitePackages $sitePackages -PackageName $packageName
        $packageDirectory = Resolve-StagingChildPath -Root $sitePackages -Candidate (Join-Path $sitePackages $packageName)
        Remove-StagingDirectory -Root $canonicalAppRoot -Path $packageDirectory
        foreach ($metadataDirectory in (Get-PackageMetadataDirectories -SitePackages $sitePackages -PackageName $packageName)) {
            Remove-StagingDirectory -Root $canonicalAppRoot -Path $metadataDirectory
        }
    }

    foreach ($relativeTreeValue in @($Policy.python_remove_relative_trees)) {
        $relativeTree = [string]$relativeTreeValue
        $relativeTreePath = Resolve-StagingChildPath -Root $pythonRoot -Candidate (Join-Path $pythonRoot $relativeTree)
        Remove-StagingDirectory -Root $canonicalAppRoot -Path $relativeTreePath
    }

    $directoryNames = @($Policy.python_remove_directory_names | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $directoriesToRemove = @(
        [System.IO.Directory]::EnumerateDirectories(
            (ConvertTo-ExtendedPath -Path $pythonRoot),
            '*',
            [System.IO.SearchOption]::AllDirectories
        ) | Where-Object {
            $directoryNames -contains ([System.IO.Path]::GetFileName($_)).ToLowerInvariant()
        } | Sort-Object Length -Descending
    )
    foreach ($directory in $directoriesToRemove) {
        Remove-StagingDirectory -Root $canonicalAppRoot -Path $directory
    }

    $fileExtensions = @($Policy.python_remove_file_extensions | ForEach-Object { ([string]$_).ToLowerInvariant() })
    foreach ($file in @(
        [System.IO.Directory]::EnumerateFiles(
            (ConvertTo-ExtendedPath -Path $pythonRoot),
            '*',
            [System.IO.SearchOption]::AllDirectories
        ) | Where-Object {
            $fileExtensions -contains [System.IO.Path]::GetExtension($_).ToLowerInvariant()
        }
    )) {
        $safeFile = Resolve-StagingChildPath -Root $canonicalAppRoot -Candidate $file
        $extendedFile = ConvertTo-ExtendedPath -Path $safeFile
        if ([System.IO.File]::Exists($extendedFile)) {
            [System.IO.File]::Delete($extendedFile)
        }
    }
}
