"""调用 faster-whisper 对连续音频块做转录或翻译。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from app.audio.chunks import SpeechSegment

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class RecognizedSpan:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class RecognitionResult:
    spans: list[RecognizedSpan]
    duration_after_vad_ms: int


def recognize_chunks(
    model: WhisperModel,
    samples: np.ndarray,
    chunks: list[SpeechSegment],
    *,
    language: str = "ja",
    task: str = "transcribe",
    beam_size: int = 5,
    on_progress: ProgressCallback | None = None,
) -> RecognitionResult:
    """逐块识别并把块内秒级时间戳换算为全局毫秒。"""

    if task not in {"transcribe", "translate"}:
        raise ValueError("task 仅支持 transcribe 或 translate。")
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim != 1:
        raise ValueError("ASR 输入必须是一维单声道采样。")
    spans: list[RecognizedSpan] = []
    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks):
        start_sample = round(chunk.start_ms * 16000 / 1000)
        end_sample = round(chunk.end_ms * 16000 / 1000)
        clip = np.ascontiguousarray(audio[start_sample:end_sample], dtype=np.float32)
        if clip.size == 0:
            continue
        for raw_start, raw_end, text in _recognize_clip(
            model, clip, language=language, task=task, beam_size=beam_size
        ):
            start_ms = max(chunk.start_ms, chunk.start_ms + round(raw_start * 1000))
            end_ms = min(chunk.end_ms, chunk.start_ms + round(raw_end * 1000))
            if end_ms > start_ms:
                spans.append(RecognizedSpan(start_ms=start_ms, end_ms=end_ms, text=text))
        if on_progress is not None:
            on_progress(index + 1, total_chunks)
    return RecognitionResult(
        spans=spans,
        duration_after_vad_ms=sum(chunk.duration_ms for chunk in chunks),
    )


def translate_spans(
    model: WhisperModel,
    samples: np.ndarray,
    spans: list[RecognizedSpan],
    *,
    language: str = "ja",
    beam_size: int = 5,
) -> list[str]:
    """用本地翻译模型逐段生成中文译文，顺序与输入一致。"""

    audio = np.asarray(samples, dtype=np.float32)
    translations: list[str] = []
    for span in spans:
        start_sample = round(span.start_ms * 16000 / 1000)
        end_sample = round(span.end_ms * 16000 / 1000)
        clip = np.ascontiguousarray(audio[start_sample:end_sample], dtype=np.float32)
        if clip.size == 0:
            translations.append("")
            continue
        pieces = [
            text
            for _, _, text in _recognize_clip(
                model, clip, language=language, task="translate", beam_size=beam_size
            )
        ]
        translations.append("".join(pieces).strip())
    return translations


def _recognize_clip(
    model: WhisperModel,
    clip: np.ndarray,
    *,
    language: str,
    task: str,
    beam_size: int,
) -> list[tuple[float, float, str]]:
    segments, _info = model.transcribe(
        clip,
        language=language,
        task=task,
        beam_size=beam_size,
        condition_on_previous_text=False,
        word_timestamps=False,
        vad_filter=False,
    )
    recognized: list[tuple[float, float, str]] = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            recognized.append((segment.start, segment.end, text))
    return recognized
