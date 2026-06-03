"""Pydantic v2 schemas for the Notifications API.

All response models use camelCase aliases to align with the frontend
(Next.js) convention established across the project.
[Source: architecture.md#API-Contracts]
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationChannel(str, Enum):
    """Supported outbound notification delivery channels."""

    sms = "sms"
    whatsapp = "whatsapp"
    email = "email"


class TestNotificationRequest(BaseModel):
    """Payload for POST /api/v1/notifications/test."""

    model_config = ConfigDict(populate_by_name=True)

    channel: NotificationChannel = Field(
        ...,
        description="Delivery channel: sms, whatsapp, or email.",
    )
    to: str = Field(
        ...,
        min_length=1,
        description="Destination — phone number (E.164) for SMS/WhatsApp, email address for email.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Text body of the test notification.",
    )


class TestNotificationResponse(BaseModel):
    """Response body for POST /api/v1/notifications/test."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(..., description="Whether the message was dispatched successfully.")
    channel: NotificationChannel = Field(..., description="Channel that was used.")
    sid_or_message_id: Optional[str] = Field(
        None,
        alias="sidOrMessageId",
        description="Twilio SID (SMS/WhatsApp) or empty string (email).",
    )
