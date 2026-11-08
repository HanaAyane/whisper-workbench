"""任务 API 的数据契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    mode: Literal["transcribe", "translate"] = "transcribe"
    asr_model_id: str = Field(min_length=1)
    translation: TranslationOptions = Field(default_factory=TranslationOptions)
    language: str = "ja"
    glossary_id: str | None = "default"
    device: Literal["auto", "cpu", "cuda"] | None = None
    compute_type: Literal["int8", "int8_float16", "float16", "bfloat16"] | None = None
    export_formats: list[Literal["srt", "vtt", "lrc", "txt"]] = Field(default_factory=list)
    vad: VadOptions = Field(default_factory=VadOptions)


class Segment(BaseModel):
    id: int
    start: int
    end: int
    raw_text: str
    raw_translation: str | None = None
    text: str
    translation: str | None = None
    hits: list[dict[str, object]] = Field(default_factory=list)


JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobStage = Literal["decode", "vad", "asr", "glossary", "export"]


class JobStatus(BaseModel):
    id: str
    state: JobState
    progress: float
    stage: JobStage | None
    message: str
    segments: list[Segment] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    error: str | None = None
