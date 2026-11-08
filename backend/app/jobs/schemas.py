"""任务 API 的数据契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.glossary.models import TermHit

ExportFormat = Literal["srt", "vtt", "lrc", "txt"]
SegmentField = Literal["text", "translation"]


class VadOptions(BaseModel):
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    min_speech_duration_ms: int = Field(default=300, ge=0)
    min_silence_duration_ms: int = Field(default=100, ge=0)
    speech_pad_ms: int = Field(default=200, ge=0)


class TranslationOptions(BaseModel):
    provider: Literal["deepseek"] = "deepseek"
    model: str | None = Field(default=None, min_length=1)


class JobRequest(BaseModel):
    input_path: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=512)
    recording: Literal["temporary", "retained"] | None = None
    mode: Literal["transcribe", "translate"] = "transcribe"
    asr_model_id: str = Field(min_length=1)
    translation: TranslationOptions = Field(default_factory=TranslationOptions)
    language: str = "ja"
    glossary_id: str | None = "default"
    device: Literal["auto", "cpu", "cuda"] | None = None
    compute_type: Literal["int8", "int8_float16", "float16", "bfloat16"] | None = None
    export_formats: list[ExportFormat] = Field(default_factory=list)
    vad: VadOptions = Field(default_factory=VadOptions)


class ReviewHit(TermHit):
    decision: Literal["pending", "accepted", "rejected"] = "pending"
    original_text: str | None = None
    applied_revision: int = 0


class Segment(BaseModel):
    id: int
    start: int
    end: int
    raw_text: str
    raw_translation: str | None = None
    text: str
    translation: str | None = None
    hits: list[ReviewHit] = Field(default_factory=list)
    revision: int = 0


class SegmentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    translation: str | None
    revision: int = Field(ge=0)


class HitSelection(BaseModel):
    entry_id: str
    field: SegmentField
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class SegmentReview(BaseModel):
    action: Literal["accept", "reject", "undo"]
    revision: int = Field(ge=0)
    hit: HitSelection | None = None

    @model_validator(mode="after")
    def check_selection(self) -> SegmentReview:
        if (self.action == "undo") != (self.hit is None):
            raise ValueError("接受或拒绝时必须指定命中，撤销时只需要指定片段。")
        return self


class ExportRequest(BaseModel):
    format: ExportFormat


JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobStage = Literal["decode", "vad", "asr", "glossary", "export"]
ACTIVE_STATES = {"queued", "running"}


class JobStatus(BaseModel):
    id: str
    state: JobState
    progress: float
    stage: JobStage | None
    message: str
    segments: list[Segment] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    error: str | None = None
    name: str = ""
    mode: Literal["transcribe", "translate"] = "transcribe"
    recorded_path: str | None = None
    created_at: str = ""
    revision: int = 0
    cancel_requested: bool = False
    glossary_id: str | None = None
