"""DeepSeek 翻译客户端测试；全部使用 MockTransport，不发出真实网络请求。"""

import json

import httpx
import pytest
from app.config import Settings
from app.translation.deepseek import (
    DeepSeekConfig,
    DeepSeekTranslator,
    TranslationAuthError,
    TranslationNotConfiguredError,
    TranslationResponseError,
)


def _settings(tmp_path):
    return Settings(
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        manifest_path=tmp_path / "models" / "manifest.json",
        temp_dir=tmp_path / "tmp",
        token="dev",
    )


def _config(**overrides):
    values = {"api_key": "test-key", "max_retries": 0}
    values.update(overrides)
    return DeepSeekConfig(**values)


def _response(translations):
    content = json.dumps({"translations": translations}, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_config_reads_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    config = DeepSeekConfig.from_settings(_settings(tmp_path))

    assert config.api_key == "env-key"
    assert config.base_url == "https://example.test"
    assert config.model == "deepseek-v4-pro"


def test_config_reads_dotenv(tmp_path, monkeypatch):
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY='dotenv-key'\nDEEPSEEK_MODEL=deepseek-flash\n", encoding="utf-8"
    )

    config = DeepSeekConfig.from_settings(_settings(tmp_path))

    assert config.api_key == "dotenv-key"
    assert config.model == "deepseek-flash"


def test_config_requires_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(TranslationNotConfiguredError, match="DEEPSEEK_API_KEY"):
        DeepSeekConfig.from_settings(_settings(tmp_path))


def test_translate_preserves_order_and_sends_expected_payload():
    requests = []

    def handler(request):
        requests.append(request)
        return _response([{"id": 1, "text": "谢谢"}, {"id": 0, "text": "你好"}])

    translator = DeepSeekTranslator(_config(), transport=httpx.MockTransport(handler))
    result = translator.translate_segments(["こんにちは", "ありがとう"])
    translator.close()

    assert result == ["你好", "谢谢"]
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "deepseek-flash"
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert body["temperature"] == 0.2


def test_translate_batches_more_than_twenty_segments():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        segments = json.loads(body["messages"][1]["content"])["segments"]
        calls.append(len(segments))
        return _response([{"id": item["id"], "text": f"译{item['id']}"} for item in segments])

    translator = DeepSeekTranslator(_config(), transport=httpx.MockTransport(handler))
    result = translator.translate_segments([f"原文{i}" for i in range(21)])
    translator.close()

    assert calls == [20, 1]
    assert result == [f"译{i}" for i in range(21)]


def test_invalid_json_retries():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        return _response([{"id": 0, "text": "你好"}])

    translator = DeepSeekTranslator(_config(max_retries=1), transport=httpx.MockTransport(handler))
    assert translator.translate_segments(["こんにちは"]) == ["你好"]
    translator.close()
    assert len(calls) == 2


def test_auth_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "invalid key"})

    translator = DeepSeekTranslator(_config(max_retries=3), transport=httpx.MockTransport(handler))
    with pytest.raises(TranslationAuthError, match="API Key"):
        translator.translate_segments(["こんにちは"])
    translator.close()
    assert len(calls) == 1


def test_missing_translation_id_is_rejected():
    def handler(request):
        return _response([{"id": 0, "text": "你好"}])

    translator = DeepSeekTranslator(_config(), transport=httpx.MockTransport(handler))
    with pytest.raises(TranslationResponseError):
        translator.translate_segments(["こんにちは", "ありがとう"])
    translator.close()


def test_empty_input_does_not_call_api():
    def handler(request):
        raise AssertionError("不应发出请求")

    translator = DeepSeekTranslator(_config(), transport=httpx.MockTransport(handler))
    assert translator.translate_segments([]) == []
    translator.close()
