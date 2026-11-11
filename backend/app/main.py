"""本地 Sidecar：所有请求鉴权，只允许环回 HTTP 来源。"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.glossary import router as glossary_router
from app.api.health import VERSION
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.jobs import ws_router
from app.api.models import router as models_router
from app.api.translation import router as translation_router
from app.config import LOCAL_ORIGIN, Settings
from app.jobs.manager import JobManager, JobRunner
from app.translation.deepseek import DeepSeekTranslator

logger = logging.getLogger("uvicorn.error")


def create_app(
    settings: Settings | None = None,
    *,
    job_runner: JobRunner | None = None,
    translator: DeepSeekTranslator | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        job_manager = JobManager(config, job_runner=job_runner, translator=translator)
        job_manager.start()
        application.state.job_manager = job_manager
        application.state.token = config.token or secrets.token_urlsafe(32)
        if config.token is None:
            # 仅通过本地进程 stdout 交付凭据，不通过 HTTP 暴露，不写业务日志。
            print("SIDECAR_TOKEN " + json.dumps({"token": application.state.token}), flush=True)
        logger.info("本地服务已启动；模型检查按需执行，不加载权重。")
        try:
            yield
        finally:
            job_manager.close()
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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
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
    application.include_router(jobs_router, prefix="/api")
    application.include_router(ws_router)
    application.include_router(glossary_router, prefix="/api")
    application.include_router(translation_router, prefix="/api")
    return application


app = create_app()


def serve() -> None:
    import uvicorn

    def watch_desktop() -> None:
        # Electron 持有 stdin 管道。父进程异常退出时，停止本地服务。
        sys.stdin.buffer.read(1)
        os._exit(0)

    desktop = os.environ.get("JP_WORKBENCH_DESKTOP") == "1"
    if desktop:
        threading.Thread(target=watch_desktop, daemon=True).start()

    class DesktopServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            if desktop and self.started:
                port = self.servers[0].sockets[0].getsockname()[1]
                ready = {"port": port, "token": app.state.token}
                print("SIDECAR_READY " + json.dumps(ready), flush=True)

    DesktopServer(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=0 if desktop else 8765,
            access_log=not desktop,
            loop="asyncio",
            http="h11",
            ws="wsproto",
            lifespan="on",
        )
    ).run()


if __name__ == "__main__":
    serve()
