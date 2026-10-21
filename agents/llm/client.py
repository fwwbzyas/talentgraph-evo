from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from time import perf_counter
from typing import Any, Callable

import httpx


FallbackFactory = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    provider_status: dict[str, Any]


class OpenAICompatibleClient:
    """Small OpenAI-compatible JSON client with an auditable offline mode."""

    timeout_env_var = "TALENTGRAPH_LLM_TIMEOUT_SECONDS"
    retries_env_var = "TALENTGRAPH_LLM_RETRIES"
    default_timeout_seconds = 180.0

    def __init__(self, timeout_seconds: float | None = None) -> None:
        self.disabled = os.getenv("TALENTGRAPH_LLM_DISABLED", "").strip().lower() in {"1", "true", "yes"}
        self.trust_env = os.getenv("TALENTGRAPH_LLM_TRUST_ENV_PROXY", "0").strip().lower() in {"1", "true", "yes"}
        self.base_url = os.getenv("TALENTGRAPH_LLM_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("TALENTGRAPH_LLM_API_KEY", "")
        self.model = os.getenv("TALENTGRAPH_LLM_MODEL", "")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else self._env_float(
            self.timeout_env_var,
            self.default_timeout_seconds,
        )
        self.retries = max(0, self._env_int(self.retries_env_var, 1))

    @property
    def configured(self) -> bool:
        return not self.disabled and all(
            self._usable_configuration_value(value)
            for value in (self.base_url, self.api_key, self.model)
        )

    @staticmethod
    def _usable_configuration_value(value: str) -> bool:
        normalized = value.strip().casefold()
        if not normalized:
            return False
        return not (
            normalized in {
                "replace-with-rotated-key",
                "your-model-name",
                "your-vision-model-name",
            }
            or "your-provider.example" in normalized
            or normalized.startswith("replace-with-")
        )

    def status(self) -> dict[str, Any]:
        return {
            "provider": "openai-compatible",
            "configured": self.configured,
            "model": self.model or None,
            "mode": "remote" if self.configured else "deterministic_fallback",
            "timeout_seconds": self.timeout_seconds,
            "retries": self.retries,
            "trust_env_proxy": self.trust_env,
        }

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        fallback: dict[str, Any] | FallbackFactory,
        timeout_seconds: float | None = None,
        retries: int | None = None,
        max_tokens: int | None = None,
        disable_thinking: bool = False,
        model: str | None = None,
    ) -> LLMResult:
        started = perf_counter()
        effective_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        effective_retries = max(0, retries if retries is not None else self.retries)
        effective_model = (model or self.model).strip()
        request_status = {
            **self.status(),
            "model": effective_model or None,
            "timeout_seconds": effective_timeout,
            "retries": effective_retries,
        }
        if not self.configured:
            return self._fallback(
                fallback,
                "missing_environment_configuration",
                status=request_status,
                duration_ms=self._elapsed_ms(started),
            )

        last_reason = "unknown_error"
        for attempt in range(effective_retries + 1):
            try:
                request_body: dict[str, Any] = {
                    "model": effective_model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                if max_tokens is not None:
                    request_body["max_tokens"] = max(128, int(max_tokens))
                if disable_thinking:
                    if "api.deepseek.com" in self.base_url.casefold():
                        request_body["thinking"] = {"type": "disabled"}
                    else:
                        request_body["enable_thinking"] = False
                response = httpx.post(
                    self._chat_completions_url(),
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=request_body,
                    timeout=effective_timeout,
                    trust_env=self.trust_env,
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                message = choice["message"]
                content = message["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError(
                        "empty model content "
                        f"(finish_reason={choice.get('finish_reason')}, "
                        f"reasoning_chars={len(str(message.get('reasoning_content') or ''))})"
                    )
                data = self._parse_json(content)
                return LLMResult(
                    data=data,
                    provider_status={
                        **request_status,
                        "mode": "remote",
                        "ok": True,
                        "fallback": False,
                        "attempts": attempt + 1,
                        "duration_ms": self._elapsed_ms(started),
                    },
                )
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_reason = f"{type(exc).__name__}: {str(exc)[:160]}"
                if attempt < effective_retries and self._retryable(exc):
                    continue
                break
        return self._fallback(
            fallback,
            last_reason,
            status=request_status,
            duration_ms=self._elapsed_ms(started),
        )

    def _fallback(
        self,
        fallback: dict[str, Any] | FallbackFactory,
        reason: str,
        *,
        status: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> LLMResult:
        data = fallback() if callable(fallback) else dict(fallback)
        provider_status = {
            **(status or self.status()),
            "mode": "deterministic_fallback",
            "ok": True,
            "fallback": True,
            "reason": reason,
        }
        if duration_ms is not None:
            provider_status["duration_ms"] = duration_ms
        return LLMResult(
            data=data,
            provider_status=provider_status,
        )

    def _parse_json(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = str(content).strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.I).strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            sliced = self._json_object_slice(text)
            if not sliced or sliced == text:
                raise
            result = json.loads(sliced)
        if not isinstance(result, dict):
            raise ValueError("LLM JSON response must be an object")
        return result

    def _json_object_slice(self, text: str) -> str:
        start = text.find("{")
        if start < 0:
            return ""
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        return ""

    def _chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _retryable(self, exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {408, 409, 429, 500, 502, 503, 504}
        return False

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))

    def _env_float(self, name: str, default: float) -> float:
        try:
            value = float(os.getenv(name, ""))
            return value if value > 0 else default
        except ValueError:
            return default

    def _env_int(self, name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, ""))
            return value if value >= 0 else default
        except ValueError:
            return default


class OpenAICompatibleVisionClient(OpenAICompatibleClient):
    """OpenAI-compatible vision client for OCR/layout understanding."""

    timeout_env_var = "TALENTGRAPH_VISION_TIMEOUT_SECONDS"
    retries_env_var = "TALENTGRAPH_VISION_RETRIES"

    def __init__(self, timeout_seconds: float | None = None) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self.base_url = os.getenv("TALENTGRAPH_VISION_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("TALENTGRAPH_VISION_API_KEY", "")
        self.model = os.getenv("TALENTGRAPH_VISION_MODEL", "")

    def generate_json_with_images(
        self,
        *,
        system_prompt: str,
        text_prompt: str,
        images: list[dict[str, str]],
        fallback: dict[str, Any] | FallbackFactory,
    ) -> LLMResult:
        if not self.configured:
            return self._fallback(fallback, "missing_vision_environment_configuration")
        if not images:
            return self._fallback(fallback, "no_images_for_vision_parse")

        content: list[dict[str, Any]] = [{"type": "text", "text": text_prompt}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image['mime_type']};base64,{image['base64']}"},
            }
            for image in images
        )
        last_reason = "unknown_error"
        for attempt in range(self.retries + 1):
            try:
                request_body: dict[str, Any] = {
                    "model": self.model,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                }
                if "api.deepseek.com" in self.base_url.casefold():
                    request_body["thinking"] = {"type": "disabled"}
                response = httpx.post(
                    self._chat_completions_url(),
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=request_body,
                    timeout=self.timeout_seconds,
                    trust_env=self.trust_env,
                )
                response.raise_for_status()
                body = response.json()
                data = self._parse_json(body["choices"][0]["message"]["content"])
                return LLMResult(
                    data=data,
                    provider_status={
                        **self.status(),
                        "mode": "vision_remote",
                        "ok": True,
                        "fallback": False,
                        "attempts": attempt + 1,
                    },
                )
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_reason = f"{type(exc).__name__}: {str(exc)[:160]}"
                if attempt < self.retries and self._retryable(exc):
                    continue
                break
        return self._fallback(fallback, last_reason)
