# Week 6 Windows Lightweight Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a separately named Windows ZIP smaller than 1,000,000,000 bytes while retaining both local models, Tika, five-format ingestion, local Chroma retrieval, and offline startup.

**Architecture:** Keep the existing complete-package path unchanged and add an explicit `lightweight` package profile. Store the audited pruning policy in JSON, apply it only to the temporary staging tree, build a minimal Java image with the existing jlink wrapper, generate the manifest after pruning, and reject an oversized temporary ZIP before it reaches the delivery directory. Build the final archive from the exact application commit `b8180477ade5829f551e2c55922a54500f142c1e`; the packaging-tool branch is separate because packaging code is not shipped inside `app/`.

**Tech Stack:** PowerShell 5.1, Python 3.10/pytest, .NET `System.IO.Compression`, Java 23 `jlink`, Flutter Windows release, local Sentence Transformers/MobileCLIP models, Apache Tika, ChromaDB.

---

## File map

- Create `tools/week6/lightweight_package_profile.json`: versioned exclusions, Java module list, and the strict byte limit.
- Create `tools/week6/lightweight_package.ps1`: staging-only pruning, license preservation, and canonical child-path guards.
- Modify `tools/week6/build_portable_java.ps1`: accept an explicit module list while preserving the current `ALL-MODULE-PATH` default.
- Modify `tools/week6/package_stable_build.ps1`: add the profile switch, call the helper, write profile metadata, and enforce the archive-size gate.
- Modify `tools/week6/tests/test_powershell_tools.py`: red/green coverage for pruning, required-file retention, jlink selection, manifest metadata, output naming, and the strict byte limit.
- Modify `docs/week6/README.md`: document the lightweight artifact and verification command without changing the three submitted DOCX reports.

### Task 1: Lock the lightweight policy with a failing packaging test

**Files:**
- Create: `tools/week6/lightweight_package_profile.json`
- Modify: `tools/week6/tests/test_powershell_tools.py:382-595`

- [ ] **Step 1: Add a fixture helper that creates removable and required runtime files**

Add this helper immediately before `test_package_stable_build_uses_whitelist_and_records_commit`:

```python
def _add_lightweight_runtime_fixture(runtime: Path, java_runtime: Path) -> None:
    site = runtime / "Lib" / "site-packages"
    required = site / "sentence_transformers"
    required.mkdir(parents=True)
    (required / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    torch_lib = site / "torch" / "lib"
    torch_lib.mkdir(parents=True)
    (torch_lib / "torch_cpu.dll").write_bytes(b"runtime-dll")
    (torch_lib / "torch_cpu.lib").write_bytes(b"linker-only")
    (site / "torch" / "include").mkdir(parents=True)
    (site / "torch" / "include" / "torch.h").write_text("header\n", encoding="utf-8")
    for package in ("pycocoevalcap", "clip_benchmark", "datasets", "pyarrow", "pandas"):
        package_root = site / package
        package_root.mkdir(parents=True)
        (package_root / "payload.bin").write_bytes(b"evaluation-only")
        dist_info = site / f"{package}-1.0.dist-info"
        licenses = dist_info / "licenses"
        licenses.mkdir(parents=True)
        (licenses / "LICENSE").write_text(f"{package} license\n", encoding="utf-8")
    cache = required / "__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"cache")
    tests = required / "tests"
    tests.mkdir()
    (tests / "test_model.py").write_text("assert True\n", encoding="utf-8")

    jlink = java_runtime / "bin" / "jlink.ps1"
    jlink.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)\n"
        "$index=[Array]::IndexOf($Rest,'--output')\n"
        "if($index -lt 0){exit 2}\n"
        "$out=$Rest[$index+1]\n"
        "New-Item -ItemType Directory -Force -Path (Join-Path $out 'bin') | Out-Null\n"
        "[IO.File]::WriteAllText((Join-Path $out 'bin/java.exe'),'java')\n",
        encoding="utf-8",
    )
    (java_runtime / "jmods").mkdir()
    (java_runtime / "jmods" / "java.base.jmod").write_bytes(b"jmod")
```

- [ ] **Step 2: Write the failing lightweight-profile test**

Parameterize the existing whitelist test by adding this decorator:

```python
@pytest.mark.parametrize("package_profile", ["complete", "lightweight"])
```

