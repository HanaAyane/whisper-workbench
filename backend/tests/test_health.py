"""Phase 1 API 的鉴权、来源限制与本地模型状态。"""

import json
from dataclasses import replace

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def settings(tmp_path):
    return Settings(
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        manifest_path=tmp_path / "models" / "manifest.json",
        temp_dir=tmp_path / "tmp",
        token="dev",
    )


def test_health_without_models(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"X-Sidecar-Token": "dev"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0", "models_ok": False}


@pytest.mark.parametrize("path", ["/api/health", "/api/models"])
@pytest.mark.parametrize("token", [None, "wrong", ""])
def test_authentication_required(settings, path, token):
    headers = {} if token is None else {"X-Sidecar-Token": token}
    with TestClient(create_app(settings)) as client:
        response = client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "本地服务令牌缺失或无效。"


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://127.0.0.1"])
def test_allowed_cors(settings, origin):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": origin, "X-Sidecar-Token": "dev"})
        preflight = client.options(
            "/api/models",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Sidecar-Token",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1.evil:5173",
        "http://192.168.1.2",
        "null",
    ],
)
def test_reject_other_origins(settings, origin):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": origin, "X-Sidecar-Token": "dev"})
        preflight = client.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == preflight.status_code == 403
    assert "access-control-allow-origin" not in response.headers


def test_random_token_rotates_and_is_not_returned(settings, capsys):
    application = create_app(replace(settings, token=None))
    with TestClient(application) as client:
        first = application.state.token
        assert len(first) >= 32
        assert client.get("/api/health", headers={"X-Sidecar-Token": "dev"}).status_code == 401
        response = client.get("/api/health", headers={"X-Sidecar-Token": first})
        assert response.status_code == 200
        assert first not in response.text
    assert application.state.token is None
    with TestClient(application):
        assert application.state.token != first
    assert "SIDECAR_TOKEN" in capsys.readouterr().out


def test_models_complete_missing_and_bad_manifest(settings, catalog):
    root, manifest, _ = catalog
    application = create_app(replace(settings, project_root=root, manifest_path=manifest))
    headers = {"X-Sidecar-Token": "dev"}
    with TestClient(application) as client:
        report = client.get("/api/models", headers=headers).json()
        assert report["models_ok"] is True
        assert report["models"][0]["ok"] is True
        assert client.get("/api/health", headers=headers).json()["models_ok"] is True
        (root / "vad.onnx").unlink()
        assert client.get("/api/health", headers=headers).json()["models_ok"] is False
        manifest.write_text("{", encoding="utf-8")
        response = client.get("/api/models", headers=headers)
        assert response.status_code == 200
        assert response.json()["errors"]
        assert response.json()["models_ok"] is False


def test_authentication_error_keeps_cors(settings):
    origin = "http://127.0.0.1:5173"
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": origin})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == origin
    assert "令牌" in response.json()["detail"]


def test_invalid_model_paths_are_reported(settings, catalog):
    root, manifest, data = catalog
    data["models"][0]["path"] = "bad\u0000path"
    data["vad"]["model_path"] = "bad\u0000vad"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with TestClient(
        create_app(replace(settings, project_root=root, manifest_path=manifest))
    ) as client:
        for path in ("/api/health", "/api/models"):
            response = client.get(path, headers={"X-Sidecar-Token": "dev"})
            assert response.status_code == 200
            assert response.json()["models_ok"] is False
        assert len(response.json()["errors"]) == 2


def test_settings_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("JP_WORKBENCH_ROOT", str(tmp_path))
    monkeypatch.setenv("JP_WORKBENCH_MODELS_DIR", "assets")
    monkeypatch.setenv("JP_WORKBENCH_TEMP_DIR", "scratch")
    monkeypatch.setenv("JP_WORKBENCH_DEVICE", "cpu")
    monkeypatch.setenv("JP_WORKBENCH_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("SIDECAR_TOKEN", "dev")
    monkeypatch.delenv("JP_WORKBENCH_MANIFEST", raising=False)
    config = Settings.from_env()
    assert config.models_dir == tmp_path / "assets"
    assert config.manifest_path == tmp_path / "assets" / "manifest.json"
    assert config.temp_dir == tmp_path / "scratch"
    assert config.device == "cpu"


@pytest.mark.parametrize(
    "name,value",
    [
        ("JP_WORKBENCH_DEVICE", "remote"),
        ("JP_WORKBENCH_COMPUTE_TYPE", "unknown"),
        ("SIDECAR_TOKEN", ""),
        ("SIDECAR_TOKEN", "中文"),
    ],
)
def test_invalid_settings(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_env()
