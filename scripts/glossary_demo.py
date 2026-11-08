"""Phase 4 术语表演示：读取本地词表，输出命中列表和替换文本。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.glossary.io import load_entries
from app.glossary.models import GlossaryError
from app.glossary.replacer import preview_text


def main() -> int:
    parser = argparse.ArgumentParser(description="术语表精确匹配与替换预览。")
    parser.add_argument("--text", required=True, help="待检查文本")
    parser.add_argument("--glossary", type=Path, default=Path("data/glossary/demo.json"))
    parser.add_argument("--field", choices=["text", "translation"], default="text")
    parser.add_argument("--json", action="store_true", help="输出 JSON 便于程序处理")
    args = parser.parse_args()

    try:
        entries = load_entries(args.glossary)
    except GlossaryError as exc:
        print(f"词表不可用：{exc}")
        return 2
    result = preview_text(args.text, entries, args.field)

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    print(f"命中 {len(result.hits)} 条（field={args.field}）：")
    for hit in result.hits:
        replacement = "（保留原文）" if hit.replacement is None else hit.replacement
        print(
            f"- {hit.entry_id} [{hit.start},{hit.end}) "
            f"{hit.matched_text!r} -> {replacement!r} ({hit.policy.value})"
        )
    print(f"替换后：{result.replaced_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