Add `package_profile: str` after the existing `tmp_path: Path` argument in the function signature.

Immediately after the existing Java fixture is created, insert:

```python
if package_profile == "lightweight":
    _add_lightweight_runtime_fixture(runtime, java_runtime)
```

Change the existing command literal to a `command` variable, append these exact arguments, then call `_run(command, tmp_path)`:

```python
command.extend(["-PackageProfile", package_profile])
if package_profile == "lightweight":
    command.extend(["-JlinkExecutable", str(java_runtime / "bin" / "jlink.ps1")])
```

```python
assert result.returncode == 0, result.stdout + result.stderr
with ZipFile(output) as archive:
    names = {name.replace("\\", "/") for name in archive.namelist()}
    assert "app/runtime/python/Lib/site-packages/sentence_transformers/__init__.py" in names
    assert "app/runtime/python/Lib/site-packages/torch/lib/torch_cpu.dll" in names
    assert "app/runtime/java/bin/java.exe" in names
    assert not any("pycocoevalcap" in name for name in names)
    assert not any("clip_benchmark" in name for name in names)
    assert not any("/datasets/" in name for name in names)
    assert not any("/pyarrow/" in name for name in names)
    assert not any("/pandas/" in name for name in names)
    assert not any("/__pycache__/" in name for name in names)
    assert not any("/tests/" in name for name in names)
    assert not any(name.endswith(".lib") for name in names)
    assert "app/licenses/excluded-python-components/pycocoevalcap/LICENSE" in names
    manifest = json.loads(archive.read("app/PACKAGE_MANIFEST.json"))
    assert manifest["package_profile"] == "lightweight"
    assert manifest["archive_size_limit_bytes"] == 1_000_000_000
    assert manifest["pruning_policy_version"] == "1"
    assert manifest["java_runtime_mode"] == "jlink"
```

- [ ] **Step 3: Run the test and verify the red state**

Run:

```powershell
$env:TEMP='F:\contentretrivalsystem\tmp'
$env:TMP='F:\contentretrivalsystem\tmp'
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest `
  tools/week6/tests/test_powershell_tools.py -k lightweight_profile -vv
