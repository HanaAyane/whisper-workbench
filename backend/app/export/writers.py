"""使用已保存的编辑副本生成 UTF-8 字幕内容。"""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

from app.jobs.schemas import ExportFormat, Segment


def timestamp(ms: int, separator: str = ",") -> str:
    hours, remainder = divmod(max(ms, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def render_srt(cues: Iterable[tuple[int, int, str]]) -> str:
    return "\n".join(
        f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, start=1)
    )


def render_subtitles(segments: list[Segment], format: ExportFormat) -> str:
    cues = []
    for segment in segments:
        lines = [
            line
            for field in (segment.text, segment.translation or "")
            for line in field.strip().splitlines()
            if line.strip()
        ]
        if lines:
            cues.append((segment.start, segment.end, "\n".join(lines)))
    if format == "srt":
        return render_srt(cues)
    if format == "vtt":
        return "WEBVTT\n\n" + "\n".join(
            f"{timestamp(start, '.')} --> {timestamp(end, '.')}\n{escape(text, quote=False)}\n"
            for start, end, text in cues
        )
    if format == "lrc":
        return "".join(
            _lyric_time(start) + line + "\n" for start, _, text in cues for line in text.split("\n")
        )
    return "\n".join(text + "\n" for _, _, text in cues)


def _lyric_time(ms: int) -> str:
    minutes, remainder = divmod(max(ms, 0), 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"[{minutes:02d}:{seconds:02d}.{millis // 10:02d}]"
