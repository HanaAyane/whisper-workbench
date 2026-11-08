"""术语表数据模型与校验。"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GlossaryError(RuntimeError):
    """术语表校验或存储错误的基类。"""


class GlossaryValidationError(GlossaryError):
    """导入内容不合法。"""


class GlossaryNotFoundError(GlossaryError):
    """指定词表不存在。"""


class ReplacementPolicy(str, Enum):
    correct = "correct"
    translate = "translate"
    keep = "keep"
    mask = "mask"


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    variants: list[str] = Field(default_factory=list)
    target: str = ""
    category: str = "term"
    match_mode: Literal["exact", "regex", "fuzzy"] = "exact"
    regex: str | None = None
    priority: int = 100
    field: Literal["text", "translation"] = "text"
    policy: ReplacementPolicy = ReplacementPolicy.keep
    enabled: bool = True

    @field_validator("source")
    @classmethod
    def _source_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source 不能为空。")
        return value.strip()

    @field_validator("variants")
    @classmethod
    def _clean_variants(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    @field_validator("match_mode")
    @classmethod
    def _only_exact(cls, value: str) -> str:
        if value != "exact":
            raise ValueError("当前仅支持 match_mode=exact；regex/fuzzy 属于 V1，尚未实现。")
        return value

    @field_validator("policy")
    @classmethod
    def _no_mask(cls, value: ReplacementPolicy) -> ReplacementPolicy:
        if value is ReplacementPolicy.mask:
            raise ValueError("mask 策略属于 STRETCH，尚未实现。")
        return value

    @model_validator(mode="after")
    def _validate_policy_field(self) -> GlossaryEntry:
        if self.policy in (ReplacementPolicy.correct, ReplacementPolicy.translate):
            if not self.target.strip():
                raise ValueError("correct/translate 策略必须提供非空 target。")
        if self.policy is ReplacementPolicy.correct and self.field != "text":
            raise ValueError("correct 策略只能作用于 text（日语原文）。")
        if self.policy is ReplacementPolicy.translate and self.field != "translation":
            raise ValueError("translate 策略只能作用于 translation（中文译文）。")
        return self


class TermHit(BaseModel):
    entry_id: str
    field: Literal["text", "translation"]
    start: int
    end: int
    matched_text: str
    replacement: str | None = None
    policy: ReplacementPolicy
    confidence: float = 1.0


class ReplacementResult(BaseModel):
    text: str
    replaced_text: str
    hits: list[TermHit] = Field(default_factory=list)
