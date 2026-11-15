from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import httpx

from backend.app.gnani import GnaniAPIError, GnaniGateway
from backend.app.gnani.cache import TTSCache
from backend.app.gnani.ledger import GnaniLedger
from backend.app.gnani.limiter import PriorityLimiter


def test_priority_limiter_runs_waiters_by_priority() -> None:
    async def scenario() -> list[str]:
        limiter = PriorityLimiter(1)
        order: list[str] = []

        async def take(label: str, priority: int) -> None:
            async with limiter.slot(priority):
                order.append(label)

        async with limiter.slot():
            preview = asyncio.create_task(take("preview", PriorityLimiter.PREVIEW))
            live = asyncio.create_task(take("live", PriorityLimiter.LIVE))
            await asyncio.sleep(0)
        await asyncio.gather(preview, live)
        return order

    assert asyncio.run(scenario()) == ["live", "preview"]


def test_tts_cache_prevents_duplicate_provider_calls() -> None:
    async def scenario() -> tuple[bool, bool, int]:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=b"RIFF-audio", headers={"content-type": "audio/wav"})

        with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
            path = Path(directory)
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            gateway = GnaniGateway(
                api_key="test-key",
                client=client,
                ledger=GnaniLedger(path / "ledger.sqlite"),
                cache=TTSCache(path / "cache"),
                tts_cost_inr_per_1000_chars=0.01,
            )
            _, first = await gateway.synthesize("Namaste")
            _, second = await gateway.synthesize("Namaste")
            await client.aclose()
            return bool(first["cached"]), bool(second["cached"]), calls

    first_cached, second_cached, calls = asyncio.run(scenario())
    assert not first_cached
    assert second_cached
    assert calls == 1


def test_stt_retries_rate_limit_then_succeeds(monkeypatch) -> None:
    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("backend.app.gnani.client.asyncio.sleep", no_wait)

    async def scenario() -> tuple[dict, int]:
        calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={"detail": {"error_code": "RATE_LIMITED", "message": "slow"}})
            return httpx.Response(
                200,
                json={"success": True, "model": "prisma-v3.0", "transcript": "hello"},
            )

        with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
            path = Path(directory)
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            gateway = GnaniGateway(
                api_key="test-key",
                client=client,
                ledger=GnaniLedger(path / "retry-ledger.sqlite"),
                cache=TTSCache(path / "retry-cache"),
                stt_cost_inr_per_second=0.01,
            )
            result = await gateway.transcribe(b"audio")
            await client.aclose()
            return result, calls

    result, calls = asyncio.run(scenario())
    assert result["transcript"] == "hello"
    assert calls == 2


def test_unpriced_speech_calls_fail_closed() -> None:
    async def scenario() -> tuple[list[tuple[int, str]], int]:
        calls = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=b"RIFF-audio")

        with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
            path = Path(directory)
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            gateway = GnaniGateway(
                api_key="test-key",
                client=client,
                ledger=GnaniLedger(path / "unpriced-ledger.sqlite"),
                cache=TTSCache(path / "unpriced-cache"),
                stt_cost_inr_per_second=None,
                tts_cost_inr_per_1000_chars=None,
            )
            try:
                errors = []
                for request in (
                    gateway.transcribe(b"audio"),
                    gateway.synthesize("Unpriced request"),
                ):
                    try:
                        await request
                    except GnaniAPIError as error:
                        errors.append((error.status_code, error.code))
                    else:
                        raise AssertionError("Unpriced speech call must be blocked.")
            finally:
                await client.aclose()
            return errors, calls

    errors, calls = asyncio.run(scenario())
    assert errors == [(402, "COST_UNCALIBRATED"), (402, "COST_UNCALIBRATED")]
    assert calls == 0


def test_budget_guard_blocks_before_the_provider_call() -> None:
    async def scenario() -> tuple[int, str, int]:
        calls = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=b"RIFF-audio")

        with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
            path = Path(directory)
            ledger = GnaniLedger(path / "budget-ledger.sqlite")
            ledger.record(
                kind="tts",
                model="timbre-v3.0",
                units=1,
                estimated_inr=7.0,
                request_id="previous",
                status=200,
                latency_ms=1,
            )
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            gateway = GnaniGateway(
                api_key="test-key",
                client=client,
                ledger=ledger,
                cache=TTSCache(path / "budget-cache"),
                tts_cost_inr_per_1000_chars=100,
                credit_budget_inr=10,
            )
            try:
                await gateway.synthesize("1234567890")
            except GnaniAPIError as error:
                result = (error.status_code, error.code, calls)
            else:
                raise AssertionError("The budget threshold must block the next TTS request.")
            finally:
                await client.aclose()
            return result

    status_code, code, calls = asyncio.run(scenario())
    assert status_code == 402
    assert code == "LOCAL_BUDGET_GUARD"
    assert calls == 0


def test_shipped_defaults_price_speech_so_the_voice_path_stays_enabled() -> None:
    from backend.app import settings

    assert settings.STT_COST_INR_PER_SECOND > 0
    assert settings.TTS_COST_INR_PER_1000_CHARS > 0

    async def scenario() -> tuple[float | None, int]:
        calls = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=b"RIFF-audio", headers={"content-type": "audio/wav"})

        with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
            path = Path(directory)
            ledger = GnaniLedger(path / "default-ledger.sqlite")
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            gateway = GnaniGateway(
                api_key="test-key",
                client=client,
                ledger=ledger,
                cache=TTSCache(path / "default-cache"),
                stt_cost_inr_per_second=settings.STT_COST_INR_PER_SECOND,
                tts_cost_inr_per_1000_chars=settings.TTS_COST_INR_PER_1000_CHARS,
            )
            try:
                await gateway.synthesize("Namaste")
            finally:
                await client.aclose()
            return ledger.summary()["estimated_inr"], calls

    estimated_inr, calls = asyncio.run(scenario())
    assert calls == 1
    assert estimated_inr is not None and estimated_inr > 0

