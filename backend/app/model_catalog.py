"""只检查本地模型清单和必需文件，不加载模型或发起下载。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MODEL_FILES = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "preprocessor_config.json",
    "vocabulary.json",
)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _check_file(path: Path) -> dict[str, Any]:
    return {"path": str(path), "ok": path.is_file()}


def inspect_manifest(manifest_path: Path, project_root: Path) -> dict[str, Any]:
    """相对路径统一以项目根解析；缺失和格式错误以可展示结果返回。"""
    result: dict[str, Any] = {
        "manifest_path": str(manifest_path.resolve()),
        "models": [],
        "vad": None,
        "models_ok": False,
        "errors": [],
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        result["errors"].append(f"无法读取模型清单：{manifest_path.resolve()}（{error}）")
        return result

    if not isinstance(manifest, dict):
        result["errors"].append("模型清单必须是 JSON 对象。")
        return result
    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        result["errors"].append("模型清单 models 必须是非空数组。")
        models = []
    seen: set[str] = set()
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            result["errors"].append(f"models[{index}] 必须是对象。")
            continue
        required = ("id", "type", "label", "path", "language", "task", "compute_type")
        invalid = [
            key for key in required if not isinstance(model.get(key), str) or not model[key].strip()
        ]
        if invalid:
            result["errors"].append(f"models[{index}] 缺少非空字符串字段：{', '.join(invalid)}。")
            continue
        if model["id"] in seen:
            result["errors"].append(f"模型 id 重复：{model['id']}。")
        seen.add(model["id"])
        if (model["type"], model["task"]) not in {
            ("asr", "transcribe"),
            ("translate", "translate"),
        }:
            result["errors"].append(f"模型 {model['id']} 的 type/task 组合不支持。")
        directory = _resolve(project_root, model["path"])
        checks = [_check_file(directory / name) for name in MODEL_FILES]
        result["models"].append(
            {**model, "path": str(directory), "ok": all(c["ok"] for c in checks), "files": checks}
        )

    vad = manifest.get("vad")
    if not isinstance(vad, dict) or any(
        not isinstance(vad.get(key), str) or not vad[key].strip()
        for key in ("model_path", "metadata_path")
    ):
        result["errors"].append("模型清单 vad 必须包含非空 model_path 和 metadata_path。")
    else:
        checks = [
            _check_file(_resolve(project_root, vad[key])) for key in ("model_path", "metadata_path")
        ]
        result["vad"] = {"ok": all(c["ok"] for c in checks), "files": checks}

    result["models_ok"] = bool(
        not result["errors"]
        and result["models"]
        and all(model["ok"] for model in result["models"])
        and result["vad"]
        and result["vad"]["ok"]
    )
    return result
