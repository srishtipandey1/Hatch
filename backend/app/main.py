from __future__ import annotations

import base64
import json
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.audio import AudioConversionError, to_wav
from backend.app.compiler import SUPPORTED_LANGUAGES, compile_agent
from backend.app.gnani import GnaniAPIError, GnaniGateway
from backend.app.gnani.limiter import PriorityLimiter
from backend.app.llm import LLMAPIError, LLMGateway
from backend.app.models import AgentCreate, AgentSpec, TestReport, TextTurn
from backend.app.runtime import respond
from backend.app.simulator import run_test_and_repair
from backend.app.settings import (
    DATA_DIR,
    GNANI_MAX_CONCURRENCY,
    PRISMA_MODEL,
    TIMBRE_MODEL,
    TTS_VOICE,
)
from backend.app.store import HatchStore

store = HatchStore(DATA_DIR / "hatch.sqlite3")
llm = LLMGateway()
gateway = GnaniGateway(limiter=PriorityLimiter(GNANI_MAX_CONCURRENCY))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await gateway.close()
    await llm.close()


app = FastAPI(title="Hatch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1800)
    language: str = "hi-IN"
    model: str = TIMBRE_MODEL
    voice: str = TTS_VOICE
    speed: float = 1.0


def split_for_tts(text: str, max_chars: int = 180) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text]


async def synthesize_chunks(
    text: str,
    *,
    model: str,
    voice: str,
    language: str,
    speed: float = 1.0,
) -> tuple[list[str], list[dict[str, object]]]:
    encoded: list[str] = []
    metadata: list[dict[str, object]] = []
    for chunk in split_for_tts(text):
        audio, meta = await gateway.synthesize(
            chunk,
            model=model,
            voice=voice,
            language=language,
            speed=speed,
        )
        encoded.append(base64.b64encode(audio).decode("ascii"))
        metadata.append(meta)
    return encoded, metadata


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Hatch"}


@app.get("/api/ledger")
def ledger_summary() -> dict[str, float | int | None]:
    return gateway.ledger.summary()


@app.post("/api/tts")
async def tts(request: TTSRequest) -> Response:
    try:
        audio, metadata = await gateway.synthesize(
            request.text,
            model=request.model,
            voice=request.voice,
            language=request.language,
            speed=request.speed,
        )
    except GnaniAPIError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    headers = {"X-Gnani-Model": request.model}
    if metadata.get("request_id"):
        headers["X-Gnani-Request-ID"] = str(metadata["request_id"])
    return Response(content=audio, media_type="audio/wav", headers=headers)


@app.post("/api/voice/turn")
async def voice_turn(audio: UploadFile = File(...)) -> dict[str, object]:
    raw_audio = await audio.read(12 * 1024 * 1024 + 1)
    if not raw_audio:
        raise HTTPException(status_code=400, detail="No audio was recorded.")
    if len(raw_audio) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Recording exceeds the 12 MB limit.")
    started = time.perf_counter()
    try:
        wav_audio = await to_wav(raw_audio, audio.filename or "turn.webm")
        stt = await gateway.transcribe(wav_audio, filename="turn.wav")
        transcript = str(stt.get("transcript", "")).strip()
        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="No speech was recognized. Try again or type your description.",
            )
        detected_language = stt.get("detected_language_code")
        language = detected_language if detected_language in SUPPORTED_LANGUAGES else "hi-IN"
        audio_chunks, tts_metadata = await synthesize_chunks(
            transcript,
            model=TIMBRE_MODEL,
            voice=TTS_VOICE,
            language=language,
        )
    except AudioConversionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except GnaniAPIError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "transcript": transcript,
        "detected_language_code": stt.get("detected_language_code"),
        "stt_model": stt.get("model", PRISMA_MODEL),
        "stt_latency_seconds": stt.get("end_to_end_latency"),
        "stt_request_id": stt.get("request_id"),
        "tts_model": tts_metadata[0].get("model", TIMBRE_MODEL) if tts_metadata else TIMBRE_MODEL,
        "tts_request_id": tts_metadata[0].get("request_id") if tts_metadata else None,
        "tts_cached": all(bool(meta.get("cached")) for meta in tts_metadata),
        "audio_base64": audio_chunks[0] if audio_chunks else "",
        "audio_chunks": audio_chunks,
        "total_latency_seconds": round(time.perf_counter() - started, 3),
        "ledger": gateway.ledger.summary(),
    }


