"""按本地清单加载 CTranslate2 模型，不下载权重。"""

from __future__ import annotations

import gc
import json
import threading
from dataclasses import dataclass
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from app.config import Settings
from app.model_catalog import MODEL_FILES
from app.model_discovery import build_manifest


class ModelError(RuntimeError):
    """模型清单或加载失败的基类。"""


class ModelNotFoundError(ModelError):
    """清单中没有指定 id 的模型。"""


class ModelUnavailableError(ModelError):
    """模型目录或必需文件不完整。"""


class ModelLoadError(ModelError):
    """CTranslate2 无法初始化模型。"""


@dataclass(frozen=True)
class ModelSpec:
    id: str
    type: str
    label: str
    path: Path
    language: str
    task: str
    compute_type: str


@dataclass(frozen=True)
class LoadedModel:
    spec: ModelSpec
    model: WhisperModel
    device: str
    compute_type: str


class ModelManager:
    """只允许一个活动模型；重复请求复用缓存，卸载时立即释放。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self._loaded: dict[tuple[str, str, str], LoadedModel] = {}

    def _read_manifest(self) -> dict:
        if self.settings.models_root is not None:
            return build_manifest(self.settings.models_root)
        try:
            manifest = json.loads(self.settings.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ModelError(f"无法读取模型清单：{self.settings.manifest_path}（{exc}）") from exc
        if not isinstance(manifest, dict):
            raise ModelError("模型清单必须是 JSON 对象。")
        return manifest

    def list_specs(self) -> list[ModelSpec]:
        manifest = self._read_manifest()
        if not isinstance(manifest.get("models"), list):
            raise ModelError("模型清单格式错误：models 必须是数组。")
        specs: list[ModelSpec] = []
        for index, item in enumerate(manifest["models"]):
            if not isinstance(item, dict):
                raise ModelError(f"模型清单 models[{index}] 必须是对象。")
            required = ("id", "type", "label", "path", "language", "task", "compute_type")
            missing = [
                key for key in required if not isinstance(item.get(key), str) or not item[key]
            ]
            if missing:
                raise ModelError(f"模型清单 models[{index}] 缺少字段：{', '.join(missing)}。")
            specs.append(
                ModelSpec(
                    id=item["id"],
                    type=item["type"],
                    label=item["label"],
                    path=self._resolve(item["path"]),
                    language=item["language"],
                    task=item["task"],
                    compute_type=item["compute_type"],
                )
            )
        return specs

    def get_spec(self, model_id: str, expected_type: str | None = None) -> ModelSpec:
        for spec in self.list_specs():
            if spec.id == model_id:
                if expected_type is not None and spec.type != expected_type:
                    raise ModelNotFoundError(
                        f"模型 {model_id} 的类型是 {spec.type}，不能用于 {expected_type}。"
                    )
                return spec
        raise ModelNotFoundError(f"模型清单中没有 id 为 {model_id} 的模型。")

    def vad_paths(self) -> tuple[Path, Path]:
        """从清单解析本地 VAD 的 ONNX 与 metadata 绝对路径。"""
        manifest = self._read_manifest()
        vad = manifest.get("vad")
        if not isinstance(vad, dict):
            raise ModelError("模型清单缺少 vad 配置。")
        values = []
        for key in ("model_path", "metadata_path"):
            value = vad.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ModelError(f"模型清单 vad.{key} 必须是非空路径。")
            values.append(self._resolve(value))
        return values[0], values[1]

    def resolve_device(self, requested: str | None = None) -> str:
        device = requested or self.settings.device
        if device == "auto":
            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        if device not in {"cpu", "cuda"}:
            raise ModelError(f"设备仅支持 auto、cpu 或 cuda，收到 {device!r}。")
        return device

    def resolve_compute_type(self, device: str, requested: str | None = None) -> str:
        compute_type = requested or self.settings.compute_type
        supported = set(ctranslate2.get_supported_compute_types(device))
        if compute_type not in supported:
            raise ModelError(
                f"设备 {device} 不支持计算类型 {compute_type}；可用："
                + "、".join(sorted(supported))
                + "。"
            )
        return compute_type

    def load(
        self,
        model_id: str,
        *,
        expected_type: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> LoadedModel:
        spec = self.get_spec(model_id, expected_type)
        resolved_device = self.resolve_device(device)
        resolved_compute = self.resolve_compute_type(
            resolved_device, compute_type or spec.compute_type
        )
        key = (spec.id, resolved_device, resolved_compute)
        with self._lock:
            cached = self._loaded.get(key)
            if cached is not None:
                return cached

            missing = [name for name in MODEL_FILES if not (spec.path / name).is_file()]
            if missing:
                raise ModelUnavailableError(
                    f"模型 {spec.id} 文件不完整：{spec.path} 缺少 {', '.join(missing)}。"
                )
            try:
                model = WhisperModel(
                    str(spec.path),
                    device=resolved_device,
                    compute_type=resolved_compute,
                    local_files_only=True,
                )
            except Exception as exc:
                raise ModelLoadError(
                    f"模型 {spec.id} 加载失败：{exc}；请检查模型目录、CUDA 驱动，"
                    "或改用 cpu/int8 重试。"
                ) from exc
            loaded = LoadedModel(
                spec=spec,
                model=model,
                device=resolved_device,
                compute_type=resolved_compute,
            )
            self._loaded[key] = loaded
            return loaded

    def unload(self, model_id: str | None = None) -> None:
        with self._lock:
            if model_id is None:
                self._loaded.clear()
            else:
                for key in [key for key in self._loaded if key[0] == model_id]:
                    self._loaded.pop(key, None)
        gc.collect()

    @property
    def loaded_ids(self) -> list[str]:
        with self._lock:
            return sorted({key[0] for key in self._loaded})

    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return (
            path.resolve() if path.is_absolute() else (self.settings.project_root / path).resolve()
        )
