"""Phase 3 冒烟脚本：音频 → 解码 → VAD/切块 → 本地 ASR → SRT。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.asr.model_manager import ModelError, ModelManager
from app.asr.whisper_backend import recognize_chunks
from app.audio.chunks import merge_speech_segments
from app.audio.decode import decode_audio
from app.audio.vad import detect_speech
from app.config import Settings


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(max(milliseconds, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_srt(spans: list[tuple[int, int, str]], path: Path) -> None:
    blocks = [
        f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(spans, start=1)
    ]
    path.write_text("\n".join(blocks), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="本地日语 ASR 冒烟：音频转 SRT。")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", default="whisper-ja-1.5B")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--language", default="ja")
    parser.add_argument("--no-vad-onnx", action="store_true", help="强制使用能量阈值 VAD")
    args = parser.parse_args()

    settings = Settings.from_env()
    manager = ModelManager(settings)
    try:
        loaded = manager.load(
            args.model, expected_type="asr", device=args.device, compute_type=args.compute_type
        )
    except ModelError as exc:
        print(f"模型不可用：{exc}", file=sys.stderr)
        return 2

    print(f"模型：{loaded.spec.id}（{loaded.device}/{loaded.compute_type}）")
    decoded = decode_audio(args.audio)
    print(f"音频：{decoded.duration_ms} 毫秒，16000 Hz 单声道")
    try:
        vad_model, vad_metadata = manager.vad_paths()
    except ModelError:
        vad_model = vad_metadata = None
    speech = detect_speech(
        decoded.samples,
        use_onnx=not args.no_vad_onnx,
        model_path=vad_model,
        metadata_path=vad_metadata,
    )
    chunks = merge_speech_segments(speech)
    print(f"语音：{sum(segment.duration_ms for segment in speech)} 毫秒，{len(chunks)} 个推理块")

    result = recognize_chunks(
        loaded.model,
        decoded.samples,
        chunks,
        language=args.language,
        task="transcribe",
    )
    spans = [(span.start_ms, span.end_ms, span.text) for span in result.spans]
    output = args.out or args.audio.with_suffix(".srt")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_srt(spans, output)
    print(f"分段：{len(spans)}；SRT：{output}")
    if not spans:
        print("提示：未识别到文本（合成正弦波属正常结果，不代表真实语音效果）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
