from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import apps.api.main as api_main
from agents.speech.service import SpeechTranscript


class FakeSpeechSession:
    def __init__(self) -> None:
        self.audio_chunks: list[bytes] = []
        self.finalize_calls = 0

    def feed_pcm16(self, pcm_bytes: bytes) -> SpeechTranscript:
        self.audio_chunks.append(pcm_bytes)
        return SpeechTranscript(
            text="partial answer",
            raw_text="partial answer",
            is_final=False,
        )

    def finalize(self) -> SpeechTranscript:
        self.finalize_calls += 1
        return SpeechTranscript(
            text="complete answer",
            raw_text="complete answer",
            is_final=True,
            corrected_terms=("FastAPI",),
        )


class FakeSpeechService:
    def __init__(self) -> None:
        self.session = FakeSpeechSession()
        self.started_with: list[object] | None = None

    def status(self) -> dict:
        return {
            "engine": "FakeASR",
            "model": "fake-streaming-model",
            "state": "ready",
            "installed": True,
            "device": "cpu",
            "sample_rate": 16_000,
            "streaming": True,
        }

    def start_session(self, hotwords: list[object]) -> FakeSpeechSession:
        self.started_with = hotwords
        return self.session


@pytest.fixture
def speech_api(monkeypatch):
    service = FakeSpeechService()
    monkeypatch.setattr(api_main, "speech_service", service)
    monkeypatch.setattr(
        api_main.auth_service,
        "resolve_token",
        lambda token: {"user_id": "user_test", "role": "enterprise"}
        if token == "valid-token"
        else None,
    )
    return TestClient(api_main.app), service


def test_speech_status_requires_a_valid_bearer_token(speech_api):
    client, _service = speech_api

    unauthorized = client.get("/api/speech/status")
    authorized = client.get(
        "/api/speech/status",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {
        "engine": "FakeASR",
        "model": "fake-streaming-model",
        "state": "ready",
        "installed": True,
        "device": "cpu",
        "sample_rate": 16_000,
        "streaming": True,
    }


def test_speech_websocket_rejects_an_invalid_start_token(speech_api):
    client, service = speech_api

    with client.websocket_connect("/api/speech/stream") as websocket:
        websocket.send_json({"type": "start", "token": "expired-token"})

        assert websocket.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert closed.value.code == 4401
    assert service.started_with is None


def test_speech_websocket_streams_audio_and_completes_with_fake_session(speech_api):
    client, service = speech_api
    pcm_chunk = b"\x01\x00\x02\x00"

    with client.websocket_connect("/api/speech/stream") as websocket:
        websocket.send_json(
            {
                "type": "start",
                "token": "valid-token",
                "hotwords": ["FastAPI", "LangGraph"],
            }
        )

        assert websocket.receive_json() == {
            "type": "status",
            "state": "loading",
            "message": "\u6b63\u5728\u51c6\u5907\u672c\u5730\u8bed\u97f3\u6a21\u578b",
        }
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        assert ready["engine"] == "FakeASR"
        assert ready["streaming"] is True

        websocket.send_bytes(pcm_chunk)
        assert websocket.receive_json() == {
            "type": "transcript",
            "text": "partial answer",
            "raw_text": "partial answer",
            "is_final": False,
            "corrected_terms": [],
        }

        websocket.send_json({"type": "stop"})
        assert websocket.receive_json() == {
            "type": "transcript",
            "text": "complete answer",
            "raw_text": "complete answer",
            "is_final": True,
            "corrected_terms": ["FastAPI"],
        }
        assert websocket.receive_json() == {
            "type": "complete",
            "text": "complete answer",
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert closed.value.code == 1000
    assert service.started_with == ["FastAPI", "LangGraph"]
    assert service.session.audio_chunks == [pcm_chunk]
    assert service.session.finalize_calls == 1
