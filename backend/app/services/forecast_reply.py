"""The WhatsApp answer to "prévision mardi" (HOS-358) — deterministic, no model.

Renders what the forecast engine returned (the same engine and guardrail as the
MCP tool ``get_operational_predictions``), the stored context it was given
(``forecast_context``) and the recommendation already sent for that day, if any.

Rules (unchanged by the 05/11/2026 layout rework — only the presentation moved):

* A mock forecast (no trained model, ``prediction.is_mock``) is never shown as
  a figure: the answer says there is no forecast (HOS-303).
* Every context element is what was stored or is said to be unavailable. The covers
  figure does not use this context yet (no Prophet regressors), so the answer
  says so instead of implying it does.
* Whose staffing rules were used is said (Décision #43): the hotel's, or defaults.
  When the rule is a default, "usual staffing" is a default too and is labelled so.
* A figure a guardrail could not check (``forecast_guardrail.verified`` false,
  rule B, HOS-366) is shown with a qualitative "not verified" reserve, never as
  a clean figure and never with a confidence percentage.

Layout: one short block per question the manager has — how many covers, how many
staff, what is around — with WhatsApp emphasis (``*bold*``, ``_italic_``) and one
closing hint on how to ask for another day. The figure comes first.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

from app.core import config
from app.i18n.abstention_messages import localized_message
from app.services.staffing_context import CLASS_LABELS

_DAYS = {
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}
_WEATHER = {
    "fr": {"clear": "ciel dégagé", "partly_cloudy": "partiellement nuageux", "cloudy": "couvert",
           "fog": "brouillard", "rain": "pluie", "snow": "neige", "showers": "averses",
           "thunderstorm": "orage"},
    "en": {"clear": "clear sky", "partly_cloudy": "partly cloudy", "cloudy": "cloudy",
           "fog": "fog", "rain": "rain", "snow": "snow", "showers": "showers",
           "thunderstorm": "thunderstorm"},
}
_ROLES = {
    "fr": {"servers": ("serveur", "serveurs"), "hosts": ("à l'accueil", "à l'accueil"),
           "runners": ("runner", "runners"), "kitchen": ("en cuisine", "en cuisine")},
    "en": {"servers": ("server", "servers"), "hosts": ("host", "hosts"),
           "runners": ("runner", "runners"), "kitchen": ("in the kitchen", "in the kitchen")},
}
_STATUS = {
    "fr": {"dispatched": "en attente de décision", "accepted": "validée", "rejected": "refusée",
           "modified": "corrigée"},
    "en": {"dispatched": "waiting for a decision", "accepted": "accepted", "rejected": "rejected",
           "modified": "corrected"},
}
_T = {
    "fr": {
        "title": "📊 *Prévision · {day} · {service}*",
        "figure": "*{covers} couverts*{range}",
        "range": " · fourchette {lo}–{hi}",
        "baseline": "_Valeur de référence : la prévision du modèle était jugée peu fiable._",
        "mock": "Pas de prévision chiffrée : aucun modèle de prévision n'est encore entraîné.",
        "unavailable": "Prévision indisponible pour le moment.",
        "bad_date": "Je ne trouve pas la date « {ref} ».",
        "staff_title": "👥 *Effectif conseillé*",
        "usual": "habituel : {n}",
        "rules_hotel": "_Selon les règles de l'hôtel._",
        "rules_default": "_Règles et effectif habituel par défaut, non fixés par l'hôtel._",
        "rules_mixed": "_Règles de l'hôtel quand elles sont fixées, par défaut ailleurs._",
        "rec": "📌 *Recommandation déjà envoyée* : {what} ({status}).",
        "rec_delta": "{n} extra{s}",
        "rec_cut": "{n} de moins",
        "rec_none": "effectif habituel",
        "context_title": "🌤 *Contexte*",
        "weather": "Météo : {v}",
        "weather_unknown": "non disponible",
        "events": "Événements : {v}",
        "events_none": "aucun connu à proximité",
        "events_unknown": "non disponibles",
        "occupancy": "Occupation : {pct} %",
        "occupancy_unknown": "Occupation : non disponible",
        "not_used": "_Ces éléments ne modifient pas encore le chiffre de couverts._",
        "hint": "💬 _Un autre jour ? Écrivez « prévision {day} »._",
        "demo": "🧪 _Démonstration : hôtel fictif, modèle entraîné sur des données synthétiques._",
        "km": "{d} km",
        "ack": "⏳ Demande reçue : je calcule la prévision {day}…",
    },
    "en": {
        "title": "📊 *Forecast · {day} · {service}*",
        "figure": "*{covers} covers*{range}",
        "range": " · range {lo}–{hi}",
        "baseline": "_Reference value: the model's forecast was judged unreliable._",
        "mock": "No forecast figure: no forecasting model is trained yet.",
        "unavailable": "Forecast unavailable right now.",
        "bad_date": "I can't find the date \"{ref}\".",
        "staff_title": "👥 *Suggested staffing*",
        "usual": "usual: {n}",
        "rules_hotel": "_Based on the hotel's rules._",
        "rules_default": "_Default rules and usual staffing, not set by the hotel._",
        "rules_mixed": "_The hotel's rules where set, defaults elsewhere._",
        "rec": "📌 *Recommendation already sent*: {what} ({status}).",
        "rec_delta": "{n} extra staff",
        "rec_cut": "{n} fewer",
        "rec_none": "usual staffing",
        "context_title": "🌤 *Context*",
        "weather": "Weather: {v}",
        "weather_unknown": "unavailable",
        "events": "Events: {v}",
        "events_none": "none known nearby",
        "events_unknown": "unavailable",
        "occupancy": "Occupancy: {pct}%",
        "occupancy_unknown": "Occupancy: unavailable",
        "not_used": "_These do not change the covers figure yet._",
        "hint": "💬 _Another day? Reply “forecast {day}”._",
        "demo": "🧪 _Demonstration: fictional hotel, model trained on synthetic data._",
        "km": "{d} km",
        "ack": "⏳ Request received: computing the {day} forecast…",
    },
}


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def day_label(day: date, locale: Optional[str] = "fr") -> str:
    return f"{_DAYS[_loc(locale)][day.weekday()]} {day:%d/%m}"


def _num(value: float, loc: str) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if loc == "fr" else text


def _staff_block(staffing: Mapping[str, Any], loc: str) -> Optional[list[str]]:
    t = _T[loc]
    deltas = staffing.get("deltas") or {}
    bullets = []
    for role in ("servers", "hosts", "runners", "kitchen"):
        n = staffing.get(role) or 0
        if not n:
            continue
        one, many = _ROLES[loc][role]
        line = f"• {n} {one if n == 1 else many}"
        d = deltas.get(role)
        if d:  # delta = recommended - usual, so usual = n - d (a default when the rule is a default)
            line += f" ({t['usual'].format(n=int(n - d))})"
        bullets.append(line)
    if not bullets:
        return None
    rules = staffing.get("rules") or {}
    sources = {r.get("covers_per_source") for role, r in rules.items()
               if role != "sommeliers" and isinstance(r, Mapping)
               and r.get("covers_per_source") in ("hotel", "default")}
    note = (t["rules_hotel"] if sources == {"hotel"}
            else t["rules_default"] if sources == {"default"}
            else t["rules_mixed"] if sources else None)
    return [t["staff_title"], *bullets, *([note] if note else [])]


def _recommendation_line(rec: Any, loc: str) -> Optional[str]:
    if rec is None:
        return None
    t = _T[loc]
    ra = getattr(rec, "risk_assessment", None)
    delta = ra.get("recommended_delta_staff") if isinstance(ra, Mapping) else None
    if isinstance(delta, (int, float)) and delta > 0:
        what = t["rec_delta"].format(n=int(delta), s="s" if delta > 1 else "")
    elif isinstance(delta, (int, float)) and delta < 0:
        what = t["rec_cut"].format(n=abs(int(delta)))
    elif isinstance(delta, (int, float)):
        what = t["rec_none"]
    else:
        what = (getattr(rec, "message_text", "") or "").strip().splitlines()[0][:120] or "—"
    status = _STATUS[loc].get(getattr(rec, "status", ""), getattr(rec, "status", ""))
    return t["rec"].format(what=what, status=status)


def _context_block(context: Mapping[str, Any], loc: str, with_note: bool) -> list[str]:
    t = _T[loc]
    sources = context.get("context_sources") or {}
    lines = [t["context_title"]]
    weather = context.get("weather") or {}
    if weather.get("condition") or weather.get("temp") is not None:
        w = [_WEATHER[loc].get(weather.get("condition"), weather.get("condition"))]
        if weather.get("temp") is not None:
            w.append(f"{_num(float(weather['temp']), loc)} °C")
        lines.append("• " + t["weather"].format(v=", ".join(x for x in w if x)))
    else:
        lines.append("• " + t["weather"].format(v=t["weather_unknown"]))
    events = context.get("events") or []
    if events:
        labels = []
        for e in events[:3]:
            name = e.get("name") or e.get("title") or "?"
            dist = e.get("distance_km")
            labels.append(f"{name} ({t['km'].format(d=_num(float(dist), loc))})"
                          if dist is not None else name)
        lines.append("• " + t["events"].format(v=", ".join(labels)))
    elif (sources.get("events") or {}).get("status") in ("ok", "caller"):
        lines.append("• " + t["events"].format(v=t["events_none"]))
    else:
        lines.append("• " + t["events"].format(v=t["events_unknown"]))
    occ = context.get("occupancy")
    lines.append("• " + (t["occupancy"].format(pct=round(float(occ) * 100)) if occ is not None
                         else t["occupancy_unknown"]))
    if with_note:
        lines.append(t["not_used"])
    return lines


def render_forecast(
    result: Optional[Mapping[str, Any]],
    context: Mapping[str, Any],
    day: date,
    service: str,
    locale: Optional[str] = "fr",
    recommendation: Any = None,
    demo_notice: Optional[bool] = None,
) -> str:
    """``result`` = ``engine.get_forecast(...)``, ``None`` when the engine is
    unavailable or failed. Blocks are separated by a blank line.

    ``demo_notice`` adds the "fictional hotel, synthetic data" line to a served forecast;
    ``None`` reads ``config.FORECAST_DEMO_NOTICE`` (off by default)."""
    loc = _loc(locale)
    t = _T[loc]
    fmt = {"day": day_label(day, loc), "service": CLASS_LABELS[loc].get(service, service)}
    prediction = (result or {}).get("prediction") or {}
    blocks: list[list[str]] = [[t["title"].format(**fmt)]]
    mock = bool(prediction.get("is_mock"))
    served = False
    if result is None or prediction.get("covers") is None:
        blocks[0].append(t["unavailable"])
    elif mock:
        blocks[0].append(t["mock"])
    else:
        served = True
        interval = prediction.get("calibrated_interval")
        lo, hi = (interval if isinstance(interval, (list, tuple)) and len(interval) == 2
                  else (prediction.get("range_min"), prediction.get("range_max")))
        rng = (t["range"].format(lo=round(float(lo)), hi=round(float(hi)))
               if lo is not None and hi is not None else "")
        blocks[0].append(t["figure"].format(covers=round(float(prediction["covers"])), range=rng))
        if prediction.get("baseline_used"):
            blocks[0].append(t["baseline"])
        guard = result.get("forecast_guardrail") or {}
        if guard.get("verified") is False:
            # Rule B (HOS-366): a check did not run — qualitative reserve, no number.
            blocks[0].append(f"⚠️ _{localized_message('guardrail_not_verified', loc)}_")
        staffing = result.get("staffing_recommendation")
        if isinstance(staffing, Mapping):
            staff = _staff_block(staffing, loc)
            if staff:
                blocks.append(staff)
    rec_line = _recommendation_line(recommendation, loc)
    if rec_line:
        blocks.append([rec_line])
    blocks.append(_context_block(context, loc, with_note=served))
    if served:
        nxt = _DAYS[loc][(day.weekday() + 1) % 7]
        blocks.append([t["hint"].format(day=nxt.lower())])
        if config.FORECAST_DEMO_NOTICE if demo_notice is None else demo_notice:
            blocks.append([t["demo"]])
    return "\n\n".join("\n".join(b) for b in blocks)


def ack_reply(ref: str, locale: Optional[str] = "fr") -> str:
    """Immediate "received, working on it" line sent while the engine runs.
    ``ref`` is what the manager wrote ("vendredi soir"), echoed back so the
    manager sees the request was understood. Nothing is computed here."""
    ref = " ".join((ref or "").split())[:40]
    return _T[_loc(locale)]["ack"].format(day=f"« {ref} »" if ref else "").replace("  ", " ")


def bad_date_reply(ref: str, locale: Optional[str] = "fr") -> str:
    return _T[_loc(locale)]["bad_date"].format(ref=ref)
