"""多模式精确匹配：最长优先、同长度按 priority 高者优先。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

try:  # pragma: no cover - 取决于本地可选依赖
    import ahocorasick
except ImportError:  # pragma: no cover
    ahocorasick = None

from app.glossary.models import GlossaryEntry, ReplacementPolicy, TermHit
from app.glossary.normalizer import normalize_pattern, normalize_text


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    matched_text: str
    entry: GlossaryEntry


def match_text(text: str, entries: list[GlossaryEntry], field: str) -> list[TermHit]:
    """在指定字段上匹配启用的 exact 词条，返回互不重叠的命中。"""

    patterns: dict[str, list[GlossaryEntry]] = defaultdict(list)
    for entry in entries:
        if not entry.enabled or entry.field != field:
            continue
        for value in [entry.source, *entry.variants]:
            pattern = normalize_pattern(value)
            if pattern:
                patterns[pattern].append(entry)
    if not patterns or not text:
        return []

    normalized, mapping = normalize_text(text)
    candidates: list[_Candidate] = []
    seen: set[tuple[int, int, str]] = set()
    for start_norm, end_norm, pattern in _find_pattern_spans(normalized, patterns):
        if start_norm >= len(mapping) or end_norm > len(mapping):
            continue
        start = mapping[start_norm]
        end = mapping[end_norm - 1] + 1
        if end <= start:
            continue
        matched_text = text[start:end]
        for entry in patterns[pattern]:
            key = (start, end, entry.id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(_Candidate(start, end, matched_text, entry))

    candidates.sort(
        key=lambda item: (
            item.start,
            -(item.end - item.start),
            -item.entry.priority,
            item.entry.id,
        )
    )
    hits: list[TermHit] = []
    last_end = -1
    for candidate in candidates:
        if candidate.start < last_end:
            continue
        entry = candidate.entry
        replacement = None if entry.policy is ReplacementPolicy.keep else entry.target
        hits.append(
            TermHit(
                entry_id=entry.id,
                field=entry.field,
                start=candidate.start,
                end=candidate.end,
                matched_text=candidate.matched_text,
                replacement=replacement,
                policy=entry.policy,
            )
        )
        last_end = candidate.end
    return hits


def _find_pattern_spans(normalized: str, patterns: dict[str, list[GlossaryEntry]]):
    if ahocorasick is not None:
        automaton = ahocorasick.Automaton()
        for pattern in patterns:
            automaton.add_word(pattern, pattern)
        automaton.make_automaton()
        for end_index, pattern in automaton.iter(normalized):
            yield end_index - len(pattern) + 1, end_index + 1, pattern
        return
    for pattern in patterns:
        start = 0
        while True:
            index = normalized.find(pattern, start)
            if index < 0:
                break
            yield index, index + len(pattern), pattern
            start = index + 1


find_matches = match_text
