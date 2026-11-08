"""生成可公开分享的合成音频；正弦波不是日语语音，不冒充 ASR 参照文本。"""

from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000


def make_demo_assets(output_dir: Path) -> tuple[Path, Path]:
    """写入六秒单声道 WAV 和如实描述信号内容的文本。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    samples = np.zeros(SAMPLE_RATE * 6, dtype=np.float32)
    for start_s, end_s, frequency in ((0.5, 2.0, 440.0), (3.0, 4.5, 660.0)):
        start = round(start_s * SAMPLE_RATE)
        end = round(end_s * SAMPLE_RATE)
        time = np.arange(end - start, dtype=np.float32) / SAMPLE_RATE
        samples[start:end] = 0.2 * np.sin(2 * np.pi * frequency * time)

    audio_path = output_dir / "sample.wav"
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(audio_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())

    text_path = output_dir / "sample.txt"
    text_path.write_text(
        "合成音频说明（非日语语音，不可用于 ASR 转录准确率评测）\n"
        "采样率：16000 Hz；声道：1；时长：6 秒。\n"
        "0.5–2.0 秒：440 Hz 正弦波；3.0–4.5 秒：660 Hz 正弦波；其余为静音。\n",
        encoding="utf-8",
    )
    return audio_path, text_path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Phase 2 合成音频和对应说明文本。")
    parser.add_argument("--out", type=Path, default=Path("data/demo"), help="输出目录")
    args = parser.parse_args()
    audio_path, text_path = make_demo_assets(args.out)
    print(f"已生成合成音频：{audio_path}")
    print(f"已生成信号说明：{text_path}")


if __name__ == "__main__":
    main()
