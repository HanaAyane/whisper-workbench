"""翻译预设、DeepSeek 配置状态与模型列表（只读，不持久化任何密钥）。"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.translation.deepseek import DeepSeekConfig, TranslationError, list_models
from app.translation.prompt import (
    DEFAULT_SYSTEM_PROMPT,
    MANDATORY_RULES,
    MAX_SYSTEM_PROMPT_CHARS,
)

router = APIRouter()


class ModelsRequest(BaseModel):
    # 设置页刚填写的 Key；省略时使用 .env / 环境变量里的配置。
    api_key: str | None = Field(default=None, min_length=1, max_length=512)


@router.get("/translation/prompt")
def translation_prompt() -> dict[str, Any]:
    # 固定规则只用于界面展示；实际发送时由后端重新拼装，客户端改不了。
    return {
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "mandatory_rules": MANDATORY_RULES,
        "max_chars": MAX_SYSTEM_PROMPT_CHARS,
    }


@router.get("/translation/config")
def translation_config(request: Request) -> dict[str, Any]:
    """暴露 .env / 环境变量里的生效模型与强度，不返回 Key 本身。"""
    config = DeepSeekConfig.from_settings(request.app.state.settings, require_key=False)
    return {
        "api_key_configured": bool(config.api_key),
        "model": config.model,
        "thinking": config.thinking,
        "base_url": config.base_url,
    }


@router.post("/translation/models")
def translation_models(body: ModelsRequest, request: Request) -> dict[str, Any]:
    """按当前 Key 读取 DeepSeek 模型列表；Key 只用于这一次请求。"""
    try:
        config = DeepSeekConfig.from_settings(request.app.state.settings, api_key=body.api_key)
        return {
            "models": list_models(config),
            "base_url": config.base_url,
            "model": config.model,
            "thinking": config.thinking,
        }
    except TranslationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
