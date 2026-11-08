"""术语表 CSV/JSON 导入导出。"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from app.glossary.models import GlossaryEntry, GlossaryValidationError, ReplacementPolicy
from app.glossary.normalizer import normalize_pattern

CSV_COLUMNS = (
    "source",
    "variants",
    "target",
    "category",
    "match_mode",
    "regex",
    "priority",
    "field",
    "policy",
    "enabled",
)


def parse_entries(content: str, fmt: str) -> list[GlossaryEntry]:
    if fmt == "csv":
        return _parse_csv(content)
    if fmt == "json":
        return _parse_json(content)
    raise GlossaryValidationError("词表格式仅支持 csv 或 json。")


def load_entries(path: str | Path) -> list[GlossaryEntry]:
    file = Path(path)
    if not file.is_file():
        raise GlossaryValidationError(f"词表文件不存在：{file}")
    suffix = file.suffix.lower()
    if suffix not in {".csv", ".json"}:
        raise GlossaryValidationError("词表文件仅支持 .csv 或 .json。")
    return parse_entries(file.read_text(encoding="utf-8-sig"), suffix[1:])


def dump_entries(entries: list[GlossaryEntry], fmt: str) -> str:
    if fmt == "csv":
        return _dump_csv(entries)
    if fmt == "json":
        return json.dumps(
            [entry.model_dump(mode="json") for entry in entries], ensure_ascii=False, indent=2
        )
    raise GlossaryValidationError("词表格式仅支持 csv 或 json。")


def merge_duplicates(entries: list[GlossaryEntry]) -> tuple[list[GlossaryEntry], list[str]]:
    """合并同 source 的重复词条；目标/字段/策略冲突时拒绝导入。"""

    seen_ids: set[str] = set()
    merged: dict[str, GlossaryEntry] = {}
    warnings: list[str] = []
    for entry in entries:
        if entry.id in seen_ids:
            raise GlossaryValidationError(f"词条 id 重复：{entry.id}")
        seen_ids.add(entry.id)
        key = normalize_pattern(entry.source)
        existing = merged.get(key)
        if existing is None:
            merged[key] = entry
            continue
        if (
            existing.target != entry.target
            or existing.field != entry.field
            or existing.policy != entry.policy
        ):
            raise GlossaryValidationError(f"source 重复但 target/field/policy 冲突：{entry.source}")
        variants = list(dict.fromkeys([*existing.variants, *entry.variants]))
        merged[key] = existing.model_copy(update={"variants": variants})
        warnings.append(f"已合并重复 source：{entry.source}")
    return list(merged.values()), warnings


def _parse_csv(content: str) -> list[GlossaryEntry]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise GlossaryValidationError("CSV 缺少表头。")
    headers = {name.strip() for name in reader.fieldnames if name}
    missing = [name for name in ("source",) if name not in headers]
    if missing:
        raise GlossaryValidationError(f"CSV 缺少必需列：{', '.join(missing)}")
    entries: list[GlossaryEntry] = []
    for index, row in enumerate(reader):
        cleaned = {(key or "").strip(): (value or "").strip() for key, value in row.items()}
        if not cleaned.get("source"):
            continue
        try:
            entries.append(
                GlossaryEntry(
                    id=cleaned.get("id") or f"term-{index + 1:03d}",
                    source=cleaned["source"],
                    variants=_split_variants(cleaned.get("variants", "")),
                    target=cleaned.get("target", ""),
                    category=cleaned.get("category") or "term",
                    match_mode=cleaned.get("match_mode") or "exact",
                    regex=cleaned.get("regex") or None,
                    priority=int(cleaned.get("priority") or 100),
                    field=cleaned.get("field") or "text",
                    policy=ReplacementPolicy(cleaned.get("policy") or "keep"),
                    enabled=_parse_bool(cleaned.get("enabled", "true")),
                )
            )
        except (ValueError, TypeError) as exc:
            raise GlossaryValidationError(f"CSV 第 {index + 2} 行无效：{exc}") from exc
    return entries


def _parse_json(content: str) -> list[GlossaryEntry]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise GlossaryValidationError(f"JSON 词表格式错误：{exc}") from exc
    if isinstance(data, dict):
        data = data.get("entries")
    if not isinstance(data, list):
        raise GlossaryValidationError("JSON 词表必须是数组，或包含 entries 数组。")
    entries: list[GlossaryEntry] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise GlossaryValidationError(f"JSON 第 {index + 1} 项必须是对象。")
        values = dict(item)
        values.setdefault("id", f"term-{index + 1:03d}")
        if isinstance(values.get("variants"), str):
            values["variants"] = _split_variants(values["variants"])
        try:
            entries.append(GlossaryEntry(**values))
        except (ValueError, TypeError) as exc:
            raise GlossaryValidationError(f"JSON 第 {index + 1} 项无效：{exc}") from exc
    return entries


def _dump_csv(entries: list[GlossaryEntry]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "source": entry.source,
                "variants": "|".join(entry.variants),
                "target": entry.target,
                "category": entry.category,
                "match_mode": entry.match_mode,
                "regex": entry.regex or "",
                "priority": entry.priority,
                "field": entry.field,
                "policy": entry.policy.value,
                "enabled": "true" if entry.enabled else "false",
            }
        )
    return output.getvalue()


def _split_variants(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
