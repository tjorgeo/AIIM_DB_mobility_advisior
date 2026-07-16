"""Deterministic seasonal demand projection — pure, no LLM, no network I/O.

Extrapolates a demand forecast from an analyst summary's historical monthly averages,
with a same-calendar-month prior-year seasonal override on top. This is the
deterministic baseline the whole system is guaranteed to have.

The LLM-powered demand *reasoning* that runs on top of this (reading calendar text,
detecting life events, producing adjusted scenarios) lives in
``agent/llm_steps/forecast_reasoner.py``; it falls back to this projection when no key
is configured or the model reply can't be parsed. Keeping that call out of this module
restores the ``engines`` package contract: pure functions, no LLM, no I/O.

Note: this engine forecasts *demand* (trip counts) only — never money. All euro/CO₂
figures stay in the analysis/optimization engines.
"""

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
    # month ("YYYY-MM") -> raw transport_mode -> stats for that month. Same raw
    # transport_mode granularity as dominant_patterns (regional_train and
    # long_distance_train stay distinct), but split by month instead of aggregated
    # over the whole window. Used by the full-window average plus seasonal override
    # (see _mode_full_average / _same_months_prior_year_average), which falls back to
    # the flat dominant_patterns average for any mode with no monthly data.
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
    # Bilingual, mirroring the memo (english/german) — description_en/description_de
    # must be the same content in each language, not two different texts. Consumers
    # (memo.py, PortfolioDetail.jsx) pick whichever matches the UI language.
    description_en: str
    description_de: str
    predicted_demand: List[PredictedDemand]


class UncertaintyFlags(BaseModel):
    life_event_detected: bool
    life_event_type: Optional[str] = None
    recommend_re_evaluation_in_days: Optional[int] = None


class ForecastOutput(BaseModel):
    forecast_horizon_days: int
    scenarios: List[Scenario]
    uncertainty_flags: UncertaintyFlags
    rationale_en: str
    rationale_de: str


# ---------------------------------------------------------------------------
# Deterministic projection
# ---------------------------------------------------------------------------

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


def seasonal_projection(
    analyst_summary: dict,
    forecast_horizon_days: int,
    calendar_events: list | None = None,
    ics_text: str | None = None,
    raw_calendar_entries: list | None = None,
    as_of_date: str | date | None = None,
) -> dict:
    """Extrapolation from historical averages — no LLM required.

    For each mode, defaults to the average over ALL available months in
    monthly_mode_breakdown (up to 12, or however many exist) rather than a short
    recent window — a brief recent uptick/dip is often seasonal noise or a blip, not
    a lasting trend, and a short window can't tell the difference. Falls back to the
    flat dominant_patterns average when a mode has no monthly data at all (e.g. an
    older caller that only supplies dominant_patterns).

    On top of that full-history average, checks for a genuine seasonal signal: if the
    specific calendar month(s) the forecast window covers were themselves unusually
    high/low in prior year(s) (``_same_months_prior_year_average``), and that deviates
    from the flat full-history average by at least ``_SEASONAL_DEVIATION_THRESHOLD``,
    the seasonal figure is used instead — so a real December peak or June trough is
    reflected, without every month-to-month wiggle being mistaken for one.

    Calendar data (any of the three params) is deliberately NOT used to adjust the
    numbers here — detecting life events or trip-specific demand from calendar text
    requires the LLM reasoning step. Rather than silently dropping it, if any calendar
    data was supplied this is called out explicitly in the rationale.

    ``as_of_date`` accepts an ISO "YYYY-MM-DD" string, a ``date``, or ``None`` (=today).
    """
    if isinstance(as_of_date, str):
        as_of_date = date.fromisoformat(as_of_date)
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).date()
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

    rationale_en = (
        "Deterministic fallback: LLM not available. Each mode uses the average over "
        "all available months of data, overridden by a same-calendar-month prior-year "
        "average where that reveals a strong seasonal signal (>="
        f"{_SEASONAL_DEVIATION_THRESHOLD:.0%} deviation from the flat average)."
    )
    rationale_de = (
        "Deterministischer Fallback: Kein LLM verfügbar. Jedes Verkehrsmittel nutzt den "
        "Durchschnitt über alle verfügbaren Monate, überschrieben durch einen "
        "Vorjahres-Durchschnitt für dieselben Kalendermonate, wenn dieser ein starkes "
        f"saisonales Signal zeigt (>={_SEASONAL_DEVIATION_THRESHOLD:.0%} Abweichung vom "
        "Durchschnitt)."
    )
    if calendar_supplied:
        rationale_en += (
            " Upcoming calendar entries were supplied but not analyzed — detecting life "
            "events or trip-specific demand from calendar data requires an LLM; re-run "
            "once one is configured to factor these in."
        )
        rationale_de += (
            " Bevorstehende Kalendereinträge wurden übermittelt, aber nicht analysiert — "
            "die Erkennung von Lebensereignissen oder fahrtspezifischer Nachfrage aus "
            "Kalenderdaten erfordert ein LLM; erneut ausführen, sobald eines konfiguriert "
            "ist, um diese zu berücksichtigen."
        )

    return ForecastOutput(
        forecast_horizon_days=forecast_horizon_days,
        scenarios=[
            Scenario(
                label="baseline",
                description_en=(
                    "Forecast derived from historical averages across the full available "
                    "history, adjusted for strong seasonal signals where present (LLM not "
                    "configured — deterministic fallback)."
                ),
                description_de=(
                    "Prognose basierend auf historischen Durchschnittswerten über den "
                    "gesamten verfügbaren Zeitraum, angepasst an starke saisonale Signale, "
                    "sofern vorhanden (kein LLM konfiguriert — deterministischer Fallback)."
                ),
                predicted_demand=predicted,
            )
        ],
        uncertainty_flags=UncertaintyFlags(life_event_detected=False),
        rationale_en=rationale_en,
        rationale_de=rationale_de,
    ).model_dump()
