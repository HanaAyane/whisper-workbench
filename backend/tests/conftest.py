"""合成文件检查数据；不包含可推理模型。"""

import json

import pytest
from app.model_catalog import MODEL_FILES


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
