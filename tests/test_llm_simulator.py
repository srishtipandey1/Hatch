from __future__ import annotations

import asyncio
import json
import re

import httpx

from backend.app.llm import LLMAPIError, LLMGateway
from backend.app.models import AgentSpec, GeneratedCopy, LanguagePolicy, STTConfig, Verdict, VoiceConfig
from backend.app.simulator import RepairPlan, SCENARIOS, _run_scenario, run_test_and_repair


def test_invalid_json_gets_one_structured_repair_request() -> None:
    async def scenario() -> tuple[GeneratedCopy, int]:
        responses = iter([
            "not json",
            json.dumps({
                "name": "Store helper",
                "persona": "Polite helper.",
                "opening_line": "Hello.",
                "closing_line": "Goodbye.",
                "system_prompt": "Help with stated facts.",
            }),
        ])
        calls = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": next(responses)}}]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        llm = LLMGateway(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            client=client,
        )
        result = await llm.structured(
            system="Return structured copy.",
            user="Generate a concise helper.",
            schema=GeneratedCopy,
        )
        await client.aclose()
        return result, calls

    copy, calls = asyncio.run(scenario())
    assert copy.name == "Store helper"
    assert calls == 2


def test_llm_rate_limit_error_is_explicit_and_safe() -> None:
    async def scenario() -> LLMAPIError:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="provider detail not shown")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        llm = LLMGateway(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            client=client,
        )
        try:
            await llm.text(system="Be concise.", user="Say hello.")
        except LLMAPIError as error:
            return error
        finally:
            await client.aclose()
        raise AssertionError("Expected the rate-limit response to fail.")

    error = asyncio.run(scenario())

    assert error.status_code == 429
    assert "rate limit" in error.message
    assert "provider detail" not in error.message


def test_llm_retries_a_transient_rate_limit(monkeypatch) -> None:
    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("backend.app.llm.asyncio.sleep", no_wait)

    async def scenario() -> tuple[str, int]:
        calls = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "OK"}}]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        llm = LLMGateway(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            client=client,
        )
        try:
            answer = await llm.text(system="Be concise.", user="Say hello.")
        finally:
            await client.aclose()
        return answer, calls

    answer, calls = asyncio.run(scenario())

    assert answer == "OK"
    assert calls == 2


def test_llm_validation_error_exposes_safe_provider_diagnostic() -> None:
    async def scenario() -> LLMAPIError:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"message": "Unsupported response format."}})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        llm = LLMGateway(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            client=client,
        )
        try:
            await llm.text(system="Be concise.", user="Say hello.")
        except LLMAPIError as error:
            return error
        finally:
            await client.aclose()
        raise AssertionError("Expected the invalid request to fail.")

    error = asyncio.run(scenario())

    assert error.status_code == 400
    assert "Unsupported response format." in error.message
    assert "test-key" not in error.message


def test_structured_requests_always_satisfy_json_mode_requirement() -> None:
    async def scenario() -> GeneratedCopy:
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            messages = " ".join(message["content"] for message in body["messages"])
            if "json" not in messages.lower():
                return httpx.Response(
                    400,
                    json={"error": {"message": "Messages must mention json."}},
                )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps({
                    "name": "Shop helper",
                    "persona": "Polite assistant.",
                    "opening_line": "Hello.",
                    "closing_line": "Goodbye.",
                    "system_prompt": "Use stated facts only.",
                })}}]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        llm = LLMGateway(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            client=client,
        )
        try:
            return await llm.structured(
                system="Create concise copy.",
                user="Make an assistant.",
                schema=GeneratedCopy,
            )
        finally:
            await client.aclose()

    copy = asyncio.run(scenario())

    assert copy.name == "Shop helper"


def test_simulator_evidence_turn_is_taken_from_agent_reply() -> None:
    class StubJudge:
        async def structured(self, **_kwargs) -> Verdict:
            return Verdict(
                scenario_id="wrong-id",
                result="pass",
                reason="Uses the declared order information.",
                evidence_turn="not a quote",
            )

    spec = AgentSpec(
        agent_id="test-agent",
        name="Shop helper",
        persona="Polite support agent.",
        opening_line="Hello.",
        closing_line="Goodbye.",
        system_prompt="Use the synthetic order store.",
        language_policy=LanguagePolicy(primary="en-IN", allowed=["en-IN"], switch_rule="Follow caller."),
        voice=VoiceConfig(model="timbre-v3.0", voice="Shivani", language="en-IN"),
        stt=STTConfig(model="prisma-v3.0", language_code="indic-auto", format="codemix"),
        synthetic_store={"orders": [{"order_id": "ORD-1004", "status": "Delayed", "eta": "in two days"}]},
    )
    scenario = next(item for item in SCENARIOS if item["id"] == "code-mix-order")

    verdict, reply = asyncio.run(_run_scenario(spec, scenario, StubJudge()))

    assert verdict.scenario_id == scenario["id"]
    assert verdict.evidence_turn in reply


def test_simulator_reports_before_and_after_one_repair_round() -> None:
    class StubLLM:
        repaired = False

        async def text(self, **_kwargs) -> str:
            return "I can help with that."

        async def structured(self, *, schema, user, **_kwargs):
            if schema is RepairPlan:
                self.repaired = True
                return RepairPlan(
                    addendum="Stay within scope and keep responses concise.",
                    reason="The confused caller needs a clearer explanation.",
                )
            match = re.search(r"Scenario ID: ([^\n]+)", user)
            scenario_id = match.group(1) if match else "unknown"
            result = "fail" if scenario_id == "confused-caller" and not self.repaired else "pass"
            return Verdict(
                scenario_id=scenario_id,
                result=result,
                reason="Scenario check completed.",
                evidence_turn="I can help with that.",
            )

    class StubStore:
        def save_spec_version(self, _spec) -> None:
            pass

        def save_report(self, report) -> None:
            self.report = report

    spec = AgentSpec(
        agent_id="test-agent",
        name="Shop helper",
        persona="Polite support agent.",
        opening_line="Hello.",
        closing_line="Goodbye.",
        system_prompt="Use the synthetic order store.",
        language_policy=LanguagePolicy(primary="en-IN", allowed=["en-IN"], switch_rule="Follow caller."),
        voice=VoiceConfig(model="timbre-v3.0", voice="Shivani", language="en-IN"),
        stt=STTConfig(model="prisma-v3.0", language_code="indic-auto", format="codemix"),
        synthetic_store={"orders": [{"order_id": "ORD-1004", "status": "Delayed", "eta": "in two days"}]},
    )
    llm = StubLLM()
    store = StubStore()

    report = asyncio.run(run_test_and_repair(spec, llm, store))

    assert len(report.before_verdicts) == len(SCENARIOS)
    assert report.before_verdicts[0].result == "fail"
    assert len(report.verdicts) == len(SCENARIOS)
    assert all(verdict.result == "pass" for verdict in report.verdicts)
    assert "6/7 passed before repair; 7/7 after one repair round." == report.summary
    assert len(report.repairs) == 1