```

Expected: FAIL because `package_stable_build.ps1` does not accept `-PackageProfile` and no pruning occurs.

- [ ] **Step 4: Add the exact policy file**

Create `tools/week6/lightweight_package_profile.json` with this complete content:

```json
{
  "schema_version": 1,
  "profile": "lightweight",
  "pruning_policy_version": "1",
  "archive_size_limit_bytes": 1000000000,
  "python_remove_packages": [
    "pycocoevalcap",
    "clip_benchmark",
    "datasets",
    "pandas",
    "pyarrow",
    "pytest",
    "_pytest",
    "pytest_cov",
    "coverage",
    "pip",
    "setuptools",
    "reportlab",
    "pygments",
    "hf_xet",
    "onnxruntime",
    "kubernetes",
    "sympy",
    "torchgen"
  ],
  "python_remove_directory_names": ["__pycache__", "tests", "test", "testing"],
  "python_remove_file_extensions": [".pyc", ".pyo", ".lib"],
  "python_remove_relative_trees": ["Lib/test", "Lib/ensurepip", "Lib/site-packages/torch/include"],
  "java_modules": [
    "java.base",
    "java.desktop",
    "java.logging",
    "java.management",
    "java.naming",
    "java.net.http",
    "java.sql",
    "java.xml",
    "jdk.crypto.ec",
    "jdk.unsupported"
  ]
}
```

- [ ] **Step 5: Commit the red test and policy**

```powershell
git add tools/week6/tests/test_powershell_tools.py tools/week6/lightweight_package_profile.json
git commit -m "test(week6): specify lightweight package profile"
```

### Task 2: Implement staging-only pruning and minimal Java generation

**Files:**
- Create: `tools/week6/lightweight_package.ps1`
- Modify: `tools/week6/build_portable_java.ps1:1-55`
- Modify: `tools/week6/package_stable_build.ps1:1-371`
- Test: `tools/week6/tests/test_powershell_tools.py`

- [ ] **Step 1: Create the guarded pruning helper**

Create `tools/week6/lightweight_package.ps1` with functions having these exact interfaces:

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-StagingChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $candidatePath = [IO.Path]::GetFullPath($Candidate)
    if (-not $candidatePath.StartsWith(
        $rootPath + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Lightweight pruning target escapes staging root: $candidatePath"
    }
    return $candidatePath
}

function Remove-StagingDirectory {
    param([string]$Root, [string]$Path)
    $target = Resolve-StagingChildPath -Root $Root -Candidate $Path
    if ([IO.Directory]::Exists($target)) {
        [IO.Directory]::Delete($target, $true)
    }
}

function Copy-ExcludedPackageLicenses {
    param([string]$AppRoot, [string]$SitePackages, [string]$PackageName)
    $licenseRoot = Join-Path $AppRoot "licenses/excluded-python-components/$PackageName"
    $distInfos = @(Get-ChildItem -LiteralPath $SitePackages -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match ('^(?i)' + [regex]::Escape($PackageName).Replace('_', '[-_.]') + '[-_.].*\.dist-info$') })
    foreach ($distInfo in $distInfos) {
        foreach ($license in @(Get-ChildItem -LiteralPath $distInfo.FullName -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(?i)(LICENSE|COPYING|NOTICE)' })) {
            [IO.Directory]::CreateDirectory($licenseRoot) | Out-Null
            Copy-Item -LiteralPath $license.FullName -Destination (Join-Path $licenseRoot $license.Name) -Force
        }
    }
}

function Invoke-LightweightPythonPruning {
    param(
        [Parameter(Mandatory = $true)][string]$AppRoot,
        [Parameter(Mandatory = $true)][pscustomobject]$Policy
    )
    $runtime = Resolve-StagingChildPath -Root $AppRoot -Candidate (Join-Path $AppRoot 'runtime/python')
    $site = Resolve-StagingChildPath -Root $AppRoot -Candidate (Join-Path $runtime 'Lib/site-packages')
    foreach ($package in @($Policy.python_remove_packages)) {
        Copy-ExcludedPackageLicenses -AppRoot $AppRoot -SitePackages $site -PackageName ([string]$package)
        Remove-StagingDirectory -Root $AppRoot -Path (Join-Path $site ([string]$package))
        foreach ($metadata in @(Get-ChildItem -LiteralPath $site -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match ('^(?i)' + [regex]::Escape([string]$package).Replace('_', '[-_.]') + '[-_.].*\.(dist-info|egg-info)$') })) {
            Remove-StagingDirectory -Root $AppRoot -Path $metadata.FullName
        }
    }
    foreach ($relativeTree in @($Policy.python_remove_relative_trees)) {
        Remove-StagingDirectory -Root $AppRoot -Path (Join-Path $runtime ([string]$relativeTree))
    }
    $directories = @([IO.Directory]::EnumerateDirectories($runtime, '*', [IO.SearchOption]::AllDirectories) |
        Sort-Object Length -Descending)
    foreach ($directory in $directories) {
        if ([IO.Path]::GetFileName($directory) -in @($Policy.python_remove_directory_names)) {
            Remove-StagingDirectory -Root $AppRoot -Path $directory
        }
    }
    foreach ($file in @([IO.Directory]::EnumerateFiles($runtime, '*', [IO.SearchOption]::AllDirectories))) {
        if ([IO.Path]::GetExtension($file) -in @($Policy.python_remove_file_extensions)) {
            $safeFile = Resolve-StagingChildPath -Root $AppRoot -Candidate $file
            [IO.File]::Delete($safeFile)
        }
    }
}
```

- [ ] **Step 2: Extend the existing jlink wrapper without changing its default**

Add `[string[]]$Modules = @('ALL-MODULE-PATH')` to `build_portable_java.ps1`, validate it is non-empty, and replace the hard-coded module argument with:

```powershell
$moduleList = ($Modules | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ','
if ([string]::IsNullOrWhiteSpace($moduleList)) {
    throw 'At least one Java module is required'
}
$arguments = @(
    '--module-path', $jmods,
    '--add-modules', $moduleList,
    '--strip-debug',
    '--no-header-files',
    '--no-man-pages',
    '--compress=2',
    '--output', $output
)
```

- [ ] **Step 3: Integrate the profile into the package script**

Add parameters and profile loading:

```powershell
[ValidateSet('complete', 'lightweight')]
[string]$PackageProfile = 'complete',
[long]$ArchiveSizeLimitBytes = 0,
[string]$LightweightProfilePath,
[string]$JlinkExecutable
```

