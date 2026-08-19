from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Case:
    patient_name: str = "Eleanor Martinez"
    patient_age: int = 72
    insurance: str = "Original Medicare Part B"

    equipment: str = "Standard manual wheelchair"
    billing_code: str = "K0001"

    pcp_name: str = "Dr. Sarah Chen"
    pcp_practice: str = "Sunrise Family Medicine"
    pcp_phone: str = "(312) 555-0198"
    pcp_call_count: int = 0

    order_status: str = "verbal"  # verbal | requested | signed

    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None
    supplier_fax: Optional[str] = None
    delivery_eta: Optional[str] = None

    status: str = "active"  # active | completed | escalated
    escalation_reason: Optional[str] = None

    # This timeline is the handoff document if a human takes over mid-case
    timeline: list = field(default_factory=list)
    patient_messages: list = field(default_factory=list)
    suppliers_tried: list = field(default_factory=list)

    def log(self, event: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.timeline.append(f"[{ts}] {event}")

    def notify_patient(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.patient_messages.append(f"[{ts}] {message}")

    def summary(self) -> dict:
        return {
            "patient_name": self.patient_name,
            "patient_age": self.patient_age,
            "insurance": self.insurance,
            "equipment": self.equipment,
            "billing_code": self.billing_code,
            "pcp_name": self.pcp_name,
            "pcp_practice": self.pcp_practice,
            "pcp_phone": self.pcp_phone,
            "order_status": self.order_status,
            "supplier_name": self.supplier_name,
            "supplier_phone": self.supplier_phone,
            "supplier_fax": self.supplier_fax,
            "delivery_eta": self.delivery_eta,
            "case_status": self.status,
            "suppliers_tried": self.suppliers_tried,
            "suppliers_tried_count": len(self.suppliers_tried),
            "pcp_calls_made": self.pcp_call_count,
        }


def make_eleanor_case() -> Case:
    return Case()
