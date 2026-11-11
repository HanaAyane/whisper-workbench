"""翻译提示词预设：只读默认值，供桌面设置页展示与恢复默认。"""

from typing import Any

from fastapi import APIRouter

from app.translation.prompt import (
    DEFAULT_SYSTEM_PROMPT,
    MANDATORY_RULES,
    MAX_SYSTEM_PROMPT_CHARS,
)

router = APIRouter()


@router.get("/translation/prompt")
def translation_prompt() -> dict[str, Any]:
    # 固定规则只用于界面展示；实际发送时由后端重新拼装，客户端改不了。
    return {
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "mandatory_rules": MANDATORY_RULES,
        "max_chars": MAX_SYSTEM_PROMPT_CHARS,
    }
