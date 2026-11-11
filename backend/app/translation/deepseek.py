"""DeepSeek Chat Completions 翻译客户端。

设计约束：
- 只发送待翻译文本，不发送音频或文件；
- API Key 只从环境变量或项目本地 ``.env`` 读取，不写入日志；
- 返回与输入等长的译文列表，供 Segment 对齐。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import Settings
from app.translation.prompt import compose_system_prompt, render_user_content

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
MAX_BATCH_CHARS = 6000
MAX_BATCH_ITEMS = 20

ProgressCallback = Callable[[int, int], None]


class TranslationError(RuntimeError):
    """翻译失败的基类，消息使用中文。"""


class TranslationNotConfiguredError(TranslationError):
    """缺少 API Key 或配置无效。"""


class TranslationAuthError(TranslationError):
    """DeepSeek 鉴权失败。"""


class TranslationRateLimitError(TranslationError):
    """DeepSeek 限流。"""


class TranslationResponseError(TranslationError):
    """DeepSeek 返回内容无法解析。"""


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_s: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_settings(cls, settings: Settings) -> DeepSeekConfig:
        dotenv = _read_dotenv(settings.project_root / ".env")
        api_key = os.environ.get("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY", "")
        if not api_key.strip():
            raise TranslationNotConfiguredError(
                "未配置 DeepSeek API Key：请在项目 .env 或环境变量 DEEPSEEK_API_KEY 中设置。"
            )
        base_url = (
            (
                os.environ.get("DEEPSEEK_BASE_URL")
                or dotenv.get("DEEPSEEK_BASE_URL")
                or DEFAULT_BASE_URL
            )
            .strip()
            .rstrip("/")
        )
        try:
            destination = urlsplit(base_url)
            allowed = destination.hostname and (
                destination.scheme == "https"
                or (destination.scheme == "http" and destination.hostname == "127.0.0.1")
            )
        except ValueError:
            allowed = False
        if not allowed or any(
            (destination.username, destination.password, destination.query, destination.fragment)
        ):
            raise TranslationNotConfiguredError(
                "DEEPSEEK_BASE_URL 必须使用 HTTPS 或本机 127.0.0.1，且只能包含服务地址和路径。"
            )
        model = (
            os.environ.get("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
        ).strip()
        return cls(api_key=api_key.strip(), base_url=base_url, model=model)


class DeepSeekTranslator:
    """按批翻译字幕文本，保持与输入相同的顺序和数量。"""

    def __init__(
        self, config: DeepSeekConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            timeout=config.timeout_s,
            transport=transport,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def translate_segments(
        self,
        texts: list[str],
        *,
        source_language: str = "ja",
        target_language: str = "zh",
        system_prompt: str | None = None,
        on_progress: ProgressCallback | None = None,
        check_cancelled: Callable[[], None] | None = None,
    ) -> list[str]:
        if not texts:
            return []
        batches = list(_batches(texts))
        translations: dict[int, str] = {}
        for batch_index, batch in enumerate(batches, start=1):
            translations.update(
                self._translate_batch(
                    batch,
                    source_language=source_language,
                    target_language=target_language,
                    system_prompt=system_prompt,
                    check_cancelled=check_cancelled,
                )
            )
            if on_progress is not None:
                on_progress(batch_index, len(batches))
        missing = [index for index in range(len(texts)) if index not in translations]
        if missing:
            raise TranslationResponseError("DeepSeek 返回的译文数量与输入不一致。")
        return [translations[index] for index in range(len(texts))]

    def _translate_batch(
        self,
        batch: list[tuple[int, str]],
        *,
        source_language: str,
        target_language: str,
        system_prompt: str | None,
        check_cancelled: Callable[[], None] | None,
    ) -> dict[int, str]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": compose_system_prompt(system_prompt, target_language),
                },
                {
                    "role": "user",
                    "content": render_user_content(batch),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 8192,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if check_cancelled is not None:
                check_cancelled()
            try:
                response = self._client.post(
                    f"{self.config.base_url}/chat/completions", json=payload
                )
                if response.status_code == 401:
                    raise TranslationAuthError("DeepSeek API Key 无效或已过期。")
                if response.status_code == 402:
                    raise TranslationError("DeepSeek 账户余额不足。")
                if response.status_code == 429:
                    raise TranslationRateLimitError("DeepSeek 请求过于频繁，请稍后重试。")
                if response.status_code >= 400:
                    raise TranslationResponseError(
                        f"DeepSeek 翻译请求失败（HTTP {response.status_code}）。"
                    )
                return self._parse_response(response.json(), batch)
            except TranslationAuthError:
                raise
            except TranslationRateLimitError as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (attempt + 1))
            except TranslationResponseError as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (attempt + 1))
            except TranslationError:
                raise
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (attempt + 1))
        if isinstance(last_error, TranslationError):
            raise last_error
        raise TranslationResponseError("DeepSeek 翻译请求失败，请稍后重试。") from last_error

    def _parse_response(self, data: Any, batch: list[tuple[int, str]]) -> dict[int, str]:
        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            items = parsed["translations"]
            if not isinstance(items, list):
                raise TypeError
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise TranslationResponseError("DeepSeek 返回的翻译结果格式无效。") from exc
        expected = {index for index, _ in batch}
        result: dict[int, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise TranslationResponseError("DeepSeek 返回的翻译结果格式无效。")
            try:
                index = int(item["id"])
                text = str(item["text"]).strip()
            except (KeyError, TypeError, ValueError) as exc:
                raise TranslationResponseError("DeepSeek 返回的翻译结果格式无效。") from exc
            if index not in expected or not text:
                raise TranslationResponseError("DeepSeek 返回的翻译结果与输入不匹配。")
            result[index] = text
        if set(result) != expected:
            raise TranslationResponseError("DeepSeek 返回的译文数量与输入不一致。")
        return result


def _batches(texts: list[str]) -> Iterator[list[tuple[int, str]]]:
    current: list[tuple[int, str]] = []
    size = 0
    for index, text in enumerate(texts):
        if current and (len(current) >= MAX_BATCH_ITEMS or size + len(text) > MAX_BATCH_CHARS):
            yield current
            current = []
            size = 0
        current.append((index, text))
        size += len(text)
    if current:
        yield current


def _read_dotenv(path: Path) -> dict[str, str]:
    """读取简单 KEY=VALUE 的 .env；不覆盖进程环境变量。"""

    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
