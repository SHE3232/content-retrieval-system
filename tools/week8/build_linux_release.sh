#!/usr/bin/env bash
set -euo pipefail

repo="${REPOSITORY_ROOT:-$(pwd)}"
source_commit="${SOURCE_COMMIT:-}"
flutter_sdk="${FLUTTER_SDK:-}"
source_models="${SOURCE_MODEL_ROOT:-}"
source_manifest="${SOURCE_MODEL_MANIFEST:-}"
linux_jdk="${LINUX_JDK_DIR:-}"
tika_jar_source="${TIKA_JAR:-$repo/tools/tika/tika-server-standard-3.3.1.jar}"
tika_checksum_source="${TIKA_CHECKSUM_FILE:-$tika_jar_source.sha512}"
output_root="${OUTPUT_ROOT:-}"
working_root="${WORKING_ROOT:-/mnt/f/contentretrivalsystem/.tmp/week8/linux-release}"
evidence_dir="${EVIDENCE_DIR:-$repo/docs/week8/evidence/platform/linux}"
uv_bin="${UV_BIN:-$HOME/.local/bin/uv}"
archive_limit="${ARCHIVE_SIZE_LIMIT_BYTES:-2500000000}"
skip_flutter_build="${SKIP_FLUTTER_BUILD:-0}"
run_root=""

