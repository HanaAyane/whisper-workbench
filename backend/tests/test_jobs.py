"""Phase 3 任务状态机与 /api/jobs 接口测试（使用假 runner，不加载模型）。"""

import time
import wave
from dataclasses import replace
from threading import Event
from uuid import uuid4

import numpy as np
import pytest
from app.asr.whisper_backend import RecognitionResult, RecognizedSpan
from app.audio.chunks import SpeechSegment
from app.config import Settings
from app.glossary.models import GlossaryEntry
from app.glossary.store import GlossaryStore
from app.jobs.manager import JobManager
from app.jobs.schemas import JobRequest, JobStatus, Segment
from app.main import create_app
from app.storage.jobs import JobStore
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


def test_cancel_running_and_queued_jobs(settings, tmp_path):
    audio = _write_wav(tmp_path / "sample.wav")
    started = Event()
    release = Event()
    calls = []

    def blocking(request, report):
        calls.append(request)
        started.set()
        assert release.wait(5)
        return _segments(request, report)

    with TestClient(create_app(settings, job_runner=blocking)) as client:
        running = client.post("/api/jobs", json=_payload(audio), headers=HEADERS).json()["id"]
        try:
            assert started.wait(2)
            queued = client.post("/api/jobs", json=_payload(audio), headers=HEADERS).json()["id"]
            assert (
                client.post(f"/api/jobs/{queued}/cancel", headers=HEADERS).json()["state"]
                == "cancelled"
            )
            assert (
                client.post(f"/api/jobs/{running}/cancel", headers=HEADERS).json()["state"]
                == "running"
            )
        finally:
            release.set()
        assert _wait(client, running)["state"] == "cancelled"
        assert _wait(client, queued)["state"] == "cancelled"
    assert len(calls) == 1


def test_fifo_push_cancel_and_restart(settings, tmp_path):
    settings = replace(settings, recordings_dir=tmp_path / "recordings")
    settings.recordings_dir.mkdir()
    media = _write_wav(tmp_path / "sample.wav")
    started = Event()
    release = Event()
    order = []

    def runner(request, report):
        order.append(request.name)
        if request.name == "第一":
            report(0.2, "vad", "正在检测语音")
            started.set()
            assert release.wait(5)
        return _segments(request, report)

    with TestClient(create_app(settings, job_runner=runner)) as client:
        recording = _write_wav(settings.recordings_dir / f"recording-{uuid4()}.webm")
        first = (
            client.post(
                "/api/jobs",
                json={**_payload(recording), "name": "第一", "recording": "temporary"},
                headers=HEADERS,
            )
            .raise_for_status()
            .json()
        )
        try:
            assert started.wait(2)
            rest = [
                client.post(
                    "/api/jobs", json={**_payload(media), "name": name}, headers=HEADERS
                ).json()
                for name in ["第二", "第三"]
            ]
            assert [job["state"] for job in rest] == ["queued", "queued"]
            path = f"/ws/jobs/{first['id']}"
            with (
                pytest.raises(WebSocketDisconnect),
                client.websocket_connect(
                    path, headers={**HEADERS, "origin": "https://example.org"}
                ),
            ):
                pytest.fail("外部来源不应连接")
            with pytest.raises(WebSocketDisconnect), client.websocket_connect(path):
                pytest.fail("缺少令牌不应连接")
            with client.websocket_connect(path, subprotocols=["jp-workbench", "dev"]) as ws:
                assert ws.accepted_subprotocol == "jp-workbench"
                running = ws.receive_json()
                assert (running["state"], running["stage"], running["progress"]) == (
                    "running",
                    "vad",
                    0.2,
                )
                client.post(f"/api/jobs/{first['id']}/cancel", headers=HEADERS).raise_for_status()
                assert ws.receive_json()["cancel_requested"]
                assert recording.exists()
                release.set()
                terminal = ws.receive_json()
                assert terminal["state"] == "cancelled"
                assert terminal["revision"] > running["revision"]
                assert not recording.exists()
            for job in rest:
                assert _wait(client, job["id"])["state"] == "succeeded"
        finally:
            release.set()
    assert order == ["第一", "第二", "第三"]
    with TestClient(create_app(settings, job_runner=runner)) as client:
        history = client.get("/api/jobs", headers=HEADERS).json()
        assert [(job["name"], job["state"]) for job in history] == [
            ("第三", "succeeded"),
            ("第二", "succeeded"),
            ("第一", "cancelled"),
        ]
        assert history[0]["segments"][0]["raw_text"] == "テストです。"
    assert order == ["第一", "第二", "第三"]
    assert media.is_file()


