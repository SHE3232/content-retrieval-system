#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port=8000
check_only=0
tika_pid=""
backend_pid=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) check_only=1; shift ;;
    --port) port="$2"; shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[[ "$port" =~ ^[0-9]+$ && "$port" -ge 1 && "$port" -le 65535 ]] || {
  printf 'Port must be between 1 and 65535\n' >&2
  exit 2
}

cleanup() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
  if [[ -n "$tika_pid" ]] && kill -0 "$tika_pid" 2>/dev/null; then
    kill "$tika_pid" 2>/dev/null || true
    wait "$tika_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

python="$package_root/runtime/python/bin/python3.10"
java="$package_root/runtime/java/bin/java"
frontend="$package_root/frontend/content_retrieval_app"
backend_src="$package_root/backend/src"
model_root="$package_root/models"
manifest="$model_root/model-manifest.json"
tika_jar="$package_root/tools/tika/tika-server-standard-3.3.1.jar"
tika_checksum="$tika_jar.sha512"
data_dir="$package_root/data"

for required in "$python" "$java" "$frontend" "$manifest" \
  "$tika_jar" "$tika_checksum"; do
  [[ -f "$required" ]] || {
    printf 'Required package file is missing: %s\n' "$required" >&2
    exit 1
  }
done
[[ -d "$backend_src" && -d "$model_root" ]] || {
  printf 'Backend source or model root is missing\n' >&2
  exit 1
}
[[ -x "$python" && -x "$java" && -x "$frontend" ]] || {
  printf 'Packaged executables are not executable\n' >&2
  exit 1
}

expected_sha512="$(tr -d '[:space:]' < "$tika_checksum")"
actual_sha512="$(sha512sum "$tika_jar" | awk '{print $1}')"
[[ "$expected_sha512" =~ ^[0-9a-f]{128}$ && "$actual_sha512" == "$expected_sha512" ]] || {
  printf 'Tika SHA-512 verification failed\n' >&2
  exit 1
}

PYTHONPATH="$backend_src" "$python" - "$manifest" "$model_root" <<'PY'
import sys
from pathlib import Path

from content_retrieval.embeddings.manifest import ModelManifest
from content_retrieval.runtime import IMAGE_MODEL_ID, TEXT_MODEL_ID

manifest = ModelManifest.load(Path(sys.argv[1]), model_root=Path(sys.argv[2]))
text_entry = manifest.require(TEXT_MODEL_ID)
text_entry.verify()
image_entry = next(
    (entry for entry in manifest.entries if entry.model_id == IMAGE_MODEL_ID),
    None,
)
if image_entry is not None:
    image_entry.verify()
PY

"$python" -c 'import uvicorn; import chromadb; import sentence_transformers'
"$java" -version >/dev/null 2>&1

if [[ "$check_only" == 1 ]]; then
  printf 'Linux integrated package preflight passed\n'
  exit 0
fi

mkdir -p "$data_dir/logs"
"$java" -jar "$tika_jar" -p 9998 \
  >"$data_dir/logs/tika.log" 2>&1 &
tika_pid=$!

"$python" - 9998 "$tika_pid" <<'PY'
import os
import socket
import sys
import time

port = int(sys.argv[1])
pid = int(sys.argv[2])
deadline = time.monotonic() + 120
while time.monotonic() < deadline:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            raise SystemExit(0)
    except OSError:
        try:
            os.kill(pid, 0)
        except OSError:
            raise SystemExit("Tika exited before readiness")
        time.sleep(0.25)
raise SystemExit("Tika readiness timed out")
PY

export CONTENT_RETRIEVAL_MODEL_ROOT="$model_root"
export CONTENT_RETRIEVAL_MANIFEST_PATH="$manifest"
export CONTENT_RETRIEVAL_DATA_DIR="$data_dir"
export CONTENT_RETRIEVAL_TIKA_URL="http://127.0.0.1:9998"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$backend_src"

"$python" -m uvicorn content_retrieval.mvp:create_mvp_app \
  --factory --app-dir "$backend_src" --host 127.0.0.1 --port "$port" \
  >"$data_dir/logs/backend.log" 2>&1 &
backend_pid=$!

"$python" - "$port" "$backend_pid" <<'PY'
import json
import os
import sys
import time
from urllib.request import urlopen

port = int(sys.argv[1])
pid = int(sys.argv[2])
deadline = time.monotonic() + 300
while time.monotonic() < deadline:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
            payload = json.load(response)
        if response.status == 200 and payload.get("status") == "ready":
            raise SystemExit(0)
    except Exception:
        try:
            os.kill(pid, 0)
        except OSError:
            raise SystemExit("Backend exited before readiness")
        time.sleep(0.5)
raise SystemExit("Backend readiness timed out")
PY

(cd "$package_root/frontend" && "$frontend")
