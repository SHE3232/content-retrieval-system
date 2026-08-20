Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-LightweightArchiveSize {
    param(
        [Parameter(Mandatory = $true)][long]$ArchiveBytes,
        [Parameter(Mandatory = $true)][long]$LimitBytes
    )

    if ($ArchiveBytes -ge $LimitBytes) {
        throw "Lightweight archive size limit exceeded: $ArchiveBytes bytes >= $LimitBytes bytes"
    }
}

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

function Remove-StagingFile {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $safePath = Resolve-StagingChildPath -Root $Root -Candidate $Path
    $extendedPath = ConvertTo-ExtendedPath -Path $safePath
    if ([System.IO.Directory]::Exists($extendedPath)) {
        throw "Expected a file but found a directory in the lightweight pruning policy: $safePath"
    }
    if ([System.IO.File]::Exists($extendedPath)) {
        [System.IO.File]::Delete($extendedPath)
    }
}

function Get-PreparedLazyImportPatch {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)]$Patch
    )

    $relativePath = [string]$Patch.relative_path
    $topLevelImport = [string]$Patch.top_level_import
    $callLine = [string]$Patch.call_line
    $targetPath = Resolve-StagingChildPath -Root $PythonRoot -Candidate (
        Join-Path $PythonRoot $relativePath
    )
    $extendedTarget = ConvertTo-ExtendedPath -Path $targetPath
    if (-not [System.IO.File]::Exists($extendedTarget)) {
        throw "Lazy import patch target file not found: $relativePath"
    }

    $utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
    $content = [System.IO.File]::ReadAllText($extendedTarget, $utf8Strict)
    $parts = [System.Text.RegularExpressions.Regex]::Split($content, '(\r\n|\n|\r)')
    $topLevelCount = 0
    $callCount = 0
    for ($index = 0; $index -lt $parts.Length; $index += 2) {
        if ($parts[$index] -ceq $topLevelImport) {
            $topLevelCount++
        }
        if ($parts[$index] -ceq $callLine) {
            $callCount++
        }
    }
    if ($topLevelCount -ne 1 -or $callCount -ne 1) {
        throw (
            "Lazy import patch requires exactly one top-level import and one call line in " +
            "${relativePath}; found import=$topLevelCount call=$callCount"
        )
    }

    $indentMatch = [System.Text.RegularExpressions.Regex]::Match($callLine, '^(\s*)\S')
    if (-not $indentMatch.Success) {
        throw "Lazy import patch call line has no executable content: $relativePath"
    }
    $localImport = $indentMatch.Groups[1].Value + $topLevelImport
    $newlineMatch = [System.Text.RegularExpressions.Regex]::Match($content, '\r\n|\n|\r')
    $preferredNewline = if ($newlineMatch.Success) {
        $newlineMatch.Value
    } else {
        [Environment]::NewLine
    }
    $builder = [System.Text.StringBuilder]::new()
    for ($index = 0; $index -lt $parts.Length; $index += 2) {
        $line = $parts[$index]
        $lineDelimiter = if ($index + 1 -lt $parts.Length) { $parts[$index + 1] } else { '' }
        if ($line -ceq $topLevelImport) {
            continue
        }
        if ($line -ceq $callLine) {
            $insertionNewline = if ([string]::IsNullOrEmpty($lineDelimiter)) {
                $preferredNewline
            } else {
                $lineDelimiter
            }
            [void]$builder.Append($localImport)
            [void]$builder.Append($insertionNewline)
        }
        [void]$builder.Append($line)
        [void]$builder.Append($lineDelimiter)
    }

    return [pscustomobject]@{
        Path = $targetPath
        Content = $builder.ToString()
    }
}

