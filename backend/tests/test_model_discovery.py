"""安装目录模型发现的测试；只用空占位文件，不创建可推理模型。"""

from pathlib import Path

from app.asr.model_manager import ModelManager
from app.config import Settings
from app.main import create_app
from app.model_catalog import MODEL_FILES, inspect_models
from app.model_discovery import VAD_METADATA, VAD_MODEL, build_manifest
from fastapi.testclient import TestClient

HEADERS = {"X-Sidecar-Token": "dev"}


def _settings(tmp_path, models_root):
    return Settings(
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        manifest_path=tmp_path / "manifest.json",
        temp_dir=tmp_path / "tmp",
        token="dev",
        models_root=models_root,
    )


def _make_model(directory, names=MODEL_FILES):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).touch()
    return directory


def _make_vad(root):
    (root / VAD_MODEL).touch()
    (root / VAD_METADATA).write_text("{}", encoding="utf-8")


def test_discovers_complete_model(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "whisper-ja-1.5B")
    _make_vad(root)

    report = inspect_models(_settings(tmp_path, root))

    assert report["source"] == "discovery"
    assert report["model_directory"] == str(root)
    assert report["models"][0]["id"] == "whisper-ja-1.5B"
    assert report["models"][0]["ok"] is True
    assert all(check["ok"] for check in report["models"][0]["files"])
    assert report["vad"]["ok"] is True
    assert report["models_ok"] is True


def test_incomplete_model_is_listed_with_missing_files(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    # 缺少 model.bin，但 config.json 与 tokenizer.json 仍在，仍应被识别为模型目录。
    _make_model(root / "broken", [name for name in MODEL_FILES if name != "model.bin"])

    report = inspect_models(_settings(tmp_path, root))

    assert report["models"][0]["id"] == "broken"
    assert report["models"][0]["ok"] is False
    assert any("model.bin" in error for error in report["errors"])
    assert report["models_ok"] is False


def test_ignores_non_model_directories(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    (root / "empty").mkdir()
    _make_model(root / "real")

    report = inspect_models(_settings(tmp_path, root))

    assert [model["id"] for model in report["models"]] == ["real"]


def test_empty_model_directory(tmp_path):
    root = tmp_path / "model"
    root.mkdir()

    report = inspect_models(_settings(tmp_path, root))

    assert report["models"] == []
    assert report["models_ok"] is False
    assert any(str(root) in error and "whisper-ja-1.5B" in error for error in report["errors"])
    assert report["hints"]["model_directory"] == str(root)


def test_missing_model_directory(tmp_path):
    root = tmp_path / "no-model"

    report = inspect_models(_settings(tmp_path, root))

    assert any("不存在" in error for error in report["errors"])
    assert report["hints"]
    assert report["source"] == "discovery"
    assert report["models_ok"] is False


def test_permission_error_is_reported(tmp_path, monkeypatch):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "real")

    def deny(_self):
        raise PermissionError("合成权限故障")

    monkeypatch.setattr(Path, "iterdir", deny)

    report = inspect_models(_settings(tmp_path, root))

    assert any("权限" in error or "无法访问" in error for error in report["errors"])


def test_missing_vad_keeps_asr_model(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "whisper-ja-1.5B")

    report = inspect_models(_settings(tmp_path, root))

    assert report["vad"]["ok"] is False
    assert report["models"][0]["ok"] is True
    assert report["models_ok"] is False
    assert not any(
        "VAD" in error or "vad" in error or VAD_MODEL in error for error in report["errors"]
    )


def test_model_manager_reuses_discovery(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "whisper-ja-1.5B")

    manager = ModelManager(_settings(tmp_path, root))

    assert [spec.id for spec in manager.list_specs()] == ["whisper-ja-1.5B"]


def test_build_manifest_shape(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "b-model")
    _make_model(root / "A-model")
    _make_vad(root)

    manifest = build_manifest(root)

    assert [model["id"] for model in manifest["models"]] == ["A-model", "b-model"]
    assert manifest["vad"]["model_path"] == str((root / VAD_MODEL).resolve())
    assert manifest["vad"]["metadata_path"] == str((root / VAD_METADATA).resolve())


def test_api_models_uses_discovery(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    _make_model(root / "whisper-ja-1.5B")
    _make_vad(root)

    application = create_app(_settings(tmp_path, root))
    with TestClient(application) as client:
        response = client.get("/api/models", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["source"] == "discovery"
