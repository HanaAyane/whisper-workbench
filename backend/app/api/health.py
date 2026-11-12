"""服务健康检查；缺少模型不代表服务不可访问。"""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.model_catalog import inspect_manifest

VERSION = "0.2.0"
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    models_ok: bool


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    report = inspect_manifest(settings.manifest_path, settings.project_root)
    return HealthResponse(status="ok", version=VERSION, models_ok=report["models_ok"])
