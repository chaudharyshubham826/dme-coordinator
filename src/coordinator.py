from __future__ import annotations

import json
import os
from typing import Any

import httpx
from groq import Groq

from .case import Case
from .phone import call_supplier, call_pcp

# verify=False works around corporate SSL inspection proxies
_client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
    http_client=httpx.Client(verify=False),
)

COORDINATOR_MODEL = os.environ.get("COORDINATOR_MODEL", "qwen/qwen3.6-27b")

# Policy constants — not things the model should decide dynamically
MAX_SUPPLIER_CALLS = 12
MAX_PCP_CALLS = 3

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_case",
            "description": (
                "Get current case details and status. "
                "Check suppliers_tried before calling a supplier to avoid duplicates."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_list",
            "description": "Get the full list of Medicare-enrolled DME suppliers in the Chicago area.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_supplier",
            "description": (
                "Call a DME supplier to check if they can serve Eleanor. "
                "Outcomes: no_answer | voicemail | decline_medicare_full | "
                "decline_no_stock | decline_wrong_area | accept. "
                "Do not call anyone already in suppliers_tried."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": ["supplier_name", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_pcp",
            "description": (
                "Call Dr. Chen's office to request or follow up on the written order. "
                "Outcomes: order_pending | still_pending | pcp_unreachable | order_signed | order_stuck. "
                "Max 3 calls total."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {"type": "string"},
                },
                "required": ["purpose"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_case_note",
            "description": "Add a note to the case audit trail. Document decisions and what you found.",
            "parameters": {
                "type": "object",
                "properties": {"note": {"type": "string"}},
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_patient",
            "description": (
                "Send an update to Eleanor. Plain English, no jargon. "
                "She's 72 and finds this system confusing — keep it warm and clear."
            ),
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_complete",
            "description": (
                "Mark the case complete. Only call when supplier is confirmed AND written order is signed. "
                "Both conditions must be true."
            ),
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Hand off to a human advocate. Use when genuinely stuck — not for temporary setbacks. "
                "Include what was done and exactly what the human needs to do next."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                    "what_was_done": {"type": "string"},
                    "recommended_next_step": {"type": "string"},
                },
                "required": ["reason", "urgency", "what_was_done", "recommended_next_step"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an automated DME case coordinator working Eleanor Martinez's wheelchair case.
No care advocate is in the loop. Work the case yourself and only involve a human when you're genuinely stuck.

CASE:
- Patient: Eleanor Martinez, 72 — Original Medicare Part B (no Medigap)
- Equipment: Standard manual wheelchair, billing code K0001
- PCP: Dr. Sarah Chen | Sunrise Family Medicine | (312) 555-0198
- Status: Verbal order 3 days ago. Written order not signed. No supplier found yet.

WHAT NEEDS TO HAPPEN:
1. Find a supplier who stocks K0001, takes new Medicare Part B patients, and can deliver.
2. Get Dr. Chen's written order signed and faxed to that supplier.
3. When both are done, notify Eleanor and mark the case complete.

Log your reasoning as you go — the audit trail matters if a human picks this up later.

ESCALATE when: all suppliers exhausted, PCP unresponsive after 3 attempts, or anything requiring clinical judgment.
Don't escalate for: one no-answer (move on), order not ready on first call (follow up), single decline (try next).

Patient communication: warm and plain. She's 72, she doesn't know what K0001 means. Tell her what's happening and what she owes (~20% of approved amount, no supplemental coverage).

Always check suppliers_tried before calling a supplier."""


def _line(label: str = "") -> None:
    if label:
        print(f"\n--- {label} ---")
    else:
        print()


def _print_thinking(text: str) -> None:
    _line("🤖 COORDINATOR")
    print(text)


def _print_call(entity: str, phone: str, transcript: str) -> None:
    _line(f"📞 Calling: {entity} | {phone}")
    print(transcript)


def _print_patient_update(message: str) -> None:
    _line("📱 PATIENT UPDATE → Eleanor Martinez")
    print(message)


def _print_escalation(reason: str, urgency: str, done: str, next_step: str) -> None:
    _line("⚠  ESCALATING TO HUMAN ADVOCATE")
    print(f"Urgency    : {urgency.upper()}")
    print(f"Reason     : {reason}")
    print(f"Done so far: {done}")
    print(f"Next step  : {next_step}")


def _print_complete(summary: str) -> None:
    _line("✅ CASE COMPLETE")
    print(summary)


class DMECoordinator:
    def __init__(self, case: Case, suppliers: list[dict]) -> None:
        self.case = case
        self.suppliers = suppliers
        self.messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def run(self) -> None:
        width = 54
        print("\n" + "═" * width)
        print("  DME COORDINATOR — Eleanor Martinez's Case")
        print("═" * width)
        print(f"  Model : {COORDINATOR_MODEL}")
        print(f"  Suppliers in directory: {len(self.suppliers)}")
        print("═" * width)

        self.messages.append({
            "role": "user",
            "content": "/no_think Begin working Eleanor Martinez's case. Work through it until resolved or you need human help.",
        })

        while True:
            response = _client.chat.completions.create(
                model=COORDINATOR_MODEL,
                max_tokens=4096,
                tools=TOOLS,
                messages=self.messages,
            )

            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason

            if message.content:
                _print_thinking(message.content)

            assistant_msg: dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ]
            self.messages.append(assistant_msg)

            if finish_reason == "stop" or not message.tool_calls:
                break

            for tc in message.tool_calls:
                inp = json.loads(tc.function.arguments)
                result = self._dispatch(tc.function.name, inp)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

            if self.case.status in ("completed", "escalated"):
                break

        self._print_summary()

    def _dispatch(self, name: str, inp: dict) -> Any:
        if name == "get_case":
            return self.case.summary()

        if name == "get_supplier_list":
            return self.suppliers

        if name == "call_supplier":
            return self._do_call_supplier(inp["supplier_name"], inp["phone"])

        if name == "call_pcp":
            return self._do_call_pcp(inp["purpose"])

        if name == "log_case_note":
            note = inp["note"]
            self.case.log(note)
            print(f"\n📋 {note}")
            return {"status": "logged"}

        if name == "notify_patient":
            msg = inp["message"]
            self.case.notify_patient(msg)
            _print_patient_update(msg)
            return {"status": "sent"}

        if name == "mark_complete":
            self.case.status = "completed"
            summary = inp["summary"]
            self.case.log(f"COMPLETED: {summary}")
            _print_complete(summary)
            return {"status": "completed"}

        if name == "escalate_to_human":
            self.case.status = "escalated"
            self.case.escalation_reason = inp["reason"]
            self.case.log(f"ESCALATED: {inp['reason']}")
            _print_escalation(
                inp["reason"],
                inp["urgency"],
                inp["what_was_done"],
                inp["recommended_next_step"],
            )
            return {"status": "escalated"}

        return {"error": f"Unknown tool: {name}"}

    def _do_call_supplier(self, supplier_name: str, phone: str) -> dict:
        if len(self.case.suppliers_tried) >= MAX_SUPPLIER_CALLS:
            return {"error": f"All {MAX_SUPPLIER_CALLS} suppliers tried. Escalate if none accepted."}

        if supplier_name in self.case.suppliers_tried:
            return {"info": f"{supplier_name} already called.", "suppliers_tried": self.case.suppliers_tried}

        self.case.suppliers_tried.append(supplier_name)
        self.case.log(f"Called {supplier_name}")

        context = (
            f"Calling for Eleanor Martinez, 72, Original Medicare Part B. "
            f"Needs a standard manual wheelchair (K0001). "
            f"Checking: taking new Medicare patients? Have K0001 in stock? Delivery timeline?"
        )

        result = call_supplier(supplier_name, phone, context)
        _print_call(supplier_name, phone, result["transcript"])

        if result["outcome"] == "accept":
            self.case.supplier_name = supplier_name
            self.case.supplier_phone = phone
            self.case.delivery_eta = result.get("delivery_eta", "3-5 business days")
            self.case.log(f"Supplier confirmed: {supplier_name} — {self.case.delivery_eta}")

        return {
            "outcome": result["outcome"],
            "can_accept": result.get("can_accept", False),
            "delivery_eta": result.get("delivery_eta"),
            "note": result.get("note", ""),
            "suppliers_tried_so_far": len(self.case.suppliers_tried),
            "suppliers_remaining": len(self.suppliers) - len(self.case.suppliers_tried),
        }

    def _do_call_pcp(self, purpose: str) -> dict:
        if self.case.pcp_call_count >= MAX_PCP_CALLS:
            return {"error": f"Hit {MAX_PCP_CALLS} PCP calls. Escalate if order still not signed."}

        self.case.pcp_call_count += 1
        self.case.log(f"PCP call #{self.case.pcp_call_count}: {purpose}")

        context = (
            f"Following up on Eleanor Martinez's K0001 wheelchair order. "
            f"Dr. Chen gave a verbal order 3 days ago — written order not yet signed. "
            f"Purpose: {purpose}."
        )
        if self.case.supplier_name:
            context += f" {self.case.supplier_name} is confirmed and waiting for the faxed order."

        result = call_pcp(self.case.pcp_call_count, context)
        _print_call("Dr. Chen's Office (Sunrise Family Medicine)", self.case.pcp_phone, result["transcript"])

        if result.get("order_now_signed"):
            self.case.order_status = "signed"
            self.case.log("Written order signed by Dr. Chen.")
        elif result["outcome"] in ("still_pending", "order_pending"):
            self.case.order_status = "requested"

        return {
            "outcome": result["outcome"],
            "order_now_signed": result.get("order_now_signed", False),
            "current_order_status": self.case.order_status,
            "pcp_call_number": self.case.pcp_call_count,
            "pcp_calls_remaining": MAX_PCP_CALLS - self.case.pcp_call_count,
        }

    def _print_summary(self) -> None:
        c = self.case
        width = 54
        print("\n" + "═" * width)
        print("  CASE SUMMARY")
        print("═" * width)
        print(f"  Status         : {c.status.upper()}")
        print(f"  Patient        : {c.patient_name}, age {c.patient_age}")
        print(f"  Equipment      : {c.equipment} ({c.billing_code})")
        print(f"  Order Status   : {c.order_status}")
        print(f"  Supplier       : {c.supplier_name or 'None confirmed'}")
        print(f"  Delivery ETA   : {c.delivery_eta or 'N/A'}")
        print(f"  Suppliers tried: {len(c.suppliers_tried)} of {MAX_SUPPLIER_CALLS}")
        print(f"  PCP calls made : {c.pcp_call_count} of {MAX_PCP_CALLS}")
        if c.escalation_reason:
            print(f"  Escalation     : {c.escalation_reason}")
        print("═" * width)

        if c.timeline:
            print("\n  Timeline:")
            for entry in c.timeline:
                print(f"    {entry}")

        if c.patient_messages:
            print("\n  Patient was told:")
            for msg in c.patient_messages:
                print(f"    {msg.split(chr(10))[0][:100]}")
        print()