After resolving `$repository`, load the policy only for the lightweight profile:

```powershell
$lightweightPolicy = $null
if ($PackageProfile -eq 'lightweight') {
    if ([string]::IsNullOrWhiteSpace($LightweightProfilePath)) {
        $LightweightProfilePath = Join-Path $PSScriptRoot 'lightweight_package_profile.json'
    }
    $policyFile = Resolve-RequiredFile -Path $LightweightProfilePath -Label 'Lightweight package profile'
    $lightweightPolicy = Get-Content -Raw -LiteralPath $policyFile | ConvertFrom-Json
    if ($ArchiveSizeLimitBytes -eq 0) {
        $ArchiveSizeLimitBytes = [long]$lightweightPolicy.archive_size_limit_bytes
    }
    if ($ArchiveSizeLimitBytes -le 0) {
        throw 'ArchiveSizeLimitBytes must be positive for a lightweight package'
    }
    . (Join-Path $PSScriptRoot 'lightweight_package.ps1')
}
```

After `$javaRuntime` is resolved, select the actual jlink executable:

```powershell
$resolvedJlink = if ([string]::IsNullOrWhiteSpace($JlinkExecutable)) {
    Resolve-RequiredFile -Path (Join-Path $javaRuntime 'bin/jlink.exe') -Label 'jlink executable'
} else {
    Resolve-RequiredFile -Path $JlinkExecutable -Label 'jlink executable'
}
```

Choose the new default output name only in lightweight mode, call `build_portable_java.ps1` instead of copying the full JDK, and prune after all inputs are copied but before the manifest is generated:

```powershell
$defaultArchiveName = if ($PackageProfile -eq 'lightweight') {
    '01_Windows轻量集成稳定版.zip'
} else {
    '01_Windows完整集成稳定版.zip'
}

if ($PackageProfile -eq 'lightweight') {
    & (Join-Path $PSScriptRoot 'build_portable_java.ps1') `
        -OutputDirectory (Join-Path $appRoot 'runtime/java') `
        -JavaHome $javaRuntime `
        -JlinkExecutable $resolvedJlink `
        -Modules @($lightweightPolicy.java_modules)
    if ($LASTEXITCODE -ne 0) { throw 'Lightweight Java runtime build failed' }
} else {
    Copy-DirectoryContents -Source $javaRuntime -Destination (Join-Path $appRoot 'runtime/java')
}

if ($PackageProfile -eq 'lightweight') {
    Invoke-LightweightPythonPruning -AppRoot $appRoot -Policy $lightweightPolicy
}
```

Set these manifest values:

```powershell
package_profile = $PackageProfile
archive_size_limit_bytes = $(if ($PackageProfile -eq 'lightweight') { $ArchiveSizeLimitBytes } else { $null })
pruning_policy_version = $(if ($PackageProfile -eq 'lightweight') { [string]$lightweightPolicy.pruning_policy_version } else { $null })
excluded_runtime_components = $(if ($PackageProfile -eq 'lightweight') { @($lightweightPolicy.python_remove_packages) } else { @() })
java_runtime_mode = $(if ($PackageProfile -eq 'lightweight') { 'jlink' } else { 'bundled' })
```

- [ ] **Step 4: Run the focused test and verify green**

Run the Task 1 command again. Expected: the lightweight test passes and required runtime markers remain in the ZIP.

- [ ] **Step 5: Run the full packaging test file**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest `
  tools/week6/tests/test_powershell_tools.py -q
```

Expected: `12 passed`; the existing complete-package case still reports `java_runtime_mode == "bundled"`.

- [ ] **Step 6: Commit the implementation**

```powershell
git add tools/week6/lightweight_package.ps1 tools/week6/build_portable_java.ps1 `
  tools/week6/package_stable_build.ps1 tools/week6/tests/test_powershell_tools.py
