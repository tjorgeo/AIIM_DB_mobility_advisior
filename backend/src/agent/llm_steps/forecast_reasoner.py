"""LLM demand-reasoning step for the 90/365-day forecast.

Reads a user's historical travel summary plus (optionally) upcoming calendar text,
and lets the LLM reason over uncertainty — a possible relocation, a trip already on
the calendar — to produce one or more demand scenarios. It forecasts *demand* (trip
counts) only, never money.

This is the LLM half of what used to be ``engines/forecasting.forecast``; the
deterministic half is now ``engines.forecasting.seasonal_projection``. ``reason_demand``
is the pure single LLM call (returns ``None`` on no-parse/error); ``forecast`` is the
orchestrator that prefers the LLM and falls back to the projection, reproducing the
original ``forecast()`` behaviour for the callers that still want one entry point
(``pipeline.py`` and the ``/api/forecaster*`` debug endpoints).
"""

import json
from datetime import date, datetime, timezone

from agent.engines.forecasting import ForecastOutput, seasonal_projection
from agent.json_extract import extract_json


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_JSON_SCHEMA = """\
{{
  "forecast_horizon_days": <int>,
  "scenarios": [
    {{
      "label": <str>,
      "description_en": <str>,
      "description_de": <str>,
      "predicted_demand": [
        {{
          "mode": <str>,
          "estimated_trips": <int>,
          "estimated_km": <float>,
          "confidence": "high" | "medium" | "low",
          "basis": <str>
        }}
      ]
    }}
  ],
  "uncertainty_flags": {{
    "life_event_detected": <bool>,
    "life_event_type": <str | null>,
    "recommend_re_evaluation_in_days": <int | null>
  }},
  "rationale_en": <str>,
  "rationale_de": <str>
}}"""

_RULES = """\
Rules:
1. Always include a "baseline" scenario derived from the historical patterns.
2. If a life_event with confidence "medium" or "high" is present, produce a SECOND
   scenario that covers the SAME full {horizon}-day window as baseline (not just the
   period after the event) — use baseline rates up to the event date, then the
   adjusted rates from the event date through the end of the window (label examples:
   "post_relocation", "new_job"). Both scenarios' predicted_demand totals must be
   directly comparable full-horizon numbers, not baseline-vs-partial-window.
3. In the life-event scenario, only change predicted_demand for the mode(s) the
   event's description plausibly and directly affects (e.g. a new long-distance
   commute affects long_distance_train, not bike_sharing or e_scooter). For every
   other mode, keep that scenario's estimated_trips/estimated_km equal to the
   baseline scenario's own figure for that mode — do not introduce a speculative
   change (up or down) to a mode the event gives no concrete reason to expect a
   change in, even a small one. When in doubt whether a mode is affected, leave it
   at the baseline figure.
4. If signals are ambiguous (confidence "low"), note this in the rationale but do NOT
   create a second scenario.
5. The basis field must briefly explain the reasoning for each mode's prediction.
6. Set life_event_detected: true and recommend_re_evaluation_in_days only when a
   life_event with high/medium confidence is present.
7. dominant_patterns and monthly_mode_breakdown both use the same raw transport-mode
   granularity (e.g. regional_train and long_distance_train are reported separately,
   never merged into one "train" figure). monthly_mode_breakdown additionally splits
   that same data by calendar month (month -> mode -> trips/distance/CO2/cost). Default
   to the average over ALL available months (not just the most recent ones) — a short
   recent uptick or dip is often seasonal noise, not a lasting trend, and only looking
   at the last few months mistakes one for the other. Only deviate from the full-history
   average when there is a genuine, strong seasonal signal: check whether the specific
   calendar month(s) the forecast window falls in were themselves unusually high/low in
   prior year(s) of monthly_mode_breakdown (e.g. this mode's data from the same months
   one year ago), and if so weight toward that seasonal figure instead of the flat
   average — but only for a clear, large deviation, not a mild one. Explain whichever
   choice you made in the basis field and rationale.
8. The payload's top-level as_of_date is today's date. Treat the {horizon}-day forecast
   window as starting from as_of_date — not from the last month in
   monthly_mode_breakdown or the earliest calendar entry — and use it to judge how
   recent monthly_mode_breakdown's months are and how near-term or far-out each
   calendar entry is.
9. Every "_en"/"_de" field pair (each scenario's description_en/description_de, and
   the top-level rationale_en/rationale_de) must be a complete, self-contained
   explanation in exactly ONE language — never mix English and German within a
   single field, never leave one empty, and never concatenate both languages into
   one field (e.g. joined by a separator). The "_en" and "_de" fields must convey
   the same content as natural translations of each other, not different text.

Respond with STRICT JSON matching the schema below — no markdown fences, no prose outside the JSON.
"""

