"""优先运行本地 Whisper ONNX VAD，不可用时降级为能量阈值检测。"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime

from app.audio.chunks import SpeechSegment
from app.config import Settings

LOGGER = logging.getLogger(__name__)
ENERGY_FRAME_MS = 30


def detect_speech(
    samples: np.ndarray,
    sample_rate: int = 16000,
    *,
    model_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
    feature_config_path: str | Path | None = None,
    use_onnx: bool = True,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 100,
    speech_pad_ms: int = 200,
    energy_threshold: float = 0.01,
) -> list[SpeechSegment]:
    """返回真实音频时间轴上的语音区间，所有末端均不超过输入时长。"""

    audio = _validate_audio(samples, sample_rate)
    _validate_options(
        threshold,
        min_speech_duration_ms,
        min_silence_duration_ms,
        speech_pad_ms,
        energy_threshold,
    )
    duration_ms = math.ceil(audio.size * 1000 / sample_rate)

    if use_onnx:
        settings = Settings.from_env()
        onnx_path = (
            Path(model_path) if model_path is not None else settings.models_dir / "whisper_vad.onnx"
        )
        meta_path = (
            Path(metadata_path)
            if metadata_path is not None
            else settings.models_dir / "whisper_vad_metadata.json"
        )
        try:
            detector = _WhisperOnnxVad(onnx_path, meta_path, feature_config_path)
            probabilities, frame_ms = detector.predict(audio, sample_rate)
        except Exception as exc:  # 外部模型/运行时异常统一降级，避免整个任务中断。
            LOGGER.warning("ONNX VAD 不可用，改用能量阈值检测：%s", exc)
        else:
            return _probabilities_to_segments(
                probabilities,
                frame_duration_ms=frame_ms,
                audio_duration_ms=duration_ms,
                threshold=threshold,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
                speech_pad_ms=speech_pad_ms,
            )
    else:
        LOGGER.info("ONNX VAD 已禁用，使用能量阈值检测。")

    probabilities = _energy_probabilities(audio, sample_rate, energy_threshold)
    return _probabilities_to_segments(
        probabilities,
        frame_duration_ms=ENERGY_FRAME_MS,
        audio_duration_ms=duration_ms,
        threshold=threshold,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
        speech_pad_ms=speech_pad_ms,
    )


def _validate_audio(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate <= 0:
        raise ValueError("采样率必须大于 0。")
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim != 1:
        raise ValueError("VAD 输入必须是一维单声道采样。")
    if audio.size == 0:
        raise ValueError("VAD 输入不能为空。")
    if not np.isfinite(audio).all():
        raise ValueError("VAD 输入包含 NaN 或无穷值。")
    return audio


def _validate_options(
    threshold: float,
    min_speech_duration_ms: int,
    min_silence_duration_ms: int,
    speech_pad_ms: int,
    energy_threshold: float,
) -> None:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("VAD 阈值必须在 0 到 1 之间。")
    if min_speech_duration_ms < 0 or min_silence_duration_ms < 0 or speech_pad_ms < 0:
        raise ValueError("VAD 时长和填充参数不能小于 0。")
    if energy_threshold < 0:
        raise ValueError("能量阈值不能小于 0。")


def _energy_probabilities(
    audio: np.ndarray, sample_rate: int, energy_threshold: float
) -> np.ndarray:
    frame_samples = round(sample_rate * ENERGY_FRAME_MS / 1000)
    frame_count = math.ceil(audio.size / frame_samples)
    padded = np.pad(audio, (0, frame_count * frame_samples - audio.size))
    frames = padded.reshape(frame_count, frame_samples)
    rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))
    return (rms >= energy_threshold).astype(np.float32)


def _probabilities_to_segments(
    probabilities: np.ndarray,
    *,
    frame_duration_ms: int,
    audio_duration_ms: int,
    threshold: float,
    min_speech_duration_ms: int,
    min_silence_duration_ms: int,
    speech_pad_ms: int,
) -> list[SpeechSegment]:
    """用双阈值滞回保留短静音，过滤短语音并限制实际音频边界。"""

    negative_threshold = max(threshold - 0.15, 0.01)
    raw: list[SpeechSegment] = []
    triggered = False
    start_ms = 0
    temporary_end_ms: int | None = None

    for index, probability in enumerate(probabilities):
        current_ms = index * frame_duration_ms
        if probability >= threshold:
            if not triggered:
                start_ms = current_ms
                triggered = True
            temporary_end_ms = None
        elif triggered and probability < negative_threshold:
            if temporary_end_ms is None:
                temporary_end_ms = current_ms
            if current_ms - temporary_end_ms >= min_silence_duration_ms:
                if temporary_end_ms - start_ms >= min_speech_duration_ms:
                    raw.append(SpeechSegment(start_ms, temporary_end_ms))
                triggered = False
                temporary_end_ms = None

    if triggered:
        raw.append(SpeechSegment(start_ms, audio_duration_ms))

    padded: list[SpeechSegment] = []
    for segment in raw:
        start = max(0, segment.start_ms - speech_pad_ms)
        end = min(audio_duration_ms, segment.end_ms + speech_pad_ms)
        if end <= start or end - start < min_speech_duration_ms:
            continue
        if padded and start <= padded[-1].end_ms:
            previous = padded[-1]
            padded[-1] = SpeechSegment(previous.start_ms, max(previous.end_ms, end))
        else:
            padded.append(SpeechSegment(start, end))
    return padded


class _WhisperOnnxVad:
    """本地 Whisper log-Mel 到语音概率的轻量封装，不访问模型仓库。"""

    def __init__(
        self,
        model_path: Path,
        metadata_path: Path,
        feature_config_path: str | Path | None,
    ) -> None:
        if not model_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError("未找到 whisper_vad.onnx 或其 metadata。")
        self.metadata = _read_json_object(metadata_path)
        self.frame_duration_ms = _positive_metadata_int(self.metadata, "frame_duration_ms")
        self.total_duration_ms = _positive_metadata_int(self.metadata, "total_duration_ms")
        self.input_shape = self.metadata.get("input_shape")
        self.output_shape = self.metadata.get("output_shape")
        if self.input_shape != [1, 80, 3000] or self.total_duration_ms != 30000:
            raise ValueError("仅支持输入为 [1, 80, 3000]、窗口为 30 秒的 Whisper VAD。")

        if feature_config_path is not None:
            config_path = Path(feature_config_path)
        elif self.metadata.get("preprocessor_config_path"):
            config_path = metadata_path.parent / self.metadata["preprocessor_config_path"]
        else:
            config_path = model_path.parent / "whisper-base" / "preprocessor_config.json"
        self.feature_config = _read_json_object(config_path)
        self.mel_filters = np.asarray(self.feature_config.get("mel_filters"), dtype=np.float32)
        if self.mel_filters.shape != (80, 201):
            raise ValueError("Whisper 特征配置必须包含形状为 [80, 201] 的 mel_filters。")
        self.hop_length = int(self.feature_config.get("hop_length", 160))
        self.n_fft = int(self.feature_config.get("n_fft", 400))
        if self.hop_length != 160 or self.n_fft != 400:
            raise ValueError("Whisper VAD 仅支持 hop_length=160、n_fft=400 的特征配置。")

        self.session = onnxruntime.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        inputs = self.session.get_inputs()
        if len(inputs) != 1:
            raise ValueError("Whisper VAD ONNX 必须只有一个输入。")
        self.input_name = inputs[0].name

    def predict(self, audio: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
        if sample_rate != 16000:
            raise ValueError("Whisper ONNX VAD 要求 16000 Hz 单声道输入。")
        window_samples = self.total_duration_ms * sample_rate // 1000
        output_frames = int(self.output_shape[1])
        expected_frames = self.total_duration_ms // self.frame_duration_ms
        if output_frames != expected_frames:
            raise ValueError("Whisper VAD 输出帧数与 metadata 不一致。")

        probabilities: list[np.ndarray] = []
        for offset in range(0, audio.size, window_samples):
            window = audio[offset : offset + window_samples]
            actual_samples = window.size
            if actual_samples < window_samples:
                window = np.pad(window, (0, window_samples - actual_samples))
            features = self._extract_features(window)
            logits = self.session.run(None, {self.input_name: features})[0]
            values = np.asarray(logits, dtype=np.float32).reshape(-1)
            if values.size != output_frames:
                raise ValueError("Whisper VAD ONNX 实际输出形状与 metadata 不一致。")
            window_probabilities = 1.0 / (1.0 + np.exp(-np.clip(values, -80.0, 80.0)))
            actual_frames = math.ceil(
                actual_samples * 1000 / (sample_rate * self.frame_duration_ms)
            )
            probabilities.append(window_probabilities[:actual_frames])
        return np.concatenate(probabilities), self.frame_duration_ms

    def _extract_features(self, audio: np.ndarray) -> np.ndarray:
        padded = np.pad(audio, (self.n_fft // 2, self.n_fft // 2), mode="reflect")
        frame_count = 1 + (padded.size - self.n_fft) // self.hop_length
        frames = np.lib.stride_tricks.as_strided(
            padded,
            shape=(frame_count, self.n_fft),
            strides=(padded.strides[0] * self.hop_length, padded.strides[0]),
        )
        window = np.hanning(self.n_fft + 1)[:-1].astype(np.float32)
        spectrum = np.fft.rfft(frames * window, axis=1)
        magnitudes = np.square(np.abs(spectrum)).T[:, :-1]
        mel_spectrogram = self.mel_filters @ magnitudes
        log_spectrogram = np.log10(np.maximum(mel_spectrogram, 1e-10))
        log_spectrogram = np.maximum(log_spectrogram, log_spectrogram.max() - 8.0)
        features = (log_spectrogram + 4.0) / 4.0
        if features.shape != (80, 3000):
            raise ValueError(f"Whisper 特征形状错误：{features.shape}。")
        return features[None, :, :].astype(np.float32, copy=False)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"未找到本地 VAD 配置：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"VAD 配置必须是 JSON 对象：{path}")
    return value


def _positive_metadata_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"VAD metadata 的 {key} 必须是正整数。")
    return value
