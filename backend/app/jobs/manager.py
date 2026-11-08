"""持久化任务队列与本地推理。"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.asr.model_manager import ModelError, ModelManager
from app.asr.whisper_backend import recognize_chunks
from app.audio.chunks import merge_speech_segments
from app.audio.decode import SUPPORTED_SUFFIXES, AudioDecodeError, decode_audio
from app.audio.vad import detect_speech
from app.config import Settings
from app.glossary.models import GlossaryEntry, GlossaryNotFoundError, GlossaryValidationError
from app.glossary.store import GlossaryStore
from app.jobs.cancellation import JobCancelled
from app.jobs.review import edit_text, propose, review
from app.jobs.schemas import JobRequest, JobStage, JobStatus, Segment, SegmentEdit, SegmentReview
from app.storage.jobs import JobStore
from app.translation.deepseek import DeepSeekConfig, DeepSeekTranslator, TranslationError

logger = logging.getLogger(__name__)
ProgressReporter = Callable[[float, JobStage, str], None]
JobRunner = Callable[[JobRequest, ProgressReporter], list[Segment]]
JobListener = Callable[[JobStatus], None]
_RECORDING_NAME = re.compile(r"recording-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.webm")


class JobManager:
    """单 worker 按提交顺序执行。数据库提交后才发送状态。"""

    def __init__(
        self,
        settings: Settings,
        *,
        job_runner: JobRunner | None = None,
        translator: DeepSeekTranslator | None = None,
    ) -> None:
        self.settings = settings
        self.model_manager = ModelManager(settings)
        self._runner = job_runner
        self._translator = translator
        self._lock = threading.RLock()
        self._store: JobStore
        self._started = False
        self._closing = False
        self._recordings: dict[str, Path] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._listeners: dict[str, set[JobListener]] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jp-job")

    @property
    def recordings_dir(self) -> Path:
        return (
            self.settings.recordings_dir or self.settings.project_root / "data" / "recordings-tmp"
        ).resolve()

    def start(self) -> None:
        try:
            self._store = JobStore(
                self.settings.jobs_path or self.settings.project_root / "data" / "jobs.sqlite3"
            )
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError(
                "无法打开任务数据库，请检查写入权限或关闭占用数据库的实例。"
            ) from exc
        try:
            for path in self.recordings_dir.glob("recording-*.webm"):
                if (
                    _RECORDING_NAME.fullmatch(path.name)
                    and path.is_file()
                    and not path.is_symlink()
                ):
                    self._remove_recording(path)
            interrupted = self._store.list(active_only=True)
            self._store.save(
                *(
                    job.model_copy(
                        update={
                            "state": "cancelled",
                            "message": "上次退出时任务中断",
                            "cancel_requested": False,
                            "revision": job.revision + 1,
                        }
                    )
                    for job in interrupted
                )
            )
            for job in self._store.without_review_snapshot():
                # 迁移只按已保存的副本重新匹配，避免沿用旧版的原文位置。
                try:
                    entries = self._load_glossary(job.glossary_id) if job.segments else []
                except (GlossaryValidationError, OSError):
                    logger.warning("历史词表无法读取，已保留当前字幕。")
                    entries = []
                self._update(
                    job,
                    entries=entries,
                    segments=[propose(segment, entries) for segment in job.segments],
                )
            self._started = True
        except Exception:
            self._store.close()
            raise

    def create_job(self, request: JobRequest) -> JobStatus:
        path = Path(request.input_path).expanduser()
        if not path.is_file():
            raise ValueError("音频文件不存在或不是普通文件，请重新选择媒体。")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"不支持的音频/视频格式：{path.suffix or '无扩展名'}。")
        self.model_manager.get_spec(request.asr_model_id, expected_type="asr")
        if request.mode == "translate" and self._translator is None:
            try:
                self._translation_config(request)
            except TranslationError as exc:
                raise ValueError(str(exc)) from exc

        recording = None
        if request.recording == "temporary":
            recording = path.resolve()
            if (
                recording.parent != self.recordings_dir
                or not _RECORDING_NAME.fullmatch(recording.name)
                or path.is_symlink()
            ):
                raise ValueError("临时录音必须位于工作台专用目录。")

        with self._lock:
            if self._closing:
                raise ValueError("本地服务正在关闭，请重新启动工作台。")
            if recording is not None and recording in self._recordings.values():
                raise ValueError("此录音已提交。")
            now = datetime.now().astimezone()
            job = JobStatus(
                id=f"job-{now:%Y%m%d}-{uuid4().hex}",
                name=request.name or path.name,
                mode=request.mode,
                glossary_id=request.glossary_id,
                recorded_path=str(path.resolve()) if request.recording == "retained" else None,
                created_at=now.isoformat(),
                state="queued",
                stage="decode",
                progress=0,
                message="排队中",
            )
            self._store.save(job)
            if recording is not None:
                self._recordings[job.id] = recording
            # 写入与入队共享同一把锁，避免并发提交时队列顺序错位。
            self._executor.submit(self._execute, job.id, request)
            return job

    def get_job(self, job_id: str) -> JobStatus:
        with self._lock:
            return self._store.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        with self._lock:
            return self._store.list()

    def update_segment(self, job_id: str, segment_id: int, edit: SegmentEdit) -> JobStatus:
        return self._change_segment(
            job_id,
            segment_id,
            edit.revision,
            lambda segment, entries: edit_text(segment, edit, entries),
        )

    def review_segment(self, job_id: str, segment_id: int, decision: SegmentReview) -> JobStatus:
        return self._change_segment(
            job_id,
            segment_id,
            decision.revision,
            lambda segment, entries: review(segment, decision, entries),
        )

    def _change_segment(
        self,
        job_id: str,
        segment_id: int,
        revision: int,
        change: Callable[[Segment, list[GlossaryEntry]], Segment],
    ) -> JobStatus:
        with self._lock:
            job = self._store.get(job_id)
            if job.state != "succeeded":
                raise ValueError("任务完成后才能编辑字幕。")
            for index, segment in enumerate(job.segments):
                if segment.id != segment_id:
                    continue
                if segment.revision != revision:
                    raise ValueError("这个片段已更新，请重新读取后再保存。")
                updated = change(segment, self._store.glossary(job_id))
                if updated == segment:
                    return job
                segments = job.segments.copy()
                segments[index] = updated.model_copy(update={"revision": revision + 1})
                return self._update(job, segments=segments)
            raise KeyError(segment_id)

    @contextmanager
    def subscribe(self, job_id: str, listener: JobListener) -> Iterator[JobStatus]:
        with self._lock:
            job = self._store.get(job_id)
            self._listeners.setdefault(job_id, set()).add(listener)
        try:
            yield job
        finally:
            with self._lock:
                listeners = self._listeners[job_id]
                listeners.remove(listener)
                if not listeners:
                    del self._listeners[job_id]

    def close(self) -> None:
        with self._lock:
            self._closing = True
            if self._started:
                for job in self._store.list(active_only=True):
                    self.cancel_job(job.id)
        self._executor.shutdown(wait=True, cancel_futures=True)
        if self._started:
            self._store.close()
            self._started = False

    def cancel_job(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._store.get(job_id)
            if job.state == "queued":
                self._finish_recording(job_id)
                return self._update(job, state="cancelled", message="已取消")
            if job.state == "running" and not job.cancel_requested:
                job = self._update(
                    job, cancel_requested=True, message="正在取消，等待当前处理步骤结束"
                )
                self._cancel_events[job_id].set()
            return job

    def _update(
        self, job: JobStatus, *, entries: list[GlossaryEntry] | None = None, **changes
    ) -> JobStatus:
        value = job.model_copy(update={**changes, "revision": job.revision + 1})
        self._store.save(value, entries=entries)
        for notify in self._listeners.get(job.id, ()):
            notify(value)
        return value

    def _remove_recording(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("临时录音暂时无法清理，下次启动时重试。")

    def _finish_recording(self, job_id: str) -> None:
        recording = self._recordings.pop(job_id, None)
        if recording is not None:
            self._remove_recording(recording)

    def _execute(self, job_id: str, request: JobRequest) -> None:
        # 每帧取消检查只读线程事件，避免解码和推理频繁访问数据库。
        cancelled = threading.Event()
        with self._lock:
            job = self._store.get(job_id)
            if job.state == "cancelled":
                return
            self._update(job, state="running", progress=0.01, message="开始处理")
            self._cancel_events[job_id] = cancelled

        def check_cancelled() -> None:
            if cancelled.is_set():
                raise JobCancelled

        def report(progress: float, stage: JobStage, message: str) -> None:
            with self._lock:
                check_cancelled()
                job = self._store.get(job_id)
                self._update(
                    job,
                    progress=max(job.progress, min(progress, 1.0)),
                    stage=stage,
                    message=message,
                )

        error = None
        segments: list[Segment] = []
        entries: list[GlossaryEntry] = []
        try:
            check_cancelled()
            if self._runner is None:
                segments = self._run_pipeline(request, report, check_cancelled)
            else:
                segments = self._runner(request, report)
            if segments and request.glossary_id:
                report(0.92, "glossary", "正在生成术语建议")
                entries = self._load_glossary(request.glossary_id)
                for index, segment in enumerate(segments):
                    check_cancelled()
                    segments[index] = propose(segment, entries)
            report(0.98, "export", "正在保存任务结果")
        except JobCancelled:
            cancelled.set()
        except Exception as exc:
            error = _error_message(exc)
            logger.warning("任务 %s 失败（%s）", job_id, type(exc).__name__)

        with self._lock:
            job = self._store.get(job_id)
            self._finish_recording(job_id)
            del self._cancel_events[job_id]
            if cancelled.is_set():
                self._update(job, state="cancelled", message="已取消", cancel_requested=False)
            elif error is not None:
                self._update(job, state="failed", message="处理失败", error=error)
            else:
                message = "处理完成" if segments else "处理完成（无语音段）"
                self._update(
                    job,
                    state="succeeded",
                    message=message,
                    progress=1.0,
                    segments=segments,
                    entries=entries,
                )

    def _run_pipeline(
        self,
        request: JobRequest,
        report: ProgressReporter,
        check_cancelled: Callable[[], None] | None = None,
    ) -> list[Segment]:
        report(0.03, "decode", "正在解码音频")
        decoded = decode_audio(request.input_path, check_cancelled=check_cancelled)
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
            check_cancelled=check_cancelled,
        )
        chunks = merge_speech_segments(speech, max_duration_ms=30000)
        if not chunks:
            report(0.9, "vad", "未检测到语音，跳过后处理")
            return []

        report(0.24, "asr", "正在加载本地模型")
        loaded = self.model_manager.load(
            request.asr_model_id,
            expected_type="asr",
            device=request.device,
            compute_type=request.compute_type,
        )
        report(0.25, "asr", "开始转写")

        def chunk_progress(done: int, total: int) -> None:
            report(0.25 + 0.55 * done / max(total, 1), "asr", f"正在转写 {done}/{total} 块")

        result = recognize_chunks(
            loaded.model,
            decoded.samples,
            chunks,
            language=request.language,
            task="transcribe",
            on_progress=chunk_progress,
            check_cancelled=check_cancelled,
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
                    check_cancelled=check_cancelled,
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
        logger.info(
            "任务处理完成：音频 %d 毫秒，语音 %d 毫秒，%d 段。",
            decoded.duration_ms,
            result.duration_after_vad_ms,
            len(segments),
        )
        return segments

    def _load_glossary(self, glossary_id: str | None) -> list[GlossaryEntry]:
        if glossary_id is not None:
            try:
                return GlossaryStore(self.settings).load(glossary_id)
            except GlossaryNotFoundError:
                pass
        return []

    def _translation_config(self, request: JobRequest) -> DeepSeekConfig:
        config = DeepSeekConfig.from_settings(self.settings)
        if request.translation.model and request.translation.model != config.model:
            config = replace(config, model=request.translation.model)
        return config


def _error_message(error: Exception) -> str:
    detail = str(error).lower()
    if any(term in detail for term in ("out of memory", "alloc_failed", "显存不足")):
        return "推理内存或显存不足。请关闭占用显存的程序，改用 int8 或 CPU 后重试。"
    if isinstance(error, AudioDecodeError):
        return "无法解码音频。请检查媒体是否完整，或转换为 WAV 后重试。"
    if isinstance(error, FileNotFoundError):
        return "输入媒体已不存在，请重新选择文件。"
    if isinstance(error, ModelError):
        return f"{error} 请在设置中检查模型清单和推理配置。"
    if isinstance(error, TranslationError | GlossaryValidationError):
        return str(error)
    return "本地处理失败。请检查媒体、模型和推理设置后重试。"
