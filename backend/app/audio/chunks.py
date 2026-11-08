"""将有序语音区间合并为适合本地推理的连续音频块。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class SpeechSegment:
    """毫秒时间区间，采用左闭右开语义。"""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("语音区间必须满足 0 <= start_ms < end_ms。")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def merge_speech_segments(
    segments: list[SpeechSegment],
    *,
    max_duration_ms: int = 30000,
    max_silence_gap_ms: int = 500,
) -> list[SpeechSegment]:
    """合并短静音，必要时按硬边界拆分，保证每块不超过最大时长。"""

    if max_duration_ms <= 0:
        raise ValueError("最大切块时长必须大于 0 毫秒。")
    if max_silence_gap_ms < 0:
        raise ValueError("最大静音间隔不能小于 0 毫秒。")
    if not segments:
        return []

    ordered = sorted(segments)
    normalized: list[SpeechSegment] = []
    for segment in ordered:
        if normalized and segment.start_ms <= normalized[-1].end_ms:
            previous = normalized[-1]
            normalized[-1] = SpeechSegment(previous.start_ms, max(previous.end_ms, segment.end_ms))
        else:
            normalized.append(segment)

    chunks: list[SpeechSegment] = []
    current_start: int | None = None
    current_end: int | None = None
    for segment in normalized:
        for piece in _split_segment(segment, max_duration_ms):
            if current_start is None or current_end is None:
                current_start, current_end = piece.start_ms, piece.end_ms
                continue
            gap_ms = piece.start_ms - current_end
            merged_duration_ms = piece.end_ms - current_start
            if gap_ms <= max_silence_gap_ms and merged_duration_ms <= max_duration_ms:
                current_end = piece.end_ms
            else:
                chunks.append(SpeechSegment(current_start, current_end))
                current_start, current_end = piece.start_ms, piece.end_ms
    if current_start is not None and current_end is not None:
        chunks.append(SpeechSegment(current_start, current_end))
    return chunks


def _split_segment(segment: SpeechSegment, max_duration_ms: int) -> list[SpeechSegment]:
    return [
        SpeechSegment(start_ms, min(start_ms + max_duration_ms, segment.end_ms))
        for start_ms in range(segment.start_ms, segment.end_ms, max_duration_ms)
    ]
