"""从环境读取本地配置，不修改系统设置或自动创建模型目录。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ORIGIN = r"http://127\.0\.0\.1(?::[0-9]+)?"


def _path(name: str, default: Path, root: Path) -> Path:
    value = Path(os.environ.get(name, str(default))).expanduser()
    return (root / value).resolve() if not value.is_absolute() else value.resolve()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    models_dir: Path
    manifest_path: Path
    temp_dir: Path
    device: str = "auto"
    compute_type: str = "int8"
    token: str | None = None
    jobs_path: Path | None = None
    recordings_dir: Path | None = None
    models_root: Path | None = None

    @classmethod
    def from_env(cls) -> Settings:
        root = _path("JP_WORKBENCH_ROOT", PROJECT_ROOT, PROJECT_ROOT)
        models = _path("JP_WORKBENCH_MODELS_DIR", root / "models", root)
        token = os.environ.get("SIDECAR_TOKEN")
        if token is not None and (not token.strip() or not token.isascii()):
            raise ValueError("SIDECAR_TOKEN 必须是非空 ASCII 字符串。")
        device = os.environ.get("JP_WORKBENCH_DEVICE", "auto")
        compute_type = os.environ.get("JP_WORKBENCH_COMPUTE_TYPE", "int8")
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("设备仅支持 auto、cpu 或 cuda。")
        if compute_type not in {"int8", "int8_float16", "float16", "bfloat16"}:
            raise ValueError("计算类型仅支持 int8、int8_float16、float16 或 bfloat16。")
        models_root_env = os.environ.get("JP_WORKBENCH_MODELS_ROOT")
        return cls(
            project_root=root,
            models_dir=models,
            manifest_path=_path("JP_WORKBENCH_MANIFEST", models / "manifest.json", root),
            temp_dir=_path("JP_WORKBENCH_TEMP_DIR", root / "data" / "tmp", root),
            device=device,
            compute_type=compute_type,
            token=token,
            jobs_path=_path("JP_WORKBENCH_JOBS_DB", root / "data" / "jobs.sqlite3", root),
            recordings_dir=_path(
                "JP_WORKBENCH_RECORDINGS_DIR", root / "data" / "recordings-tmp", root
            ),
            models_root=(
                _path("JP_WORKBENCH_MODELS_ROOT", Path(models_root_env), root)
                if models_root_env
                else None
            ),
        )
