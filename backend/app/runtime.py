from __future__ import annotations

import json
import re
import time

from backend.app.llm import LLMGateway
from backend.app.models import AgentSpec

ORDER_ID = re.compile(r"\bORD-\d{4}\b", re.IGNORECASE)
PRIVATE_DATA_TERMS = re.compile(r"\b(aadhaar|pan card|otp|password|pin number)\b", re.IGNORECASE)
HANDOFF_TERMS = re.compile(r"\b(human|teammate|manager|representative)\b", re.IGNORECASE)
UNSUPPORTED_TERMS = re.compile(
    r"\b(phone calls?|telephony|outbound calls?|call (?:my )?customers|"
    r"(?:charge|take|process) (?:a )?(?:real )?payments?|real crm|clone (?:my|a) voice)\b",
    re.IGNORECASE,
)


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
    if PRIVATE_DATA_TERMS.search(text):
        if spec.language_policy.primary == "hi-IN":
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
            _refuse_unsupported(spec.language_policy.primary),
            False,
            round(time.perf_counter() - started, 3),
        )
    order_id = ORDER_ID.search(text)
    orders = spec.synthetic_store.get("orders")
    if order_id and isinstance(orders, list):
        order = next(
            (
                item for item in orders
                if isinstance(item, dict)
                and str(item.get("order_id", "")).upper() == order_id.group().upper()
            ),
            None,
        )
        if order:
            if spec.language_policy.primary == "hi-IN":
                status = "delay hua hai" if str(order["status"]).lower() == "delayed" else "pack ho gaya hai"
                eta = "do din mein" if str(order["eta"]).lower() == "in two days" else "kal"
                response = f"Aapka demo order {order['order_id']} {status}. Delivery ka estimate {eta} hai."
            else:
                response = (
                    f"Your demo order {order['order_id']} is {str(order['status']).lower()}. "
                    f"The current delivery estimate is {order['eta']}."
                )
        else:
            response = f"I could not find demo order {order_id.group()}. Please check the order ID."
        return response, False, round(time.perf_counter() - started, 3)

    handoff = bool(HANDOFF_TERMS.search(text)) and any(
        word in text.lower() for word in ("talk", "connect", "speak", "transfer", "human")
    )
    if handoff:
        if spec.language_policy.primary == "hi-IN":
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
