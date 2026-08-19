"""
Phone call simulation.

Outcome assignment: random.choices() — NO AI.
Dialogue: LLM only for accept/order_signed (the interesting cases).
          Everything else is pre-scripted with variety — no API call needed.
          This keeps the demo fast: ~2 LLM calls total instead of 15+.
"""

from __future__ import annotations

import os
import random

import httpx
from groq import Groq

_client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
    http_client=httpx.Client(verify=False),
)
PHONE_MODEL = os.environ.get("PHONE_MODEL", "qwen/qwen3.6-27b")

# ---------------------------------------------------------------------------
# Supplier outcome distribution
# Accept rate 13% — coordination is hard. ~20% of runs exhaust all 12.
# ---------------------------------------------------------------------------
_SUPPLIER_OUTCOMES = [
    "no_answer",
    "voicemail",
    "decline_medicare_full",
    "decline_no_stock",
    "decline_wrong_area",
    "accept",
]
_SUPPLIER_WEIGHTS = [0.22, 0.15, 0.28, 0.10, 0.12, 0.13]

_VOICEMAILS = [
    "You've reached {name}. Our office is currently closed or assisting other customers. "
    "Please leave your name and number and we'll return your call.",
    "Thanks for calling {name}. We're unable to take your call right now. "
    "Leave a message and someone will get back to you shortly.",
    "You've reached the voicemail of {name}. "
    "Please leave a detailed message and we'll call you back as soon as possible.",
]

_DECLINE_SCRIPTS = {
    "decline_medicare_full": [
        "Rep: {name}, how can I help?\nCoordinator: Hi, calling about a Medicare Part B patient needing a K0001 wheelchair.\n"
        "Rep: I appreciate you reaching out, but we're not accepting new Medicare Part B patients right now — our census is full. Sorry about that.",
        "Rep: {name}, this is Sarah.\nCoordinator: Hi Sarah, calling about a Medicare patient needing a standard wheelchair.\n"
        "Rep: Oh, unfortunately we've had to pause new Medicare enrollments. Our billing team is just backed up. Try us again next quarter.",
    ],
    "decline_no_stock": [
        "Rep: {name}, go ahead.\nCoordinator: Hi, do you carry K0001 standard manual wheelchairs for a Medicare Part B patient?\n"
        "Rep: We do normally, but we're completely out of K0001s right now — backorder issue with our supplier. Probably 6 weeks out.",
        "Rep: {name}, can I help you?\nCoordinator: Yes, I'm looking for a K0001 standard wheelchair for a Medicare patient.\n"
        "Rep: We specialize in power chairs, not manual. You'll need to try someone else for that.",
    ],
    "decline_wrong_area": [
        "Rep: {name}.\nCoordinator: Hi, calling about delivering a wheelchair to a patient in Chicago.\n"
        "Rep: What's the zip code? ... Yeah, that's outside our service area, sorry. We don't cover that part of the city.",
        "Rep: {name}, how can I help?\nCoordinator: I need wheelchair delivery for a patient on the north side of Chicago.\n"
        "Rep: We're primarily suburban — Cook County outside the city. That address would be a bit too far for us.",
    ],
}

# PCP outcome distributions
_PCP_CALL2_OUTCOMES = ["order_signed", "still_pending", "pcp_unreachable"]
_PCP_CALL2_WEIGHTS = [0.65, 0.30, 0.05]

_PCP_CALL3_OUTCOMES = ["order_signed", "order_stuck"]
_PCP_CALL3_WEIGHTS = [0.65, 0.35]

_PCP_PENDING_SCRIPTS = [
    "Receptionist: Sunrise Family Medicine.\nCoordinator: Hi, calling about a written order for Eleanor Martinez's wheelchair.\n"
    "Receptionist: Let me check... Dr. Chen hasn't signed it yet — she's been slammed with patients today. I'll leave her a note to make it a priority.",
    "Receptionist: Dr. Chen's office.\nCoordinator: Following up on a K0001 wheelchair order for Eleanor Martinez.\n"
    "Receptionist: I see it here, it's waiting for the doctor's signature. She's in with patients all afternoon. I'll flag it urgent for her.",
]