function Invoke-LightweightLazyImportPatches {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)]$Patches
    )

    $preparedPatches = @(
        foreach ($patch in @($Patches)) {
            Get-PreparedLazyImportPatch -PythonRoot $PythonRoot -Patch $patch
        }
    )
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    foreach ($preparedPatch in $preparedPatches) {
        [System.IO.File]::WriteAllText(
            (ConvertTo-ExtendedPath -Path $preparedPatch.Path),
            $preparedPatch.Content,
            $utf8WithoutBom
        )
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
                if (-not (
                    $directoryName.EndsWith('.dist-info', [System.StringComparison]::OrdinalIgnoreCase) -or
                    $directoryName.EndsWith('.egg-info', [System.StringComparison]::OrdinalIgnoreCase)
                )) {
                    return $false
                }

                $metadataPackageName = $null
                foreach ($metadataFileName in @('METADATA', 'PKG-INFO')) {
                    $metadataFile = [System.IO.Path]::Combine($_, $metadataFileName)
                    if (-not [System.IO.File]::Exists($metadataFile)) {
                        continue
                    }
                    foreach ($line in [System.IO.File]::ReadAllLines($metadataFile)) {
                        $nameHeader = [System.Text.RegularExpressions.Regex]::Match(
                            $line,
                            '^\s*Name\s*:\s*(.+?)\s*$',
                            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
                        )
                        if ($nameHeader.Success) {
                            $metadataPackageName = $nameHeader.Groups[1].Value
                            break
                        }
                    }
                    if ($null -ne $metadataPackageName) {
                        break
                    }
                }
                if ($null -eq $metadataPackageName) {
                    return $false
                }
                return (Get-NormalizedPythonPackageName -Name $metadataPackageName) -eq $normalizedPackage
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
        $metadataDestination = Resolve-StagingChildPath -Root $licenseDestination -Candidate (
            Join-Path $licenseDestination ([System.IO.Path]::GetFileName($safeMetadataDirectory))
        )
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
            $relativeFile = $safeFile.Substring($safeMetadataDirectory.Length + 1)
            $destinationFile = Resolve-StagingChildPath -Root $metadataDestination -Candidate (
                Join-Path $metadataDestination $relativeFile
            )
            [System.IO.Directory]::CreateDirectory(
                (ConvertTo-ExtendedPath -Path ([System.IO.Path]::GetDirectoryName($destinationFile)))
            ) | Out-Null
            [System.IO.File]::Copy(
                (ConvertTo-ExtendedPath -Path $safeFile),
                (ConvertTo-ExtendedPath -Path $destinationFile),
                $true
            )
        }
    }
}

function Test-PathIsSameOrDescendant {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $candidatePath = [System.IO.Path]::GetFullPath(
        (ConvertFrom-ExtendedPath -Path $Candidate)
    ).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $rootPath = [System.IO.Path]::GetFullPath(
        (ConvertFrom-ExtendedPath -Path $Root)
    ).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    if ($candidatePath.Equals($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $candidatePath.StartsWith(
        $rootPath + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Get-LightweightPrunableDirectories {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$DirectoryNames,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$PreservedRoots
    )

    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($PythonRoot)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($directory in [System.IO.Directory]::EnumerateDirectories(
            (ConvertTo-ExtendedPath -Path $current),
            '*',
            [System.IO.SearchOption]::TopDirectoryOnly
        )) {
            $safeDirectory = Resolve-StagingChildPath -Root $PythonRoot -Candidate $directory
            $directoryName = [System.IO.Path]::GetFileName($safeDirectory)
            if (
                $directoryName.EndsWith('.dist-info', [System.StringComparison]::OrdinalIgnoreCase) -or
                $directoryName.EndsWith('.egg-info', [System.StringComparison]::OrdinalIgnoreCase)
            ) {
                continue
            }

            $isPreserved = $false
            foreach ($preservedRoot in $PreservedRoots) {
                if (Test-PathIsSameOrDescendant -Candidate $safeDirectory -Root $preservedRoot) {
                    $isPreserved = $true
                    break
                }
            }
            if ($isPreserved) {
                continue
            }
            if ($DirectoryNames -contains $directoryName.ToLowerInvariant()) {
                Write-Output $safeDirectory
                continue
            }
            $pending.Push($safeDirectory)
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
    $preservedRoots = @(
        foreach ($preserveTreeValue in @($Policy.python_preserve_relative_trees)) {
            $preserveTree = [string]$preserveTreeValue
            Resolve-StagingChildPath -Root $pythonRoot -Candidate (Join-Path $pythonRoot $preserveTree)
        }
    )

    Invoke-LightweightLazyImportPatches `
        -PythonRoot $pythonRoot `
        -Patches @($Policy.python_lazy_import_patches)

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

    foreach ($relativeFileValue in @($Policy.python_remove_relative_files)) {
        $relativeFile = [string]$relativeFileValue
        $relativeFilePath = Resolve-StagingChildPath -Root $pythonRoot -Candidate (Join-Path $pythonRoot $relativeFile)
        Remove-StagingFile -Root $pythonRoot -Path $relativeFilePath
    }

    $directoryNames = @($Policy.python_remove_directory_names | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $directoriesToRemove = @(
        Get-LightweightPrunableDirectories `
            -PythonRoot $pythonRoot `
            -DirectoryNames $directoryNames `
            -PreservedRoots $preservedRoots
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
