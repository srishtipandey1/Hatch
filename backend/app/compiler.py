from __future__ import annotations

import uuid
import re
import time

from backend.app.llm import LLMGateway
from backend.app.lint import lint_spec
from backend.app.models import (
    ActionDecl,
    AgentSpec,
    GeneratedCopy,
    LanguagePolicy,
    Provenance,
    Question,
    RequirementSet,
    STTConfig,
    SessionLimits,
    Unsupported,
    VoiceConfig,
)

LANGUAGE_CODES = {
    "hi": "hi-IN", "hindi": "hi-IN",
    "en": "en-IN", "english": "en-IN",
    "ta": "ta-IN", "tamil": "ta-IN",
    "te": "te-IN", "telugu": "te-IN",
    "kn": "kn-IN", "kannada": "kn-IN",
    "ml": "ml-IN", "malayalam": "ml-IN",
    "mr": "mr-IN", "marathi": "mr-IN",
    "pa": "pa-IN", "punjabi": "pa-IN",
    "bn": "bn-IN", "bengali": "bn-IN",
    "gu": "gu-IN", "gujarati": "gu-IN",
    "hi-en": "hi-en",
}
SUPPORTED_LANGUAGES = set(LANGUAGE_CODES.values())
HINDI_ROMAN_WORDS = {
    "aap", "aapki", "accha", "banao", "bhi", "chahiye", "dukaan", "hai", "kaise",
    "kar", "kare", "karo", "ki", "liye", "main", "madad", "mere", "mujhe", "namaste",
    "par", "polite", "rahe", "sahayata", "wali", "wale",
}
ENGLISH_AGENT_WORDS = {
    "agent", "assistant", "customer", "support", "orders", "returns", "booking",
    "service", "help", "human", "team",
}


def detect_hinglish(description: str) -> bool:
    words = set(re.findall(r"[a-z]+", description.lower()))
    explicit = "hinglish" in description.lower() or "code-mix" in description.lower()
    return explicit or bool(words & HINDI_ROMAN_WORDS and words & ENGLISH_AGENT_WORDS)


def requested_unsupported(description: str) -> list[Unsupported]:
    candidates = [
        (
            re.compile(
                r"\b(?:phone calls?|telephony|outbound calls?|call (?:my )?customers on (?:their )?phones?)\b",
                re.IGNORECASE,
            ),
            "Phone and outbound calls are not available in Hatch.",
            "Use the browser voice runtime for an inbound demo conversation.",
        ),
        (
            re.compile(
                r"\b(?:real crm|connect to (?:my )?crm|crm integration|"
                r"(?:process|take|charge) (?:real )?payments?)\b",
                re.IGNORECASE,
            ),
            "Live CRM and payment integrations are not available.",
            "Use the declared synthetic demo store; do not process real payments.",
        ),
        (
            re.compile(r"\b(clone my voice|voice cloning|clone a voice)\b", re.IGNORECASE),
            "Voice cloning is outside this demo's supported scope.",
            "Choose a stock Timbre voice.",
        ),
    ]
    unsupported = []
    for pattern, reason, alternative in candidates:
        match = pattern.search(description)
        if match and not re.search(
            r"\b(?:no|not|never|don't|do not|avoid|without)\W*$",
            description[max(0, match.start() - 20):match.start()],
            re.IGNORECASE,
        ):
            unsupported.append(Unsupported(
                request=match.group(0),
                reason=reason,
                alternative=alternative,
            ))
    return unsupported


def _normalize_language(value: str) -> str | None:
    key = value.strip().lower().replace("_", "-")
    if key in LANGUAGE_CODES:
        return LANGUAGE_CODES[key]
    if key.endswith("-in"):
        return LANGUAGE_CODES.get(key.split("-", 1)[0])
    return None


def _defaulted(reason: str) -> Provenance:
    return Provenance(source="defaulted", evidence=reason)


def _shares_meaningful_word(left: str, right: str) -> bool:
    left_words = {word for word in re.findall(r"[a-z]{4,}", left.lower())}
    right_words = {word for word in re.findall(r"[a-z]{4,}", right.lower())}
    return bool(left_words & right_words)


def _mark_stated_from_description(requirements: RequirementSet, description: str) -> None:
    lower = description.lower()

    def mark(field: str, condition: bool, evidence: str | None = None) -> None:
        if condition:
            requirements.provenance[field] = Provenance(
                source="stated",
                evidence=(evidence or description)[:180],
            )

    mark(
        "business_context",
        bool(requirements.business_context.strip())
        and _shares_meaningful_word(requirements.business_context, description),
    )
    mark(
        "agent_goal",
        bool(requirements.agent_goal.strip())
        and _shares_meaningful_word(requirements.agent_goal, description),
    )
    mark(
        "tone",
        bool(requirements.tone.strip())
        and any(
            word in lower
            for word in ("polite", "friendly", "warm", "professional", "calm", "empathetic", "formal")
        ),
    )
    mark(
        "responsibilities",
        bool(requirements.responsibilities)
        and any(_shares_meaningful_word(item, description) for item in requirements.responsibilities),
    )
    mark(
        "escalation",
        bool(requirements.escalation)
        and any(word in lower for word in ("human", "team", "escalate", "manager", "representative")),
    )
    mark(
        "prohibitions",
        bool(requirements.prohibitions)
        and any(
            word in lower
            for word in ("never", "do not", "don't", "privacy", "confidential", "not share")
        ),
    )
    mark(
        "languages",
        bool(requirements.languages)
        and any(
            name in lower
            for name in (
                "hindi", "english", "tamil", "telugu", "kannada", "malayalam",
                "marathi", "punjabi", "bengali", "gujarati", "hinglish",
            )
        ),
    )
    mark("code_mix_expected", detect_hinglish(description))