git commit -m "feat(week6): add lightweight package profile"
```

### Task 3: Add the strict pre-delivery size gate

**Files:**
- Modify: `tools/week6/tests/test_powershell_tools.py`
- Modify: `tools/week6/package_stable_build.ps1:355-371`

- [ ] **Step 1: Write a failing size-limit test**

Add `test_lightweight_package_rejects_archive_at_or_above_limit`. Construct the same minimal release/backend/runtime/java/models/tools paths as the parameterized package test, call `_add_lightweight_runtime_fixture(runtime, java_runtime)`, and invoke the package script with `-PackageProfile lightweight`, `-JlinkExecutable str(java_runtime / "bin" / "jlink.ps1")`, and `-ArchiveSizeLimitBytes 128`. Assert:

```python
assert result.returncode != 0
assert "archive size limit" in (result.stdout + result.stderr).lower()
assert not output.exists()
assert not staging.exists() or not any(staging.iterdir())
```

- [ ] **Step 2: Run the single test and verify red**

Expected: FAIL because the script currently moves the temporary ZIP without checking its length.

- [ ] **Step 3: Enforce the limit before the final move**

Immediately after `New-ZipFromDirectory` and before `Move-Item`, add:

```powershell
if ($PackageProfile -eq 'lightweight') {
    $archiveBytes = [IO.FileInfo]::new($temporaryZip).Length
    if ($archiveBytes -ge $ArchiveSizeLimitBytes) {
        throw "Lightweight archive size limit exceeded: $archiveBytes bytes >= $ArchiveSizeLimitBytes bytes"
    }
}
Move-Item -LiteralPath $temporaryZip -Destination $absoluteOutput
```

Include the byte count in normal output:

```powershell
$archiveBytes = [IO.FileInfo]::new($absoluteOutput).Length
Write-Output "Archive bytes: $archiveBytes"
```

- [ ] **Step 4: Verify red-to-green and full regression**

Run the single size test, then the complete `test_powershell_tools.py` file. Expected: the single test passes, followed by `13 passed` with no skipped packaging tests.

- [ ] **Step 5: Commit**

```powershell
git add tools/week6/package_stable_build.ps1 tools/week6/tests/test_powershell_tools.py
git commit -m "fix(week6): reject oversized lightweight archives"
```

### Task 4: Document and statically verify the delivery flow

**Files:**
- Modify: `docs/week6/README.md`
- Test: `tools/week6/tests/test_powershell_tools.py`

- [ ] **Step 1: Add the exact lightweight build contract to the README**

Document that the original complete ZIP remains authoritative, the new filename is `01_Windows轻量集成稳定版.zip`, the byte gate is strict decimal bytes, both models remain embedded, and the lightweight build uses the application source commit recorded in its manifest.

- [ ] **Step 2: Run static checks**

```powershell
git diff --check
Select-String -LiteralPath tools/week6/package_stable_build.ps1 `
  -Pattern 'PackageProfile|ArchiveSizeLimitBytes|Invoke-LightweightPythonPruning'
Select-String -LiteralPath docs/week6/README.md `
  -Pattern '1,000,000,000|01_Windows轻量集成稳定版.zip'
```

Expected: `git diff --check` exits 0 and both searches return matches.

- [ ] **Step 3: Commit**

```powershell
git add docs/week6/README.md
git commit -m "docs(week6): document lightweight stable package"
```

### Task 5: Build the real lightweight candidate from the exact application commit

**Files:**
- Read: `F:\contentretrivalsystem\output\week6\第六周最终提交_请上传这4项\01_Windows完整集成稳定版.zip`
- Create: detached source worktree `F:\contentretrivalsystem\.worktrees\week6-lightweight-source-b818`
- Create: candidate ZIP under that worktree's `output/week6/lightweight-candidate/`

- [ ] **Step 1: Record the original package identity**

```powershell
$fullZip='F:\contentretrivalsystem\output\week6\第六周最终提交_请上传这4项\01_Windows完整集成稳定版.zip'
$fullBefore=Get-Item -LiteralPath $fullZip
$fullHashBefore=(Get-FileHash -Algorithm SHA256 -LiteralPath $fullZip).Hash.ToLowerInvariant()
```

- [ ] **Step 2: Create and verify the detached source worktree**

```powershell
$sourceWt='F:\contentretrivalsystem\.worktrees\week6-lightweight-source-b818'
git worktree add --detach $sourceWt b8180477ade5829f551e2c55922a54500f142c1e
git -C $sourceWt status --porcelain=v1 --untracked-files=all
```

Expected: the status output is empty and `HEAD` equals `b8180477ade5829f551e2c55922a54500f142c1e`.

- [ ] **Step 3: Verify reusable extracted assets**

Use the already validated short-path extraction from the complete package:

```powershell
$assets='F:\w6xb81\app'
Get-Item -LiteralPath `
  "$assets\frontend\content_retrieval_app.exe", `
  "$assets\runtime\python\python.exe", `
  "$assets\runtime\java\bin\java.exe", `
  "$assets\runtime\java\bin\jlink.exe", `
  "$assets\runtime\java\jmods", `
  "$assets\models\model-manifest.json", `
  "$assets\tools\tika\tika-server-standard-3.3.1.jar"
```

