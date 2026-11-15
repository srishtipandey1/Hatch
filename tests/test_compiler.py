import asyncio

from backend.app.compiler import _normalize_agent_name, detect_hinglish, negotiate, requested_unsupported
from backend.app.compiler import compile_agent
from backend.app.models import GeneratedCopy, RequirementSet, VoiceConfig


def test_hinglish_description_enables_code_mix() -> None:
    assert detect_hinglish(
        "Mere kapde ki dukaan ke liye customer support agent banao"
    )
    assert not detect_hinglish("Create an English-only customer support assistant")


def test_capability_negotiation_reports_unsupported_language() -> None:
    requirements = RequirementSet(
        business_context="shop",
        agent_goal="help customers",
        languages=["Assamese"],
        code_mix_expected=False,
        tone="warm",
    )

    policy, voice, stt, unsupported = negotiate(requirements)

    assert policy.allowed == ["hi-IN", "en-IN"]
    assert voice.model == "timbre-v3.0"
    assert stt.format == "transcribe"
    assert unsupported[0].request == "Assamese"
    assert "Bengali" in unsupported[0].alternative


def test_capability_negotiation_accepts_bcp47_codes() -> None:
    requirements = RequirementSet(
        business_context="shop",
        agent_goal="help customers",
        languages=["hi-IN", "en-IN"],
        code_mix_expected=True,
        tone="warm",
    )

    policy, _voice, stt, unsupported = negotiate(requirements)

    assert policy.allowed == ["hi-IN", "en-IN"]
    assert not unsupported
    assert stt.format == "codemix"


def test_unsupported_live_integrations_are_surfaced() -> None:
    unsupported = requested_unsupported(
        "Also call customers on their phones and process payments."
    )

    assert len(unsupported) == 2
    assert any("Phone" in item.reason for item in unsupported)
    assert any("payment" in item.reason for item in unsupported)


def test_negated_unsupported_requests_are_not_reported() -> None:
    assert requested_unsupported("No phone calls or real payments.") == []


def test_agent_name_removes_duplicate_support_suffix() -> None:
    assert _normalize_agent_name("Clothing Store Customer Support Support") == "Clothing Store Customer Support"


def test_compiler_keeps_hinglish_and_provenance_without_provider() -> None:
    class StubLLM:
        async def structured(self, *, schema, **_kwargs):
            if schema is RequirementSet:
                return RequirementSet(
                    business_context="clothing store",
                    agent_goal="help with orders",
                    languages=["Hinglish"],
                    code_mix_expected=False,
                    tone="warm",
                    responsibilities=["handle orders"],
                    provenance={},
                )
            return GeneratedCopy(
                name="Shivani",
                persona="Warm store assistant",
                opening_line="Namaste, how may I help?",
                closing_line="Dhanyavaad.",
                system_prompt="Help with stated order questions.",
            )

    spec = asyncio.run(compile_agent(
        "Hinglish mein customer support agent banao for my kapde ki dukaan.",
        StubLLM(),
    ))

    assert spec.language_policy.allowed == ["hi-IN", "en-IN"]
    assert spec.stt.format == "codemix"
    assert spec.responsibilities == ["handle orders"]
    assert not spec.unsupported
    assert spec.name == "Clothing Store Support"
    assert spec.provenance["languages"].source == "stated"
    assert {
        "agent_id", "system_prompt", "synthetic_store", "unsupported", "open_questions", "lint_issues"
    } <= set(spec.provenance)


def test_legacy_symbolic_voice_speed_migrates_to_numeric_rate() -> None:
    config = VoiceConfig(model="timbre-v3.0", voice="Shivani", language="hi-IN", speed="medium")

    assert config.speed == 1.0

