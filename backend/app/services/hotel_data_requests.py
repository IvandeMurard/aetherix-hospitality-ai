"""Requests the hotel's agent makes that only a human may confirm.

HOS-349, Décisions #43 and #44: the hotel reaches its data through its own
agent over MCP. The agent reads and requests; anything irreversible, or any
sharing of the hotel's data, waits for a human.

* **Deletion of all the hotel's data.** The agent asks; the owner receives a
  one-time code on WhatsApp (the verified number on the hotel's profile) and
  confirms with ``SUPPRIMER <code>`` / ``DELETE <code>``. The deletion then
  runs after ``DELETION_DELAY`` and can be cancelled until then, by the owner
  (``ANNULER <code>`` / ``CANCEL <code>``) or by the agent: stopping is always
  safe. The owner is told by WhatsApp and, when configured, by e-mail.
* **Opt-in to the Hive.** Same confirmation (``HIVE OUI <code>`` /
  ``HIVE YES <code>``). An opt-out needs no confirmation (``hive_gate``).

The agent never sees the code: it is sent to the owner only and stored as a
sha256. The request keeps who relayed it (the MCP token label) and who
confirmed it (the owner, on WhatsApp): an agent's request is never recorded as
a human decision (Décision #39).
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import hive_gate, hotel_data

logger = logging.getLogger(__name__)

CONFIRM_TTL = timedelta(hours=2)
DELETION_DELAY = timedelta(hours=24)
KINDS = ("deletion", "hive_opt_in")
OPEN = ("pending_confirmation", "scheduled")
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L

Sender = Callable[[str, str], Awaitable[object]]


class RequestError(Exception):
    """Typed refusal for the MCP layer."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


# --- WhatsApp command --------------------------------------------------------

@dataclass(frozen=True)
class Command:
    action: str   # confirm_deletion | confirm_hive | cancel
    code: str
    locale: str


_COMMANDS = (
    (re.compile(r"^\s*supprimer\s+([a-z0-9]{6})\s*$", re.I), "confirm_deletion", "fr"),
    (re.compile(r"^\s*delete\s+([a-z0-9]{6})\s*$", re.I), "confirm_deletion", "en"),
    (re.compile(r"^\s*hive\s+oui\s+([a-z0-9]{6})\s*$", re.I), "confirm_hive", "fr"),
    (re.compile(r"^\s*hive\s+yes\s+([a-z0-9]{6})\s*$", re.I), "confirm_hive", "en"),
    (re.compile(r"^\s*annuler\s+([a-z0-9]{6})\s*$", re.I), "cancel", "fr"),
    (re.compile(r"^\s*cancel\s+([a-z0-9]{6})\s*$", re.I), "cancel", "en"),
)


def match_command(body: str) -> Optional[Command]:
    """Exact whole-message commands only; anything else is not ours."""
    for pattern, action, locale in _COMMANDS:
        m = pattern.match(body or "")
        if m:
            return Command(action, m.group(1).upper(), locale)
    return None


_TEXT = {
    "ask_deletion": {
        "fr": ("Votre agent a demandé la suppression de toutes les données de {hotel} chez Aetherix. "
               "Pour confirmer, répondez : SUPPRIMER {code} (valable 2 h). La suppression aura lieu 24 h "
               "après votre confirmation et pourra être annulée d'ici là. Sans réponse, rien n'est supprimé."),
        "en": ("Your agent asked to delete all of {hotel}'s data held by Aetherix. To confirm, reply: "
               "DELETE {code} (valid 2 h). Deletion happens 24 h after you confirm and can be cancelled "
               "until then. Without a reply, nothing is deleted."),
    },
    "ask_hive": {
        "fr": ("Votre agent a demandé que {hotel} contribue au Hive : des moyennes sur au moins 5 hôtels, "
               "jamais vos valeurs seules ni votre nom. Pour confirmer, répondez : HIVE OUI {code} "
               "(valable 2 h). Sans réponse, rien ne change."),
        "en": ("Your agent asked for {hotel} to contribute to the Hive: averages over at least 5 hotels, "
               "never your values alone or your name. To confirm, reply: HIVE YES {code} (valid 2 h). "
               "Without a reply, nothing changes."),
    },
    "deletion_scheduled": {
        "fr": "Suppression confirmée. Elle aura lieu le {when}. Pour annuler d'ici là : ANNULER {code}.",
        "en": "Deletion confirmed. It will run on {when}. To cancel until then: CANCEL {code}.",
    },
    "hive_confirmed": {
        "fr": "C'est noté : {hotel} contribue au Hive. Vous pouvez retirer ce consentement à tout moment.",
        "en": "Done: {hotel} now contributes to the Hive. You can withdraw this consent at any time.",
    },
    "cancelled": {
        "fr": "Demande annulée. Rien n'a été supprimé ni partagé.",
        "en": "Request cancelled. Nothing was deleted or shared.",
    },
    "unknown_code": {
        "fr": "Ce code ne correspond à aucune demande en cours (ou il a expiré). Rien n'a été fait.",
        "en": "This code matches no open request (or it expired). Nothing was done.",
    },
    "deleted": {
        "fr": "Les données de {hotel} vont être supprimées maintenant ({rows} lignes). Les sauvegardes expirent selon leur durée de rétention.",
        "en": "{hotel}'s data is being deleted now ({rows} rows). Backups expire with their retention window.",
    },
}


