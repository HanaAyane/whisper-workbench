"""对已保存字幕做术语复核，所有位置以当前字幕的 Unicode 字符为准。"""

from __future__ import annotations

from app.glossary.matcher import match_text
from app.glossary.models import GlossaryEntry
from app.jobs.schemas import ReviewHit, Segment, SegmentEdit, SegmentField, SegmentReview

FIELDS: tuple[SegmentField, ...] = ("text", "translation")


def propose(segment: Segment, entries: list[GlossaryEntry]) -> Segment:
    """生成建议，保留当前文本及模型原始输出。"""
    for field in FIELDS:
        segment = _refresh(segment, entries, field, [])
    return segment


def edit_text(segment: Segment, edit: SegmentEdit, entries: list[GlossaryEntry]) -> Segment:
    if (segment.raw_translation is None) != (edit.translation is None):
        raise ValueError("译文字段与任务模式不符。")
    updated = segment
    for field in FIELDS:
        old = getattr(updated, field)
        new = getattr(edit, field)
        if old == new:
            continue
        start, end, replacement = _changed_range(old, new)
        updated = _replace(updated, entries, field, start, end, replacement)
    return updated


def review(segment: Segment, request: SegmentReview, entries: list[GlossaryEntry]) -> Segment:
    selection = request.hit
    if request.action == "undo":
        last = max(
            (hit for hit in segment.hits if hit.decision == "accepted"),
            key=lambda hit: hit.applied_revision,
            default=None,
        )
        if last is None or last.original_text is None:
            raise ValueError("这个片段没有可撤销的替换。")
        return _replace(segment, entries, last.field, last.start, last.end, last.original_text)

    if selection is None:
        raise ValueError("请选择要处理的术语建议。")
    hit = next(
        (
            item
            for item in segment.hits
            if item.decision == "pending"
            and (item.entry_id, item.field, item.start, item.end)
            == (selection.entry_id, selection.field, selection.start, selection.end)
        ),
        None,
    )
    if hit is None:
        raise ValueError("这条术语建议已变更，请重新查看字幕。")
    if hit.replacement is None or hit.replacement == hit.matched_text:
        raise ValueError("这条命中仅用于标记。")
    if request.action == "reject":
        rejected = hit.model_copy(update={"decision": "rejected"})
        return segment.model_copy(
            update={"hits": [rejected if item is hit else item for item in segment.hits]}
        )
    accepted = hit.model_copy(
        update={
            "decision": "accepted",
            "original_text": hit.matched_text,
            "matched_text": hit.replacement,
            "end": hit.start + len(hit.replacement),
            "applied_revision": segment.revision + 1,
        }
    )
    return _replace(segment, entries, hit.field, hit.start, hit.end, hit.replacement, accepted)


def _changed_range(old: str, new: str) -> tuple[int, int, str]:
    """保留没有变化的共同前缀和后缀，重新定位其中的复核决定。"""
    left = 0
    for before, after in zip(old, new, strict=False):
        if before != after:
            break
        left += 1
    old_end, new_end = len(old), len(new)
    while min(old_end, new_end) > left and old[old_end - 1] == new[new_end - 1]:
        old_end -= 1
        new_end -= 1
    return left, old_end, new[left:new_end]


def _replace(
    segment: Segment,
    entries: list[GlossaryEntry],
    field: SegmentField,
    start: int,
    end: int,
    replacement: str,
    accepted: ReviewHit | None = None,
) -> Segment:
    value = getattr(segment, field)
    delta = len(replacement) - (end - start)
    retained = []
    for hit in segment.hits:
        if hit.field != field or hit.decision == "pending":
            continue
        if hit.end <= start:
            retained.append(hit)
        elif hit.start >= end:
            retained.append(
                hit.model_copy(update={"start": hit.start + delta, "end": hit.end + delta})
            )
    if accepted is not None:
        retained.append(accepted)
    updated = segment.model_copy(update={field: value[:start] + replacement + value[end:]})
    return _refresh(updated, entries, field, retained)


def _refresh(
    segment: Segment,
    entries: list[GlossaryEntry],
    field: SegmentField,
    retained: list[ReviewHit],
) -> Segment:
    value = getattr(segment, field)
    pending = [
        ReviewHit(**hit.model_dump())
        for hit in match_text(value or "", entries, field)
        if not any(hit.start < mark.end and mark.start < hit.end for mark in retained)
    ]
    hits = [hit for hit in segment.hits if hit.field != field]
    hits.extend(retained)
    hits.extend(pending)
    hits.sort(key=lambda hit: (hit.field != "text", hit.start))
    return segment.model_copy(update={"hits": hits})
