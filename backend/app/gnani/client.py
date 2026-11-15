from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import httpx

from backend.app.gnani.cache import TTSCache
from backend.app.gnani.ledger import GnaniLedger
from backend.app.gnani.limiter import PriorityLimiter
from backend.app.settings import (
    AUDIO_CACHE_DIR,
    CREDIT_BUDGET_INR,
    DATA_DIR,
    GNANI_API_KEY,
    GNANI_MAX_CONCURRENCY,
    PRISMA_MODEL,
    STT_COST_INR_PER_SECOND,
    TIMBRE_MODEL,
    TTS_COST_INR_PER_1000_CHARS,
    TTS_VOICE,
)

API_BASE = "https://api.vachana.ai"
RETRY_DELAYS = (0.5, 1.0, 2.0)
RETRYABLE_STATUS = {429, 500, 503, 504}
TTS_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2026": "...", "\u00a0": " ", "\u200b": "", "\u200c": "", "\u200d": "",
    "\ufeff": "",
}
MIN_AUDIO_BYTES = 1200


def normalize_for_tts(text: str) -> str:
    for source, target in TTS_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = re.sub(r"[*_#`]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class GnaniAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class GnaniGateway:
    def __init__(
        self,
        *,
        api_key: str = GNANI_API_KEY,
        client: httpx.AsyncClient | None = None,
        limiter: PriorityLimiter | None = None,
        ledger: GnaniLedger | None = None,
        cache: TTSCache | None = None,
        stt_cost_inr_per_second: float | None = STT_COST_INR_PER_SECOND,
        tts_cost_inr_per_1000_chars: float | None = TTS_COST_INR_PER_1000_CHARS,
        credit_budget_inr: float = CREDIT_BUDGET_INR,
    ) -> None:
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(35.0), follow_redirects=False)
        self._owns_client = client is None
        self.limiter = limiter or PriorityLimiter(GNANI_MAX_CONCURRENCY)
        self.ledger = ledger or GnaniLedger(DATA_DIR / "hatch.sqlite3")
        self.cache = cache or TTSCache(AUDIO_CACHE_DIR)
        self.budget_inr = credit_budget_inr
        self.stt_cost_inr_per_second = stt_cost_inr_per_second
        self.tts_cost_inr_per_1000_chars = tts_cost_inr_per_1000_chars

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _error(self, response: httpx.Response) -> GnaniAPIError:
        code = f"HTTP_{response.status_code}"
        message = "Gnani request failed"
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            payload: Any = body.get("error", body.get("detail", body))
            if isinstance(payload, dict):
                code = str(payload.get("error_code", payload.get("type", code)))
                message = str(payload.get("message", message))
            elif isinstance(payload, str):
                message = payload
            elif isinstance(body.get("message"), str):
                message = body["message"]
        if self.api_key:
            message = message.replace(self.api_key, "[REDACTED]")
        return GnaniAPIError(response.status_code, code, message[:500])

    async def _send(
        self,
        *,
        method: str,
        url: str,
        priority: int,
        kind: str,
        model: str,
        units: float,
        estimated_inr: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if not self.api_key:
            raise RuntimeError("GNANI_API_KEY is missing; speech requests are unavailable.")
        if estimated_inr is None:
            raise GnaniAPIError(
                402,
                "COST_UNCALIBRATED",
                "Hatch blocked this unpriced speech request. Set the measured STT/TTS rate in .env to enable it.",
            )
        headers = dict(kwargs.pop("headers", {}))
        headers["X-API-Key-ID"] = self.api_key
        attempts = 0
        while True:
            started = time.perf_counter()
            async with self.limiter.slot(priority):
                if estimated_inr is not None:
                    spent = self.ledger.summary()["estimated_inr"] or 0.0
                    if spent + estimated_inr > self.budget_inr * 0.7:
                        raise GnaniAPIError(
                            402,
                            "LOCAL_BUDGET_GUARD",
                            "Hatch paused speech calls at 70% of the configured credit budget.",
                        )
                try:
                    response = await self.client.request(method, url, headers=headers, **kwargs)
                except httpx.HTTPError as error:
                    self.ledger.record(
                        kind=kind,
                        model=model,
                        units=units,
                        estimated_inr=estimated_inr,
                        request_id=None,
                        status=0,
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
                    raise GnaniAPIError(
                        502,
                        "NETWORK_ERROR",
                        f"Gnani connection failed ({type(error).__name__}).",
                    ) from error
                latency_ms = (time.perf_counter() - started) * 1000
                request_id = response.headers.get("X-API-Request-ID") or response.headers.get("X-Request-ID")
                self.ledger.record(
                    kind=kind,
                    model=model,
                    units=units,
                    estimated_inr=estimated_inr,
                    request_id=request_id,
                    status=response.status_code,
                    latency_ms=latency_ms,
                )
            if response.status_code in RETRYABLE_STATUS and attempts < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempts]
                attempts += 1
                await asyncio.sleep(delay)
                continue
            if response.is_error:
                raise self._error(response)
            return response

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "turn.wav",
        model: str = PRISMA_MODEL,
        language_code: str = "indic-auto",
        audio_format: str = "codemix",
        priority: int = PriorityLimiter.LIVE,
    ) -> dict[str, Any]:
        fields: dict[str, str] = {"language_code": language_code, "format": audio_format}
        if model == "prisma-v3.0":
            fields["model"] = model
        response = await self._send(
            method="POST",
            url=f"{API_BASE}/stt/v3",
            priority=priority,
            kind="stt",
            model=model,
            units=len(audio) / 32000,
            estimated_inr=(
                len(audio) / 32000 * self.stt_cost_inr_per_second
                if self.stt_cost_inr_per_second is not None else None
            ),
            data=fields,
            files={"audio_file": (filename, audio, "audio/wav")},
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise GnaniAPIError(response.status_code, "INVALID_RESPONSE", "STT returned invalid JSON.") from error
        if not isinstance(payload, dict) or payload.get("success") is False:
            raise GnaniAPIError(response.status_code, "STT_FAILED", "STT did not return a transcript.")
        return payload

    async def synthesize(
        self,
        text: str,
        *,
        model: str = TIMBRE_MODEL,
        voice: str = TTS_VOICE,
        language: str = "hi-IN",
        speed: float = 1.0,
        priority: int = PriorityLimiter.LIVE,
    ) -> tuple[bytes, dict[str, Any]]:
        text = normalize_for_tts(text)
        if not text:
            raise GnaniAPIError(400, "EMPTY_TEXT", "There is no speakable text in this reply.")
        cache_key = self.cache.key(model=model, voice=voice, language=language, speed=speed, text=text)
        cached = await asyncio.to_thread(self.cache.get, cache_key)
        if cached is not None:
            return cached, {"cached": True, "model": model}
        response = await self._send(
            method="POST",
            url=f"{API_BASE}/api/v1/tts/inference",
            priority=priority,
            kind="tts",
            model=model,
            units=float(len(text)),
            estimated_inr=(
                len(text) / 1000 * self.tts_cost_inr_per_1000_chars
                if self.tts_cost_inr_per_1000_chars is not None else None
            ),
            json={
                "text": text,
                "model": model,
                "voice": voice,
                "language": language,
                "speed": speed,
                "audio_config": {
                    "sample_rate": 24000,
                    "num_channels": 1,
                    "sample_width": 2,
                    "encoding": "pcm_s16le",
                    "container": "wav",
                },
            },
        )
        if "json" in response.headers.get("content-type", "").lower():
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if isinstance(payload, dict) and payload.get("success") is False:
                raise GnaniAPIError(
                    int(payload.get("status_code", 502)),
                    "TTS_FAILED",
                    str(payload.get("message", "TTS synthesis failed"))[:500],
                )
        audio = response.content
        if len(audio) < MIN_AUDIO_BYTES:
            raise GnaniAPIError(
                response.status_code,
                "EMPTY_AUDIO",
                "Timbre returned audio that is too short to play. Text fallback is available.",
            )
        if not audio.startswith(b"RIFF"):
            raise GnaniAPIError(
                response.status_code,
                "INVALID_AUDIO",
                "Timbre returned an unexpected audio format. Text fallback is available.",
            )
        await asyncio.to_thread(self.cache.put, cache_key, audio)
        return audio, {
            "cached": False,
            "model": model,
            "request_id": response.headers.get("X-API-Request-ID") or response.headers.get("X-Request-ID"),
        }