def _t(key: str, locale: str, **kw) -> str:
    return _TEXT[key]["en" if locale == "en" else "fr"].format(**kw)


# --- default channels (best effort, never block) -----------------------------

async def _send_whatsapp(to: str, body: str) -> object:
    from app.integrations.twilio_client import TwilioClient

    return await TwilioClient().send_whatsapp(to, body)


async def _send_email(to: str, subject: str, body: str) -> object:
    from app.integrations.sendgrid_client import SendGridClient

    return await SendGridClient().send_email(to, subject, body)


async def _notify(profile, text: str, *, whatsapp: Sender, email=None, subject: str = "Aetherix") -> bool:
    """WhatsApp to the verified number (required to confirm); e-mail copy when set."""
    sent = False
    try:
        await whatsapp(profile.phone_number, text)
        sent = True
    except Exception:  # noqa: BLE001 — a failed send never raises past here
        logger.warning("hotel_data_requests: WhatsApp send failed for %s", profile.tenant_id)
    if getattr(profile, "notification_email", None):
        try:
            await (email or _send_email)(profile.notification_email, subject, text)
        except Exception:  # noqa: BLE001
            logger.info("hotel_data_requests: e-mail copy not sent for %s", profile.tenant_id)
    return sent


# --- requests ------------------------------------------------------------------

async def _profile(db: AsyncSession, tenant_id: str):
    from app.db.models import RestaurantProfile

    return (await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
    )).scalars().first()


def _hotel_name(profile) -> str:
    return getattr(profile, "outlet_name", None) or getattr(profile, "property_name", None) or profile.tenant_id


def as_dict(r) -> dict:
    """A request as the agent may see it: never the code or its hash."""
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "data_request_id": str(r.id), "kind": r.kind, "status": r.status,
        "requested_by": r.requested_by, "created_at": iso(r.created_at),
        "confirm_expires_at": iso(r.confirm_expires_at), "execute_after": iso(r.execute_after),
        "confirmed_by": r.confirmed_by, "confirmed_at": iso(r.confirmed_at),
        "cancelled_by": r.cancelled_by, "cancelled_at": iso(r.cancelled_at),
        "executed_at": iso(r.executed_at),
    }


async def create_request(
    db: AsyncSession, tenant_id: str, kind: str, *, requested_by: str, note: Optional[str] = None,
    now: Optional[datetime] = None, whatsapp: Optional[Sender] = None, email=None,
) -> dict:
    """Open a request and send the owner its one-time code. Commits nothing."""
    from app.db.models import HotelDataRequest

    if kind not in KINDS:
        raise RequestError("invalid_input", f"kind must be one of {KINDS}")
    profile = await _profile(db, tenant_id)
    if profile is None:
        raise RequestError("not_found", "no hotel profile for this tenant")
    if not profile.phone_number:
        raise RequestError("no_verified_channel",
                           "the hotel has no WhatsApp number on its profile: the owner could not confirm")
    now = now or datetime.now(timezone.utc)
    open_same = (await db.execute(
        select(HotelDataRequest).where(HotelDataRequest.tenant_id == tenant_id,
                                       HotelDataRequest.kind == kind,
                                       HotelDataRequest.status.in_(OPEN))
    )).scalars().first()
    if open_same is not None:
        raise RequestError("already_open", f"a {kind} request is already open ({open_same.id})")
    code = new_code()
    row = HotelDataRequest(
        id=uuid.uuid4(), tenant_id=tenant_id, kind=kind, status="pending_confirmation",
        requested_by=(requested_by or "agent")[:200], requested_via="mcp", code_hash=code_hash(code),
        confirm_expires_at=now + CONFIRM_TTL, note=(note or None) and note.strip()[:500], created_at=now,
    )
    db.add(row)
    await db.flush()
    locale = getattr(profile, "manager_locale", None) or "fr"
    text = _t("ask_deletion" if kind == "deletion" else "ask_hive", locale, hotel=_hotel_name(profile), code=code)
    sent = await _notify(profile, text, whatsapp=whatsapp or _send_whatsapp, email=email)
    out = as_dict(row)
    out["owner_notified"] = sent
    out["how_to_confirm"] = ("The owner received a one-time code on WhatsApp and confirms there. "
                             "Nothing happens without that confirmation.")
    return out


async def list_requests(db: AsyncSession, tenant_id: str) -> list[dict]:
    from app.db.models import HotelDataRequest

    rows = (await db.execute(
        select(HotelDataRequest).where(HotelDataRequest.tenant_id == tenant_id)
        .order_by(HotelDataRequest.created_at.desc())
    )).scalars().all()
    return [as_dict(r) for r in rows]


