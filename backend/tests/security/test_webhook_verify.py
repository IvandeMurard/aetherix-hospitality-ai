"""Unit tests for verify_hmac_sha256 helper (HOS-112 AC4).

Tests are hermetic: no I/O, no DB, no env vars.
"""
from __future__ import annotations

import hashlib
import hmac

from app.security.webhook_verify import verify_hmac_sha256

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Valid signature
# ---------------------------------------------------------------------------

class TestValidSignature:
    def test_matching_signature_returns_true(self):
        body = b'{"event": "reservation.created"}'
        secret = "my-webhook-secret"
        sig = _make_valid_signature(body, secret)
        assert verify_hmac_sha256(body, sig, secret) is True

    def test_empty_body_matching_signature_returns_true(self):
        body = b""
        secret = "ping-secret"
        sig = _make_valid_signature(body, secret)
        assert verify_hmac_sha256(body, sig, secret) is True

    def test_binary_body_matching_signature_returns_true(self):
        body = bytes(range(256))
        secret = "binary-secret"
        sig = _make_valid_signature(body, secret)
        assert verify_hmac_sha256(body, sig, secret) is True


# ---------------------------------------------------------------------------
# Invalid signature
# ---------------------------------------------------------------------------

class TestInvalidSignature:
    def test_wrong_signature_returns_false(self):
        body = b'{"event": "test"}'
        secret = "correct-secret"
        assert verify_hmac_sha256(body, "deadbeef" * 8, secret) is False

    def test_tampered_body_returns_false(self):
        body = b'{"amount": 100}'
        secret = "s3cr3t"
        sig = _make_valid_signature(body, secret)
        assert verify_hmac_sha256(b'{"amount": 999}', sig, secret) is False

    def test_wrong_secret_returns_false(self):
        body = b"payload"
        sig = _make_valid_signature(body, "correct-secret")
        assert verify_hmac_sha256(body, sig, "wrong-secret") is False

    def test_prefix_attack_returns_false(self):
        body = b"payload"
        secret = "s3cr3t"
        sig = _make_valid_signature(body, secret)
        # Prepending the valid sig with a length prefix must not match
        assert verify_hmac_sha256(body, "0040" + sig, secret) is False


# ---------------------------------------------------------------------------
# Guard clauses — no exceptions on empty inputs
# ---------------------------------------------------------------------------

class TestEmptyInputGuards:
    def test_empty_signature_returns_false(self):
        assert verify_hmac_sha256(b"body", "", "secret") is False

    def test_empty_secret_returns_false(self):
        body = b"body"
        sig = _make_valid_signature(body, "real-secret")
        assert verify_hmac_sha256(body, sig, "") is False

    def test_both_empty_returns_false(self):
        assert verify_hmac_sha256(b"", "", "") is False

    def test_none_like_empty_signature_does_not_raise(self):
        # Caller may pass header value that came back as empty string
        result = verify_hmac_sha256(b"data", "", "secret")
        assert result is False

    def test_all_empty_does_not_raise(self):
        result = verify_hmac_sha256(b"", "", "")
        assert result is False
