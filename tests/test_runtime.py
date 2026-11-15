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


def test_hindi_handoff_triggers_on_angry_or_human_request() -> None:
    spec = build_spec()
    spec.language_policy.primary = "hi-IN"
    spec.language_policy.allowed = ["hi-IN", "en-IN"]

    reply, handoff, _latency = asyncio.run(
        respond(spec, "Mujhe kisi manager ya human se baat karni hai, main bohot gussa hoon!", [], UnusedLLM())
    )

    assert handoff
    assert "human teammate" in reply


def test_synthetic_orders_range_supported() -> None:
    from backend.app.compiler import compile_agent
    class DummyLLM:
        async def structured(self, **kwargs):
            from backend.app.models import RequirementSet, GeneratedCopy
            if kwargs["schema"] == RequirementSet:
                return RequirementSet(
                    business_context="Clothing store",
                    agent_goal="Help with orders and returns",
                    languages=["hi-IN", "en-IN"],
                    tone="Warm and polite",
                    code_mix_expected=False,
                    responsibilities=["orders", "returns"],
                )
            return GeneratedCopy(
                name="Store Support",
                persona="Helpful assistant",
                opening_line="Namaste!",
                closing_line="Alvida!",
                system_prompt="Be polite.",
            )
    spec = asyncio.run(compile_agent("Clothing store", DummyLLM()))
    assert len(spec.synthetic_store["orders"]) == 10
    assert spec.synthetic_store["orders"][0]["order_id"] == "ORD-1001"
    assert spec.synthetic_store["orders"][-1]["order_id"] == "ORD-1010"

