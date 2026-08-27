#!/usr/bin/env bash
set -euo pipefail

repo="${REPOSITORY_ROOT:-$(pwd)}"
source_commit="${SOURCE_COMMIT:-}"
output_dir="${OUTPUT_DIR:-}"
evidence_dir="${EVIDENCE_DIR:-$repo/docs/week8/evidence/platform/macos}"
final_evidence_json="${FINAL_EVIDENCE_JSON:-}"
e2e_base_url="${E2E_BASE_URL:-}"

[[ "$(uname -s)" == "Darwin" ]] || {
  printf 'This release gate must run on a real macOS host\n' >&2
  exit 1
}
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'SOURCE_COMMIT must be a full 40-character lowercase hash\n' >&2
  exit 1
}
[[ -n "$output_dir" ]] || {
  printf 'OUTPUT_DIR is required\n' >&2
  exit 1
}
[[ -n "$e2e_base_url" ]] || {
  printf 'E2E_BASE_URL is required for the full five-format research check\n' >&2
  exit 1
}

repo="$(realpath "$repo")"
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

mkdir -p "$output_dir" "$evidence_dir"
sw_vers > "$evidence_dir/sw_vers.txt"
uname -a > "$evidence_dir/uname.txt"
system_profiler SPHardwareDataType > "$evidence_dir/hardware.txt"
flutter --version > "$evidence_dir/flutter-version.txt"
dart --version > "$evidence_dir/dart-version.txt" 2>&1

(
  cd "$repo"
  python3.10 -m pytest backend/tests -q
  python3.10 -m pytest tools/week5/tests -q
  python3.10 -m pytest tools/week6/tests -q
  python3.10 -m pytest tools/compliance/tests -q
  python3.10 -m pytest tools/week8/tests -q
)
(
  cd "$repo/frontend"
  flutter analyze --no-pub
  flutter test --no-pub
  flutter build macos --release --no-pub 2>&1 | tee "$evidence_dir/flutter-build.log"
)

app_path="$repo/frontend/build/macos/Build/Products/Release/content_retrieval_app.app"
[[ -d "$app_path" ]] || {
  printf 'Flutter macOS release app is missing: %s\n' "$app_path" >&2
  exit 1
}
archive="$output_dir/offline-retrieval-v1.0.0-macos-universal.zip"
[[ ! -e "$archive" ]] || {
  printf 'Output archive already exists: %s\n' "$archive" >&2
  exit 1
}
ditto -c -k --sequesterRsrc --keepParent "$app_path" "$archive"
shasum -a 256 "$archive" > "$evidence_dir/app-archive.sha256"

python3.10 "$repo/tools/week5/run_real_five_format_e2e.py" \
  --base-url "$e2e_base_url" \
  --output "$evidence_dir/five-format-e2e.json"

python3.10 - "$evidence_dir/automated-evidence.json" "$source_commit" \
  "$archive" <<'PY'
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

output = Path(sys.argv[1])
archive = Path(sys.argv[3])
data = {
    "schema_version": 1,
    "source_commit": sys.argv[2],
    "host": {
        "platform": platform.system(),
        "sw_vers": subprocess.check_output(["sw_vers"], text=True),
        "uname": subprocess.check_output(["uname", "-a"], text=True),
        "hardware": subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"], text=True
        ),
        "simulator": False,
    },
    "flutter_build": {
        "command": "flutter build macos --release --no-pub",
        "exit_code": 0,
        "log": "flutter-build.log",
    },
    "app_archive": {
        "path": str(archive),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    },
    "runtime_checks": {
        "launch": "PENDING_MANUAL",
        "health": "PENDING_MANUAL",
        "five_format_e2e": "PASS",
    },
    "voiceover": {
        "navigation": False,
        "labels": False,
        "search_results": False,
        "high_contrast": False,
        "text_150_percent": False,
        "reduced_motion": False,
        "copy_path": False,
        "open_file": False,
    },
    "screenshots": [],
}
output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

if [[ -n "$final_evidence_json" ]]; then
  python3.10 "$repo/tools/week8/validate_macos_evidence.py" \
    "$final_evidence_json" --expected-commit "$source_commit"
else
  printf 'Automated macOS build finished; complete the VoiceOver runbook before PASS.\n'
fi
