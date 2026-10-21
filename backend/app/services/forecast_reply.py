"""The WhatsApp answer to "prévision mardi" (HOS-358) — deterministic, no model.

Renders what the forecast engine returned (the same engine and guardrail as the
MCP tool ``get_operational_predictions``), the stored context it was given
(``forecast_context``) and the recommendation already sent for that day, if any.

Rules:

* A mock forecast (no trained model, ``prediction.is_mock``) is never shown as
  a figure: the answer says there is no forecast (HOS-303).
* Every context element is what was stored or is said to be unknown. The covers
  figure does not use this context yet (no Prophet regressors), so the answer
  says so instead of implying it does.
* Whose staffing rules were used is said (Décision #43): the hotel's, or defaults.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional

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
        "head": "Prévision {day}, {service} : {covers} couverts{range}.",
        "range": " (fourchette {lo}–{hi})",
        "baseline": " Valeur de référence : la prévision du modèle était jugée peu fiable.",
        "mock": "{day}, {service} : pas de prévision chiffrée, aucun modèle de prévision n'est encore entraîné.",
        "unavailable": "{day}, {service} : prévision indisponible pour le moment.",
        "bad_date": "Je ne trouve pas la date « {ref} ».",
        "staff": "Effectif conseillé : {roles}{rules}.",
        "rules_hotel": " (règles de l'hôtel)",
        "rules_default": " (règles par défaut, non fixées par l'hôtel)",
        "rules_mixed": " (règles de l'hôtel quand elles sont fixées, par défaut ailleurs)",
        "rec": "Recommandation déjà envoyée pour ce jour : {what} ({status}).",
        "rec_delta": "{n} extra{s}",
        "rec_cut": "{n} de moins",
        "rec_none": "effectif habituel",
        "context": "À savoir : {items}.",
        "weather_unknown": "météo inconnue",
        "events_none": "aucun événement connu à proximité",
        "events_unknown": "événements inconnus",
        "occupancy": "occupation {pct} %",
        "occupancy_unknown": "occupation inconnue",
        "not_used": "La prévision de couverts ne tient pas encore compte de ce contexte.",
        "km": "{d} km",
    },
    "en": {
        "head": "Forecast {day}, {service}: {covers} covers{range}.",
        "range": " (range {lo}–{hi})",
        "baseline": " Reference value: the model's forecast was judged unreliable.",
        "mock": "{day}, {service}: no forecast figure, no forecasting model is trained yet.",
        "unavailable": "{day}, {service}: forecast unavailable right now.",
        "bad_date": "I can't find the date \"{ref}\".",
        "staff": "Suggested staffing: {roles}{rules}.",
        "rules_hotel": " (the hotel's rules)",
        "rules_default": " (default rules, not set by the hotel)",
        "rules_mixed": " (the hotel's rules where set, defaults elsewhere)",
        "rec": "Recommendation already sent for this day: {what} ({status}).",
        "rec_delta": "{n} extra staff",
        "rec_cut": "{n} fewer",
        "rec_none": "usual staffing",
        "context": "Good to know: {items}.",
        "weather_unknown": "weather unknown",
        "events_none": "no known event nearby",
        "events_unknown": "events unknown",
        "occupancy": "occupancy {pct}%",
        "occupancy_unknown": "occupancy unknown",
        "not_used": "The covers forecast does not take this context into account yet.",
        "km": "{d} km",
    },
}


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def day_label(day: date, locale: Optional[str] = "fr") -> str:
    return f"{_DAYS[_loc(locale)][day.weekday()]} {day:%d/%m}"


def _num(value: float, loc: str) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if loc == "fr" else text


def _staff_line(staffing: Mapping[str, Any], loc: str) -> Optional[str]:
    t = _T[loc]
    deltas = staffing.get("deltas") or {}
    parts = []
    for role in ("servers", "hosts", "runners", "kitchen"):
        n = staffing.get(role) or 0
        if not n:
            continue
        one, many = _ROLES[loc][role]
        part = f"{n} {one if n == 1 else many}"
        d = deltas.get(role)
        if d:
            part += f" ({d:+d})"
        parts.append(part)
    if not parts:
        return None
    rules = staffing.get("rules") or {}
    sources = {r.get("covers_per_source") for role, r in rules.items()
               if role != "sommeliers" and isinstance(r, Mapping)
               and r.get("covers_per_source") in ("hotel", "default")}
    rules_label = (t["rules_hotel"] if sources == {"hotel"}
                   else t["rules_default"] if sources == {"default"}
                   else t["rules_mixed"] if sources else "")
    return t["staff"].format(roles=", ".join(parts), rules=rules_label)


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


def _context_line(context: Mapping[str, Any], loc: str) -> str:
    t = _T[loc]
    sources = context.get("context_sources") or {}
    items = []
    weather = context.get("weather") or {}
    if weather.get("condition") or weather.get("temp") is not None:
        w = [_WEATHER[loc].get(weather.get("condition"), weather.get("condition"))]
        if weather.get("temp") is not None:
            w.append(f"{_num(float(weather['temp']), loc)} °C")
        items.append(", ".join(x for x in w if x))
    else:
        items.append(t["weather_unknown"])
    events = context.get("events") or []
    if events:
        labels = []
        for e in events[:3]:
            name = e.get("name") or e.get("title") or "?"
            dist = e.get("distance_km")
            labels.append(f"{name} ({t['km'].format(d=_num(float(dist), loc))})"
                          if dist is not None else name)
        items.append(", ".join(labels))
    elif (sources.get("events") or {}).get("status") in ("ok", "caller"):
        items.append(t["events_none"])
    else:
        items.append(t["events_unknown"])
    occ = context.get("occupancy")
    items.append(t["occupancy"].format(pct=round(float(occ) * 100)) if occ is not None
                 else t["occupancy_unknown"])
    return t["context"].format(items=" ; ".join(items) if loc == "fr" else "; ".join(items))


def render_forecast(
    result: Optional[Mapping[str, Any]],
    context: Mapping[str, Any],
    day: date,
    service: str,
    locale: Optional[str] = "fr",
    recommendation: Any = None,
) -> str:
    """``result`` = ``engine.get_forecast(...)``, ``None`` when the engine is
    unavailable or failed."""
    loc = _loc(locale)
    t = _T[loc]
    fmt = {"day": day_label(day, loc), "service": CLASS_LABELS[loc].get(service, service)}
    prediction = (result or {}).get("prediction") or {}
    lines: list[str] = []
    mock = bool(prediction.get("is_mock"))
    if result is None or prediction.get("covers") is None:
        lines.append(t["unavailable"].format(**fmt))
    elif mock:
        lines.append(t["mock"].format(**fmt))
    else:
        interval = prediction.get("calibrated_interval")
        lo, hi = (interval if isinstance(interval, (list, tuple)) and len(interval) == 2
                  else (prediction.get("range_min"), prediction.get("range_max")))
        rng = (t["range"].format(lo=round(float(lo)), hi=round(float(hi)))
               if lo is not None and hi is not None else "")
        head = t["head"].format(covers=round(float(prediction["covers"])), range=rng, **fmt)
        if prediction.get("baseline_used"):
            head += t["baseline"]
        lines.append(head)
        staffing = result.get("staffing_recommendation")
        if isinstance(staffing, Mapping):
            staff = _staff_line(staffing, loc)
            if staff:
                lines.append(staff)
    rec_line = _recommendation_line(recommendation, loc)
    if rec_line:
        lines.append(rec_line)
    lines.append(_context_line(context, loc))
    if result is not None and not mock and prediction.get("covers") is not None:
        lines.append(t["not_used"])
    return "\n".join(lines)


def bad_date_reply(ref: str, locale: Optional[str] = "fr") -> str:
    return _T[_loc(locale)]["bad_date"].format(ref=ref)
