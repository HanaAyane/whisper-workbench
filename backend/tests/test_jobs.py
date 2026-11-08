"""Phase 3 任务状态机与 /api/jobs 接口测试（使用假 runner，不加载模型）。"""

import time
import wave

import numpy as np
import pytest
from app.config import Settings
from app.jobs.schemas import Segment
from app.main import create_app
from fastapi.testclient import TestClient

HEADERS = {"X-Sidecar-Token": "dev"}


@pytest.fixture
def settings(tmp_path, catalog):
    root, manifest, _ = catalog
    return Settings(
        project_root=root,
        models_dir=root / "models",
        manifest_path=manifest,
        temp_dir=tmp_path / "tmp",
        token="dev",
    )


def _write_wav(path):
    samples = (0.1 * np.sin(np.arange(16000) * 0.1)).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(samples.tobytes())
    return path


def _payload(audio_path):
    return {
        "input_path": str(audio_path),
        "mode": "transcribe",
        "asr_model_id": "synthetic-test",
        "language": "ja",
    }


def _wait(client, job_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        if data["state"] in {"succeeded", "failed", "cancelled"}:
            return data
        time.sleep(0.01)
    raise AssertionError("任务未在超时内结束")


def _segments(_request, report):
    report(0.5, "asr", "正在转写 1/1 块")
    return [
        Segment(
            id=0,
            start=0,
            end=1200,
            raw_text="テストです。",
            text="テストです。",
            raw_translation=None,
            translation=None,
        )
    ]


def test_job_success_lifecycle(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")
    application = create_app(settings, job_runner=_segments)
    with TestClient(application) as client:
        response = client.post("/api/jobs", json=_payload(audio), headers=HEADERS)
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert response.json()["state"] in {"queued", "running", "succeeded"}
        data = _wait(client, job_id)
    assert data["state"] == "succeeded"
    assert data["progress"] == 1.0
    assert data["segments"][0]["raw_text"] == "テストです。"
    assert data["segments"][0]["text"] == "テストです。"
    assert data["error"] is None


def test_job_failure_is_queryable(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")

    def broken(_request, report):
        report(0.3, "asr", "正在转写")
        raise RuntimeError("模型显存不足，请改用 int8_float16")

    application = create_app(settings, job_runner=broken)
    with TestClient(application) as client:
        job_id = client.post("/api/jobs", json=_payload(audio), headers=HEADERS).json()["id"]
        data = _wait(client, job_id)
    assert data["state"] == "failed"
    assert "显存不足" in data["error"]


def test_create_rejects_missing_audio(settings, tmp_path):
    application = create_app(settings, job_runner=_segments)
    with TestClient(application) as client:
        response = client.post(
            "/api/jobs", json=_payload(tmp_path / "missing.wav"), headers=HEADERS
        )
    assert response.status_code == 400
    assert "不存在" in response.json()["detail"]


def test_create_rejects_unknown_model(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")
    application = create_app(settings, job_runner=_segments)
    payload = {**_payload(audio), "asr_model_id": "missing-model"}
    with TestClient(application) as client:
        response = client.post("/api/jobs", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "missing-model" in response.json()["detail"]


def test_translate_requires_translate_model(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")
    application = create_app(settings, job_runner=_segments)
    payload = {**_payload(audio), "mode": "translate"}
    with TestClient(application) as client:
        response = client.post("/api/jobs", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "translate_model_id" in response.json()["detail"]


def test_unknown_job_returns_404(settings):
    application = create_app(settings, job_runner=_segments)
    with TestClient(application) as client:
        response = client.get("/api/jobs/job-20260101-001", headers=HEADERS)
    assert response.status_code == 404


def test_jobs_endpoints_require_token(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")
    application = create_app(settings, job_runner=_segments)
    with TestClient(application) as client:
        post = client.post("/api/jobs", json=_payload(audio))
        get = client.get("/api/jobs/anything")
    assert post.status_code == get.status_code == 401


def test_cors_preflight_allows_post(settings):
    application = create_app(settings, job_runner=_segments)
    with TestClient(application) as client:
        response = client.options(
            "/api/jobs",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Sidecar-Token",
            },
        )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
