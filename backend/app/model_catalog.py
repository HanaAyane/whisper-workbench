"""只检查本地模型清单和必需文件，不加载模型或发起下载。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.model_discovery import VAD_METADATA, VAD_MODEL, is_model_directory, model_entry

MODEL_FILES = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "preprocessor_config.json",
    "vocabulary.json",
)


def _resolve(root: Path, value: str) -> Path:
    if "\x00" in value:
        raise ValueError("路径不能包含空字符。")
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _check_file(path: Path) -> dict[str, Any]:
    try:
        return {"path": str(path), "ok": path.is_file()}
    except (OSError, ValueError) as error:
        return {"path": str(path), "ok": False, "error": f"无法检查文件：{error}"}


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
        try:
            directory = _resolve(project_root, model["path"])
            checks = [_check_file(directory / name) for name in MODEL_FILES]
            result["models"].append(
                {
                    **model,
                    "path": str(directory),
                    "ok": all(c["ok"] for c in checks),
                    "files": checks,
                }
            )
        except (OSError, ValueError) as error:
            message = f"模型 {model['id']} 路径无效或无法访问：{model['path']!r}（{error}）"
            result["errors"].append(message)
            result["models"].append({**model, "ok": False, "files": [], "error": message})

    vad = manifest.get("vad")
    if not isinstance(vad, dict) or any(
        not isinstance(vad.get(key), str) or not vad[key].strip()
        for key in ("model_path", "metadata_path")
    ):
        result["errors"].append("模型清单 vad 必须包含非空 model_path 和 metadata_path。")
    else:
        checks = []
        for key in ("model_path", "metadata_path"):
            try:
                checks.append(_check_file(_resolve(project_root, vad[key])))
            except (OSError, ValueError) as error:
                message = f"VAD 路径无效或无法访问：{vad[key]!r}（{error}）"
                result["errors"].append(message)
                checks.append({"path": vad[key], "ok": False, "error": message})
        result["vad"] = {"ok": all(c["ok"] for c in checks), "files": checks}

    result["models_ok"] = bool(
        not result["errors"]
        and result["models"]
        and all(model["ok"] for model in result["models"])
        and result["vad"]
        and result["vad"]["ok"]
    )
    return result


def inspect_models(settings: Any) -> dict[str, Any]:
    """存在 models_root 时走安装目录发现，否则保持读取清单文件。"""
    models_root = getattr(settings, "models_root", None)
    if models_root is not None:
        return _inspect_discovery(models_root, settings.project_root)
    return inspect_manifest(settings.manifest_path, settings.project_root)


def _inspect_discovery(root: Path, project_root: Path) -> dict[str, Any]:
    """扫描安装目录生成报告；读取失败也返回完整结构而不是抛异常。"""
    root = Path(root)
    report: dict[str, Any] = {
        "manifest_path": str((root / "manifest.json").resolve()),
        "model_directory": str(root),
        "source": "discovery",
        "models": [],
        "vad": {"ok": False, "files": []},
        "models_ok": False,
        "errors": [],
        "hints": {
            "model_directory": str(root),
            "example_subdirectory": "whisper-ja-1.5B",
            "expected_files": list(MODEL_FILES),
            "vad_files": [VAD_MODEL, VAD_METADATA],
            "note": (
                "将 CTranslate2 Whisper 模型文件放入 <模型目录>/<模型子目录>/；"
                "VAD 文件放入模型目录根。模型权重由用户提供，工作台不会自动下载。"
            ),
        },
    }

    vad_checks = [_check_file(root / VAD_MODEL), _check_file(root / VAD_METADATA)]
    report["vad"] = {"ok": all(check["ok"] for check in vad_checks), "files": vad_checks}

    if not root.is_dir():
        report["errors"].append(
            f"模型目录不存在：{root}。请确认安装完整，或手动创建该目录后重新扫描。"
        )
        return report

    try:
        children = sorted(
            (child for child in root.iterdir() if child.is_dir()),
            key=lambda child: child.name.lower(),
        )
    except (OSError, PermissionError) as error:
        report["errors"].append(f"无法访问模型目录，请检查目录权限：{root}（{error}）")
        return report

    for directory in children:
        if not is_model_directory(directory):
            continue
        checks = [_check_file(directory / name) for name in MODEL_FILES]
        entry = {**model_entry(directory), "ok": all(c["ok"] for c in checks), "files": checks}
        report["models"].append(entry)
        if not entry["ok"]:
            missing = [
                name for name, check in zip(MODEL_FILES, checks, strict=True) if not check["ok"]
            ]
            report["errors"].append(f"模型 {entry['id']} 缺少文件：{', '.join(missing)}。")

    if not report["models"]:
        report["errors"].append(
            f"模型目录中没有发现可用的 CTranslate2 模型：{root}。"
            f"请在 {root}/whisper-ja-1.5B 放置模型文件。"
        )

    report["models_ok"] = bool(
        report["models"] and all(model["ok"] for model in report["models"]) and report["vad"]["ok"]
    )
    return report
