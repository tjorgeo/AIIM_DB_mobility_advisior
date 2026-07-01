"""LLM-powered 90-day mobility demand forecaster.

Accepts a month-by-month usage breakdown from the analyst (last 12 months,
one entry per calendar month, each with per-mode trip counts and average trip
distances) plus optional calendar events. The LLM reasons over trends,
seasonality, and calendar signals to produce one or more demand scenarios.
When no API key is configured the agent degrades gracefully to a deterministic
baseline extrapolated from the historical monthly averages.
"""

import json
import re
from collections import defaultdict
from typing import List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

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
    """Pull the first JSON object out of an LLM reply (handles ```json fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ForecasterAgent:
    def run(
        self,
        monthly_mode_breakdown: list,
        calendar_events: list | None = None,
        ics_text: str | None = None,
        forecast_horizon_days: int = 90,
    ) -> dict:
        """
        Produce a 90-day demand forecast from the analyst's monthly mode breakdown.

        ``monthly_mode_breakdown`` is a list of monthly entries (chronological),
        each with the shape::

            {"month": "2025-07", "modes": {"train": {"trips": 18, "avg_distance_km": 210.3}, ...}}

        Accepts either pre-structured ``calendar_events`` or a raw ``ics_text`` string.
        Falls back to a deterministic baseline when no LLM is configured.
        """
        try:
            from graph.llm import llm_available, get_llm
            from langchain_core.messages import SystemMessage, HumanMessage
            _has_llm = llm_available()
        except ImportError:
            _has_llm = False

        if not _has_llm:
            return self._deterministic_fallback(monthly_mode_breakdown, forecast_horizon_days)

        if ics_text:
            raw_events = _parse_ics(ics_text)
            system_prompt = _SYSTEM_PROMPT_RAW_ICS.format(horizon=forecast_horizon_days)
            payload = {
                "monthly_mode_breakdown": monthly_mode_breakdown,
                "raw_calendar_entries": raw_events,
                "forecast_horizon_days": forecast_horizon_days,
            }
        else:
            system_prompt = _SYSTEM_PROMPT_STRUCTURED.format(horizon=forecast_horizon_days)
            payload = {
                "monthly_mode_breakdown": monthly_mode_breakdown,
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
            print("[ForecasterAgent] Could not parse LLM response; using deterministic fallback.")
        except Exception as exc:
            print(f"[ForecasterAgent] LLM call failed ({exc}); using deterministic fallback.")

        return self._deterministic_fallback(monthly_mode_breakdown, forecast_horizon_days)

    def _deterministic_fallback(
        self, monthly_mode_breakdown: list, forecast_horizon_days: int
    ) -> dict:
        """Extrapolate per-mode averages across all observed months."""
        months_forecast = forecast_horizon_days / 30
        n_months = len(monthly_mode_breakdown) or 1

        # Accumulate totals across all months
        mode_trips: dict[str, int] = defaultdict(int)
        mode_distance: dict[str, float] = defaultdict(float)
        for entry in monthly_mode_breakdown:
            for mode, stats in entry.get("modes", {}).items():
                mode_trips[mode] += stats["trips"]
                mode_distance[mode] += stats["avg_distance_km"] * stats["trips"]

        predicted = []
        for mode in sorted(mode_trips, key=lambda m: -mode_trips[m]):
            total = mode_trips[mode]
            avg_trips_per_month = total / n_months
            avg_dist = (mode_distance[mode] / total) if total else 0.0
            predicted.append(PredictedDemand(
                mode=mode,
                estimated_trips=int(round(avg_trips_per_month * months_forecast)),
                estimated_km=round(avg_dist * avg_trips_per_month * months_forecast, 1),
                confidence="medium",
                basis="Historical monthly average extrapolated over the forecast period.",
            ))

        return ForecastOutput(
            forecast_horizon_days=forecast_horizon_days,
            scenarios=[
                Scenario(
                    label="baseline",
                    description=(
                        "Forecast derived from historical averages "
                        "(LLM not configured — deterministic fallback)."
                    ),
                    predicted_demand=predicted,
                )
            ],
            uncertainty_flags=UncertaintyFlags(life_event_detected=False),
            rationale=(
                "Deterministic fallback: LLM not available. "
                "Based on historical monthly averages from the analyst."
            ),
        ).model_dump()


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_MONTHLY_MODE_BREAKDOWN = [
    {"month": "2025-07", "modes": {"public_transport": {"trips": 42, "avg_distance_km": 8.2}, "bike_sharing": {"trips": 10, "avg_distance_km": 3.1}}},
    {"month": "2025-08", "modes": {"public_transport": {"trips": 35, "avg_distance_km": 8.5}, "bike_sharing": {"trips": 14, "avg_distance_km": 3.4}}},
    {"month": "2025-09", "modes": {"public_transport": {"trips": 44, "avg_distance_km": 8.1}, "bike_sharing": {"trips": 11, "avg_distance_km": 3.0}}},
    {"month": "2025-10", "modes": {"public_transport": {"trips": 48, "avg_distance_km": 7.9}, "bike_sharing": {"trips": 8, "avg_distance_km": 2.9}}},
    {"month": "2025-11", "modes": {"public_transport": {"trips": 46, "avg_distance_km": 8.0}}},
    {"month": "2025-12", "modes": {"public_transport": {"trips": 38, "avg_distance_km": 8.3}}},
    {"month": "2026-01", "modes": {"public_transport": {"trips": 45, "avg_distance_km": 8.1}}},
    {"month": "2026-02", "modes": {"public_transport": {"trips": 44, "avg_distance_km": 8.2}}},
    {"month": "2026-03", "modes": {"public_transport": {"trips": 47, "avg_distance_km": 8.0}, "bike_sharing": {"trips": 6, "avg_distance_km": 3.0}}},
    {"month": "2026-04", "modes": {"public_transport": {"trips": 46, "avg_distance_km": 8.1}, "bike_sharing": {"trips": 9, "avg_distance_km": 3.2}}},
    {"month": "2026-05", "modes": {"public_transport": {"trips": 45, "avg_distance_km": 8.2}, "bike_sharing": {"trips": 12, "avg_distance_km": 3.3}}},
    {"month": "2026-06", "modes": {"public_transport": {"trips": 40, "avg_distance_km": 8.4}, "bike_sharing": {"trips": 13, "avg_distance_km": 3.5}}},
]

MOCK_CALENDAR_EVENTS = [
    {
        "date": "2026-07-15",
        "destination": "Munich",
        "transport_hint": "long_distance_train",
        "confidence": "high",
    },
    {
        "date": "2026-08-01",
        "type": "life_event",
        "label": "possible_relocation",
        "confidence": "medium",
    },
    {
        "date": "2026-09-10",
        "destination": "Berlin",
        "transport_hint": "long_distance_train",
        "confidence": "low",
    },
]


if __name__ == "__main__":
    import sys
    import os

    # Allow `from graph.llm import ...` when running this file directly
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    agent = ForecasterAgent()
    result = agent.run(MOCK_MONTHLY_MODE_BREAKDOWN, MOCK_CALENDAR_EVENTS, forecast_horizon_days=90)
    print(json.dumps(result, indent=2, ensure_ascii=False))