@app.post("/api/agents", status_code=201)
async def create_agent(request: AgentCreate) -> AgentSpec:
    try:
        spec = await compile_agent(request.description, llm)
    except LLMAPIError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    store.save_agent(spec)
    return spec


@app.get("/api/agents")
def list_agents() -> list[dict[str, object]]:
    return store.list_agents()


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str) -> AgentSpec:
    spec = store.get_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Hatched agent not found.")
    return spec


@app.post("/api/agents/{agent_id}/test")
async def test_agent(agent_id: str) -> TestReport:
    spec = store.get_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Hatched agent not found.")
    try:
        return await run_test_and_repair(spec, llm, store)
    except LLMAPIError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/agents/{agent_id}/test-report")
def get_test_report(agent_id: str) -> TestReport | None:
    spec = store.get_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Hatched agent not found.")
    return store.get_report(f"{spec.agent_id}:v{spec.version}")


@app.post("/api/agents/{agent_id}/turn")
async def agent_text_turn(agent_id: str, request: TextTurn) -> dict[str, object]:
    spec = store.get_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Hatched agent not found.")
    try:
        reply, handoff, latency = await respond(spec, request.text, request.history, llm)
    except LLMAPIError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"text": reply, "latency_seconds": latency, "handoff": handoff}


@app.post("/api/agents/{agent_id}/voice-turn")
async def agent_voice_turn(
    agent_id: str,
    audio: UploadFile = File(...),
    history: str = Form(default="[]"),
) -> dict[str, object]:
    spec = store.get_spec(agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Hatched agent not found.")
    try:
        previous = json.loads(history)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Conversation history must be valid JSON.") from error
    if not isinstance(previous, list):
        raise HTTPException(status_code=400, detail="Conversation history must be a list.")
    raw_audio = await audio.read(12 * 1024 * 1024 + 1)
    if not raw_audio:
        raise HTTPException(status_code=400, detail="No audio was recorded.")
    if len(raw_audio) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Recording exceeds the 12 MB limit.")
    started = time.perf_counter()
    try:
        wav_audio = await to_wav(raw_audio, audio.filename or "turn.webm")
        stt = await gateway.transcribe(
            wav_audio,
            filename="turn.wav",
            model=spec.stt.model,
            language_code=spec.stt.language_code,
            audio_format=spec.stt.format,
        )
        transcript = str(stt.get("transcript", "")).strip()
        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="No speech was recognized. Try again or type your message.",
            )
        valid_history = [
            item for item in previous
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
        ]
        reply, handoff, llm_latency = await respond(spec, transcript, valid_history, llm)
        detected_language = stt.get("detected_language_code")
        language = detected_language if detected_language in spec.language_policy.allowed else spec.voice.language
        audio_chunks, tts_metadata = await synthesize_chunks(
            reply,
            model=spec.voice.model,
            voice=spec.language_policy.per_language_voice.get(language, spec.voice.voice),
            language=language,
        )
    except AudioConversionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except GnaniAPIError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error
    except LLMAPIError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "transcript": transcript,
        "reply": reply,
        "detected_language_code": stt.get("detected_language_code"),
        "stt_latency_seconds": stt.get("end_to_end_latency"),
        "stt_request_id": stt.get("request_id"),
        "llm_latency_seconds": llm_latency,
        "total_latency_seconds": round(time.perf_counter() - started, 3),
        "handoff": handoff,
        "audio_base64": audio_chunks[0] if audio_chunks else "",
        "audio_chunks": audio_chunks,
        "tts_request_id": tts_metadata[0].get("request_id") if tts_metadata else None,
        "tts_cached": all(bool(meta.get("cached")) for meta in tts_metadata),
        "ledger": gateway.ledger.summary(),
    }
