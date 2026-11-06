"""使用临时占位文件测试文件校验，不伪装成可推理模型。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.model_catalog import MODEL_FILES, inspect_manifest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def catalog(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    for name in MODEL_FILES:
        (model_dir / name).touch()
    (tmp_path / "vad.onnx").touch()
    (tmp_path / "vad.json").write_text("{}", encoding="utf-8")
    data = {
        "models": [
            {
                "id": "synthetic-test",
                "type": "asr",
                "label": "仅供文件校验测试",
                "path": "model",
                "language": "ja",
                "task": "transcribe",
                "compute_type": "int8",
            }
        ],
        "vad": {"model_path": "vad.onnx", "metadata_path": "vad.json"},
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return tmp_path, manifest, data


def test_complete_and_missing_files(catalog):
    root, manifest, _ = catalog
    assert inspect_manifest(manifest, root)["models_ok"] is True
    (root / "model" / "model.bin").unlink()
    report = inspect_manifest(manifest, root)
    assert report["models_ok"] is False
    assert report["models"][0]["files"][0] == {
        "path": str(root / "model" / "model.bin"),
        "ok": False,
    }


@pytest.mark.parametrize("content", ["{", "[]", "{}", '{"models": [null], "vad": {}}'])
def test_invalid_manifest(tmp_path, content):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(content, encoding="utf-8")
    report = inspect_manifest(manifest, tmp_path)
    assert report["models_ok"] is False
    assert report["errors"]


def test_absent_manifest(tmp_path):
    report = inspect_manifest(tmp_path / "missing.json", tmp_path)
    assert report["models_ok"] is False
    assert str(tmp_path / "missing.json") in report["errors"][0]


def test_duplicate_and_invalid_model(catalog):
    root, manifest, data = catalog
    data["models"].append(data["models"][0].copy())
    data["models"][0]["task"] = "invalid"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    report = inspect_manifest(manifest, root)
    assert report["models_ok"] is False
    assert len(report["errors"]) == 2


def test_cli_reports_missing_assets(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_models.py"),
            "--manifest",
            str(tmp_path / "absent.json"),
        ],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 1
    assert str(tmp_path / "absent.json") in result.stdout
    assert "未执行下载" in result.stdout