Expected: every path resolves. If `F:\w6xb81` is absent, re-extract the unchanged complete ZIP to a new short F-drive path and first verify its manifest/file count.

- [ ] **Step 4: Run all packaging tests immediately before the real build**

Run the full `test_powershell_tools.py` command from the feature worktree. Expected: `13 passed`.

- [ ] **Step 5: Build the candidate**

Invoke the feature-branch packaging tool against the detached b818 source tree:

```powershell
$toolWt='F:\contentretrivalsystem\.worktrees\week6-lightweight-package'
$candidate=Join-Path $sourceWt 'output\week6\lightweight-candidate\01_Windows轻量集成稳定版.zip'
$env:TEMP='F:\contentretrivalsystem\tmp'
$env:TMP='F:\contentretrivalsystem\tmp'
& "$toolWt\tools\week6\package_stable_build.ps1" `
  -RepositoryRoot $sourceWt `
  -SourceCommit 'b8180477ade5829f551e2c55922a54500f142c1e' `
  -FrontendReleaseDir "$assets\frontend" `
  -PythonRuntimeDir "$assets\runtime\python" `
  -JavaRuntimeDir "$assets\runtime\java" `
  -ModelRoot "$assets\models" `
  -ModelManifestPath "$assets\models\model-manifest.json" `
  -TikaJar "$assets\tools\tika\tika-server-standard-3.3.1.jar" `
  -TikaChecksumFile "$assets\tools\tika\tika-server-standard-3.3.1.jar.sha512" `
  -MvpLauncher "$sourceWt\tools\start-mvp.ps1" `
  -IntegratedLauncher "$sourceWt\tools\week6\start-integrated.ps1" `
  -ThirdPartySourceDir "$sourceWt\third_party\mobileclip-src" `
  -PackageProfile lightweight `
  -OutputZip $candidate
```

Expected: exit 0, `Archive bytes` is below 1,000,000,000, and the output is only in the candidate directory.

### Task 6: Verify the candidate before copying it to the final directory

**Files:**
- Read: candidate ZIP
- Create: short audit extraction such as `F:\w6light-audit\app`
- Create: audit evidence JSON under `F:\contentretrivalsystem\tmp\week6-lightweight-evidence\`

- [ ] **Step 1: Perform read-only archive and manifest audit**

Run this read-only PowerShell audit:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$candidateInfo=Get-Item -LiteralPath $candidate
if($candidateInfo.Length -ge 1000000000){throw "Oversized archive: $($candidateInfo.Length)"}
$stream=[IO.File]::OpenRead($candidate)
$archive=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Read)
try {
  $entry=$archive.GetEntry('app/PACKAGE_MANIFEST.json')
  if($null -eq $entry){throw 'Package manifest missing'}
  $reader=[IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
  try {$manifest=$reader.ReadToEnd() | ConvertFrom-Json} finally {$reader.Dispose()}
  if($manifest.source_commit -ne 'b8180477ade5829f551e2c55922a54500f142c1e'){throw 'Source commit mismatch'}
  if($manifest.package_profile -ne 'lightweight'){throw 'Package profile mismatch'}
  if($manifest.first_run_downloads -ne $false){throw 'Unexpected first-run downloads'}
  if($manifest.java_runtime_mode -ne 'jlink'){throw 'Java runtime mode mismatch'}
  if(([int]$manifest.files.Count + 1) -ne $archive.Entries.Count){throw 'Manifest count mismatch'}
} finally {$archive.Dispose();$stream.Dispose()}
```

This proves:

```text
archive.Length < 1000000000
manifest.source_commit == b8180477ade5829f551e2c55922a54500f142c1e
manifest.package_profile == lightweight
manifest.first_run_downloads == false
manifest.java_runtime_mode == jlink
manifest.files.Count + 1 == archive.Entries.Count
```

