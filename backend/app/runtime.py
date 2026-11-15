from __future__ import annotations

import json
import re
import time

from backend.app.llm import LLMGateway
from backend.app.models import AgentSpec

ORDER_ID = re.compile(r"\b(?:ORD|ARD|ओआरडी|ऑर्डर|आर्डर)[\s\-:]*(\d{4})\b", re.IGNORECASE)
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
HINDI_DIGIT_WORDS = {
    "शून्य": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
    "पांच": "5", "पाँच": "5", "छह": "6", "सात": "7", "आठ": "8", "नौ": "9",
}
PRIVATE_DATA_TERMS = re.compile(r"\b(aadhaar|pan card|otp|password|pin number)\b", re.IGNORECASE)
HANDOFF_TERMS = re.compile(r"\b(human|teammate|manager|representative)\b", re.IGNORECASE)
UNSUPPORTED_TERMS = re.compile(
    r"\b(phone calls?|telephony|outbound calls?|call (?:my )?customers|"
    r"(?:charge|take|process) (?:a )?(?:real )?payments?|real crm|clone (?:my|a) voice)\b",
    re.IGNORECASE,
)
HINDI_ROMAN_WORDS = {
    "aap", "aapka", "aapki", "batao", "bataiye", "chahiye", "hai", "hain",
    "kab", "karo", "karein", "kripya", "madad", "mera", "mere", "mujhe",
    "nahi", "namaste", "sahayata",
}


def _normalize_digits(text: str) -> str:
    text = text.translate(DEVANAGARI_DIGITS)
    for word, digit in HINDI_DIGIT_WORDS.items():
        text = text.replace(word, digit)
    return re.sub(r"(?<=\d) (?=\d)", "", text)


def _find_order_id(text: str) -> str | None:
    match = ORDER_ID.search(_normalize_digits(text))
    if match:
        return f"ORD-{match.group(1)}"
    return None


def _caller_language(text: str, spec: AgentSpec) -> str:
    allowed = spec.language_policy.allowed
    if re.search(r"[\u0900-\u097f]", text):
        return "hi-IN" if "hi-IN" in allowed else spec.language_policy.primary
    if re.search(r"[A-Za-z]", text):
        words = set(re.findall(r"[a-z]+", text.lower()))
        if words & HINDI_ROMAN_WORDS:
            return "hi-IN" if "hi-IN" in allowed else spec.language_policy.primary
        for candidate in ("en-IN", "hi-en"):
            if candidate in allowed:
                return candidate
    return spec.language_policy.primary


def _refuse_unsupported(primary: str) -> str:
    if primary == "hi-IN":
        return (
            "Maaf kijiye, ye demo browser par voice aur chat hi support karta hai. "
            "Phone calls, real payments aur CRM connect nahi ho sakte. "
            "Main aapke order ya return policy mein madad kar sakta hoon."
        )
    return (
        "This demo only supports voice and chat in the browser. "
        "It cannot place phone calls, take real payments, or connect to a live CRM. "
        "I can still help with orders and returns."
    )


def build_system_prompt(spec: AgentSpec) -> str:
    sections = [
        spec.system_prompt.strip(),
        (
            "You are speaking on a live voice call. Reply with natural spoken words only. "
            "Keep every reply to one or two short sentences. "
            "Never output JSON, markdown, bullet points, URLs, emojis, or meta-commentary."
        ),
        f"Languages: {', '.join(spec.language_policy.allowed)}. {spec.language_policy.switch_rule}",
    ]
    if spec.responsibilities:
        sections.append("Responsibilities:\n" + "\n".join(f"- {item}" for item in spec.responsibilities))
    if spec.knowledge:
        facts = []
        for fact in spec.knowledge:
            question = "; ".join(fact.question_variants) if fact.question_variants else "General"
            facts.append(f"- Asked about: {question}\n  Answer: {fact.answer}")
        sections.append("Approved business facts (never invent beyond these):\n" + "\n".join(facts))
    if spec.escalation:
        sections.append("Escalate when needed:\n" + "\n".join(f"- {item}" for item in spec.escalation))
    if spec.prohibitions:
        sections.append("Never do this:\n" + "\n".join(f"- {item}" for item in spec.prohibitions))
    return "\n\n".join(section for section in sections if section)


async def respond(
    spec: AgentSpec,
    text: str,
    history: list[dict[str, str]],
    llm: LLMGateway,
) -> tuple[str, bool, float]:
    started = time.perf_counter()
    language = _caller_language(text, spec)
    if PRIVATE_DATA_TERMS.search(text):
        if language == "hi-IN":
            return (
                "Kripya private ya payment details share na karein. Main general sawalon mein madad kar sakta hoon.",
                False,
                round(time.perf_counter() - started, 3),
            )
        return (
            "Please do not share private or payment details. I can still help with general questions.",
            False,
            round(time.perf_counter() - started, 3),
        )
    if UNSUPPORTED_TERMS.search(text):
        return (
            _refuse_unsupported(language),
            False,
            round(time.perf_counter() - started, 3),
        )
    order_id = _find_order_id(text)
    orders = spec.synthetic_store.get("orders")
    if order_id and isinstance(orders, list):
        order = next(
            (
                item for item in orders
                if isinstance(item, dict)
                and str(item.get("order_id", "")).upper() == order_id.upper()
            ),
            None,
        )
        if order:
            if language == "hi-IN":
                status = "delay hua hai" if str(order["status"]).lower() == "delayed" else "pack ho gaya hai"
                eta = "do din mein" if str(order["eta"]).lower() == "in two days" else "kal"
                response = f"Aapka demo order {order['order_id']} {status}. Delivery ka estimate {eta} hai."
            else:
                response = (
                    f"Your demo order {order['order_id']} is {str(order['status']).lower()}. "
                    f"The current delivery estimate is {order['eta']}."
                )
        else:
            response = f"I could not find demo order {order_id}. Please check the order ID."
        return response, False, round(time.perf_counter() - started, 3)

    handoff = bool(HANDOFF_TERMS.search(text)) and any(
        word in text.lower() for word in ("talk", "connect", "speak", "transfer", "human")
    )
    if handoff:
        if language == "hi-IN":
            return (
                "Main is baat ko aage madad ke liye ek human teammate ko de raha hoon.",
                True,
                round(time.perf_counter() - started, 3),
            )
        return (
            "I will hand this conversation to a human teammate for further help.",
            True,
            round(time.perf_counter() - started, 3),
        )

    transcript = [
        f"{item['role']}: {str(item.get('content', ''))[:1000]}"
        for item in history[-12:]
        if item.get("role") in {"user", "assistant"}
    ]
    transcript.append(f"caller: {text}")
    reply = await llm.text(
        system=build_system_prompt(spec),
        user=(
            f"Agent name: {spec.name}\n"
            "Use only this synthetic demo store data when an order is referenced: "
            f"{json.dumps(spec.synthetic_store, ensure_ascii=False)}\n\n"
            f"Conversation:\n{chr(10).join(transcript)}"
        ),
    )
    return reply, False, round(time.perf_counter() - started, 3)

