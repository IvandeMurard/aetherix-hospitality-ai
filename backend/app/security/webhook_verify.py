"""Reusable HMAC-SHA256 webhook signature verification (HOS-112 AC4).

Designed for Apaleo-style webhooks (X-Apaleo-Signature header) and any
future provider that signs via HMAC-SHA256 over the raw request body.
Twilio uses HMAC-SHA1 with a different payload construction — that logic
stays in app/api/routes/webhook.py (_validate_twilio_signature).
"""
from __future__ import annotations

import hashlib
import hmac


def verify_hmac_sha256(body: bytes, header_signature: str, secret: str) -> bool:
    """Constant-time comparison of HMAC-SHA256.

    Args:
        body: raw request body (bytes, before JSON/form parsing)
        header_signature: hex-encoded signature from the provider header
        secret: shared secret with the webhook provider

    Returns:
        True if signature matches, False otherwise (never raises).

    Note:
        Uses hmac.compare_digest to prevent timing-oracle attacks.
        Empty body is valid (some providers send empty-body pings).
        Empty header_signature or secret always returns False.
    """
    if not header_signature or not secret:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, header_signature)