# Prompt variant A: pre-structured CalendarEvent list
_SYSTEM_PROMPT_STRUCTURED = (
    "You are a mobility demand forecaster for Deutsche Bahn customers.\n\n"
    "Given a user's historical travel behaviour summary and a list of upcoming "
    "structured calendar events, produce a structured {horizon}-day demand forecast.\n\n"
    + _RULES + _JSON_SCHEMA
)

# Prompt variant B: raw ICS events that the LLM must first filter and classify
_SYSTEM_PROMPT_RAW_ICS = (
    "You are a mobility demand forecaster for Deutsche Bahn customers.\n\n"
    "Given a user's historical travel behaviour summary and a list of raw calendar "
    "entries (extracted from an iCalendar file), produce a structured {horizon}-day "
    "demand forecast.\n\n"
    "Before forecasting, filter the raw calendar entries:\n"
    "- KEEP: trips to other cities, events with a non-local location, life events "
    "that change commute patterns (relocation, new job, start of studies, Elternzeit).\n"
    "- DISCARD: local appointments (dentist, gym, same-city lunch), recurring "
    "admin events, anything without travel relevance.\n"
    "- Assign confidence: 'high' = explicit city + travel context, "
    "'medium' = implied travel, 'low' = vague or uncertain.\n"
    "- Mark life events (type: life_event) for: Umzug, relocation, new job, "
    "start of studies, major life change.\n\n"
    + _RULES + _JSON_SCHEMA
)


def _parse_ics(ics_text: str) -> list[dict]:
    """Parse an iCalendar string into a list of raw event dicts."""
    from icalendar import Calendar
    cal = Calendar.from_ical(ics_text)
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("DTSTART")
        date_str = ""
        if dtstart:
            dt = dtstart.dt
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        events.append({
            "summary":     str(component.get("SUMMARY", "")),
            "date":        date_str,
            "location":    str(component.get("LOCATION", "")),
            "description": str(component.get("DESCRIPTION", "")),
        })
    return events


def reason_demand(
    analyst_summary: dict,
    *,
    forecast_horizon_days: int,
    resolved_as_of_date: date,
    calendar_events: list | None = None,
    ics_text: str | None = None,
    raw_calendar_entries: list[dict] | None = None,
) -> dict | None:
    """One structured-output LLM call. Returns the parsed ``ForecastOutput`` dict, or
    ``None`` when the LLM is unavailable / the reply cannot be parsed / the call errors
    (the orchestrator then falls back to the deterministic projection)."""
    try:
        from agent.llm import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError:
        return None

    # Build prompt + payload depending on calendar input type.
    if ics_text:
        raw_events = _parse_ics(ics_text)
    elif raw_calendar_entries:
        raw_events = raw_calendar_entries
    else:
        raw_events = None

    if raw_events is not None:
        system_prompt = _SYSTEM_PROMPT_RAW_ICS.format(horizon=forecast_horizon_days)
        payload = {
            "as_of_date": resolved_as_of_date.isoformat(),
            "analyst_summary": analyst_summary,
            "raw_calendar_entries": raw_events,
            "forecast_horizon_days": forecast_horizon_days,
        }
    else:
        system_prompt = _SYSTEM_PROMPT_STRUCTURED.format(horizon=forecast_horizon_days)
        payload = {
            "as_of_date": resolved_as_of_date.isoformat(),
            "analyst_summary": analyst_summary,
            "calendar_events": calendar_events or [],
            "forecast_horizon_days": forecast_horizon_days,
        }

    try:
        response = get_llm().invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ])
        data = extract_json(response.content)
        if data:
            return ForecastOutput(**data).model_dump()
        print("[forecast] Could not parse LLM response; using deterministic fallback.")
    except Exception as exc:
        print(f"[forecast] LLM call failed ({exc}); using deterministic fallback.")
    return None


