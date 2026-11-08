"""Phase 2 音频解码、能量 VAD、语音切块和临时目录测试。"""

import logging
import wave
from pathlib import Path

import numpy as np
import pytest
from app.audio.chunks import SpeechSegment, merge_speech_segments
from app.audio.decode import decode_audio
from app.audio.tempfiles import job_temp_directory
from app.audio.vad import detect_speech

SAMPLE_RATE = 16000


def _sine(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """生成确定性的 440 Hz 单声道正弦波。"""
    sample_count = round(duration_ms * sample_rate / 1000)
    time = np.arange(sample_count, dtype=np.float32) / sample_rate
    return (0.5 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    """只在 pytest 临时目录中写入 PCM16 WAV，不依赖外部音频资源。"""
    frames = np.asarray(samples)
    if frames.ndim == 1:
        frames = frames[:, np.newaxis]
    pcm = (np.clip(frames, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(frames.shape[1])
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def _bounds(segments: list[SpeechSegment]) -> list[tuple[int, int]]:
    return [(segment.start_ms, segment.end_ms) for segment in segments]


def _assert_valid_chunks(
    chunks: list[SpeechSegment],
    originals: list[SpeechSegment],
    max_duration_ms: int,
) -> None:
    """每块不超长、不重叠，且原语音的每一毫秒都仍被覆盖。"""
    assert all(0 <= chunk.start_ms < chunk.end_ms for chunk in chunks)
    assert all(chunk.end_ms - chunk.start_ms <= max_duration_ms for chunk in chunks)
    assert all(
        previous.end_ms <= current.start_ms
        for previous, current in zip(chunks, chunks[1:], strict=False)
    )
    if not originals:
        assert chunks == []
        return
    covered = np.zeros(max(segment.end_ms for segment in originals), dtype=bool)
    for chunk in chunks:
        covered[chunk.start_ms : chunk.end_ms] = True
    for segment in originals:
        assert covered[segment.start_ms : segment.end_ms].all()


def test_decode_wav_resamples_stereo_to_16k_mono_float32(tmp_path):
    source = _sine(1200, sample_rate=44100)
    stereo = np.column_stack((source, np.zeros_like(source)))
    path = tmp_path / "stereo.wav"
    _write_wav(path, stereo, sample_rate=44100)

    result = decode_audio(path)

    assert result.sample_rate == SAMPLE_RATE
    assert result.samples.ndim == 1
    assert result.samples.dtype == np.float32
    assert isinstance(result.duration_ms, int)
    assert abs(result.duration_ms - 1200) <= 30
    assert abs(result.samples.size - 1200 * SAMPLE_RATE / 1000) <= 30 * SAMPLE_RATE / 1000
    assert np.isfinite(result.samples).all()
    assert np.max(np.abs(result.samples)) > 0.1


def test_decode_rejects_unsupported_suffix(tmp_path):
    path = tmp_path / "audio.ogg"
    _write_wav(path, _sine(1000))

    with pytest.raises(ValueError) as error:
        decode_audio(path)

    assert "不支持" in str(error.value)


def test_decode_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        decode_audio(tmp_path / "missing.wav")

    assert "不存在" in str(error.value)


def test_energy_vad_finds_sine_between_silence(tmp_path):
    samples = np.concatenate(
        (
            np.zeros(SAMPLE_RATE // 2, dtype=np.float32),
            _sine(1000),
            np.zeros(SAMPLE_RATE // 2, dtype=np.float32),
        )
    )
    _write_wav(tmp_path / "silence-sine-silence.wav", samples)

    segments = detect_speech(samples, sample_rate=SAMPLE_RATE, use_onnx=False, speech_pad_ms=0)

    assert len(segments) == 1
    segment = segments[0]
    assert isinstance(segment.start_ms, int)
    assert isinstance(segment.end_ms, int)
    assert segment.start_ms == pytest.approx(500, abs=120)
    assert segment.end_ms == pytest.approx(1500, abs=120)
    assert 0 <= segment.start_ms < segment.end_ms <= 2000


def test_energy_vad_applies_configured_padding():
    samples = np.concatenate(
        (np.zeros(SAMPLE_RATE // 2, dtype=np.float32), _sine(1000), np.zeros(SAMPLE_RATE // 2))
    )

    segments = detect_speech(samples, sample_rate=SAMPLE_RATE, use_onnx=False, speech_pad_ms=200)

    assert _bounds(segments) == [(280, 1700)]


def test_energy_vad_returns_empty_for_pure_silence(tmp_path):
    samples = np.zeros(SAMPLE_RATE, dtype=np.float32)
    _write_wav(tmp_path / "silence.wav", samples)

    assert detect_speech(samples, sample_rate=SAMPLE_RATE, use_onnx=False) == []


def test_energy_vad_converts_float64_samples(tmp_path):
    samples = np.concatenate(
        (
            np.zeros(SAMPLE_RATE // 2, dtype=np.float64),
            _sine(1000).astype(np.float64),
            np.zeros(SAMPLE_RATE // 2, dtype=np.float64),
        )
    )
    _write_wav(tmp_path / "float64.wav", samples)

    segments = detect_speech(samples, sample_rate=SAMPLE_RATE, use_onnx=False, speech_pad_ms=0)

    assert len(segments) == 1
    assert segments[0].start_ms == pytest.approx(500, abs=120)
    assert segments[0].end_ms == pytest.approx(1500, abs=120)


@pytest.mark.parametrize(
    "samples",
    [
        pytest.param(np.array([], dtype=np.float32), id="empty"),
        pytest.param(np.zeros((SAMPLE_RATE, 1), dtype=np.float32), id="two-dimensional"),
        pytest.param(np.zeros((2, 2, 2), dtype=np.float32), id="three-dimensional"),
    ],
)
def test_vad_rejects_empty_or_non_mono_samples(samples):
    with pytest.raises(ValueError):
        detect_speech(samples, sample_rate=SAMPLE_RATE, use_onnx=False)


def test_onnx_vad_is_preferred_and_uses_frame_timestamps(monkeypatch):
    class FakeOnnxVad:
        def __init__(self, *args):
            pass

        def predict(self, audio, sample_rate):
            probabilities = np.zeros(50, dtype=np.float32)
            probabilities[1:3] = 1.0
            return probabilities, 20

    monkeypatch.setattr("app.audio.vad._WhisperOnnxVad", FakeOnnxVad)
    segments = detect_speech(
        np.ones(SAMPLE_RATE, dtype=np.float32),
        use_onnx=True,
        min_speech_duration_ms=0,
        speech_pad_ms=0,
    )

    assert _bounds(segments) == [(20, 60)]


def test_onnx_vad_clamps_final_segment_to_actual_audio(monkeypatch):
    class FakeOnnxVad:
        def __init__(self, *args):
            pass

        def predict(self, audio, sample_rate):
            return np.ones(51, dtype=np.float32), 20

    monkeypatch.setattr("app.audio.vad._WhisperOnnxVad", FakeOnnxVad)
    segments = detect_speech(
        np.ones(16016, dtype=np.float32),
        use_onnx=True,
        min_speech_duration_ms=0,
        speech_pad_ms=100,
    )

    assert _bounds(segments) == [(0, 1001)]


def test_onnx_failure_logs_and_uses_energy_fallback(monkeypatch, caplog):
    class BrokenOnnxVad:
        def __init__(self, *args):
            raise RuntimeError("synthetic ONNX failure")

    monkeypatch.setattr("app.audio.vad._WhisperOnnxVad", BrokenOnnxVad)
    with caplog.at_level(logging.WARNING):
        segments = detect_speech(_sine(1000), use_onnx=True, speech_pad_ms=0)

    assert segments
    assert "ONNX VAD 不可用，改用能量阈值检测" in caplog.text


def test_merge_splits_35_second_continuous_speech_at_30_seconds():
    segments = [SpeechSegment(start_ms=0, end_ms=35000)]

    chunks = merge_speech_segments(segments)

    assert _bounds(chunks) == [(0, 30000), (30000, 35000)]
    _assert_valid_chunks(chunks, segments, max_duration_ms=30000)


def test_merge_combines_only_short_silence_gaps():
    segments = [
        SpeechSegment(start_ms=0, end_ms=800),
        SpeechSegment(start_ms=1000, end_ms=1800),
        SpeechSegment(start_ms=3000, end_ms=3600),
        SpeechSegment(start_ms=3900, end_ms=4500),
    ]

    chunks = merge_speech_segments(segments)

    assert _bounds(chunks) == [(0, 1800), (3000, 4500)]
    _assert_valid_chunks(chunks, segments, max_duration_ms=30000)


def test_merge_respects_custom_duration_without_losing_speech():
    segments = [
        SpeechSegment(start_ms=0, end_ms=12000),
        SpeechSegment(start_ms=12500, end_ms=24000),
        SpeechSegment(start_ms=24500, end_ms=35000),
    ]

    chunks = merge_speech_segments(
        segments,
        max_duration_ms=10000,
        max_silence_gap_ms=500,
    )

    assert _bounds(chunks)
    _assert_valid_chunks(chunks, segments, max_duration_ms=10000)


def test_merge_accepts_empty_input():
    assert merge_speech_segments([]) == []


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"max_duration_ms": 0}, id="zero-duration"),
        pytest.param({"max_duration_ms": -1}, id="negative-duration"),
        pytest.param({"max_silence_gap_ms": -1}, id="negative-gap"),
    ],
)
def test_merge_rejects_invalid_parameters(options):
    segments = [SpeechSegment(start_ms=0, end_ms=1000)]

    with pytest.raises(ValueError):
        merge_speech_segments(segments, **options)


def test_job_temp_directory_is_scoped_and_removed(tmp_path):
    base_dir = tmp_path / "jobs"

    with job_temp_directory("job-test", base_dir=base_dir) as path:
        assert path == base_dir / "job-test"
        assert path.is_dir()
        (path / "scratch.bin").write_bytes(b"synthetic")

    assert not path.exists()
    assert base_dir.is_dir()


def test_job_temp_directory_is_removed_after_exception(tmp_path):
    base_dir = tmp_path / "jobs"

    with pytest.raises(RuntimeError, match="synthetic failure"):
        with job_temp_directory("job-exception", base_dir=base_dir) as path:
            assert path.is_dir()
            raise RuntimeError("synthetic failure")

    assert not path.exists()


@pytest.mark.parametrize(
    "job_id",
    [
        "",
        ".",
        "..",
        "../other",
        r"..\other",
        "nested/job",
        r"nested\job",
        "nested/../other",
    ],
)
def test_job_temp_directory_rejects_invalid_id_without_deleting_other_jobs(tmp_path, job_id):
    base_dir = tmp_path / "jobs"
    other = base_dir / "other"
    other.mkdir(parents=True)
    sentinel = other / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError) as error:
        with job_temp_directory(job_id, base_dir=base_dir):
            pass

    message = str(error.value).lower()
    assert "任务" in message or "job" in message
    assert other.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "keep"
