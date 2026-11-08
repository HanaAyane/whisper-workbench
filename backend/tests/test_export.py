from app.export.writers import render_subtitles
from app.jobs.schemas import Segment


def test_writers_use_current_bilingual_text_and_standard_timestamps():
    segment = Segment(
        id=3,
        start=3_612_345,
        end=3_614_260,
        raw_text="モデル原文",
        raw_translation="模型译文",
        text="編集済み <タグ> & 文",
        translation="当前译文",
    )
    empty = segment.model_copy(update={"text": "", "translation": " "})
    assert render_subtitles([empty, segment], "srt") == (
        "1\n01:00:12,345 --> 01:00:14,260\n編集済み <タグ> & 文\n当前译文\n"
    )
    assert render_subtitles([segment], "vtt") == (
        "WEBVTT\n\n01:00:12.345 --> 01:00:14.260\n編集済み &lt;タグ&gt; &amp; 文\n当前译文\n"
    )
    assert (
        render_subtitles([segment], "lrc") == "[60:12.34]編集済み <タグ> & 文\n[60:12.34]当前译文\n"
    )
    assert render_subtitles([segment], "txt") == "編集済み <タグ> & 文\n当前译文\n"
    assert render_subtitles([], "vtt") == "WEBVTT\n\n"
    assert render_subtitles([], "srt") == ""
