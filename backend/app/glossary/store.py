"""本地词表文件的读写与列表。"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from app.config import Settings
from app.glossary.io import dump_entries, load_entries
from app.glossary.models import GlossaryEntry, GlossaryNotFoundError, GlossaryValidationError

_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class GlossaryStore:
    def __init__(self, settings: Settings) -> None:
        value = os.environ.get(
            "JP_WORKBENCH_GLOSSARY_DIR", str(settings.project_root / "data" / "glossary")
        )
        self.base_dir = Path(value).expanduser().resolve()

    def list_glossaries(self) -> list[dict[str, object]]:
        if not self.base_dir.is_dir():
            return []
        result = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                entries = load_entries(path)
            except GlossaryValidationError:
                continue
            result.append({"id": path.stem, "name": path.stem, "entry_count": len(entries)})
        return result

    def load(self, glossary_id: str) -> list[GlossaryEntry]:
        path = self._path(glossary_id)
        if not path.is_file():
            raise GlossaryNotFoundError(f"词表不存在：{glossary_id}")
        return load_entries(path)

    def save(self, glossary_id: str, entries: list[GlossaryEntry]) -> None:
        path = self._path(glossary_id)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        output = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.base_dir, suffix=".tmp", delete=False
        )
        temp = Path(output.name)
        try:
            with output:
                output.write(dump_entries(entries, "json"))
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

    def delete(self, glossary_id: str) -> None:
        try:
            self._path(glossary_id).unlink()
        except FileNotFoundError as exc:
            raise GlossaryNotFoundError(f"词表不存在：{glossary_id}") from exc

    def export(self, glossary_id: str, fmt: str) -> str:
        return dump_entries(self.load(glossary_id), fmt)

    def _path(self, glossary_id: str) -> Path:
        if not _ID_PATTERN.fullmatch(glossary_id):
            raise GlossaryValidationError("词表 ID 只能包含 ASCII 字母、数字、下划线和连字符。")
        return self.base_dir / f"{glossary_id}.json"
