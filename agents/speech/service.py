from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import importlib.util
import os
import re
from threading import Lock
from typing import Iterable


SAMPLE_RATE = 16_000
CHUNK_SIZE = [0, 10, 5]
CHUNK_SAMPLES = CHUNK_SIZE[1] * 960
FINAL_SILENCE_SAMPLES = 320
MAX_HOTWORDS = 40
MAX_HOTWORD_LENGTH = 64

DEFAULT_TECHNICAL_TERMS = (
    "FastAPI",
    "LangGraph",
    "RAG",
    "Python",
    "PyTorch",
    "AIGC",
    "LLM",
    "Agent",
    "Docker",
    "Kubernetes",
    "Redis",
    "MySQL",
    "Kafka",
    "Spark",
    "Flink",
)

_LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.+#_-]{2,}")
_LATIN_KEY = re.compile(r"[^a-z0-9]+")


class SpeechModelUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeechTranscript:
    text: str
    raw_text: str
    is_final: bool
    corrected_terms: tuple[str, ...] = ()

    def as_payload(self) -> dict:
        return {
            "type": "transcript",
            "text": self.text,
            "raw_text": self.raw_text,
            "is_final": self.is_final,
            "corrected_terms": list(self.corrected_terms),
        }


def _term_key(value: str) -> str:
    return _LATIN_KEY.sub("", value.casefold())


def sanitize_hotwords(values: Iterable[object] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or ():
        text = str(value or "").strip()
        key = text.casefold()
        if not text or len(text) > MAX_HOTWORD_LENGTH or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= MAX_HOTWORDS:
            break
    return tuple(result)


def normalize_technical_terms(text: str, hotwords: Iterable[object] | None) -> tuple[str, tuple[str, ...]]:
    if not text:
        return text, ()

    terms = sanitize_hotwords((*DEFAULT_TECHNICAL_TERMS, *(hotwords or ())))
    candidates = [(term, _term_key(term)) for term in terms]
    candidates = [(term, key) for term, key in candidates if len(key) >= 3]
    corrected: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        token_key = _term_key(token)
        if len(token_key) < 3:
            return token

        exact = next((term for term, key in candidates if key == token_key), None)
        if exact:
            if exact != token:
                corrected.append(exact)
            return exact

        scored: list[tuple[float, str]] = []
        for term, key in candidates:
            if abs(len(key) - len(token_key)) > max(3, len(key) // 2):
                continue
            scored.append((SequenceMatcher(None, token_key, key).ratio(), term))
        if not scored:
            return token
        scored.sort(reverse=True)
        best_score, best_term = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        if best_score < 0.75 or best_score - second_score < 0.10:
            return token
        corrected.append(best_term)
        return best_term

    normalized = _LATIN_TOKEN.sub(replace, text)
    return normalized, tuple(dict.fromkeys(corrected))


class StreamingRecognitionSession:
    def __init__(self, service: "SpeechRecognitionService", hotwords: Iterable[object] | None = None) -> None:
        self.service = service
        self.hotwords = sanitize_hotwords(hotwords)
        self.cache: dict = {}
        self.buffer = bytearray()
        self.parts: list[str] = []

    def feed_pcm16(self, pcm_bytes: bytes) -> SpeechTranscript | None:
        if not pcm_bytes:
            return None
        if len(pcm_bytes) % 2:
            pcm_bytes = pcm_bytes[:-1]
        self.buffer.extend(pcm_bytes)
        emitted = False
        chunk_bytes = CHUNK_SAMPLES * 2
        while len(self.buffer) >= chunk_bytes:
            chunk = bytes(self.buffer[:chunk_bytes])
            del self.buffer[:chunk_bytes]
            text = self.service.transcribe_chunk(
                chunk,
                self.cache,
                is_final=False,
                hotwords=self.hotwords,
            )
            if text:
                self.parts.append(text)
                emitted = True
        return self._snapshot(is_final=False) if emitted else None

    def finalize(self) -> SpeechTranscript:
        if self.buffer:
            final_bytes = bytes(self.buffer)
            self.buffer.clear()
        else:
            final_bytes = b"\x00\x00" * FINAL_SILENCE_SAMPLES
        text = self.service.transcribe_chunk(
            final_bytes,
            self.cache,
            is_final=True,
            hotwords=self.hotwords,
        )
        if text:
            self.parts.append(text)
        return self._snapshot(is_final=True)

    def _snapshot(self, *, is_final: bool) -> SpeechTranscript:
        raw_text = "".join(self.parts).strip()
        text, corrected_terms = normalize_technical_terms(raw_text, self.hotwords)
        return SpeechTranscript(
            text=text,
            raw_text=raw_text,
            is_final=is_final,
            corrected_terms=corrected_terms,
        )


class SpeechRecognitionService:
    def __init__(self) -> None:
        self.model_name = os.getenv("TALENTGRAPH_ASR_MODEL", "paraformer-zh-streaming")
        self.requested_device = os.getenv("TALENTGRAPH_ASR_DEVICE", "auto").strip().casefold() or "auto"
        self._model = None
        self._device: str | None = None
        self._load_error: str | None = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    def status(self) -> dict:
        installed = all(
            importlib.util.find_spec(module_name) is not None
            for module_name in ("funasr", "torch", "pypinyin")
        )
        state = "ready" if self._model is not None else "error" if self._load_error else "available" if installed else "unavailable"
        return {
            "engine": "FunASR",
            "model": self.model_name,
            "state": state,
            "installed": installed,
            "device": self._device or self.requested_device,
            "sample_rate": SAMPLE_RATE,
            "streaming": True,
        }

    def start_session(self, hotwords: Iterable[object] | None = None) -> StreamingRecognitionSession:
        self.ensure_loaded()
        return StreamingRecognitionSession(self, hotwords)

    def ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                if importlib.util.find_spec("pypinyin") is None:
                    raise ModuleNotFoundError("动态热词识别需要 pypinyin")
                import torch
                from funasr import AutoModel

                if self.requested_device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                else:
                    device = self.requested_device
                if device.startswith("cuda") and not torch.cuda.is_available():
                    raise RuntimeError("当前 PyTorch 环境未启用 CUDA")

                ncpu = max(1, min(4, os.cpu_count() or 1))
                self._model = AutoModel(
                    model=self.model_name,
                    device=device,
                    ncpu=ncpu,
                    disable_update=True,
                    disable_pbar=True,
                    disable_log=True,
                )
                self._device = device
                self._load_error = None
            except Exception as exc:
                self._load_error = str(exc)
                raise SpeechModelUnavailable(f"FunASR 模型初始化失败：{exc}") from exc

    def transcribe_chunk(
        self,
        pcm_bytes: bytes,
        cache: dict,
        *,
        is_final: bool,
        hotwords: Iterable[object] | None = None,
    ) -> str:
        self.ensure_loaded()
        try:
            import numpy as np

            samples = np.frombuffer(pcm_bytes, dtype="<i2").astype(np.float32) / 32768.0
            session_hotwords = list(sanitize_hotwords(hotwords))
            with self._inference_lock:
                result = self._model.generate(
                    input=samples,
                    cache=cache,
                    is_final=is_final,
                    chunk_size=CHUNK_SIZE,
                    encoder_chunk_look_back=4,
                    decoder_chunk_look_back=1,
                    postprocess_hotwords=session_hotwords or None,
                    postprocess_hotword_threshold=0.88,
                )
            return str(result[0].get("text", "")) if result else ""
        except SpeechModelUnavailable:
            raise
        except Exception as exc:
            raise SpeechModelUnavailable(f"FunASR 实时识别失败：{exc}") from exc