cleanup() {
  if [[ -n "$run_root" && -d "$run_root" ]]; then
    case "$run_root" in
      "$working_root"/*) rm -rf -- "$run_root" ;;
      *) printf 'Refusing unsafe cleanup path: %s\n' "$run_root" >&2 ;;
    esac
  fi
}
trap cleanup EXIT

require_file() {
  [[ -f "$1" ]] || { printf '%s not found: %s\n' "$2" "$1" >&2; exit 1; }
}

require_dir() {
  [[ -d "$1" ]] || { printf '%s not found: %s\n' "$2" "$1" >&2; exit 1; }
}

[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'SOURCE_COMMIT must be a full 40-character lowercase hash\n' >&2
  exit 1
}
[[ "$archive_limit" =~ ^[0-9]+$ && "$archive_limit" -gt 0 ]] || {
  printf 'ARCHIVE_SIZE_LIMIT_BYTES must be positive\n' >&2
  exit 1
}

repo="$(realpath "$repo")"
[[ "$(git -C "$repo" rev-parse --is-inside-work-tree)" == true ]] || {
  printf 'Repository root is not a Git worktree: %s\n' "$repo" >&2
  exit 1
}
head_commit="$(git -C "$repo" rev-parse HEAD)"
[[ "$head_commit" == "$source_commit" ]] || {
  printf 'Source commit mismatch: expected %s, got %s\n' "$head_commit" "$source_commit" >&2
  exit 1
}
dirty="$(cd "$repo" && git status --porcelain=v1 --untracked-files=all)"
[[ -z "$dirty" ]] || {
  printf 'Worktree is not clean:\n%s\n' "$dirty" >&2
  exit 1
}

for legal in LICENSE NOTICE THIRD_PARTY_NOTICES.md; do
  require_file "$repo/$legal" "Legal file $legal"
done
require_file "$repo/tools/week8/build_public_model_root.py" 'Public model builder'
require_file "$repo/tools/week8/validate_linux_release.py" 'Linux archive validator'
require_file "$tika_jar_source" 'Tika server JAR'
require_file "$tika_checksum_source" 'Tika checksum'
if grep -Eq '^name = "(cuda-|nvidia-|triton")' "$repo/backend/uv.lock"; then
  printf 'Backend lock contains a CUDA/NVIDIA runtime and is not valid for the public CPU package\n' >&2
  exit 1
fi

require_dir "$flutter_sdk" 'Flutter Linux SDK'
require_file "$flutter_sdk/bin/flutter" 'Flutter executable'
require_dir "$source_models" 'Source model root'
require_file "$source_manifest" 'Source model manifest'
require_dir "$linux_jdk" 'Linux OpenJDK'
require_file "$linux_jdk/bin/jlink" 'Linux jlink executable'
require_file "$linux_jdk/release" 'Linux OpenJDK release metadata'
grep -q '^IMPLEMENTOR="Eclipse Adoptium"' "$linux_jdk/release" || {
  printf 'Linux JDK must be the approved Eclipse Adoptium runtime\n' >&2
  exit 1
}
require_file "$uv_bin" 'uv executable'
[[ -n "$output_root" ]] || {
  printf 'OUTPUT_ROOT is required\n' >&2
  exit 1
}

export PATH="$flutter_sdk/bin:$PATH"
export PUB_CACHE="${PUB_CACHE:-/mnt/f/contentretrivalsystem/.tmp/week8/pub-cache-linux}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/mnt/f/contentretrivalsystem/.tmp/week8/uv-cache-linux}"
export TMPDIR="${TMPDIR:-/mnt/f/contentretrivalsystem/.tmp/temp-linux}"
mkdir -p "$PUB_CACHE" "$UV_CACHE_DIR" "$TMPDIR" "$working_root"

if [[ "$skip_flutter_build" != 1 ]]; then
  (
    cd "$repo/frontend"
    flutter build linux --release --no-pub
  )
fi
frontend_release="$repo/frontend/build/linux/x64/release/bundle"
require_dir "$frontend_release" 'Flutter Linux release bundle'
require_file "$frontend_release/content_retrieval_app" 'Flutter Linux release executable'

run_root="$working_root/$source_commit"
[[ ! -e "$run_root" ]] || {
  printf 'Linux run root already exists: %s\n' "$run_root" >&2
  exit 1
}
mkdir -p "$run_root/app"
app_root="$run_root/app"

python3.10 "$repo/tools/week8/build_public_model_root.py" \
  --source-model-root "$source_models" \
  --source-manifest "$source_manifest" \
  --destination "$app_root/models"

cp -aL "$frontend_release" "$app_root/frontend"
mkdir -p "$app_root/backend" "$app_root/tools/tika"
cp -aL "$repo/backend/src" "$app_root/backend/src"
cp -aL "$repo/backend/pyproject.toml" "$repo/backend/uv.lock" "$app_root/backend/"
cp -aL "$repo/LICENSE" "$repo/NOTICE" "$repo/THIRD_PARTY_NOTICES.md" "$app_root/"
cp -aL "$repo/docs/dependency-licenses.csv" "$app_root/dependency-licenses.csv"
cp -aL "$tika_jar_source" "$app_root/tools/tika/tika-server-standard-3.3.1.jar"
cp -aL "$tika_checksum_source" "$app_root/tools/tika/tika-server-standard-3.3.1.jar.sha512"
cp -aL "$repo/tools/week8/start-integrated-linux.sh" "$app_root/start-integrated.sh"
chmod 755 "$app_root/start-integrated.sh" "$app_root/frontend/content_retrieval_app"

runtime_source="$run_root/runtime-source"
mkdir -p "$runtime_source/backend"
cp -aL "$repo/backend/pyproject.toml" "$repo/backend/uv.lock" "$runtime_source/backend/"
"$uv_bin" sync --project "$runtime_source/backend" --locked --no-dev
base_python="$($uv_bin python find 3.10)"
base_root="$(dirname "$(dirname "$base_python")")"
mkdir -p "$app_root/runtime/python"
cp -aL "$base_root/bin" "$app_root/runtime/python/"
cp -aL "$base_root/include" "$app_root/runtime/python/"
cp -aL "$base_root/lib" "$app_root/runtime/python/"
if [[ -f "$base_root/BUILD" ]]; then
  cp -aL "$base_root/BUILD" "$app_root/runtime/python/"
fi
require_file "$app_root/runtime/python/bin/python3.10" 'Bundled Linux Python'
site_packages="$runtime_source/backend/.venv/lib/python3.10/site-packages"
require_dir "$site_packages" 'Linux virtualenv site-packages'
cp -aflL "$site_packages/." "$app_root/runtime/python/lib/python3.10/site-packages/"

"$linux_jdk/bin/jlink" \
  --add-modules java.base,java.desktop,java.logging,java.management,java.naming,java.net.http,java.sql,java.xml,jdk.crypto.ec,jdk.unsupported \
  --strip-debug \
  --no-header-files \
  --no-man-pages \
  --compress=2 \
  --output "$app_root/runtime/java"

python3.10 - "$app_root/PACKAGE_MANIFEST.json" "$source_commit" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
manifest = {
    "schema_version": 1,
    "source_commit": sys.argv[2],
    "platform_claim": "Ubuntu 24.04 x64 release",
    "distribution_class": "general",
    "model_policy": "MobileCLIP weights are not included",
    "first_run_downloads": False,
    "python_runtime_mode": "bundled-uv-python",
    "java_runtime_mode": "Temurin-jlink",
}
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

mkdir -p "$output_root" "$evidence_dir"
archive="$output_root/offline-retrieval-v1.0.0-linux-x64.tar.gz"
[[ ! -e "$archive" ]] || {
  printf 'Output archive already exists: %s\n' "$archive" >&2
  exit 1
}
tar --dereference --hard-dereference \
  --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -C "$run_root" -czf "$archive" app

python3.10 "$repo/tools/week8/validate_linux_release.py" "$archive" \
  --expected-commit "$source_commit" \
  --size-limit-bytes "$archive_limit" \
  --output "$evidence_dir/public-archive.json"
sha256sum "$archive" > "$evidence_dir/SHA256SUMS.txt"
printf 'Linux public candidate: %s\n' "$archive"
