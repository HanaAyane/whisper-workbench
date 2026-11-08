"""Phase 4 术语表归一化、匹配、替换、导入导出与预览 API 测试。"""

import json

import pytest
from app.config import Settings
from app.glossary.io import dump_entries, merge_duplicates, parse_entries
from app.glossary.matcher import match_text
from app.glossary.models import GlossaryEntry, GlossaryValidationError
from app.glossary.normalizer import normalize_text
from app.glossary.replacer import apply_to_segment, preview_text
from app.main import create_app
from fastapi.testclient import TestClient

HEADERS = {"X-Sidecar-Token": "dev"}


def _entry(**overrides):
    values = {
        "id": "term-001",
        "source": "田中",
        "variants": [],
        "target": "田中太郎",
        "category": "person",
        "match_mode": "exact",
        "regex": None,
        "priority": 100,
        "field": "text",
        "policy": "correct",
        "enabled": True,
    }
    values.update(overrides)
    return GlossaryEntry(**values)


def _settings(tmp_path):
    return Settings(
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        manifest_path=tmp_path / "models" / "manifest.json",
        temp_dir=tmp_path / "tmp",
        token="dev",
    )


def test_normalize_fullwidth_case_and_kana():
    normalized, mapping = normalize_text("Ｔａｎａｋａ タナカ")

    assert normalized == "tanaka たなか"
    assert len(mapping) == len(normalized)
    assert mapping[0] == 0
    assert mapping[7] == 7


def test_match_source_and_variants():
    entry = _entry(variants=["たなか", "Tanaka"])
    text = "田中とたなかとＴａｎａｋａ"

    hits = match_text(text, [entry], "text")

    assert [hit.matched_text for hit in hits] == ["田中", "たなか", "Ｔａｎａｋａ"]
    assert [hit.replacement for hit in hits] == ["田中太郎", "田中太郎", "田中太郎"]


def test_longest_match_wins():
    short = _entry(id="short", source="田中", target="短")
    long = _entry(id="long", source="田中太郎", target="长")

    hits = match_text("田中太郎", [short, long], "text")

    assert len(hits) == 1
    assert hits[0].entry_id == "long"
    assert hits[0].matched_text == "田中太郎"


def test_same_length_uses_higher_priority():
    low = _entry(id="low", source="東京", target="低", priority=10)
    high = _entry(id="high", source="東京", target="高", priority=200)

    hits = match_text("東京", [low, high], "text")

    assert len(hits) == 1
    assert hits[0].entry_id == "high"


def test_overlapping_matches_do_not_overlap():
    first = _entry(id="first", source="abc", target="ABC")
    second = _entry(id="second", source="bcd", target="BCD")

    hits = match_text("abcd", [first, second], "text")

    assert len(hits) == 1
    assert hits[0].entry_id == "first"


def test_policies_keep_and_field_isolation():
    correct = _entry(id="correct", source="田中", target="田中太郎", field="text")
    translate = _entry(
        id="translate",
        source="田中",
        target="田中先生",
        field="translation",
        policy="translate",
    )
    keep = _entry(id="keep", source="さん", target="", policy="keep", field="text")

    text_result = preview_text("田中さん", [correct, translate, keep], "text")
    translation_result = preview_text("田中さん", [correct, translate, keep], "translation")

    assert [(hit.entry_id, hit.replacement) for hit in text_result.hits] == [
        ("correct", "田中太郎"),
        ("keep", None),
    ]
    assert text_result.replaced_text == "田中太郎さん"
    assert [(hit.entry_id, hit.replacement) for hit in translation_result.hits] == [
        ("translate", "田中先生")
    ]
    assert translation_result.replaced_text == "田中先生さん"


def test_apply_to_segment_returns_copy_and_keeps_raw_fields():
    segment = {
        "id": 0,
        "raw_text": "田中さん",
        "text": "田中さん",
        "raw_translation": "田中さん",
        "translation": "田中さん",
        "hits": [],
    }
    entries = [
        _entry(id="correct", source="田中", target="田中太郎", field="text"),
        _entry(
            id="translate",
            source="田中",
            target="田中先生",
            field="translation",
            policy="translate",
        ),
    ]

    result = apply_to_segment(segment, entries)

    assert result is not segment
    assert result["raw_text"] == "田中さん"
    assert result["raw_translation"] == "田中さん"
    assert result["text"] == "田中太郎さん"
    assert result["translation"] == "田中先生さん"
    assert {hit["field"] for hit in result["hits"]} == {"text", "translation"}
    assert segment["text"] == "田中さん"


