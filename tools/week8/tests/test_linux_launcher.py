from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
LAUNCHER = REPOSITORY / "tools" / "week8" / "start-integrated-linux.sh"


def test_linux_launcher_is_offline_fail_closed_and_cleans_owned_processes() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "set -euo pipefail" in source
    assert "trap cleanup EXIT INT TERM" in source
    assert "HF_HUB_OFFLINE=1" in source
    assert "TRANSFORMERS_OFFLINE=1" in source
    assert "ModelManifest.load" in source
    assert "text_entry.verify()" in source
    assert "sha512sum" in source
    assert "content_retrieval.mvp:create_mvp_app" in source
    assert "kill \"$backend_pid\"" in source
    assert "kill \"$tika_pid\"" in source
    assert "--check-only" in source
