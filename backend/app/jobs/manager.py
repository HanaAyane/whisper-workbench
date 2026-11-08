"""Phase 3 任务状态机与后台执行（内存态，持久化留待 Phase 6）。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from app.asr.model_manager import ModelManager
from app.asr.whisper_backend import recognize_chunks
from app.audio.chunks import merge_speech_segments
from app.audio.decode import SUPPORTED_SUFFIXES, decode_audio
from app.audio.vad import detect_speech
from app.config import Settings
from app.glossary.models import GlossaryNotFoundError
from app.glossary.replacer import apply_to_segment
from app.glossary.store import GlossaryStore
from app.jobs.schemas import JobRequest, JobStatus, Segment
from app.translation.deepseek import (
    DeepSeekConfig,
    DeepSeekTranslator,
    TranslationError,
)

logger = logging.getLogger(__name__)

ProgressReporter = Callable[[float, str, str], None]
JobRunner = Callable[[JobRequest, ProgressReporter], list[Segment]]


@dataclass
class JobRecord:
    id: str
    request: JobRequest
    state: str = "queued"
    progress: float = 0.0
    stage: str = "decode"
    message: str = "排队中"
    segments: list[Segment] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    error: str | None = None


class JobManager:
    """单 worker 顺序执行，状态变更加锁；关闭时等待在跑任务结束。"""

    def __init__(
        self,
        settings: Settings,
        *,
        job_runner: JobRunner | None = None,
        translator: DeepSeekTranslator | None = None,
        max_workers: int = 1,
    ) -> None:
        self.settings = settings
        self.model_manager = ModelManager(settings)
        self._runner = job_runner or self._run_pipeline
        self._translator = translator
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()
        self._counter = 0
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jp-job")

    def create_job(self, request: JobRequest) -> JobStatus:
        path = Path(request.input_path).expanduser()
        if not path.is_file():
            raise ValueError(f"音频文件不存在或不是普通文件：{path}")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"不支持的音频/视频格式：{path.suffix or '无扩展名'}。")
        self.model_manager.get_spec(request.asr_model_id, expected_type="asr")
        if request.mode == "translate":
            if request.translation.provider != "deepseek":
                raise ValueError("当前仅支持 deepseek 翻译服务。")
            if self._translator is None:
                try:
                    self._translation_config(request)
                except TranslationError as exc:
                    raise ValueError(str(exc)) from exc

        with self._lock:
            self._counter += 1
            job_id = f"job-{datetime.now():%Y%m%d}-{self._counter:03d}"
            job = JobRecord(id=job_id, request=request)
            self._jobs[job_id] = job
        self._executor.submit(self._execute, job)
        return self._status(job)

    def get_job(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return self._status(job)

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _status(self, job: JobRecord) -> JobStatus:
        return JobStatus(
            id=job.id,
            state=job.state,
            progress=job.progress,
            stage=job.stage,
            message=job.message,
            segments=list(job.segments),
            outputs=list(job.outputs),
            error=job.error,
        )

    def _execute(self, job: JobRecord) -> None:
        with self._lock:
            job.state = "running"
            job.message = "开始处理"
            job.progress = 0.01

        def report(progress: float, stage: str, message: str = "") -> None:
            with self._lock:
                job.progress = max(job.progress, min(progress, 1.0))
                job.stage = stage
                job.message = message

        try:
            segments = self._runner(job.request, report)
        except Exception as exc:  # 失败必须落到可查询状态，不能用 500 吞掉。
            logger.exception("任务 %s 失败", job.id)
            with self._lock:
                job.state = "failed"
                job.error = str(exc) or type(exc).__name__
                job.message = "处理失败"
        else:
            with self._lock:
                job.segments = segments
                job.state = "succeeded"
                job.progress = 1.0
                job.stage = "export"
                job.message = "处理完成"

    def _run_pipeline(self, request: JobRequest, report: ProgressReporter) -> list[Segment]:
        report(0.03, "decode", "正在解码音频")
        decoded = decode_audio(request.input_path)
        report(0.18, "vad", "正在检测语音")
        try:
            vad_model, vad_metadata = self.model_manager.vad_paths()
        except Exception:
            vad_model = vad_metadata = None
        speech = detect_speech(
            decoded.samples,
            model_path=vad_model,
            metadata_path=vad_metadata,
            threshold=request.vad.threshold,
            min_speech_duration_ms=request.vad.min_speech_duration_ms,
            min_silence_duration_ms=request.vad.min_silence_duration_ms,
            speech_pad_ms=request.vad.speech_pad_ms,
        )
        chunks = merge_speech_segments(speech, max_duration_ms=30000)
        if not chunks:
            report(0.95, "glossary", "未检测到语音，跳过后处理")
            report(1.0, "export", "处理完成（无语音段）")
            return []

        loaded = self.model_manager.load(request.asr_model_id, expected_type="asr")

        def chunk_progress(done: int, total: int) -> None:
            report(0.25 + 0.55 * done / max(total, 1), "asr", f"正在转写 {done}/{total} 块")

        result = recognize_chunks(
            loaded.model,
            decoded.samples,
            chunks,
            language=request.language,
            task="transcribe",
            on_progress=chunk_progress,
        )
        translations: list[str] | None = None
        if request.mode == "translate":
            report(0.82, "asr", "正在调用 DeepSeek 翻译")
            translator = self._translator or DeepSeekTranslator(self._translation_config(request))
            try:
                translations = translator.translate_segments(
                    [span.text for span in result.spans],
                    source_language=request.language,
                    target_language="zh",
                    on_progress=lambda done, total: report(
                        0.82 + 0.08 * done / max(total, 1),
                        "asr",
                        f"正在翻译 {done}/{total} 批",
                    ),
                )
            finally:
                if self._translator is None:
                    translator.close()

        segments: list[Segment] = []
        for index, span in enumerate(result.spans):
            translation = (
                translations[index]
                if translations is not None and index < len(translations)
                else None
            )
            segments.append(
                Segment(
                    id=index,
                    start=span.start_ms,
                    end=span.end_ms,
                    raw_text=span.text,
                    raw_translation=translation,
                    text=span.text,
                    translation=translation,
                )
            )
        if request.glossary_id:
            try:
                entries = GlossaryStore(self.settings).load(request.glossary_id)
            except GlossaryNotFoundError:
                report(0.94, "glossary", "未找到词表，跳过词表处理")
            else:
                if entries:
                    report(0.92, "glossary", f"正在应用词表（{len(entries)} 条）")
                    segments = [
                        Segment(**apply_to_segment(segment.model_dump(), entries))
                        for segment in segments
                    ]
        report(0.98, "export", "导出将在 Phase 7 接入")
        logger.info(
            "任务处理完成：音频 %d 毫秒，语音 %d 毫秒，%d 段。",
            decoded.duration_ms,
            result.duration_after_vad_ms,
            len(segments),
        )
        return segments

    def _translation_config(self, request: JobRequest) -> DeepSeekConfig:
        config = DeepSeekConfig.from_settings(self.settings)
        if request.translation.model and request.translation.model != config.model:
            config = replace(config, model=request.translation.model)
        return config
