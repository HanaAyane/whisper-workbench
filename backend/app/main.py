"""本地 Sidecar：所有请求鉴权，只允许环回 HTTP 来源。"""

from __future__ import annotations

import json
import logging
import re
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import VERSION
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.config import Settings

logger = logging.getLogger("uvicorn.error")
LOCAL_ORIGIN = r"http://127\.0\.0\.1(?::[0-9]+)?"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.token = config.token or secrets.token_urlsafe(32)
        if config.token is None:
            # 仅通过本地进程 stdout 交付凭据，不通过 HTTP 暴露，不写业务日志。
            print("SIDECAR_TOKEN " + json.dumps({"token": application.state.token}), flush=True)
        logger.info("本地服务已启动；模型检查按需执行，不加载权重。")
        yield
        application.state.token = None
        logger.info("本地服务已停止。")

    application = FastAPI(
        title="日语语音工作台本地服务",
        version=VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = config

    @application.middleware("http")
    async def local_auth(request: Request, call_next):
        # 浏览器预检没有 token；来源检查后交给 CORS，不进入业务路由。
        if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
            return await call_next(request)
        expected = getattr(request.app.state, "token", None)
        supplied = request.headers.get("x-sidecar-token", "")
        if not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
            return JSONResponse(status_code=401, content={"detail": "本地服务令牌缺失或无效。"})
        return await call_next(request)

    # CORS 在鉴权外层，使允许来源也能读取中文 401 错误。
    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_ORIGIN,
        allow_methods=["GET"],
        allow_headers=["X-Sidecar-Token"],
        allow_credentials=False,
    )

    @application.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin is not None and re.fullmatch(LOCAL_ORIGIN, origin) is None:
            return JSONResponse(status_code=403, content={"detail": "仅允许本机环回 HTTP 来源。"})
        return await call_next(request)

    application.include_router(health_router, prefix="/api")
    application.include_router(models_router, prefix="/api")
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
