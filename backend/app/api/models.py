"""读取本地清单并返回逐文件检查结果。"""

from typing import Any

from fastapi import APIRouter, Request

from app.model_catalog import inspect_models

router = APIRouter()


@router.get("/models")
def models(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return inspect_models(settings)
