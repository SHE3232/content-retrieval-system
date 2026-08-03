from pathlib import Path
from types import SimpleNamespace

import httpx
import content_retrieval.mvp as mvp
import pytest
from httpx import ASGITransport, AsyncClient

from content_retrieval.mvp import MvpSettings, TikaReadinessProbe


class FakeProbe:
    def __init__(self, ready: bool) -> None:
        self.ready = ready

    def is_ready(self) -> bool:
        return self.ready


class FakeRepository:
    def count(self) -> int:
        return 0


class FakeRuntime:
    def __init__(self) -> None:
        self.repository = FakeRepository()
        self.indexing_service = object()
        self.retrieval_service = SimpleNamespace(repository=self.repository)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


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


@pytest.mark.anyio
async def test_mvp_app_builds_runtime_during_lifespan_and_closes_it(
    tmp_path: Path,
) -> None:
    settings = MvpSettings(
        model_root=tmp_path / "models",
        manifest_path=tmp_path / "manifest.json",
        data_dir=tmp_path / "data",
        tika_url="http://tika.test",
    )
    runtime = FakeRuntime()
    builder_calls: list[dict[str, Path]] = []

    def build_runtime(**kwargs: Path) -> FakeRuntime:
        builder_calls.append(kwargs)
        return runtime

    app = mvp.create_mvp_app(
        settings,
        runtime_builder=build_runtime,
        tika_probe=FakeProbe(True),
    )

    assert app.state.ready is False
    assert builder_calls == []

    async with app.router.lifespan_context(app):
        assert builder_calls == [
            {
                "model_root": settings.model_root,
                "manifest_path": settings.manifest_path,
                "data_dir": settings.data_dir,
            }
        ]
        assert app.state.runtime is runtime
        assert app.state.indexing_service is runtime.indexing_service
        assert app.state.retrieval_service is runtime.retrieval_service
        assert app.state.ready is True

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    assert app.state.ready is False
    assert runtime.close_calls == 1


@pytest.mark.anyio
async def test_mvp_app_readiness_reflects_tika_becoming_unavailable(
    tmp_path: Path,
) -> None:
    settings = MvpSettings(
        model_root=tmp_path / "models",
        manifest_path=tmp_path / "manifest.json",
        data_dir=tmp_path / "data",
        tika_url="http://tika.test",
    )
    probe = FakeProbe(True)
    runtime = FakeRuntime()
    app = mvp.create_mvp_app(
        settings,
        runtime_builder=lambda **kwargs: runtime,
        tika_probe=probe,
    )

    async with app.router.lifespan_context(app):
        probe.ready = False
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}


@pytest.mark.anyio
async def test_mvp_app_closes_runtime_when_initial_tika_probe_fails(
    tmp_path: Path,
) -> None:
    settings = MvpSettings(
        model_root=tmp_path / "models",
        manifest_path=tmp_path / "manifest.json",
        data_dir=tmp_path / "data",
        tika_url="http://tika.test",
    )
    runtime = FakeRuntime()
    app = mvp.create_mvp_app(
        settings,
        runtime_builder=lambda **kwargs: runtime,
        tika_probe=FakeProbe(False),
    )

    with pytest.raises(RuntimeError, match="Tika.*not ready"):
        async with app.router.lifespan_context(app):
            pass

    assert app.state.ready is False
    assert runtime.close_calls == 1
