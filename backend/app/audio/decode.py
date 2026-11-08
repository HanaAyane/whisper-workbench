"""使用 PyAV 将本地音视频解码为 16 kHz 单声道 float32。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np

LOGGER = logging.getLogger(__name__)
TARGET_SAMPLE_RATE = 16000
SUPPORTED_SUFFIXES = frozenset({".wav", ".mp3", ".m4a", ".flac", ".mp4", ".mkv", ".webm"})


class AudioDecodeError(RuntimeError):
    """输入文件存在，但无法完成音频解码。"""


@dataclass(frozen=True)
class DecodedAudio:
    """连续的一维 PCM 采样；时长由实际采样数计算。"""

    samples: np.ndarray
    sample_rate: int = TARGET_SAMPLE_RATE

    @property
    def duration_ms(self) -> int:
        return round(self.samples.size * 1000 / self.sample_rate)


def decode_audio(
    input_path: str | Path, *, check_cancelled: Callable[[], None] | None = None
) -> DecodedAudio:
    """解码受支持的本地文件，不上传输入，也不保留中间音频副本。"""

    path = Path(input_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"音频文件不存在或不是普通文件：{path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = "、".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"不支持的音频/视频格式：{path.suffix or '无扩展名'}；支持 {supported}。")

    resampler = av.AudioResampler(format="flt", layout="mono", rate=TARGET_SAMPLE_RATE)
    decoded: list[np.ndarray] = []
    try:
        with av.open(str(path), mode="r") as container:
            stream = next(iter(container.streams.audio), None)
            if stream is None:
                raise AudioDecodeError("输入文件不包含可解码的音频轨道。")
            for frame in container.decode(stream):
                if check_cancelled is not None:
                    check_cancelled()
                decoded.extend(_frame_samples(frame, resampler))
            decoded.extend(_frame_samples(None, resampler))
    except AudioDecodeError:
        raise
    except (av.FFmpegError, OSError) as exc:
        raise AudioDecodeError(f"无法解码输入文件：{path.name}；请检查文件是否完整。") from exc

    if not decoded:
        raise AudioDecodeError("音频轨道没有可解码的采样数据。")
    samples = np.ascontiguousarray(np.concatenate(decoded), dtype=np.float32)
    if samples.size == 0:
        raise AudioDecodeError("音频轨道没有可解码的采样数据。")
    LOGGER.info("音频解码完成：%d 个采样点，时长 %d 毫秒。", samples.size, round(samples.size / 16))
    return DecodedAudio(samples=samples)


def _frame_samples(frame, resampler: av.AudioResampler) -> list[np.ndarray]:
    """重采样一帧或刷新 resampler，并将平面声道展平为单声道。"""

    frames = resampler.resample(frame)
    return [np.asarray(item.to_ndarray(), dtype=np.float32).reshape(-1) for item in frames]