def forecast(
    analyst_summary: dict,
    calendar_events: list | None = None,
    ics_text: str | None = None,
    raw_calendar_entries: list[dict] | None = None,
    forecast_horizon_days: int = 365,
    as_of_date: str | None = None,
    use_llm: bool = True,
) -> dict:
    """Produce a demand forecast: the LLM reasoning when available, else the
    deterministic ``seasonal_projection``.

    Three calendar inputs, checked in this precedence order:
    - ``ics_text``: a raw .ics string; parsed deterministically via ``_parse_ics``.
    - ``raw_calendar_entries``: already-parsed raw entries (summary/date/location/
      description) — e.g. read from ``user_calendars`` by ``context.py``.
    - ``calendar_events``: pre-structured, pre-classified ``CalendarEvent`` dicts.

    ``as_of_date`` (ISO "YYYY-MM-DD") anchors "today" for both the LLM prompt and the
    projection's seasonal-month matching; defaults to the real current date.

    ``use_llm=False`` forces the deterministic projection and skips the LLM entirely.
    Falls back to the projection when no key is configured or the reply cannot be parsed.
    """
    resolved_as_of_date = date.fromisoformat(as_of_date) if as_of_date else datetime.now(timezone.utc).date()

    try:
        from agent.llm import llm_available
        _has_llm = llm_available()
    except ImportError:
        _has_llm = False

    if use_llm and _has_llm:
        out = reason_demand(
            analyst_summary,
            forecast_horizon_days=forecast_horizon_days,
            resolved_as_of_date=resolved_as_of_date,
            calendar_events=calendar_events,
            ics_text=ics_text,
            raw_calendar_entries=raw_calendar_entries,
        )
        if out is not None:
            return out

    return seasonal_projection(
        analyst_summary, forecast_horizon_days,
        calendar_events=calendar_events, ics_text=ics_text,
        raw_calendar_entries=raw_calendar_entries, as_of_date=resolved_as_of_date,
    )


# ---------------------------------------------------------------------------
# Mock data (for the /api/forecaster/test endpoint and direct runs)
# ---------------------------------------------------------------------------

MOCK_ANALYST_SUMMARY = {
    "dominant_patterns": [
        {"mode": "public_transport", "avg_trips_per_month": 45, "avg_distance_km": 8.5},
        {"mode": "bike_sharing", "avg_trips_per_month": 12, "avg_distance_km": 3.2},
        {"mode": "e_scooter", "avg_trips_per_month": 6, "avg_distance_km": 2.8},
    ],
    "detected_seasonality": "Higher bike usage in spring/summer, more public transport in winter",
    "current_contracts": ["Deutschlandticket (€49/mo)", "CallABike subscription"],
    "monthly_mode_breakdown": {
        "2026-05": {
            "public_transport": {"trips": 40, "distance_km": 340.0, "co2_kg": 12.0, "intrinsic_cost_eur": 120.0, "effective_cost_eur": 49.0},
            "bike_sharing": {"trips": 8, "distance_km": 25.6, "co2_kg": 0.0, "intrinsic_cost_eur": 16.0, "effective_cost_eur": 16.0},
        },
        "2026-06": {
            "public_transport": {"trips": 50, "distance_km": 425.0, "co2_kg": 15.0, "intrinsic_cost_eur": 150.0, "effective_cost_eur": 49.0},
            "bike_sharing": {"trips": 16, "distance_km": 51.2, "co2_kg": 0.0, "intrinsic_cost_eur": 32.0, "effective_cost_eur": 32.0},
            "e_scooter": {"trips": 6, "distance_km": 16.8, "co2_kg": 0.3, "intrinsic_cost_eur": 9.0, "effective_cost_eur": 9.0},
        },
    },
}

MOCK_CALENDAR_EVENTS = [
    {"date": "2026-07-15", "destination": "Munich", "transport_hint": "long_distance_train", "confidence": "high"},
    {"date": "2026-08-01", "type": "life_event", "label": "possible_relocation", "confidence": "medium"},
    {"date": "2026-09-10", "destination": "Berlin", "transport_hint": "long_distance_train", "confidence": "low"},
]


if __name__ == "__main__":
    print(json.dumps(forecast(MOCK_ANALYST_SUMMARY, MOCK_CALENDAR_EVENTS, forecast_horizon_days=90), indent=2, ensure_ascii=False))
