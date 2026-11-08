"""任务创建与状态查询接口。"""

from fastapi import APIRouter, HTTPException, Request

from app.asr.model_manager import ModelError
from app.jobs.schemas import JobRequest, JobStatus

router = APIRouter()


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
