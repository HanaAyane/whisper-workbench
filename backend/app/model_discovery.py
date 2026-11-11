"""扫描安装目录下的模型文件夹，自动生成与清单兼容的结果，不下载权重。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

VAD_MODEL = "whisper_vad.onnx"
VAD_METADATA = "whisper_vad_metadata.json"


def is_model_directory(directory: Path) -> bool:
    """判断子目录是否像 CTranslate2 Whisper 模型目录。"""
    try:
        if (directory / "model.bin").is_file():
            return True
        return (directory / "config.json").is_file() and (directory / "tokenizer.json").is_file()
    except OSError:
        return False


def model_entry(directory: Path) -> dict[str, Any]:
    """生成与清单兼容的单个 ASR 模型条目。"""
    return {
        "id": directory.name,
        "type": "asr",
        "label": directory.name,
        "path": str(directory.resolve()),
        "language": "ja",
        "task": "transcribe",
        "compute_type": "int8",
    }


def build_manifest(models_root: Path) -> dict[str, Any]:
    """扫描直接子目录生成清单；目录读取异常时返回空模型列表，不抛出。"""
    result: dict[str, Any] = {"models": []}
    try:
        children = sorted(
            (child for child in models_root.iterdir() if child.is_dir()),
            key=lambda child: child.name.lower(),
        )
        result["models"] = [model_entry(child) for child in children if is_model_directory(child)]
        vad_model = models_root / VAD_MODEL
        vad_metadata = models_root / VAD_METADATA
        if vad_model.is_file() and vad_metadata.is_file():
            result["vad"] = {
                "model_path": str(vad_model.resolve()),
                "metadata_path": str(vad_metadata.resolve()),
            }
    except OSError:
        return {"models": []}
    return result