def test_disabled_entries_are_ignored():
    assert match_text("田中", [_entry(enabled=False)], "text") == []


def test_csv_roundtrip_with_pipe_variants():
    content = (
        "source,variants,target,category,match_mode,regex,priority,field,policy,enabled\n"
        "田中,たなか|Tanaka,田中太郎,person,exact,,100,text,correct,true\n"
    )

    entries = parse_entries(content, "csv")
    exported = dump_entries(entries, "csv")
    reparsed = parse_entries(exported, "csv")

    assert len(entries) == 1
    assert entries[0].variants == ["たなか", "Tanaka"]
    assert reparsed[0] == entries[0]


def test_json_duplicate_source_merges_variants():
    content = json.dumps(
        [
            {
                "id": "a",
                "source": "田中",
                "target": "田中太郎",
                "field": "text",
                "policy": "correct",
            },
            {
                "id": "b",
                "source": "田中",
                "variants": ["たなか"],
                "target": "田中太郎",
                "field": "text",
                "policy": "correct",
            },
        ],
        ensure_ascii=False,
    )
    entries = merge_duplicates(parse_entries(content, "json"))

    assert len(entries[0]) == 1
    assert entries[0][0].variants == ["たなか"]
    assert entries[1]


def test_conflicting_duplicates_are_rejected():
    content = json.dumps(
        [
            {"source": "田中", "target": "A", "field": "text", "policy": "correct"},
            {"source": "田中", "target": "B", "field": "text", "policy": "correct"},
        ],
        ensure_ascii=False,
    )

    with pytest.raises(GlossaryValidationError, match="冲突"):
        merge_duplicates(parse_entries(content, "json"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"match_mode": "regex"},
        {"match_mode": "fuzzy"},
        {"policy": "mask"},
        {"policy": "correct", "field": "translation"},
        {"policy": "translate", "field": "text"},
        {"policy": "correct", "target": ""},
    ],
)
def test_unsupported_or_inconsistent_entries_are_rejected(overrides):
    with pytest.raises(ValueError):
        _entry(**overrides)


def test_preview_api_import_export(tmp_path):
    settings = _settings(tmp_path)
    application = create_app(settings)
    content = json.dumps(
        [
            {
                "id": "term-001",
                "source": "田中",
                "variants": ["たなか"],
                "target": "田中太郎",
                "field": "text",
                "policy": "correct",
            }
        ],
        ensure_ascii=False,
    )
    with TestClient(application) as client:
        imported = client.post(
            "/api/glossary/import",
            headers=HEADERS,
            json={"glossary_id": "demo", "format": "json", "content": content},
        )
        assert imported.status_code == 200
        assert imported.json()["entry_count"] == 1

        preview = client.post(
            "/api/glossary/preview",
            headers=HEADERS,
            json={"glossary_id": "demo", "text": "田中さん", "field": "text"},
        )
        assert preview.status_code == 200
        assert preview.json()["replaced_text"] == "田中太郎さん"
        assert preview.json()["hits"][0]["entry_id"] == "term-001"

        exported = client.get("/api/glossary/demo/export?format=csv", headers=HEADERS)
        assert exported.status_code == 200
        assert "田中" in exported.text
        assert exported.headers["content-type"].startswith("text/csv")

        listed = client.get("/api/glossary", headers=HEADERS)
        assert listed.status_code == 200
        assert listed.json()["glossaries"][0]["entry_count"] == 1


def test_api_creates_updates_and_deletes_glossary(tmp_path):
    application = create_app(_settings(tmp_path))
    with TestClient(application) as client:
        url = "/api/glossary/local"
        created = client.put(url, headers=HEADERS, json=[])
        assert created.status_code == 200
        assert created.json()["entry_count"] == 0
        entry = {"id": "term-001", "source": "田中", "target": "田中太郎", "policy": "correct"}
        updated = client.put(url, headers=HEADERS, json=[entry])
        assert updated.status_code == 200
        assert updated.json()["entry_count"] == 1
        assert client.get(f"{url}/export", headers=HEADERS).json()[0]["target"] == "田中太郎"
        assert client.delete(url, headers=HEADERS).status_code == 204
        assert client.get(f"{url}/export", headers=HEADERS).status_code == 404


def test_preview_api_missing_glossary_returns_404(tmp_path):
    application = create_app(_settings(tmp_path))
    with TestClient(application) as client:
        response = client.post(
            "/api/glossary/preview",
            headers=HEADERS,
            json={"glossary_id": "missing", "text": "田中", "field": "text"},
        )
    assert response.status_code == 404