def test_recovers_interrupted_jobs_without_restarting_and_cleans_orphans(settings, tmp_path):
    settings = replace(
        settings, jobs_path=tmp_path / "history.sqlite3", recordings_dir=tmp_path / "recordings"
    )
    store = JobStore(settings.jobs_path)
    store.save(
        JobStatus(id="interrupted", state="running", stage="asr", progress=0.5, message="处理中")
    )
    store.close()
    settings.recordings_dir.mkdir()
    orphan = _write_wav(settings.recordings_dir / f"recording-{uuid4()}.webm")
    unrelated = _write_wav(settings.recordings_dir / "user.webm")
    with TestClient(create_app(settings)) as client:
        data = client.get("/api/jobs/interrupted", headers=HEADERS).json()
        assert data["state"] == "cancelled"
        assert data["progress"] == 0.5
        assert "上次退出" in data["message"]
        assert not orphan.exists()
        assert unrelated.is_file()
        assert (
            client.post(
                "/api/jobs", headers=HEADERS, json={**_payload(unrelated), "recording": "temporary"}
            ).status_code
            == 400
        )


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


def test_translate_requires_deepseek_key(settings, tmp_path, monkeypatch):
    audio = _write_wav(tmp_path / "sample.wav")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    application = create_app(settings, job_runner=_segments)
    payload = {**_payload(audio), "mode": "translate"}
    with TestClient(application) as client:
        response = client.post("/api/jobs", json=payload, headers=HEADERS)
    assert response.status_code == 400
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


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


class _FakeTranslator:
    def __init__(self):
        self.calls = []

    def translate_segments(self, texts, **_kwargs):
        self.calls.append(list(texts))
        return [f"译文{index}" for index in range(len(texts))]


def test_translation_pipeline_uses_deepseek_translator(settings, tmp_path, monkeypatch):
    audio = _write_wav(tmp_path / "sample.wav")

    class Decoded:
        samples = np.zeros(16000, dtype=np.float32)
        duration_ms = 1000

    class Loaded:
        model = object()

    translator = _FakeTranslator()
    manager = JobManager(settings, translator=translator)
    monkeypatch.setattr("app.jobs.manager.decode_audio", lambda _path, **_kwargs: Decoded())
    monkeypatch.setattr(
        "app.jobs.manager.detect_speech", lambda *_args, **_kwargs: [SpeechSegment(0, 1000)]
    )
    monkeypatch.setattr(
        "app.jobs.manager.merge_speech_segments",
        lambda *_args, **_kwargs: [SpeechSegment(0, 1000)],
    )
    monkeypatch.setattr(manager.model_manager, "load", lambda *_args, **_kwargs: Loaded())
    monkeypatch.setattr(
        "app.jobs.manager.recognize_chunks",
        lambda *_args, **_kwargs: RecognitionResult(
            spans=[RecognizedSpan(0, 1000, "こんにちは")], duration_after_vad_ms=1000
        ),
    )

    request = JobRequest(input_path=str(audio), mode="translate", asr_model_id="synthetic-test")
    segments = manager._run_pipeline(request, lambda *_args: None)
    manager.close()

    assert translator.calls == [["こんにちは"]]
    assert len(segments) == 1
    assert segments[0].raw_text == "こんにちは"
    assert segments[0].raw_translation == "译文0"
    assert segments[0].translation == "译文0"


