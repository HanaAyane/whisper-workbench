"""翻译冒烟脚本：本地 ASR → DeepSeek 翻译 → 日中双语 SRT。

只发送字幕文本到 DeepSeek，音频不上传。运行前需在项目 .env 或环境变量
中配置 DEEPSEEK_API_KEY。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from app.asr.model_manager import ModelError, ModelManager
from app.asr.whisper_backend import recognize_chunks
from app.audio.chunks import merge_speech_segments
from app.audio.decode import decode_audio
from app.audio.vad import detect_speech
from app.config import Settings
from app.translation.deepseek import (
    DeepSeekConfig,
    DeepSeekTranslator,
    TranslationError,
)


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(max(milliseconds, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_bilingual_srt(
    spans: list[tuple[int, int, str]], translations: list[str], path: Path
) -> None:
    if len(spans) != len(translations):
        raise ValueError("原文与译文数量不一致，拒绝生成字幕。")
    blocks = [
        f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n{translation}\n"
        for index, ((start, end, text), translation) in enumerate(
            zip(spans, translations, strict=True), start=1
        )
    ]
    path.write_text("\n".join(blocks), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="本地日语 ASR + DeepSeek 翻译冒烟。")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", default="whisper-ja-1.5B")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--language", default="ja")
    parser.add_argument("--translation-model", default=None)
    args = parser.parse_args()

    settings = Settings.from_env()
    try:
        config = DeepSeekConfig.from_settings(settings)
        if args.translation_model:
            config = replace(config, model=args.translation_model)
    except TranslationError as exc:
        print(f"翻译服务不可用：{exc}", file=sys.stderr)
        return 2

    manager = ModelManager(settings)
    try:
        loaded = manager.load(
            args.model, expected_type="asr", device=args.device, compute_type=args.compute_type
        )
    except ModelError as exc:
        print(f"模型不可用：{exc}", file=sys.stderr)
        return 2

    print(f"模型：{loaded.spec.id}（{loaded.device}/{loaded.compute_type}）")
    print(f"翻译：DeepSeek {config.model}")
    decoded = decode_audio(args.audio)
    print(f"音频：{decoded.duration_ms} 毫秒，16000 Hz 单声道")
    try:
        vad_model, vad_metadata = manager.vad_paths()
    except ModelError:
        vad_model = vad_metadata = None
    speech = detect_speech(decoded.samples, model_path=vad_model, metadata_path=vad_metadata)
    chunks = merge_speech_segments(speech)
    print(f"语音：{sum(segment.duration_ms for segment in speech)} 毫秒，{len(chunks)} 个推理块")

    result = recognize_chunks(
        loaded.model, decoded.samples, chunks, language=args.language, task="transcribe"
    )
    spans = [(span.start_ms, span.end_ms, span.text) for span in result.spans]
    print(f"转写：{len(spans)} 段；正在调用 DeepSeek 翻译……")

    translator = DeepSeekTranslator(config)
    try:
        translations = translator.translate_segments(
            [text for _, _, text in spans], source_language=args.language, target_language="zh"
        )
    except TranslationError as exc:
        print(f"翻译失败：{exc}", file=sys.stderr)
        return 3
    finally:
        translator.close()

    output = args.out or args.audio.with_suffix(".bilingual.srt")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_bilingual_srt(spans, translations, output)
    print(f"翻译：{len(translations)} 段；双语 SRT：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
