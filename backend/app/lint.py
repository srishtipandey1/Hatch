from __future__ import annotations

import re
import unicodedata

from backend.app.models import AgentSpec

ALLOWED_TAGS = {"pauses", "sigh"}


def lint_text(
    text: str,
    language: str = "en-IN",
    language_tagged: bool = False,
    max_sentence_words: int | None = 25,
) -> list[str]:
    issues: list[str] = []
    if re.search(r"[#*•]", text):
        issues.append("Avoid markdown headings, emphasis, and bullet characters.")
    if re.search(r"https?://|www\.", text, flags=re.IGNORECASE):
        issues.append("Avoid URLs in spoken replies.")
    if any(unicodedata.category(char) == "So" for char in text):
        issues.append("Remove emoji and decorative symbols.")
    for tag in re.findall(r"<([^>]+)>", text):
        if tag.lower() not in ALLOWED_TAGS:
            issues.append(f"Audio tag <{tag}> is not allowed for this voice policy.")
    if max_sentence_words is not None:
        for sentence in re.split(r"(?<=[.!?।])\s+", text.strip()):
            if len(sentence.split()) > max_sentence_words:
                issues.append(f"Keep each spoken sentence to {max_sentence_words} words or fewer.")
                break
    for word in re.findall(r"\b[A-Z]{3,}\b", text):
        if word not in {"FAQ", "OTP", "ID", "URL", "API", "STT", "TTS"}:
            issues.append(f"Avoid all-caps word {word}.")
            break
    if language not in {"en-IN", "hi-en"} and not language_tagged and text and not re.search(r"[\u0900-\u0d7f]", text):
        issues.append("Use native-script text or an explicit language tag for this non-English reply.")
    return issues


def lint_spec(spec: AgentSpec) -> list[str]:
    tagged = bool(spec.voice.language)
    issues = lint_text(spec.opening_line, spec.language_policy.primary, tagged)
    issues.extend(lint_text(spec.closing_line, spec.language_policy.primary, tagged))
    issues.extend(
        lint_text(
            spec.system_prompt,
            spec.language_policy.primary,
            tagged,
            max_sentence_words=None,
        )
    )
    unique = list(dict.fromkeys(issues))
    return unique