def test_pipeline_proposes_glossary_without_touching_raw_text(settings, tmp_path, monkeypatch):
    audio = _write_wav(tmp_path / "sample.wav")
    GlossaryStore(settings).save(
        "demo",
        [
            GlossaryEntry(
                id="term-001",
                source="田中",
                target="田中太郎",
                field="text",
                policy="correct",
            )
        ],
    )

    class Decoded:
        samples = np.zeros(16000, dtype=np.float32)
        duration_ms = 1000

    class Loaded:
        model = object()

    manager = JobManager(settings)
    monkeypatch.setattr("app.jobs.manager.decode_audio", lambda _path, **_kwargs: Decoded())
    monkeypatch.setattr(
        "app.jobs.manager.detect_speech", lambda *_args, **_kwargs: [SpeechSegment(0, 1000)]
    )
    monkeypatch.setattr(
        "app.jobs.manager.merge_speech_segments",
        lambda *_args, **_kwargs: [SpeechSegment(0, 1000)],
    )
    monkeypatch.setattr(manager.model_manager, "load", lambda *_args, **_kwargs: Loaded())
    monkeypatch.setattr(
        "app.jobs.manager.recognize_chunks",
        lambda *_args, **_kwargs: RecognitionResult(
            spans=[RecognizedSpan(0, 1000, "田中さん")], duration_after_vad_ms=1000
        ),
    )

    with TestClient(create_app(settings, job_runner=manager._run_pipeline)) as client:
        status = (
            client.post(
                "/api/jobs",
                headers=HEADERS,
                json={**_payload(audio), "glossary_id": "demo"},
            )
            .raise_for_status()
            .json()
        )
        segment = _wait(client, status["id"])["segments"][0]
    manager.close()
    assert segment["raw_text"] == segment["text"] == "田中さん"
    assert segment["hits"][0]["entry_id"] == "term-001"
    assert segment["hits"][0]["decision"] == "pending"


