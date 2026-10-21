from __future__ import annotations

import pytest

import agents.speech.service as speech_service_module
from agents.speech.service import (
    CHUNK_SAMPLES,
    SpeechModelUnavailable,
    SpeechRecognitionService,
    StreamingRecognitionSession,
    normalize_technical_terms,
    sanitize_hotwords,
)


class FakeSpeechService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, bool, tuple[str, ...]]] = []

    def transcribe_chunk(
        self,
        pcm_bytes: bytes,
        cache: dict,
        *,
        is_final: bool,
        hotwords: tuple[str, ...] = (),
    ) -> str:
        self.calls.append((len(pcm_bytes), is_final, hotwords))
        cache["calls"] = cache.get("calls", 0) + 1
        return "fasti" if not is_final else "和enggraphh"


def test_sanitize_hotwords_deduplicates_and_limits_values():
    values = ["FastAPI", " fastapi ", "LangGraph", "", None]
    assert sanitize_hotwords(values) == ("FastAPI", "LangGraph")


def test_technical_terms_are_corrected_without_changing_chinese_text():
    text, corrected = normalize_technical_terms(
        "我负责使用fasti和enggraphh构建服务",
        ["FastAPI", "LangGraph"],
    )
    assert text == "我负责使用FastAPI和LangGraph构建服务"
    assert corrected == ("FastAPI", "LangGraph")


def test_streaming_session_buffers_pcm_and_returns_cumulative_transcript():
    service = FakeSpeechService()
    session = StreamingRecognitionSession(service, ["FastAPI", "LangGraph"])
    almost_one_chunk = b"\x00\x00" * (CHUNK_SAMPLES - 1)

    assert session.feed_pcm16(almost_one_chunk) is None
    partial = session.feed_pcm16(b"\x00\x00")
    final = session.finalize()

    assert partial is not None
    assert partial.text == "FastAPI"
    assert partial.is_final is False
    assert final.text == "FastAPI和LangGraph"
    assert final.is_final is True
    assert service.calls[0] == (CHUNK_SAMPLES * 2, False, ("FastAPI", "LangGraph"))
    assert service.calls[1][1:] == (True, ("FastAPI", "LangGraph"))


def test_model_inference_uses_conservative_dynamic_hotword_correction():
    class FakeModel:
        def __init__(self) -> None:
            self.kwargs = None

        def generate(self, **kwargs):
            self.kwargs = kwargs
            return [{"text": "数据分西"}]

    service = SpeechRecognitionService()
    model = FakeModel()
    service._model = model

    result = service.transcribe_chunk(
        b"\x00\x00" * 960,
        {},
        is_final=False,
        hotwords=["数据分析", "FastAPI"],
    )

    assert result == "数据分西"
    assert model.kwargs["postprocess_hotwords"] == ["数据分析", "FastAPI"]
    assert model.kwargs["postprocess_hotword_threshold"] == 0.88


def test_missing_hotword_runtime_dependency_is_reported_before_model_loading(monkeypatch):
    original_find_spec = speech_service_module.importlib.util.find_spec
    monkeypatch.setattr(
        speech_service_module.importlib.util,
        "find_spec",
        lambda name: None if name == "pypinyin" else original_find_spec(name),
    )
    service = SpeechRecognitionService()

    assert service.status()["installed"] is False
    with pytest.raises(SpeechModelUnavailable, match="动态热词识别需要 pypinyin"):
        service.ensure_loaded()
