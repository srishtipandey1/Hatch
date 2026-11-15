from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Provenance(BaseModel):
    source: Literal["stated", "inferred", "defaulted"]
    evidence: str


class Fact(BaseModel):
    question_variants: list[str] = Field(default_factory=list)
    answer: str


class ActionDecl(BaseModel):
    name: str
    description: str
    params: list[str] = Field(default_factory=list)
    returns: str = ""


class Question(BaseModel):
    field: str
    question: str
    default: str


class RequirementSet(BaseModel):
    business_context: str
    agent_goal: str
    languages: list[str]
    code_mix_expected: bool
    tone: str
    responsibilities: list[str] = Field(default_factory=list)
    knowledge: list[Fact] = Field(default_factory=list)
    escalation: list[str] = Field(default_factory=list)
    prohibitions: list[str] = Field(default_factory=list)
    provenance: dict[str, Provenance] = Field(default_factory=dict)


class LanguagePolicy(BaseModel):
    primary: str
    allowed: list[str]
    switch_rule: str
    per_language_voice: dict[str, str] = Field(default_factory=dict)


class VoiceConfig(BaseModel):
    model: str
    voice: str
    language: str
    speed: float = 1.0

    @field_validator("speed", mode="before")
    @classmethod
    def normalize_legacy_speed(cls, value: object) -> object:
        if isinstance(value, str):
            aliases = {"slow": 0.9, "medium": 1.0, "fast": 1.1}
            return aliases.get(value.lower(), value)
        return value


class STTConfig(BaseModel):
    model: str
    language_code: str
    format: str


class SessionLimits(BaseModel):
    max_turns: int = 20
    max_session_s: int = 900
    idle_s: int = 60


class Unsupported(BaseModel):
    request: str
    reason: str
    alternative: str


class AgentSpec(BaseModel):
    agent_id: str
    name: str
    version: int = 1
    business_context: str = ""
    agent_goal: str = ""
    persona: str
    opening_line: str
    closing_line: str
    system_prompt: str
    language_policy: LanguagePolicy
    voice: VoiceConfig
    stt: STTConfig
    responsibilities: list[str] = Field(default_factory=list)
    knowledge: list[Fact] = Field(default_factory=list)
    actions: list[ActionDecl] = Field(default_factory=list)
    synthetic_store: dict[str, object] = Field(default_factory=dict)
    escalation: list[str] = Field(default_factory=list)
    prohibitions: list[str] = Field(default_factory=list)
    limits: SessionLimits = Field(default_factory=SessionLimits)
    provenance: dict[str, Provenance] = Field(default_factory=dict)
    unsupported: list[Unsupported] = Field(default_factory=list)
    open_questions: list[Question] = Field(default_factory=list)
    lint_issues: list[str] = Field(default_factory=list)
    compile_stages: list[dict[str, object]] = Field(default_factory=list)


class GeneratedCopy(BaseModel):
    name: str
    persona: str
    opening_line: str
    closing_line: str
    system_prompt: str


class AgentCreate(BaseModel):
    description: str = Field(min_length=8, max_length=6000)


class TextTurn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list)


class Verdict(BaseModel):
    scenario_id: str
    persona: str = ""
    result: Literal["pass", "fail"]
    reason: str
    evidence_turn: str


class TestReport(BaseModel):
    version_id: str
    verdicts: list[Verdict]
    before_verdicts: list[Verdict] = Field(default_factory=list)
    repairs: list[dict[str, object]] = Field(default_factory=list)
    summary: str