def test_review_persists_and_exports_saved_bilingual_segments(settings, tmp_path):
    media = _write_wav(tmp_path / "sample.wav")
    glossaries = GlossaryStore(settings)
    glossaries.save(
        "demo",
        [
            GlossaryEntry(id="jp", source="田中", target="田中太郎", policy="correct"),
            GlossaryEntry(
                id="zh", source="渋谷", target="涩谷", field="translation", policy="translate"
            ),
            GlossaryEntry(id="keep", source="さん", policy="keep"),
        ],
    )
    raw_text, raw_translation = "🎙田中さん と 田中", "在渋谷见面"

    def runner(_request, _report):
        return [
            Segment(
                id=0,
                start=1200,
                end=3000,
                raw_text=raw_text,
                text=raw_text,
                raw_translation=raw_translation,
                translation=raw_translation,
            )
        ]

    def decision(client, path, segment, action, *, hit=None):
        payload = {"action": action, "revision": segment["revision"]}
        if hit is not None:
            payload["hit"] = {key: hit[key] for key in ("entry_id", "field", "start", "end")}
        return client.post(path + "/review", json=payload, headers=HEADERS)

    with TestClient(
        create_app(settings, job_runner=runner, translator=_FakeTranslator())
    ) as client:
        created = (
            client.post(
                "/api/jobs",
                headers=HEADERS,
                json={**_payload(media), "glossary_id": "demo", "mode": "translate"},
            )
            .raise_for_status()
            .json()
        )
        segment = _wait(client, created["id"])["segments"][0]
        assert (segment["text"], segment["translation"]) == (raw_text, raw_translation)
        first, keep, second, chinese = segment["hits"]
        assert (first["start"], first["end"], keep["policy"]) == (1, 3, "keep")
        path = f"/api/jobs/{created['id']}/segments/0"
        assert decision(client, path, segment, "accept", hit=keep).status_code == 409
        rejected = (
            decision(client, path, segment, "reject", hit=second)
            .raise_for_status()
            .json()["segments"][0]
        )
        assert rejected["text"] == raw_text
        assert decision(client, path, segment, "accept", hit=first).status_code == 409
        segment = (
            decision(client, path, rejected, "accept", hit=first)
            .raise_for_status()
            .json()["segments"][0]
        )
        assert segment["text"] == "🎙田中太郎さん と 田中"
        assert [hit["decision"] for hit in segment["hits"]] == [
            "accepted",
            "pending",
            "rejected",
            "pending",
        ]
        segment = (
            decision(client, path, segment, "accept", hit=chinese)
            .raise_for_status()
            .json()["segments"][0]
        )
        assert segment["translation"] == "在涩谷见面"
        edit = {
            "text": "冒頭 " + segment["text"],
            "translation": segment["translation"],
            "revision": segment["revision"],
        }
        assert (
            client.patch(path, headers=HEADERS, json={**edit, "raw_text": "篡改"}).status_code
            == 422
        )
        segment = (
            client.patch(path, headers=HEADERS, json=edit).raise_for_status().json()["segments"][0]
        )
        assert segment["hits"][0]["start"] == 4
        assert segment["hits"][0]["matched_text"] == "田中太郎"
    glossaries.delete("demo")

    with TestClient(create_app(settings)) as client:
        restored = client.get(f"/api/jobs/{created['id']}", headers=HEADERS).json()["segments"][0]
        assert restored == segment
        segment = decision(client, path, restored, "undo").raise_for_status().json()["segments"][0]
        assert segment["translation"] == raw_translation
        assert segment["text"] == "冒頭 🎙田中太郎さん と 田中"
        segment = decision(client, path, segment, "undo").raise_for_status().json()["segments"][0]
        assert segment["text"] == "冒頭 " + raw_text
        assert [hit["decision"] for hit in segment["hits"]] == [
            "pending",
            "pending",
            "rejected",
            "pending",
        ]
        assert (segment["raw_text"], segment["raw_translation"]) == (raw_text, raw_translation)
        assert decision(client, path, segment, "undo").status_code == 409
        for format, timestamp in [
            ("srt", "00:00:01,200 --> 00:00:03,000"),
            ("vtt", "00:00:01.200 --> 00:00:03.000"),
            ("lrc", "[00:01.20]"),
            ("txt", ""),
        ]:
            response = client.post(
                f"/api/jobs/{created['id']}/export", headers=HEADERS, json={"format": format}
            ).raise_for_status()
            assert "charset=utf-8" in response.headers["content-type"]
            assert timestamp in response.text
            assert segment["text"] in response.text
            assert segment["translation"] in response.text


def test_legacy_subtitle_migration_recalculates_offsets_without_resetting_edits(settings, tmp_path):
    settings = replace(settings, jobs_path=tmp_path / "legacy.sqlite3")
    GlossaryStore(settings).save(
        "legacy",
        [
            GlossaryEntry(id="jp", source="田中", target="田中太郎", policy="correct"),
        ],
    )
    job = JobStatus(
        id="legacy",
        state="succeeded",
        stage="export",
        progress=1,
        message="完成",
        glossary_id="legacy",
        segments=[
            Segment(
                id=0,
                start=0,
                end=1000,
                raw_text="田中",
                text="🎙田中",
                hits=[
                    {
                        "entry_id": "jp",
                        "field": "text",
                        "start": 0,
                        "end": 2,
                        "matched_text": "田中",
                        "replacement": "田中太郎",
                        "policy": "correct",
                    }
                ],
            )
        ],
    )
    store = JobStore(settings.jobs_path)
    store.save(job)
    store.close()
    with TestClient(create_app(settings)) as client:
        result = client.get("/api/jobs/legacy", headers=HEADERS).raise_for_status().json()
        assert result["segments"][0]["raw_text"] == "田中"
        assert result["segments"][0]["text"] == "🎙田中"
        assert result["segments"][0]["hits"][0]["start"] == 1
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/jobs/legacy", headers=HEADERS).json() == result