_PCP_STILL_PENDING_SCRIPTS = [
    "Receptionist: Sunrise Family Medicine.\nCoordinator: Hi again, following up on Eleanor Martinez's wheelchair order — has Dr. Chen signed it?\n"
    "Receptionist: I'm so sorry, it's still on her desk. I promise it'll get done today — she has a gap between appointments this afternoon.",
    "Receptionist: Dr. Chen's office.\nCoordinator: Checking on the written order for Eleanor Martinez, K0001 wheelchair.\n"
    "Receptionist: Yeah, I see it — not signed yet. She's been really backed up. I'll put a sticky on her monitor. Should be done by end of day.",
]

_PCP_STUCK_SCRIPTS = [
    "Receptionist: Sunrise Family Medicine.\nCoordinator: Following up again on Eleanor Martinez's wheelchair order.\n"
    "Receptionist: Dr. Chen has some questions about it before she signs — she wants to review the chart more carefully. I really can't give you a timeline. Maybe try again tomorrow?",
    "Receptionist: Dr. Chen's office.\nCoordinator: Third follow-up on Eleanor Martinez's K0001 order — any update?\n"
    "Receptionist: The doctor still hasn't cleared it. She mentioned wanting more information. I'd suggest calling back tomorrow morning.",
]


def _llm(system: str, user: str) -> str:
    """LLM call — only used for accept and order_signed dialogue."""
    resp = _client.chat.completions.create(
        model=PHONE_MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"/no_think {user}"},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _supplier_dialogue(supplier_name: str, outcome: str, context: str) -> str:
    if outcome == "no_answer":
        return "[RING] [RING] [RING] [RING] [RING] — No answer."

    if outcome == "voicemail":
        template = random.choice(_VOICEMAILS)
        return f"[Voicemail] {template.format(name=supplier_name)}"

    if outcome in _DECLINE_SCRIPTS:
        template = random.choice(_DECLINE_SCRIPTS[outcome])
        return template.format(name=supplier_name)

    # accept — worth an LLM call, this is the interesting case
    return _llm(
        system=(
            f"You are a helpful DME specialist at {supplier_name}. "
            "A coordinator calls about a Medicare Part B patient needing a K0001 standard manual wheelchair. "
            "You CAN help: you have K0001 in stock, accept new Medicare Part B patients, "
            "can deliver in 3-5 business days once you receive the signed physician order. "
            "Provide a realistic Chicago-area fax number for receiving the order. "
            "Be friendly and efficient. Under 120 words. Use speaker labels."
        ),
        user=f"Context: {context}",
    )


def _pcp_dialogue(call_number: int, outcome: str, context: str) -> str:
    if outcome == "pcp_unreachable":
        return "[RING] [RING] [RING] [RING] [RING] — No answer. No voicemail picks up."

    if outcome == "order_pending":
        return random.choice(_PCP_PENDING_SCRIPTS)

    if outcome == "still_pending":
        return random.choice(_PCP_STILL_PENDING_SCRIPTS)

    if outcome == "order_stuck":
        return random.choice(_PCP_STUCK_SCRIPTS)

    # order_signed — worth an LLM call, this is a win
    return _llm(
        system=(
            "You are a front desk receptionist at Sunrise Family Medicine. "
            "Dr. Chen has signed the written wheelchair order for Eleanor Martinez. "
            "Confirm it's signed, confirm the billing code is K0001, and offer to fax it to the supplier. "
            "Sound relieved and helpful. Under 100 words. Use speaker labels."
        ),
        user=f"Context: {context}",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_supplier(supplier_name: str, phone: str, context: str) -> dict:
    outcome = random.choices(_SUPPLIER_OUTCOMES, weights=_SUPPLIER_WEIGHTS, k=1)[0]
    transcript = _supplier_dialogue(supplier_name, outcome, context)

    result: dict = {
        "outcome": outcome,
        "transcript": transcript,
        "can_accept": outcome == "accept",
    }
    if outcome == "accept":
        result["delivery_eta"] = "3-5 business days"
        result["note"] = "Fax number in transcript. Supplier needs signed order before scheduling."

    return result


def call_pcp(call_number: int, context: str) -> dict:
    if call_number == 1:
        outcome = "order_pending"
    elif call_number == 2:
        outcome = random.choices(_PCP_CALL2_OUTCOMES, weights=_PCP_CALL2_WEIGHTS, k=1)[0]
    else:
        outcome = random.choices(_PCP_CALL3_OUTCOMES, weights=_PCP_CALL3_WEIGHTS, k=1)[0]

    transcript = _pcp_dialogue(call_number, outcome, context)

    return {
        "outcome": outcome,
        "transcript": transcript,
        "order_now_signed": outcome == "order_signed",
    }