def _normalize_agent_name(name: str) -> str:
    normalized = re.sub(r"\b(support)(?:\s+\1)+\b", r"\1", name.strip(), flags=re.IGNORECASE)
    return normalized[:80] or "Hatch assistant"


def _questions(requirements: RequirementSet) -> list[Question]:
    questions: list[Question] = []
    if "languages" not in requirements.provenance:
        questions.append(Question(
            field="languages",
            question="Which language should the agent use?",
            default="Hindi and English",
        ))
    if not requirements.escalation:
        questions.append(Question(
            field="escalation",
            question="Who should receive difficult cases?",
            default="A human support teammate",
        ))
    if not requirements.knowledge:
        questions.append(Question(
            field="knowledge",
            question="Which business facts should the agent know?",
            default="Only use facts supplied in the conversation; do not invent policies.",
        ))
    return questions[:3]


def negotiate(requirements: RequirementSet) -> tuple[LanguagePolicy, VoiceConfig, STTConfig, list[Unsupported]]:
    unsupported: list[Unsupported] = []
    selected: list[str] = []
    for language in requirements.languages:
        normalized = _normalize_language(language)
        if normalized:
            if normalized not in selected:
                selected.append(normalized)
        else:
            unsupported.append(Unsupported(
                request=language,
                reason=f"{language} is not in the supported language catalog.",
                alternative="Bengali (`bn-IN`) is supported; use it only if it meets your needs.",
            ))
    if not selected:
        selected = ["hi-IN", "en-IN"]
    primary = selected[0]
    tone = requirements.tone.lower()
    if any(word in tone for word in ("sales", "energetic", "outbound")):
        voice = "Riyaa"
    elif any(word in tone for word in ("firm", "professional", "formal")):
        voice = "Avinash"
    elif any(word in tone for word in ("tutor", "narrat", "teacher", "learning")):
        voice = "Lakshmi"
    else:
        voice = "Shivani"
    voices = {language: voice for language in selected}
    language_policy = LanguagePolicy(
        primary=primary,
        allowed=selected,
        switch_rule="Follow the caller's language; use simple wording and confirm when unclear.",
        per_language_voice=voices,
    )
    voice_config = VoiceConfig(model="timbre-v3.0", voice=voice, language=primary)
    stt_config = STTConfig(
        model="prisma-v3.0",
        language_code="indic-auto",
        format="codemix" if requirements.code_mix_expected or "hi-en" in selected else "transcribe",
    )
    return language_policy, voice_config, stt_config, unsupported


