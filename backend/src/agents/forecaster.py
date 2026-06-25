"""LLM-powered 90-day mobility demand forecaster.

Accepts a structured analyst summary of past travel behaviour plus a list of
preprocessed calendar events. The LLM reasons over uncertainty (e.g. a possible
relocation) and produces one or more scenarios. When no API key is configured
the agent degrades gracefully to a deterministic baseline extrapolated from the
historical monthly averages supplied in the analyst summary.
"""

import json
import re
from typing import List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class DominantPattern(BaseModel):
    mode: str
    avg_trips_per_month: float
    avg_distance_km: float


class AnalystSummary(BaseModel):
    dominant_patterns: List[DominantPattern]
    detected_seasonality: str
    current_contracts: List[str]
    detected_inefficiencies: List[str]


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
        analyst_summary: dict,
        calendar_events: list | None = None,
        ics_text: str | None = None,
        forecast_horizon_days: int = 90,
    ) -> dict:
        """
        Produce a 90-day demand forecast from an analyst summary plus calendar data.

        Accepts either pre-structured ``calendar_events`` (list of CalendarEvent dicts)
        or a raw ``ics_text`` string. When ``ics_text`` is provided it takes precedence:
        the ICS is parsed deterministically and the raw entries are passed to the LLM,
        which filters for transport-relevance and classifies life events before forecasting.

        Falls back to a deterministic baseline when no API key is configured or the
        LLM response cannot be parsed.
        """
        try:
            from graph.llm import llm_available, get_llm
            from langchain_core.messages import SystemMessage, HumanMessage
            _has_llm = llm_available()
        except ImportError:
            _has_llm = False

        if not _has_llm:
            return self._deterministic_fallback(analyst_summary, forecast_horizon_days)

        # Build prompt + payload depending on calendar input type
        if ics_text:
            raw_events = _parse_ics(ics_text)
            system_prompt = _SYSTEM_PROMPT_RAW_ICS.format(horizon=forecast_horizon_days)
            payload = {
                "analyst_summary": analyst_summary,
                "raw_calendar_entries": raw_events,
                "forecast_horizon_days": forecast_horizon_days,
            }
        else:
            system_prompt = _SYSTEM_PROMPT_STRUCTURED.format(horizon=forecast_horizon_days)
            payload = {
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
            print("[ForecasterAgent] Could not parse LLM response; using deterministic fallback.")
        except Exception as exc:
            print(f"[ForecasterAgent] LLM call failed ({exc}); using deterministic fallback.")

        return self._deterministic_fallback(analyst_summary, forecast_horizon_days)

    def _deterministic_fallback(
        self, analyst_summary: dict, forecast_horizon_days: int
    ) -> dict:
        """Simple extrapolation from historical averages — no LLM required."""
        months = forecast_horizon_days / 30
        predicted = [
            PredictedDemand(
                mode=p["mode"],
                estimated_trips=int(p["avg_trips_per_month"] * months),
                estimated_km=round(
                    p["avg_distance_km"] * p["avg_trips_per_month"] * months, 1
                ),
                confidence="medium",
                basis="Historical monthly average extrapolated over the forecast period.",
            )
            for p in analyst_summary.get("dominant_patterns", [])
        ]
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
                "Based on historical monthly averages from the analyst summary."
            ),
        ).model_dump()


# ---------------------------------------------------------------------------
# Mock data
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
}

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
    result = agent.run(MOCK_ANALYST_SUMMARY, MOCK_CALENDAR_EVENTS, forecast_horizon_days=90)
    print(json.dumps(result, indent=2, ensure_ascii=False))
