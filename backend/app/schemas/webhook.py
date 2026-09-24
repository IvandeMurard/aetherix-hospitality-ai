"""Pydantic v2 schemas for the Twilio Inbound Webhook.

Story 4.3 (HOS-26): Action Logging Accept/Reject via Twilio Inbound Webhook.
Story 5.1 (HOS-28): Parse Conversational Inbound Queries.
Twilio always sends form-encoded data (application/x-www-form-urlencoded).

[Source: https://www.twilio.com/docs/messaging/guides/webhook-request]
"""
from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """Manager decision parsed from the inbound message body by the exact-keyword
    fast path (``manager_decision.match_keyword``, ADR-0007 §16.3).

    - accept    : the whole reply is an explicit FR/EN acceptance ("oui", "validé", "✅")
    - reject    : the whole reply is an explicit refusal ("non", "refusé", "❌")
    - modify    : the whole reply is an explicit correction ("corriger", "✏️")
    - decline   : "non merci", "on garde tel quel" — `rejected` when the
                  recommendation proposes a change, else confirmation (ADR-0007 §17.8)
    - ambiguous : a keyword form with two readings ("pas besoin", "bof") —
                  confirmation is asked, nothing is written until confirmed
    - unknown   : anything else — goes to the free-text path
    """

    accept = "accept"
    reject = "reject"
    modify = "modify"
    decline = "decline"
    ambiguous = "ambiguous"
    unknown = "unknown"


class QueryStatus(str, Enum):
    """Lifecycle states for a ConversationalQuery row.

    - pending    : received, not yet processed by the AI engine
    - processing : background task is actively reasoning about it
    - answered   : AI response dispatched back to the manager
    """

    pending = "pending"
    processing = "processing"
    answered = "answered"


class TwilioInboundPayload(BaseModel):
    """Fields sent by Twilio for every inbound SMS / WhatsApp message.

    Twilio field names use PascalCase; ``From_`` avoids the Python
    built-in keyword clash while preserving the ``From`` alias for
    form-data parsing.
    """

    model_config = ConfigDict(populate_by_name=True)

    # The sender's E.164 phone number (e.g. "+33612345678").
    # WhatsApp numbers are prefixed "whatsapp:+33612345678".
    From_: str = Field(..., alias="From")

    # The raw message text typed by the manager.
    Body: str = Field(default="")

    # The Twilio number that received the message.
    To: str = Field(default="")


class ConversationalQueryCreate(BaseModel):
    """Internal schema used by QueryParserService when persisting a new query row."""

    tenant_id: uuid.UUID
    property_id: uuid.UUID
    from_number: str
    body: str
    recommendation_id: uuid.UUID | None = None
    status: QueryStatus = QueryStatus.pending