async def compile_agent(description: str, llm: LLMGateway) -> AgentSpec:
    stages: list[dict[str, object]] = []

    def stage(name: str, started: float) -> None:
        stages.append({"name": name, "ms": round((time.perf_counter() - started) * 1000, 1)})

    extraction_system = (
        "You extract a safe voice-agent brief. Use only facts stated by the user. "
        "Do not invent policies, prices, hours, phone numbers, or private data. "
        "For provenance, mark direct requirements stated and reasonable design choices inferred; "
        "include short evidence from the user's text for stated fields. If uncertain, leave lists empty."
    )
    extraction_user = (
        "Extract an agent brief from the description below. Return JSON matching the requested schema. "
        "Use canonical Indian language names or BCP-47 codes when recognizable. "
        "The provenance object should map field names to {source,evidence}.\n\n"
        f"Description:\n{description}"
    )
    _stage_started = time.perf_counter()
    requirements = await llm.structured(
        system=extraction_system,
        user=extraction_user,
        schema=RequirementSet,
    )
    stage("Extract requirements", _stage_started)
    if detect_hinglish(description):
        requested_languages = [
            language for language in requirements.languages
            if language.strip().lower() not in {"hinglish", "code-mix", "code mix"}
        ]
        requirements.languages = list(dict.fromkeys([*requested_languages, "hi-IN", "en-IN"]))
        requirements.code_mix_expected = True
        evidence = "Hinglish wording detected in the user's description."
        requirements.provenance["languages"] = Provenance(source="inferred", evidence=evidence)
        requirements.provenance["code_mix_expected"] = Provenance(source="inferred", evidence=evidence)
    questions = _questions(requirements)
    if not requirements.languages:
        requirements.languages = ["hi-IN", "en-IN"]
        requirements.provenance["languages"] = _defaulted("Hindi and English are the demo defaults.")
    if not requirements.tone.strip():
        requirements.tone = "Warm, clear, and professional"
        requirements.provenance["tone"] = _defaulted("A warm support tone is the safe default.")
    if not requirements.agent_goal.strip():
        requirements.agent_goal = "Help callers with the stated responsibilities."
        requirements.provenance["agent_goal"] = _defaulted("Derived from the listed responsibilities.")
    _mark_stated_from_description(requirements, description)
    for field in (
        "business_context", "agent_goal", "languages", "code_mix_expected", "tone",
        "responsibilities", "knowledge", "escalation", "prohibitions",
    ):
        requirements.provenance.setdefault(
            field,
            _defaulted("No explicit source was identified; retained a conservative default."),
        )

    _stage_started = time.perf_counter()
    language_policy, voice, stt, unsupported = negotiate(requirements)
    unsupported.extend(requested_unsupported(description))
    stage("Negotiate capabilities", _stage_started)
    _stage_started = time.perf_counter()
    copy = await llm.structured(
        system=(
            "You write concise, spoken voice-agent copy. Avoid markdown, URLs, emojis, "
            "unsupported promises, invented business facts, and long sentences."
        ),
        user=(
            "Create name, persona, opening_line, closing_line, and a concise system_prompt. "
            "The prompt must follow the supplied responsibilities, escalation and prohibitions; "
            "never invent knowledge. Return only schema-conforming JSON.\n\n"
            f"Agent brief:\n{requirements.model_dump_json()}\n\n"
            f"Negotiated language policy:\n{language_policy.model_dump_json()}"
        ),
        schema=GeneratedCopy,
    )
    stage("Write agent copy", _stage_started)

    provenance = dict(requirements.provenance)
    for path in ("agent_id", "version", "synthetic_store", "limits", "open_questions"):
        provenance.setdefault(path, _defaulted("Generated or selected by the Hatch compiler."))
    for path in (
        "name", "persona", "opening_line", "closing_line", "system_prompt",
        "language_policy", "voice", "stt", "actions", "lint_issues",
    ):
        provenance.setdefault(
            path,
            Provenance(source="inferred", evidence="Generated or selected from the extracted requirements."),
        )
    provenance.setdefault(
        "unsupported",
        Provenance(
            source="stated" if unsupported else "inferred",
            evidence=description[:180] if unsupported else "No unsupported requests were detected.",
        ),
    )
    actions: list[ActionDecl] = []
    if any("order" in item.lower() for item in requirements.responsibilities):
        actions.append(ActionDecl(
            name="lookup_synthetic_order",
            description="Look up a demo order in the synthetic store.",
            params=["order_id"],
            returns="Synthetic order status and delivery estimate",
        ))
    for index, fact in enumerate(requirements.knowledge):
        stated = fact.answer.strip().lower() in description.lower() if fact.answer.strip() else False
        provenance.setdefault(
            f"knowledge.{index}",
            Provenance(
                source="stated" if stated else "inferred",
                evidence=(
                    description[:180] if stated
                    else "Extracted as a possible fact; verify it before treating it as policy."
                ),
            ),
        )
    for index, _action in enumerate(actions):
        provenance.setdefault(
            f"actions.{index}",
            Provenance(source="inferred", evidence="A synthetic action was derived from a stated responsibility."),
        )
    for index, _unsupported in enumerate(unsupported):
        provenance.setdefault(
            f"unsupported.{index}",
            Provenance(source="stated", evidence=description[:180]),
        )
    agent_name = _normalize_agent_name(copy.name)
    if (
        voice.voice.casefold() in agent_name.casefold()
        or agent_name.casefold() in {"support agent", "agent", "assistant"}
    ):
        agent_name = requirements.business_context[:55].strip().title() or "Hatch Support"
        if "support" not in agent_name.casefold():
            agent_name = f"{agent_name} Support".strip()
    spec = AgentSpec(
        agent_id=str(uuid.uuid4()),
        name=agent_name,
        business_context=requirements.business_context,
        agent_goal=requirements.agent_goal,
        persona=copy.persona.strip(),
        opening_line=copy.opening_line.strip(),
        closing_line=copy.closing_line.strip(),
        system_prompt=copy.system_prompt.strip(),
        language_policy=language_policy,
        voice=voice,
        stt=stt,
        responsibilities=requirements.responsibilities,
        knowledge=requirements.knowledge,
        actions=actions,
        synthetic_store={
            "orders": [
                {"order_id": "ORD-1001", "status": "Packed", "eta": "tomorrow"},
                {"order_id": "ORD-1004", "status": "Delayed", "eta": "in two days"},
            ]
        },
        escalation=requirements.escalation or ["Offer a human teammate for unresolved or sensitive cases."],
        prohibitions=requirements.prohibitions or ["Do not ask for or reveal real personal or financial data."],
        limits=SessionLimits(),
        provenance=provenance,
        unsupported=unsupported,
        open_questions=questions,
    )
    _stage_started = time.perf_counter()
    spec.lint_issues = lint_spec(spec)
    stage("Voice-readiness lint", _stage_started)
    spec.compile_stages = list(stages)
    return spec
