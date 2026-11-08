"""替换策略应用与人工复核预览，不修改原始 Segment。"""

from __future__ import annotations

from app.glossary.matcher import match_text
from app.glossary.models import GlossaryEntry, ReplacementResult, TermHit


def preview_text(text: str, entries: list[GlossaryEntry], field: str) -> ReplacementResult:
    """只生成预览结果，不写回任何原始数据。"""

    hits = match_text(text, entries, field)
    return ReplacementResult(text=text, replaced_text=apply_replacements(text, hits), hits=hits)


def apply_replacements(text: str, hits: list[TermHit]) -> str:
    """按命中区间从右到左替换；keep 策略保留原文。"""

    ordered = sorted(hits, key=lambda hit: hit.start)
    pieces: list[str] = []
    cursor = 0
    for hit in ordered:
        if hit.start < cursor or hit.end > len(text):
            continue
        pieces.append(text[cursor : hit.start])
        if hit.policy.value == "keep" or hit.replacement is None:
            pieces.append(text[hit.start : hit.end])
        else:
            pieces.append(hit.replacement)
        cursor = hit.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def apply_to_segment(segment: dict, entries: list[GlossaryEntry]) -> dict:
    """返回 Segment 副本；只改 text/translation，raw_* 保持只读。"""

    result = dict(segment)
    all_hits: list[TermHit] = []
    for field in ("text", "translation"):
        value = result.get(field)
        if not isinstance(value, str):
            continue
        preview = preview_text(value, entries, field)
        result[field] = preview.replaced_text
        all_hits.extend(preview.hits)
    result["hits"] = [hit.model_dump(mode="json") for hit in all_hits]
    return result
