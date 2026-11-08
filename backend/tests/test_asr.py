"""Phase 3 模型管理与 Whisper 后端单元测试（不加载真实权重）。"""

import json

import numpy as np
import pytest
from app.asr.model_manager import (
    ModelError,
    ModelManager,
    ModelNotFoundError,
    ModelUnavailableError,
)
from app.asr.whisper_backend import recognize_chunks, translate_spans
from app.audio.chunks import SpeechSegment
from app.config import Settings
from app.model_catalog import MODEL_FILES


@pytest.fixture
def asr_settings(tmp_path):
    model_dir = tmp_path / "models" / "ja"
    model_dir.mkdir(parents=True)
    for name in MODEL_FILES:
        (model_dir / name).write_text("{}", encoding="utf-8")
    manifest = tmp_path / "models" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "fake-asr",
                        "type": "asr",
                        "label": "测试用 ASR",
                        "path": "models/ja",
                        "language": "ja",
                        "task": "transcribe",
                        "compute_type": "int8",
                    }
                ],
                "vad": {"model_path": "vad.onnx", "metadata_path": "vad.json"},
            }
        ),
        encoding="utf-8",
    )
    return Settings(
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        manifest_path=manifest,
        temp_dir=tmp_path / "tmp",
        token="dev",
    )


def test_list_and_get_spec(asr_settings):
    manager = ModelManager(asr_settings)

    specs = manager.list_specs()

    assert [spec.id for spec in specs] == ["fake-asr"]
    assert manager.get_spec("fake-asr", expected_type="asr").path.name == "ja"
    with pytest.raises(ModelNotFoundError):
        manager.get_spec("missing")


def test_get_spec_rejects_wrong_type(asr_settings):
    manager = ModelManager(asr_settings)

    with pytest.raises(ModelNotFoundError, match="类型"):
        manager.get_spec("fake-asr", expected_type="translate")


def test_resolve_device_auto(asr_settings, monkeypatch):
    manager = ModelManager(asr_settings)
    monkeypatch.setattr("app.asr.model_manager.ctranslate2.get_cuda_device_count", lambda: 1)
    assert manager.resolve_device("auto") == "cuda"

    monkeypatch.setattr("app.asr.model_manager.ctranslate2.get_cuda_device_count", lambda: 0)
    assert manager.resolve_device("auto") == "cpu"


def test_resolve_compute_type_rejects_unsupported(asr_settings):
    manager = ModelManager(asr_settings)

    with pytest.raises(ModelError, match="不支持计算类型"):
        manager.resolve_compute_type("cpu", "bfloat16")


def test_vad_paths_resolve_from_manifest(asr_settings):
    manager = ModelManager(asr_settings)

    model_path, metadata_path = manager.vad_paths()

    assert model_path == asr_settings.project_root / "vad.onnx"
    assert metadata_path == asr_settings.project_root / "vad.json"


def test_load_uses_manifest_compute_type(asr_settings, monkeypatch):
    created = []

    class FakeWhisperModel:
        def __init__(self, path, device, compute_type, local_files_only):
            created.append((device, compute_type, local_files_only))

    monkeypatch.setattr("app.asr.model_manager.WhisperModel", FakeWhisperModel)
    manager = ModelManager(asr_settings)

    manager.load("fake-asr", device="cpu")

    assert created == [("cpu", "int8", True)]


def test_load_rejects_incomplete_model(asr_settings):
    manager = ModelManager(asr_settings)
    (asr_settings.project_root / "models" / "ja" / "model.bin").unlink()

    with pytest.raises(ModelUnavailableError, match="model.bin"):
        manager.load("fake-asr", device="cpu", compute_type="int8")


def test_load_caches_and_passes_local_only(asr_settings, monkeypatch):
    created = []

    class FakeWhisperModel:
        def __init__(self, path, device, compute_type, local_files_only):
            created.append((path, device, compute_type, local_files_only))

    monkeypatch.setattr("app.asr.model_manager.WhisperModel", FakeWhisperModel)
    manager = ModelManager(asr_settings)

    first = manager.load("fake-asr", device="cpu", compute_type="int8")
    second = manager.load("fake-asr", device="cpu", compute_type="int8")

    assert first is second
    assert len(created) == 1
    assert created[0][1:] == ("cpu", "int8", True)
    assert manager.loaded_ids == ["fake-asr"]
    manager.unload("fake-asr")
    assert manager.loaded_ids == []


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisper:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((np.asarray(audio).size, kwargs))
        return iter(self.results.pop(0)), None


def test_recognize_chunks_offsets_and_clamps():
    model = _FakeWhisper([[_FakeSegment(0.1, 0.5, " こんにちは ")]])
    samples = np.zeros(16000 * 32, dtype=np.float32)

    result = recognize_chunks(model, samples, [SpeechSegment(30000, 32000)])

    assert [(span.start_ms, span.end_ms, span.text) for span in result.spans] == [
        (30100, 30500, "こんにちは")
    ]
    assert result.duration_after_vad_ms == 2000


def test_recognize_chunks_skips_empty_text():
    model = _FakeWhisper([[_FakeSegment(0.0, 0.5, "   ")]])
    samples = np.zeros(16000, dtype=np.float32)

    assert recognize_chunks(model, samples, [SpeechSegment(0, 1000)]).spans == []


def test_translate_spans_returns_aligned_text():
    model = _FakeWhisper([[_FakeSegment(0.0, 1.0, "你好")]])
    samples = np.zeros(16000, dtype=np.float32)

    translations = translate_spans(
        model, samples, [type("Span", (), {"start_ms": 0, "end_ms": 1000})()]
    )

    assert translations == ["你好"]
    assert model.calls[0][1]["task"] == "translate"
