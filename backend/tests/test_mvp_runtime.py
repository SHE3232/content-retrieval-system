from pathlib import Path

import httpx
import content_retrieval.mvp as mvp

from content_retrieval.mvp import MvpSettings, TikaReadinessProbe


def test_settings_defaults_are_resolved_from_repository_root(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"

    settings = MvpSettings.from_environment(repository_root=repository_root, environ={})

    assert settings.model_root == (repository_root / "models").resolve()
    assert settings.manifest_path == (repository_root / "models" / "model-manifest.json").resolve()
    assert settings.data_dir == (repository_root / "data" / "mvp").resolve()
    assert settings.tika_url == "http://127.0.0.1:9998"


def test_default_settings_root_does_not_depend_on_current_working_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    settings = MvpSettings.from_environment(environ={})
    repository_root = Path(mvp.__file__).resolve().parents[3]

    assert settings.model_root == (repository_root / "models").resolve()
    assert settings.manifest_path == (repository_root / "models" / "model-manifest.json").resolve()
    assert settings.data_dir == (repository_root / "data" / "mvp").resolve()


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
    def tika_version(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/version"
        return httpx.Response(200, text="Apache Tika 3.0.0")

    transport = httpx.MockTransport(tika_version)
    probe = TikaReadinessProbe(transport=transport)

    assert probe.is_ready() is True

    other_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="other")
    )
    other_probe = TikaReadinessProbe(transport=other_transport)

    assert other_probe.is_ready() is False


def test_tika_readiness_rejects_non_200_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="Apache Tika"))

    assert TikaReadinessProbe(transport=transport).is_ready() is False


def test_tika_readiness_returns_false_for_connection_and_invalid_url() -> None:
    unavailable_transport = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("unavailable"))
    )

    assert TikaReadinessProbe(transport=unavailable_transport).is_ready() is False
    assert TikaReadinessProbe(base_url="http://[::1").is_ready() is False


def test_tika_readiness_disables_environment_proxy_configuration(monkeypatch) -> None:
    captured: dict[str, object] = {}
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="Apache Tika"))

    def recording_client(*args, **kwargs):
        captured.update(kwargs)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", recording_client)

    assert TikaReadinessProbe(transport=transport).is_ready() is True
    assert captured["trust_env"] is False
