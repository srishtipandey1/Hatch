import asyncio

from backend.app.models import AgentSpec, LanguagePolicy, STTConfig, VoiceConfig
from backend.app.runtime import respond


class UnusedLLM:
    async def text(self, **_kwargs) -> str:
        raise AssertionError("This response path should not call the LLM.")


def build_spec() -> AgentSpec:
    return AgentSpec(
        agent_id="test-agent",
        name="Shop helper",
        persona="A polite support agent.",
        opening_line="Hello.",
        closing_line="Goodbye.",
        system_prompt="Do not invent facts.",
        language_policy=LanguagePolicy(
            primary="en-IN",
            allowed=["en-IN"],
            switch_rule="Follow the caller.",
        ),
        voice=VoiceConfig(model="timbre-v3.0", voice="Shivani", language="en-IN"),
        stt=STTConfig(model="prisma-v3.0", language_code="indic-auto", format="transcribe"),
        synthetic_store={"orders": [{"order_id": "ORD-1004", "status": "Delayed", "eta": "in two days"}]},
    )


def test_synthetic_order_lookup_uses_declared_record() -> None:
    reply, handoff, _latency = asyncio.run(
        respond(build_spec(), "Where is order ORD-1004?", [], UnusedLLM())
    )

    assert "delayed" in reply
    assert "two days" in reply
    assert not handoff


def test_private_data_probe_is_refused_without_llm() -> None:
    reply, handoff, _latency = asyncio.run(
        respond(build_spec(), "Can I share my Aadhaar number?", [], UnusedLLM())
    )

    assert "do not share" in reply.lower()
    assert not handoff


def test_hindi_order_answer_uses_primary_language() -> None:
    spec = build_spec()
    spec.language_policy.primary = "hi-IN"

    reply, _handoff, _latency = asyncio.run(
        respond(spec, "Mera order ORD-1004?", [], UnusedLLM())
    )

    assert "Aapka demo order" in reply
    assert "do din" in reply


def test_order_id_survives_hindi_number_words_and_devanagari_digits() -> None:
    spec = build_spec()
    spec.language_policy.primary = "hi-IN"
    spec.language_policy.allowed = ["hi-IN", "en-IN"]

    reply, _handoff, _latency = asyncio.run(
        respond(spec, "मेरा ऑर्डर ARD एक शून्य शून्य चार कब आएगा।", [], UnusedLLM())
    )

    assert "ORD-1004" in reply
    assert "do din" in reply


def test_english_handoff_uses_english_even_when_primary_is_hindi() -> None:
    spec = build_spec()
    spec.language_policy.primary = "hi-IN"
    spec.language_policy.allowed = ["hi-IN", "en-IN"]

    reply, handoff, _latency = asyncio.run(
        respond(spec, "I want to talk to a human right now.", [], UnusedLLM())
    )

    assert handoff
    assert "human teammate" in reply