Also assert both model files, both launchers, `torch_cpu.dll`, Tika, and `runtime/java/bin/java.exe` exist, while every configured excluded component is absent.

- [ ] **Step 2: Extract to a verified short F-drive path**

Resolve `F:\w6light-audit`, verify it is the exact intended temporary target, remove only that target if it is a prior audit directory, then extract the candidate. Compare extracted file count to archive entry count.

- [ ] **Step 3: Run both packaged preflight paths**

```powershell
& 'F:\w6light-audit\app\内容检索系统.exe' --check-only
& 'F:\w6light-audit\app\启动应用.ps1' -PackageRoot 'F:\w6light-audit\app' -CheckOnly
```

Expected: both exit 0 and report the packaged Python, Java, model manifest, Tika, and frontend paths.

- [ ] **Step 4: Start the packaged backend and run five-format E2E**

Start `app/tools/start-mvp.ps1` in a long-running execution session with explicit packaged paths and an unused local port. From a second command run:

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' `
  'F:\contentretrivalsystem\.worktrees\week6-lightweight-package\tools\week5\run_real_five_format_e2e.py' `
  --base-url 'http://127.0.0.1:18765' `
  --output 'F:\contentretrivalsystem\tmp\week6-lightweight-evidence\five-format.json'
```

Expected: JSON status `PASS`, five indexed files, keyword hits for TXT/PDF/DOCX, image-semantic top hits for JPG/PNG, and reindex/remove mutations `PASS`. Stop the owned backend/Tika process tree after the run.

- [ ] **Step 5: Run explicit real-model imports from the package**

With `PYTHONPATH=F:\w6light-audit\app\backend\src`, run packaged Python to construct `build_local_runtime` with the packaged model root and a new F-drive data directory. Encode one text query and one image query, assert dimensions 384 and 512, then close the runtime.

- [ ] **Step 6: Re-run the existing package security content audit**

Run `audit_offline_security.ps1` with the new ZIP and fresh lightweight E2E/security evidence. Do not claim a new enforced-network-isolation result unless the process deny/firewall probe is actually enforced; retain the already passed b818 offline-security evidence for unchanged application behavior and report the lightweight-package process audit separately.

- [ ] **Step 7: Copy only the verified candidate to the final directory**

Before copying, recompute the original complete ZIP size/hash and assert they equal `$fullBefore.Length` and `$fullHashBefore`. Then copy the candidate as the new, separately named file:

```powershell
$finalLight='F:\contentretrivalsystem\output\week6\第六周最终提交_请上传这4项\01_Windows轻量集成稳定版.zip'
if (Test-Path -LiteralPath $finalLight) { throw "Refusing to overwrite: $finalLight" }
Copy-Item -LiteralPath $candidate -Destination $finalLight
```

- [ ] **Step 8: Fresh final verification**

Run `Get-Item`, `Get-FileHash -Algorithm SHA256`, ZIP open/read, exact byte comparison, manifest audit, and `git status --short` in both worktrees. Record the final byte count, MiB, SHA-256, source commit, test count, and any limitation. Do not report completion if any fresh command fails.

### Task 7: Review and finish the implementation branch

**Files:**
- Review: all commits after `a74972b`

- [ ] **Step 1: Run the complete focused regression suite again**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest `
  tools/week6/tests/test_powershell_tools.py -q
git diff b8180477ade5829f551e2c55922a54500f142c1e..HEAD --check
```

- [ ] **Step 2: Inspect the branch diff and ensure only planned files changed**

```powershell
git diff --stat b8180477ade5829f551e2c55922a54500f142c1e..HEAD
git status --short
```

Expected: clean worktree; only the design, plan, policy, helper, packaging scripts, tests, and Week 6 README differ.

- [ ] **Step 3: Invoke `superpowers:verification-before-completion`**

Re-run the exact archive, manifest, preflight, model, five-format, test, size, and hash commands immediately before the final response. Claims must quote those fresh results.

- [ ] **Step 4: Invoke `superpowers:finishing-a-development-branch`**

Present merge/keep/cleanup choices for `codex/week6-lightweight-package`; do not merge or delete the branch without the user's choice.
