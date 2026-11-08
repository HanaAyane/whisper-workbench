"""任务接口及受鉴权的状态推送。"""

import asyncio
import re
import secrets

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app.asr.model_manager import ModelError
from app.config import LOCAL_ORIGIN
from app.export.writers import render_subtitles
from app.jobs.schemas import (
    ACTIVE_STATES,
    ExportRequest,
    JobRequest,
    JobStatus,
    SegmentEdit,
    SegmentReview,
)

router = APIRouter()
ws_router = APIRouter()


@router.get("/jobs", response_model=list[JobStatus])
def list_jobs(request: Request) -> list[JobStatus]:
    return request.app.state.job_manager.list_jobs()


@router.post("/jobs", response_model=JobStatus, status_code=202)
def create_job(payload: JobRequest, request: Request) -> JobStatus:
    manager = request.app.state.job_manager
    try:
        return manager.create_job(payload)
    except (ModelError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, request: Request) -> JobStatus:
    try:
        return request.app.state.job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已过期。") from exc


@router.post("/jobs/{job_id}/cancel", response_model=JobStatus)
def cancel_job(job_id: str, request: Request) -> JobStatus:
    try:
        return request.app.state.job_manager.cancel_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已过期。") from exc


@router.patch("/jobs/{job_id}/segments/{segment_id}", response_model=JobStatus)
def update_segment(
    job_id: str, segment_id: int, payload: SegmentEdit, request: Request
) -> JobStatus:
    try:
        return request.app.state.job_manager.update_segment(job_id, segment_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="找不到任务或字幕片段。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/segments/{segment_id}/review", response_model=JobStatus)
def review_segment(
    job_id: str, segment_id: int, payload: SegmentReview, request: Request
) -> JobStatus:
    try:
        return request.app.state.job_manager.review_segment(job_id, segment_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="找不到任务或字幕片段。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/export", response_class=PlainTextResponse)
def export_job(job_id: str, payload: ExportRequest, request: Request) -> PlainTextResponse:
    try:
        job = request.app.state.job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="找不到任务。") from exc
    if job.state != "succeeded":
        raise HTTPException(status_code=409, detail="任务完成后才能导出字幕。")
    return PlainTextResponse(
        render_subtitles(job.segments, payload.format),
        media_type="text/vtt" if payload.format == "vtt" else "text/plain",
    )


@ws_router.websocket("/ws/jobs/{job_id}")
async def stream_job(socket: WebSocket, job_id: str) -> None:
    origin = socket.headers.get("origin")
    protocols = socket.scope["subprotocols"]
    expected = socket.app.state.token
    supplied = socket.headers.get("x-sidecar-token", "")
    if not supplied and len(protocols) == 2 and protocols[0] == "jp-workbench":
        supplied = protocols[1]
    if (
        (origin is not None and re.fullmatch(LOCAL_ORIGIN, origin) is None)
        or not expected
        or not secrets.compare_digest(expected.encode(), supplied.encode())
    ):
        await socket.close(code=1008)
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[JobStatus] = asyncio.Queue(maxsize=1)

    def enqueue(value: JobStatus) -> None:
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(value)

    def notify(value: JobStatus) -> None:
        loop.call_soon_threadsafe(enqueue, value)

    manager = socket.app.state.job_manager
    try:
        with manager.subscribe(job_id, notify) as current:
            await socket.accept(subprotocol="jp-workbench" if "jp-workbench" in protocols else None)
            receive = asyncio.create_task(socket.receive())
            try:
                while True:
                    await socket.send_json(current.model_dump(mode="json"))
                    if current.state not in ACTIVE_STATES:
                        await socket.close()
                        return
                    update = asyncio.create_task(queue.get())
                    try:
                        await asyncio.wait((receive, update), return_when=asyncio.FIRST_COMPLETED)
                        if receive.done():
                            if receive.result()["type"] != "websocket.disconnect":
                                await socket.close(code=1008)
                            return
                        current = update.result()
                    finally:
                        update.cancel()
                        await asyncio.gather(update, return_exceptions=True)
            finally:
                receive.cancel()
                await asyncio.gather(receive, return_exceptions=True)
    except KeyError:
        await socket.close(code=1008)
    except WebSocketDisconnect:
        pass
