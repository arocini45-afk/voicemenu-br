"""
In-memory session store for active calls.
For production, replace with Redis.
"""
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime


class CallState(str, Enum):
    GREETING = "greeting"
    DETECTING_LANGUAGE = "detecting_language"
    TAKING_ORDER = "taking_order"
    UPSELL = "upsell"
    CONFIRMING_ORDER = "confirming_order"
    PAYMENT_SENT = "payment_sent"
    PAYMENT_CONFIRMED = "payment_confirmed"
    DONE = "done"


class OrderItem:
    def __init__(self, item_id: str, name: str, quantity: int, unit_price: float):
        self.item_id = item_id
        self.name = name
        self.quantity = quantity
        self.unit_price = unit_price

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total,
        }


class CallSession:
    def __init__(self, call_sid: str, from_number: str):
        self.call_sid = call_sid
        self.from_number = from_number  # Customer phone number
        self.order_id = str(uuid.uuid4())[:8].upper()
        self.state = CallState.GREETING
        self.language = "pt"  # default, detected from first speech
        self.conversation_history: list[dict] = []
        self.order_items: list[OrderItem] = []
        self.payment_link: Optional[str] = None
        self.payment_intent_id: Optional[str] = None
        self.payment_confirmed = False
        self.created_at = datetime.now()
        self.customer_name: Optional[str] = None

    @property
    def order_total(self) -> float:
        return sum(item.total for item in self.order_items)

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def get_order_summary(self) -> str:
        if not self.order_items:
            return "Nenhum item no pedido." if self.language == "pt" else "No items in order."
        lines = []
        for item in self.order_items:
            lines.append(f"  • {item.quantity}x {item.name} — R$ {item.total:.2f}")
        lines.append(f"\n  Total: R$ {self.order_total:.2f}")
        return "\n".join(lines)


# Global in-memory store: call_sid -> CallSession
_sessions: dict[str, CallSession] = {}


def create_session(call_sid: str, from_number: str) -> CallSession:
    session = CallSession(call_sid, from_number)
    _sessions[call_sid] = session
    return session


def get_session(call_sid: str) -> Optional[CallSession]:
    return _sessions.get(call_sid)


def delete_session(call_sid: str):
    _sessions.pop(call_sid, None)


def get_session_by_payment_intent(payment_intent_id: str) -> Optional[CallSession]:
    for session in _sessions.values():
        if session.payment_intent_id == payment_intent_id:
            return session
    return None
