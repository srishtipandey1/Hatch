from __future__ import annotations

from backend.app.lint import lint_spec
from backend.app.models import AgentSpec, LanguagePolicy, STTConfig, VoiceConfig


def test_internal_prompt_is_not_checked_as_spoken_sentence() -> None:
    spec = AgentSpec(
        agent_id="lint-agent",
        name="Shop helper",
        persona="Polite support agent.",
        opening_line="Hello, how can I help?",
        closing_line="Goodbye.",
        system_prompt=" ".join(
            ["Use the supplied policy facts and keep the conversation within the declared business scope"] * 3
        ),
        language_policy=LanguagePolicy(
            primary="en-IN",
            allowed=["en-IN"],
            switch_rule="Follow the caller.",
        ),
        voice=VoiceConfig(model="timbre-v3.0", voice="Shivani", language="en-IN"),
        stt=STTConfig(model="prisma-v3.0", language_code="indic-auto", format="transcribe"),
    )

    assert "Keep each spoken sentence to 25 words or fewer." not in lint_spec(spec)
