from __future__ import annotations

import tempfile
from pathlib import Path

from backend.app.models import AgentSpec, LanguagePolicy, STTConfig, VoiceConfig
from backend.app.store import HatchStore


def test_legacy_spec_gets_explicit_missing_provenance() -> None:
    with tempfile.TemporaryDirectory(prefix="hatch-test-", dir=Path.cwd()) as directory:
        store = HatchStore(Path(directory) / "legacy.sqlite")
        spec = AgentSpec(
            agent_id="legacy-agent",
            name="Legacy helper",
            persona="Helpful support agent.",
            opening_line="Hello.",
            closing_line="Goodbye.",
            system_prompt="Use stated facts only.",
            language_policy=LanguagePolicy(
                primary="en-IN",
                allowed=["en-IN"],
                switch_rule="Follow the caller.",
            ),
            voice=VoiceConfig(model="timbre-v3.0", voice="Shivani", language="en-IN"),
            stt=STTConfig(model="prisma-v3.0", language_code="indic-auto", format="transcribe"),
        )
        store.save_agent(spec)

        loaded = store.get_spec("legacy-agent")

    assert loaded is not None
    assert loaded.provenance["name"].source == "defaulted"
    assert "Legacy spec" in loaded.provenance["name"].evidence
    assert set(AgentSpec.model_fields) - {"provenance"} <= set(loaded.provenance)
