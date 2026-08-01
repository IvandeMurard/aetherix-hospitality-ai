"""Pseudonymisation helpers for anything that reaches a log line.

Story 7.5 / HOS-115. The Q2-03 finding (PR #187) closed the WhatsApp inbound
logger but three call sites survived it, all on paths that only fire for an
*unknown* sender:

  - `services/action_logger.py`  — "no profile found for phone_number=%s"
  - `services/query_parser.py`   — same warning, same raw number
  - `workers/receipts_dispatcher.py` — "email sent ... to=%s"

The first two are the worst case rather than the mildest: the number that
reaches them belongs to someone who is *not* a customer — a wrong number, a
former manager, a test — so there is no contract and no legitimate interest to
lean on, and the log is the only place the value lands.

Why a truncated digest rather than dropping the value: an operator debugging a
routing failure needs to tell two senders apart across log lines. A digest does
that and nothing else. It is **pseudonymisation, not anonymisation** (RGPD
considérant 26) — a phone number has ~10^9 realistic preimages, so a digest is
brute-forceable by anyone holding the log. It reduces exposure; it does not put
the value outside the regulation, and nothing downstream may treat it as if it
did.
"""
from __future__ import annotations

import hashlib

# 12 hex chars ≈ 48 bits: collision-free at any log volume this system will
# reach, while staying too short to be mistaken for a reversible token.
_DIGEST_CHARS = 12


def pseudonymise(value: str | None) -> str:
    """Return a short stable digest of `value`, safe to put in a log line.

    Returns a literal marker for empty input rather than the digest of the
    empty string, so that "absent" and "present but unknown" stay
    distinguishable when reading logs.
    """
    if not value:
        return "<absent>"
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:_DIGEST_CHARS]}"
