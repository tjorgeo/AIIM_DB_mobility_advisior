"""LLM-powered 90-day mobility demand forecaster.

Accepts a structured analyst summary of past travel behaviour plus a list of
preprocessed calendar events. The LLM reasons over uncertainty (e.g. a possible
relocation) and produces one or more scenarios. When no API key is configured the
engine degrades gracefully to a deterministic baseline extrapolated from the
historical monthly averages in the analyst summary.

Note: this is the one engine permitted to call the LLM — it forecasts *demand*
(trip counts), not money. All euro/CO₂ figures stay in the strictly deterministic
analysis/optimization engines. The forecaster always has a deterministic fallback,
so /analyze remains reproducible when no key is set.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class DominantPattern(BaseModel):
    mode: str
    avg_trips_per_month: float
    avg_distance_km: float


class MonthlyModeStat(BaseModel):
    trips: int
    distance_km: float
    co2_kg: float
    intrinsic_cost_eur: float
    effective_cost_eur: float


class AnalystSummary(BaseModel):
    dominant_patterns: List[DominantPattern]
    detected_seasonality: str
    current_contracts: List[str]
    detected_inefficiencies: List[str]
    # month ("YYYY-MM") -> raw transport_mode -> stats for that month. Same raw
    # transport_mode granularity as dominant_patterns (regional_train and
    # long_distance_train stay distinct), but split by month instead of
    # aggregated over the whole window. Used both for LLM-side reasoning (see
    # _RULES) and by the deterministic fallback's full-window average plus
    # seasonal override (see _mode_full_average / _same_months_prior_year_average),
    # which falls back to the flat dominant_patterns average for any mode with no
    # monthly data.
    monthly_mode_breakdown: Dict[str, Dict[str, MonthlyModeStat]] = {}


class CalendarEvent(BaseModel):
    date: str
    destination: Optional[str] = None
    transport_hint: Optional[str] = None
    type: Optional[str] = None
    label: Optional[str] = None
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class PredictedDemand(BaseModel):
    mode: str
    estimated_trips: int
    estimated_km: float
    confidence: Literal["high", "medium", "low"]
    basis: str


class Scenario(BaseModel):
    label: str
    description: str
    predicted_demand: List[PredictedDemand]


class UncertaintyFlags(BaseModel):
    life_event_detected: bool
    life_event_type: Optional[str] = None
    recommend_re_evaluation_in_days: Optional[int] = None


class ForecastOutput(BaseModel):
    forecast_horizon_days: int
    scenarios: List[Scenario]
    uncertainty_flags: UncertaintyFlags
    rationale: str


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_JSON_SCHEMA = """\
{{
  "forecast_horizon_days": <int>,
  "scenarios": [
    {{
      "label": <str>,
      "description": <str>,
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
  "rationale": <str>
}}"""

_RULES = """\
Rules:
1. Always include a "baseline" scenario derived from the historical patterns.
2. If a life_event with confidence "medium" or "high" is present, produce a SECOND
   scenario that accounts for the change (label examples: "post_relocation", "new_job").
3. If signals are ambiguous (confidence "low"), note this in the rationale but do NOT
   create a second scenario.
4. The basis field must briefly explain the reasoning for each mode's prediction.
5. Set life_event_detected: true and recommend_re_evaluation_in_days only when a
   life_event with high/medium confidence is present.
6. dominant_patterns and monthly_mode_breakdown both use the same raw transport-mode
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
7. The payload's top-level as_of_date is today's date. Treat the {horizon}-day forecast
   window as starting from as_of_date — not from the last month in
   monthly_mode_breakdown or the earliest calendar entry — and use it to judge how
   recent monthly_mode_breakdown's months are and how near-term or far-out each
   calendar entry is.

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


def _extract_json(text: str):
    """Pull the first complete JSON object out of an LLM reply (tolerates prose or
    ```json fences before/after it). Uses raw_decode from the first ``{`` so it stops
    at that object's actual matching closing brace, instead of a greedy regex that
    would span to the *last* ``}`` in the whole text if any stray braces follow."""
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


# A calendar month's historical average must deviate from the mode's flat full-history
# average by at least this fraction for the seasonal-override branch to kick in — a
# mild difference is treated as noise, not a real seasonal pattern.
_SEASONAL_DEVIATION_THRESHOLD = 0.20
_MIN_MONTHS_FOR_MEDIUM_CONFIDENCE = 3


def _mode_full_average(mode: str, monthly_mode_breakdown: dict):
    """Average trips/month and avg distance/trip for ``mode`` over EVERY calendar
    month present in ``monthly_mode_breakdown`` (up to 12, or however many are
    actually available) — not just a recent window. Months without any recorded
    trips for this mode are absent from the dict entirely (not zero-filled), so this
    naturally skips gaps.

    Using the full window rather than a short recent slice avoids mistaking a
    seasonal uptick/dip (or a noisy couple of months) for a lasting trend; see
    ``_same_months_prior_year_average`` for the seasonal override that runs on top.

    Returns ``(avg_trips_per_month, avg_distance_km_per_trip, months_used)``, or
    ``None`` if the mode never appears in ``monthly_mode_breakdown`` at all.
    """
    months_with_mode = sorted(
        month for month, modes in monthly_mode_breakdown.items() if mode in modes
    )
    if not months_with_mode:
        return None
    total_trips = sum(monthly_mode_breakdown[m][mode]["trips"] for m in months_with_mode)
    total_distance = sum(monthly_mode_breakdown[m][mode]["distance_km"] for m in months_with_mode)
    avg_trips_per_month = total_trips / len(months_with_mode)
    avg_distance_per_trip = total_distance / max(total_trips, 1)
    return avg_trips_per_month, avg_distance_per_trip, len(months_with_mode)


def _forecast_target_months(as_of_date: date, forecast_horizon_days: int) -> set:
    """Calendar month numbers (1-12) that the forecast window
    ``[as_of_date, as_of_date + forecast_horizon_days]`` actually spans."""
    end_date = as_of_date + timedelta(days=forecast_horizon_days)
    months = set()
    year, month = as_of_date.year, as_of_date.month
    while (year, month) <= (end_date.year, end_date.month):
        months.add(month)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _same_months_prior_year_average(mode: str, monthly_mode_breakdown: dict, target_months: set):
    """Average trips/month and avg distance/trip for ``mode``, restricted to the
    calendar months in ``target_months`` (matched by month number, across however
    many prior years of data exist for those specific months) — i.e. "what did this
    mode typically do in these exact calendar months, historically".

    Returns ``(avg_trips_per_month, avg_distance_km_per_trip, months_matched)``, or
    ``None`` if no data exists for any of those calendar months.
    """
    matched = sorted(
        month
        for month, modes in monthly_mode_breakdown.items()
        if mode in modes and int(month.split("-")[1]) in target_months
    )
    if not matched:
        return None
    total_trips = sum(monthly_mode_breakdown[m][mode]["trips"] for m in matched)
    total_distance = sum(monthly_mode_breakdown[m][mode]["distance_km"] for m in matched)
    avg_trips_per_month = total_trips / len(matched)
    avg_distance_per_trip = total_distance / max(total_trips, 1)
    return avg_trips_per_month, avg_distance_per_trip, len(matched)


def _deterministic_fallback(
    analyst_summary: dict,
    forecast_horizon_days: int,
    calendar_events: list | None = None,
    ics_text: str | None = None,
    raw_calendar_entries: list | None = None,
    as_of_date: date | None = None,
) -> dict:
    """Extrapolation from historical averages — no LLM required.

    For each mode, defaults to the average over ALL available months in
    monthly_mode_breakdown (up to 12, or however many exist) rather than a short
    recent window — a brief recent uptick/dip is often seasonal noise or a blip, not
    a lasting trend, and a short window can't tell the difference. Falls back to the
    flat dominant_patterns average when a mode has no monthly data at all (e.g. an
    older caller that only supplies dominant_patterns).

    On top of that full-history average, checks for a genuine seasonal signal: if
    the specific calendar month(s) the forecast window covers were themselves
    unusually high/low in prior year(s) (``_same_months_prior_year_average``), and
    that deviates from the flat full-history average by at least
    ``_SEASONAL_DEVIATION_THRESHOLD``, the seasonal figure is used instead — so a
    real December peak or June trough is reflected, without every month-to-month
    wiggle in the recent data being mistaken for one.

    Calendar data (any of the three params) is deliberately NOT used to adjust the
    numbers here — detecting life events or trip-specific demand from calendar text
    requires semantic reasoning only the LLM path does. Rather than silently
    dropping it, if any calendar data was supplied this is called out explicitly in
    the rationale, so the gap is visible instead of silent.
    """
    as_of_date = as_of_date or datetime.now(timezone.utc).date()
    months = forecast_horizon_days / 30
    monthly_mode_breakdown = analyst_summary.get("monthly_mode_breakdown", {})
    target_months = _forecast_target_months(as_of_date, forecast_horizon_days)
    calendar_supplied = bool(calendar_events or ics_text or raw_calendar_entries)

    predicted = []
    for p in analyst_summary.get("dominant_patterns", []):
        mode = p["mode"]
        full = _mode_full_average(mode, monthly_mode_breakdown)

        if full is None:
            avg_trips_per_month = p["avg_trips_per_month"]
            avg_distance_per_trip = p["avg_distance_km"]
            confidence = "medium"
            basis = "Historical monthly average extrapolated over the forecast period."
        else:
            avg_trips_per_month, avg_distance_per_trip, months_used = full
            confidence = "medium" if months_used >= _MIN_MONTHS_FOR_MEDIUM_CONFIDENCE else "low"
            basis = (
                f"Average of all {months_used} available month(s) of {mode} data, "
                "extrapolated over the forecast period."
            )

            seasonal = _same_months_prior_year_average(mode, monthly_mode_breakdown, target_months)
            if seasonal is not None:
                seasonal_trips, seasonal_distance, matched_months = seasonal
                deviation = abs(seasonal_trips - avg_trips_per_month) / max(avg_trips_per_month, 1e-9)
                if deviation >= _SEASONAL_DEVIATION_THRESHOLD:
                    basis = (
                        f"Full-history average ({avg_trips_per_month:.1f} trips/month) overridden: "
                        f"the {matched_months} historical month(s) matching this forecast's own "
                        f"calendar month(s) average {seasonal_trips:.1f} trips/month for {mode} "
                        f"({deviation:.0%} away from the flat average) — a strong enough seasonal "
                        "signal to use instead of the flat average."
                    )
                    avg_trips_per_month, avg_distance_per_trip = seasonal_trips, seasonal_distance

        predicted.append(
            PredictedDemand(
                mode=mode,
                estimated_trips=int(avg_trips_per_month * months),
                estimated_km=round(avg_distance_per_trip * avg_trips_per_month * months, 1),
                confidence=confidence,
                basis=basis,
            )
        )

    rationale = (
        "Deterministic fallback: LLM not available. Each mode uses the average over "
        "all available months of data, overridden by a same-calendar-month prior-year "
        "average where that reveals a strong seasonal signal (>="
        f"{_SEASONAL_DEVIATION_THRESHOLD:.0%} deviation from the flat average)."
    )
    if calendar_supplied:
        rationale += (
            " Upcoming calendar entries were supplied but not analyzed — detecting life "
            "events or trip-specific demand from calendar data requires an LLM; re-run "
            "once one is configured to factor these in."
        )

    return ForecastOutput(
        forecast_horizon_days=forecast_horizon_days,
        scenarios=[
            Scenario(
                label="baseline",
                description=(
                    "Forecast derived from historical averages across the full available "
                    "history, adjusted for strong seasonal signals where present (LLM not "
                    "configured — deterministic fallback)."
                ),
                predicted_demand=predicted,
            )
        ],
        uncertainty_flags=UncertaintyFlags(life_event_detected=False),
        rationale=rationale,
    ).model_dump()


def forecast(
    analyst_summary: dict,
    calendar_events: list | None = None,
    ics_text: str | None = None,
    raw_calendar_entries: list[dict] | None = None,
    forecast_horizon_days: int = 90,
    as_of_date: str | None = None,
    use_llm: bool = True,
) -> dict:
    """
    Produce a 90-day demand forecast from an analyst summary plus calendar data.

    Three calendar inputs, checked in this precedence order:
    - ``ics_text``: a raw .ics string; parsed deterministically via ``_parse_ics``
      into raw entries (summary/date/location/description).
    - ``raw_calendar_entries``: already-parsed raw entries in that same shape —
      e.g. read directly from the ``user_calendars`` table by ``context.py`` —
      skips ICS parsing entirely.
    - ``calendar_events``: pre-structured, pre-classified ``CalendarEvent`` dicts
      (date/destination/transport_hint/confidence).

    Whichever raw-entry source is used (``ics_text`` or ``raw_calendar_entries``),
    the LLM itself filters for transport-relevance and classifies life events
    before forecasting (see ``_SYSTEM_PROMPT_RAW_ICS``). ``calendar_events`` is for
    callers that have already done that classification themselves.

    ``as_of_date`` (ISO "YYYY-MM-DD") anchors "today" for both the LLM prompt and
    the deterministic fallback's seasonal-month matching — it defaults to the real
    current date, and only needs overriding for tests/experiments (e.g. simulating
    "today" as a different month to check the seasonal-override logic against
    historical data without waiting for the calendar to get there).

    Falls back to a deterministic baseline when no API key is configured or the LLM
    response cannot be parsed.

    ``use_llm=False`` forces the deterministic fallback and skips the LLM call entirely —
    used on the synchronous ``/api/analyze`` fast path so the response isn't blocked on a
    forecaster round-trip; the LLM forecast is regenerated later in the background (see
    ``orchestrator.Orchestrator.generate_memo``).
    """
    resolved_as_of_date = date.fromisoformat(as_of_date) if as_of_date else datetime.now(timezone.utc).date()

    try:
        from agent.llm import llm_available, get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        _has_llm = llm_available()
    except ImportError:
        _has_llm = False

    if not use_llm or not _has_llm:
        return _deterministic_fallback(
            analyst_summary, forecast_horizon_days,
            calendar_events=calendar_events, ics_text=ics_text,
            raw_calendar_entries=raw_calendar_entries, as_of_date=resolved_as_of_date,
        )

    # Build prompt + payload depending on calendar input type
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
        data = _extract_json(response.content)
        if data:
            return ForecastOutput(**data).model_dump()
        print("[forecast] Could not parse LLM response; using deterministic fallback.")
    except Exception as exc:
        print(f"[forecast] LLM call failed ({exc}); using deterministic fallback.")

    return _deterministic_fallback(
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
    "detected_inefficiencies": [
        "E-scooter trips without subscription coverage (€45/year out-of-pocket)"
    ],
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
