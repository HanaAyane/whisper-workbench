"""NFKC、英文大小写与日文假名归一化，并保留原文索引映射。"""

from __future__ import annotations

import unicodedata


def _normalize_char(char: str) -> str:
    normalized = unicodedata.normalize("NFKC", char).casefold()
    result: list[str] = []
    for item in normalized:
        # 片假名折叠为平假名，便于同一专名的假名写法互通。
        if "\u30a1" <= item <= "\u30f6":
            result.append(chr(ord(item) - 0x60))
        else:
            result.append(item)
    return "".join(result)


def normalize_text(text: str) -> tuple[str, list[int]]:
    """返回归一化文本及“归一化索引 -> 原文索引”的映射。"""

    normalized: list[str] = []
    mapping: list[int] = []
    for original_index, char in enumerate(text):
        for item in _normalize_char(char):
            normalized.append(item)
            mapping.append(original_index)
    return "".join(normalized), mapping


def normalize_pattern(pattern: str) -> str:
    return "".join(_normalize_char(char) for char in pattern)