async def cancel_request(db: AsyncSession, tenant_id: str, data_request_id: str, *, by: str,
                         now: Optional[datetime] = None) -> dict:
    """Cancel an open request (the agent may: stopping is safe). Commits nothing."""
    from app.db.models import HotelDataRequest

    try:
        rid = uuid.UUID(str(data_request_id))
    except ValueError:
        raise RequestError("invalid_input", "data_request_id is not a UUID") from None
    row = (await db.execute(
        select(HotelDataRequest).where(HotelDataRequest.id == rid, HotelDataRequest.tenant_id == tenant_id)
    )).scalars().first()
    if row is None:
        raise RequestError("not_found", "no such request for this hotel")
    if row.status not in OPEN:
        raise RequestError("not_open", f"request is {row.status}")
    row.status, row.cancelled_by, row.cancelled_at = "cancelled", by[:200], now or datetime.now(timezone.utc)
    await db.flush()
    return as_dict(row)


async def handle_command(db: AsyncSession, profile, cmd: Command, *, now: Optional[datetime] = None) -> str:
    """Apply an owner's WhatsApp command for *this* hotel; returns the reply. Commits."""
    from app.db.models import HotelDataRequest

    now = now or datetime.now(timezone.utc)
    locale = cmd.locale
    kind = {"confirm_deletion": "deletion", "confirm_hive": "hive_opt_in"}.get(cmd.action)
    stmt = select(HotelDataRequest).where(
        HotelDataRequest.tenant_id == profile.tenant_id,
        HotelDataRequest.code_hash == code_hash(cmd.code),
        HotelDataRequest.status.in_(OPEN),
    )
    if kind:
        stmt = stmt.where(HotelDataRequest.kind == kind, HotelDataRequest.status == "pending_confirmation")
    row = (await db.execute(stmt)).scalars().first()
    if row is None or (row.status == "pending_confirmation" and _aware(row.confirm_expires_at) < now):
        return _t("unknown_code", locale)

    who = "owner_whatsapp"
    if cmd.action == "cancel":
        row.status, row.cancelled_by, row.cancelled_at = "cancelled", who, now
        await db.commit()
        return _t("cancelled", locale)
    row.confirmed_by, row.confirmed_at = who, now
    if row.kind == "deletion":
        row.status, row.execute_after = "scheduled", now + DELETION_DELAY
        await db.commit()
        return _t("deletion_scheduled", locale, when=row.execute_after.strftime("%d/%m/%Y %H:%M UTC"), code=cmd.code)
    await hive_gate.set_consent(db, profile.tenant_id, True, set_by=who, set_via="whatsapp",
                                note=f"confirmed request {row.id} (relayed by {row.requested_by})", at=now)
    row.status = "confirmed"
    await db.commit()
    return _t("hive_confirmed", locale, hotel=_hotel_name(profile))


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def expire_stale(db: AsyncSession, now: Optional[datetime] = None) -> int:
    from app.db.models import HotelDataRequest

    now = now or datetime.now(timezone.utc)
    rows = (await db.execute(
        select(HotelDataRequest).where(HotelDataRequest.status == "pending_confirmation")
    )).scalars().all()
    n = 0
    for r in rows:
        if _aware(r.confirm_expires_at) < now:
            r.status, n = "expired", n + 1
    await db.commit()
    return n


async def run_due_deletions(db: AsyncSession, now: Optional[datetime] = None, *,
                            whatsapp: Optional[Sender] = None, email=None) -> list[dict]:
    """Execute confirmed deletions whose delay has passed. Tells the owner first,
    while the profile (and its number) still exists."""
    from app.db.models import HotelDataRequest

    now = now or datetime.now(timezone.utc)
    rows = (await db.execute(
        select(HotelDataRequest).where(HotelDataRequest.status == "scheduled",
                                       HotelDataRequest.kind == "deletion")
    )).scalars().all()
    reports = []
    for r in rows:
        if r.execute_after is None or _aware(r.execute_after) > now:
            continue
        r.status = "executing"
        await db.commit()
        tenant = r.tenant_id
        profile = await _profile(db, tenant)
        preview = await hotel_data.execute_deletion(db, tenant, dry_run=True)
        if profile is not None:
            locale = getattr(profile, "manager_locale", None) or "fr"
            await _notify(profile, _t("deleted", locale, hotel=_hotel_name(profile), rows=sum(preview.rows.values())),
                          whatsapp=whatsapp or _send_whatsapp, email=email, subject="Aetherix: data deletion")
        report = await hotel_data.execute_deletion(db, tenant, dry_run=False)
        logger.info("hotel_data_requests: deletion %s executed for %s (%d rows)", r.id, tenant, sum(report.rows.values()))
        reports.append(report.as_dict())
    return reports
