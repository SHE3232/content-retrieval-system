from pathlib import Path

import httpx

from content_retrieval.mvp import MvpSettings, TikaReadinessProbe


def test_settings_defaults_are_resolved_from_repository_root(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"

    settings = MvpSettings.from_environment(repository_root=repository_root, environ={})

    assert settings.model_root == (repository_root / "models").resolve()
    assert settings.manifest_path == (repository_root / "models" / "model-manifest.json").resolve()
    assert settings.data_dir == (repository_root / "data" / "mvp").resolve()
    assert settings.tika_url == "http://127.0.0.1:9998"


def test_settings_relative_environment_values_are_resolved_from_repository_root(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    environ = {
        "CONTENT_RETRIEVAL_MODEL_ROOT": "artifacts/models",
        "CONTENT_RETRIEVAL_MANIFEST_PATH": "artifacts/manifest.json",
        "CONTENT_RETRIEVAL_DATA_DIR": "state/index",
        "CONTENT_RETRIEVAL_TIKA_URL": "http://127.0.0.1:10098",
    }

    settings = MvpSettings.from_environment(
        repository_root=repository_root,
        environ=environ,
    )

    assert settings.model_root == (repository_root / "artifacts" / "models").resolve()
    assert settings.manifest_path == (repository_root / "artifacts" / "manifest.json").resolve()
    assert settings.data_dir == (repository_root / "state" / "index").resolve()
    assert settings.tika_url == "http://127.0.0.1:10098"


def test_tika_readiness_requires_a_tika_version_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="Apache Tika 3.0.0")
    )
    probe = TikaReadinessProbe(transport=transport)

    assert probe.is_ready() is True

    other_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="other")
    )
    other_probe = TikaReadinessProbe(transport=other_transport)

    assert other_probe.is_ready() is False
