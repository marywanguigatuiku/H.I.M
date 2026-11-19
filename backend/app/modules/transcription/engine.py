"""Speech-to-text engines. Every engine takes one small audio file and returns raw Whisper-style
segments. The rest of the app never knows which service is behind it, so engines can be swapped."""
from pathlib import Path
from typing import Optional

from app.core.config import settings


class EngineError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class RateLimited(EngineError):
    def __init__(self, retry_after: float):
        super().__init__("The transcription service is busy (usage limit reached)", retryable=True)
        self.retry_after = retry_after


class NotConfigured(EngineError):
    pass


class OpenAICompatibleEngine:
    """Works with Groq and OpenAI: both offer the same /audio/transcriptions API."""

    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name, self.base_url, self.api_key, self.model = name, base_url.rstrip("/"), api_key, model

    def transcribe(self, path: Path, language: Optional[str], prompt: str) -> list[dict]:
        import httpx  # imported here so the rest of the app loads even without it

        data = {
            "model": self.model,
            "response_format": "verbose_json",
            "temperature": "0",
            "timestamp_granularities[]": ["segment", "word"],
        }
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        try:
            with open(path, "rb") as audio:
                response = httpx.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (path.name, audio, "audio/ogg")},
                    data=data,
                    timeout=httpx.Timeout(600.0, connect=30.0),
                )
        except httpx.HTTPError as exc:
            raise EngineError(f"Could not reach the transcription service: {exc.__class__.__name__}", retryable=True)

        if response.status_code == 429:
            try:
                wait = float(response.headers.get("retry-after", "60"))
            except ValueError:
                wait = 60.0
            raise RateLimited(wait)
        if response.status_code in (401, 403):
            raise EngineError("The transcription key was rejected. Check GROQ_API_KEY on the server.")
        if response.status_code >= 500:
            raise EngineError("The transcription service had a problem", retryable=True)
        if response.status_code >= 400:
            raise EngineError("The transcription service refused this audio: " + response.text[:200])

        payload = response.json()
        segments = [
            {
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", ""),
                "avg_logprob": seg.get("avg_logprob"),
                "no_speech_prob": seg.get("no_speech_prob"),
                "compression_ratio": seg.get("compression_ratio"),
                "words": [],
            }
            for seg in payload.get("segments", [])
        ]
        # word times arrive as one separate list: give each word to the segment that contains it
        for word in payload.get("words", []) or []:
            middle = (word.get("start", 0.0) + word.get("end", 0.0)) / 2
            home = next((seg for seg in segments if seg["start"] - 0.05 <= middle <= seg["end"] + 0.05), None)
            if home is None and segments:
                home = min(segments, key=lambda seg: abs((seg["start"] + seg["end"]) / 2 - middle))
            if home is not None:
                home["words"].append({"word": word.get("word", ""), "start": word.get("start", 0.0), "end": word.get("end", 0.0)})
        return segments


def get_engine() -> OpenAICompatibleEngine:
    if settings.transcribe_engine == "openai":
        if not settings.openai_api_key:
            raise NotConfigured("Transcription is not set up on this server yet (missing OPENAI_API_KEY).")
        return OpenAICompatibleEngine("openai", "https://api.openai.com/v1", settings.openai_api_key, settings.openai_model)
    if not settings.groq_api_key:
        raise NotConfigured("Transcription is not set up on this server yet (missing GROQ_API_KEY).")
    return OpenAICompatibleEngine("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, settings.groq_model)


def is_configured() -> bool:
    try:
        get_engine()
        return True
    except NotConfigured:
        return False
