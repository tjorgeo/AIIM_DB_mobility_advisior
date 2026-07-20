"""Deterministic consultation memo — the template fallback.

Pure function, no LLM. When an LLM is configured the pipeline replaces the prose
with an LLM-written version, but this template always produces a valid memo (and
the structured fields the frontend reads) so the app works without a key.

Built from ``analyze_portfolio``'s ``category_subscription_analysis`` — one line per
travel category, saying whether the currently-held subscription (if any) pays off,
whether a cheaper alternative exists, or whether pay-as-you-go is already the
cheapest option. Each category stands on its own, since that's the level at which the
underlying numbers are actually comparable (see analysis.py's ``_pricing_basis``).

Optionally also folds in one forward-looking caveat per category from the
forecaster's life-event scenario (``forecast()``'s ``projected_category_analysis``,
see analysis.py's ``project_category_subscription_analysis``) when that scenario's
projected verdict differs from today's — purely textual, never changes
``actions_required``/``total_estimated_savings_eur``, which stay grounded in the
historical verdict only.

On top of those inline caveats, the memo ends with a standalone "Looking ahead"
section (``_forecast_outlook_section``) built purely from the forecaster: any
detected life event, the behaviour shift it implies (baseline vs. life-event
scenario ``predicted_demand``), and whether that would change today's subscription
advice. Same rule applies — it's presented as a heads-up for later, never blended
into ``actions_required``/``total_estimated_savings_eur``.
"""

_CATEGORY_LABEL_EN = {
    "public_transport": "Public transport",
    "long_distance_rail": "Long-distance rail",
    "bike_sharing": "Bike sharing",
    "car_sharing": "Car sharing",
    "e_scooter": "E-scooter",
}
_CATEGORY_LABEL_DE = {
    "public_transport": "Öffentlicher Nahverkehr",
    "long_distance_rail": "Fernverkehr",
    "bike_sharing": "Bike-Sharing",
    "car_sharing": "Car-Sharing",
    "e_scooter": "E-Scooter",
}

# "public_transport" (local buses/trams + regional trains — Deutschlandticket
# territory) and "long_distance_rail" (long-distance trains only — BahnCard
# territory) are two independent categories that happen to share a DB catalog
# category (see analysis.py's category_subscription_analysis docstring). Both are
# genuinely worth holding at once — naming which modes each one's price covers
# keeps the memo from implying one replaces the other.
_MODE_LABEL_EN = {
    "public_transport": "local buses/trams",
    "regional_train": "regional trains",
    "long_distance_train": "long-distance trains",
}
_MODE_LABEL_DE = {
    "public_transport": "lokale Busse/Bahnen",
    "regional_train": "Regionalzüge",
    "long_distance_train": "Fernzüge",
}
_MODES_WORTH_NAMING = {"public_transport", "long_distance_rail"}

# Categories where a subscription ties the customer to one specific operator's own
# fleet — unlike public_transport/long_distance_rail (any operator's vehicle on the
# line works), a bike/car/e-scooter subscription only pays off if that provider
# actually has a vehicle parked nearby when needed. Worth flagging whenever we
# recommend moving to a new provider (switch_to_alternative / consider_subscribing).
_PROVIDER_DEPENDENCY_CATEGORIES = {"bike_sharing", "car_sharing", "e_scooter"}
_VEHICLE_NOUN_EN = {"bike_sharing": "bike", "car_sharing": "car", "e_scooter": "scooter"}
_VEHICLE_NOUN_DE = {"bike_sharing": "Fahrrad", "car_sharing": "Auto", "e_scooter": "Scooter"}

# Every raw transport mode the forecaster can predict demand for (see
# forecasting.py's DominantPattern/PredictedDemand) — broader than _MODE_LABEL_EN/DE
# above, which only cover the two modes worth disambiguating within a shared
# catalog category. Falls back to a humanized mode string for anything unlisted.
_ALL_MODE_LABEL_EN = {
    "public_transport": "local public transport",
    "regional_train": "regional trains",
    "long_distance_train": "long-distance trains",
    "bike_sharing": "bike sharing",
    "car_sharing": "car sharing",
    "e_scooter": "e-scooters",
}
_ALL_MODE_LABEL_DE = {
    "public_transport": "lokaler ÖPNV",
    "regional_train": "Regionalzüge",
    "long_distance_train": "Fernzüge",
    "bike_sharing": "Bike-Sharing",
    "car_sharing": "Car-Sharing",
    "e_scooter": "E-Scooter",
}

# A mode's projected trip count must move by at least this fraction between the
# baseline and life-event scenarios to be called out as a behaviour change — a
# mild wobble isn't worth putting in front of the customer.
_DEMAND_CHANGE_THRESHOLD = 0.15
_MAX_BEHAVIOR_CHANGE_LINES = 4

# uncertainty_flags.life_event_type is free text from the forecaster LLM (see
# forecasting.py's _RULES: "relocation", "new_job", "start_of_studies", "Elternzeit",
# "major_life_change" are the named examples, but nothing enforces exactly these
# strings). A natural-language noun for the common ones reads far better in a
# sentence than either the raw type or a raw scenario label like "post_relocation".
#
# English needs no article agreement ("an upcoming X" — the "an" attaches to
# "upcoming", not to X). German does — "ein bevorstehender Umzug" (masc.) vs. "eine
# bevorstehende Elternzeit" (fem.) — so the German table stores the full
# "ein/eine <noun>" phrase (no adjective baked in, so it composes into different
# sentence frames), and the neuter "ein Ereignis" fallback sidesteps having to guess
# an unknown noun's gender.
_LIFE_EVENT_NOUN_EN = {
    "relocation": "relocation",
    "new_job": "new job",
    "start_of_studies": "start of studies",
    "parental_leave": "parental leave",
    "elternzeit": "parental leave",
    "major_life_change": "life change",
}
_LIFE_EVENT_ARTICLE_NOUN_DE = {
    "relocation": "ein Umzug",
    "new_job": "ein Jobwechsel",
    "start_of_studies": "ein Studienbeginn",
    "parental_leave": "eine Elternzeit",
    "elternzeit": "eine Elternzeit",
    "major_life_change": "eine größere Veränderung",
}


def _mode_label(mode: str, lang: str) -> str:
    labels = _ALL_MODE_LABEL_EN if lang == "en" else _ALL_MODE_LABEL_DE
    return labels.get(mode, mode.replace("_", " "))


def _life_event_noun(life_event_type: str | None, lang: str) -> str:
    """English noun for the life event (no article needed — see module note)."""
    key = (life_event_type or "").strip().lower()
    fallback = (life_event_type or "life event").replace("_", " ") if lang == "en" else ""
    if lang == "en":
        return _LIFE_EVENT_NOUN_EN.get(key, fallback)
    return _life_event_article_noun_de(life_event_type)


def _life_event_article_noun_de(life_event_type: str | None) -> str:
    """German "ein/eine <noun>" phrase, gender-agreed — see module note above."""
    key = (life_event_type or "").strip().lower()
    if key in _LIFE_EVENT_ARTICLE_NOUN_DE:
        return _LIFE_EVENT_ARTICLE_NOUN_DE[key]
    # No markdown here — callers wrap this in their own ** — nesting a second pair
    # around the parenthetical would render as literal asterisks.
    humanized = (life_event_type or "").replace("_", " ")
    return f"ein Ereignis ({humanized})" if humanized else "ein Ereignis"


def _with_provider_dependency_note(text: str, category: str, alt_name: str, lang: str) -> str:
    """Appends a short subordinate clause — not a new sentence — flagging that a new
    bike/car/e-scooter provider ties the customer to that operator's own fleet, so
    they're less flexible than pay-as-you-go across providers (a nearby vehicle from
    THAT provider has to actually be available). A no-op for every other category,
    where any operator's vehicle on the line works just as well. ``text`` is assumed
    to end in a period, as every ``_category_line`` branch's text does."""
    if category not in _PROVIDER_DEPENDENCY_CATEGORIES:
        return text
    vehicle = (_VEHICLE_NOUN_EN if lang == "en" else _VEHICLE_NOUN_DE)[category]
    if lang == "en":
        clause = (
            f", though this ties you to {alt_name} specifically — worth keeping in "
            f"mind that a {vehicle} needs to actually be available nearby with them, "
            "so you're somewhat less flexible than with pay-as-you-go across providers"
        )
    else:
        clause = (
            f", wobei man dadurch an {alt_name} gebunden ist — ein {vehicle} muss "
            "dann auch tatsächlich in der Nähe verfügbar sein, man ist also etwas "
            "weniger flexibel als bei Einzelfahrten anbieterübergreifend"
        )
    return text[:-1] + clause + "."


def _current_names(entry: dict) -> str:
    names = [c["provider_plan_name"] for c in entry["current_subscriptions"] if c.get("provider_plan_name")]
    return " + ".join(names) if names else "no subscription"


def _coverage_note(entry: dict, lang: str) -> str:
    """A short parenthetical naming exactly which trip legs this category's plans
    apply to. Only shown for public_transport/long_distance_rail (see module comment
    above) — other categories map 1:1 to a single raw mode, nothing to disambiguate."""
    if entry["category"] not in _MODES_WORTH_NAMING:
        return ""
    applies_to_modes = entry.get("applies_to_modes") or []
    if not applies_to_modes:
        return ""
    labels = _MODE_LABEL_EN if lang == "en" else _MODE_LABEL_DE
    joined = ", ".join(labels.get(m, m) for m in applies_to_modes)
    return f" (covers {joined})" if lang == "en" else f" (deckt ab: {joined})"


def _category_line(entry: dict, lang: str, include_label: bool = True) -> tuple[str, float]:
    """One sentence describing the verdict for a single category, plus the
    estimated annual savings implied by that verdict (0.0 if the verdict is
    "nothing to change").

    ``include_label=False`` renders just the verdict phrase, dropping the leading
    "**Category:**" prefix — used to fold a forecast scenario's projected verdict for
    the same category into a caveat line without repeating the label the historical
    line already showed (see ``_forecast_caveat_line`` below).
    """
    en = lang == "en"
    label = (_CATEGORY_LABEL_EN if en else _CATEGORY_LABEL_DE)[entry["category"]]
    rec = entry["recommendation"]
    current = _current_names(entry)
    note = _coverage_note(entry, lang)
    prefix_with_note = f"**{label}{note}:** " if include_label else ""
    prefix_plain = f"**{label}:** " if include_label else ""
    # The scoring winner (cost+CO2+time), not necessarily the cheapest plan on file —
    # see analysis.py's recommended_alternative vs. cheapest_alternative distinction.
    # Falls back to cheapest_alternative for older persisted rows computed before that
    # field existed.
    alt = entry.get("recommended_alternative") or entry.get("cheapest_alternative")
    alt_name = alt["provider_plan_name"] if alt else None

    if rec == "keep_current":
        savings = 0.0
        text = (
            f"{prefix_with_note}{current} pays off — it's cheaper than paying as you go, so keep it."
            if en else
            f"{prefix_with_note}{current} lohnt sich — günstiger als Einzelfahrscheine, also behalten."
        )
    elif rec == "switch_to_alternative" and entry.get("actual_annual_cost_eur") is None:
        # Only reachable via a forecast scenario's projected_category_analysis: the
        # currently-held plan's pricing model needs per-leg duration/day data this
        # scenario doesn't forecast (see analysis.py's actual_annual_cost_note), so
        # there's no current-vs-alternative delta to state — say so instead of
        # crashing on None arithmetic or inventing a number.
        savings = 0.0
        text = (
            f"{prefix_with_note}{alt_name} looks cheaper than {current}, though {current}'s exact "
            f"cost can't be projected here, so the savings aren't quantifiable yet ({alt['pricing_basis']})."
            if en else
            f"{prefix_with_note}{alt_name} wirkt günstiger als {current}, die genauen Kosten von "
            f"{current} lassen sich hier aber nicht projizieren — die Ersparnis ist daher noch nicht "
            f"bezifferbar ({alt['pricing_basis']})."
        )
        text = _with_provider_dependency_note(text, entry["category"], alt_name, lang)
    elif rec == "switch_to_alternative":
        savings = round(entry["actual_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2)
        text = (
            f"{prefix_with_note}switching from {current} to {alt_name} could save an "
            f"estimated €{savings:.2f}/year ({alt['pricing_basis']})."
            if en else
            f"{prefix_with_note}ein Wechsel von {current} zu {alt_name} könnte geschätzt "
            f"€{savings:.2f}/Jahr sparen ({alt['pricing_basis']})."
        )
        text = _with_provider_dependency_note(text, entry["category"], alt_name, lang)
    elif rec == "cancel_current_go_pay_as_you_go" and entry.get("actual_annual_cost_eur") is None:
        # Same guard as above, for the pay-as-you-go verdict.
        savings = 0.0
        text = (
            f"{prefix_with_note}paying as you go looks cheaper than {current}, though {current}'s "
            f"exact cost can't be projected here, so the savings aren't quantifiable yet."
            if en else
            f"{prefix_with_note}Einzelfahrscheine wirken günstiger als {current}, die genauen Kosten "
            f"von {current} lassen sich hier aber nicht projizieren — die Ersparnis ist daher noch "
            f"nicht bezifferbar."
        )
    elif rec == "cancel_current_go_pay_as_you_go":
        savings = round(entry["actual_annual_cost_eur"] - entry["no_subscription_annual_cost_eur"], 2)
        text = (
            f"{prefix_with_note}{current} isn't paying off — cancelling and paying as you go would "
            f"save an estimated €{savings:.2f}/year."
            if en else
            f"{prefix_with_note}{current} lohnt sich nicht — eine Kündigung zugunsten von "
            f"Einzelfahrscheinen würde geschätzt €{savings:.2f}/Jahr sparen."
        )
    elif rec == "consider_subscribing":
        savings = round(entry["no_subscription_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2)
        text = (
            f"{prefix_with_note}a {alt_name} could save an estimated €{savings:.2f}/year compared to "
            f"paying as you go ({alt['pricing_basis']})."
            if en else
            f"{prefix_with_note}ein {alt_name} könnte geschätzt €{savings:.2f}/Jahr im Vergleich zu "
            f"Einzelfahrscheinen sparen ({alt['pricing_basis']})."
        )
        text = _with_provider_dependency_note(text, entry["category"], alt_name, lang)
    elif rec == "insufficient_cost_data":
        # Only reachable via a forecast scenario's projected_category_analysis — the
        # historical category_subscription_analysis always has a real cost basis.
        savings = 0.0
        text = (
            f"{prefix_plain}not enough historical data to project this category's cost reliably yet."
            if en else
            f"{prefix_plain}noch nicht genug historische Daten, um die Kosten dieser Kategorie "
            f"verlässlich zu schätzen."
        )
    else:  # no_subscription_needed
        savings = 0.0
        text = (
            f"{prefix_plain}paying as you go remains your cheapest option — no subscription needed."
            if en else
            f"{prefix_plain}Einzelfahrscheine bleiben die günstigste Option — kein Abo nötig."
        )
    return text, max(savings, 0.0)


def _join_and(parts: list[str], lang: str) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    conj = " and " if lang == "en" else " und "
    return ", ".join(parts[:-1]) + conj + parts[-1]


def _modal_shift_line(entry: dict, lang: str) -> str | None:
    """One paragraph describing a cross-category modal-shift suggestion for
    ``entry`` (one entry of ``modal_shift_suggestions``), or ``None`` when nothing
    beat staying (``suggested_shift`` is ``None``) — nothing to say for that category.

    Deliberately does NOT quote ``feasibility.reasoning`` verbatim (it's always
    written in English by modal_shift.py's LLM call/fallback) — embedding it
    untranslated into the German memo would mix languages. The LLM-written Advisor
    briefing (advisor_system.md) handles this properly by translating the reasoning
    itself; this deterministic template only states the figures plus a confidence caveat.
    """
    shift = entry.get("suggested_shift")
    if not shift:
        return None
    en = lang == "en"
    labels = _CATEGORY_LABEL_EN if en else _CATEGORY_LABEL_DE
    from_label = labels.get(entry.get("from_category"), entry.get("from_category"))
    to_label = labels.get(shift.get("to_category"), shift.get("to_category"))

    parts: list[str] = []
    stay_cost, shift_cost = entry.get("stay_annual_cost_eur"), shift.get("annual_cost_eur")
    if stay_cost is not None and shift_cost is not None:
        cost_delta = shift_cost - stay_cost
        if en:
            parts.append(
                f"save an estimated €{abs(cost_delta):.2f}/year" if cost_delta <= 0
                else f"cost an estimated €{cost_delta:.2f}/year more"
            )
        else:
            parts.append(
                f"geschätzt €{abs(cost_delta):.2f}/Jahr sparen" if cost_delta <= 0
                else f"geschätzt €{cost_delta:.2f}/Jahr mehr kosten"
            )

    stay_co2, shift_co2 = entry.get("stay_annual_co2_kg"), shift.get("annual_co2_kg")
    if stay_co2 is not None and shift_co2 is not None:
        co2_delta = shift_co2 - stay_co2
        if en:
            parts.append(
                f"cut CO₂ by {abs(co2_delta):.1f}kg/year" if co2_delta <= 0
                else f"add {co2_delta:.1f}kg/year of CO₂"
            )
        else:
            parts.append(
                f"CO₂ um {abs(co2_delta):.1f}kg/Jahr senken" if co2_delta <= 0
                else f"CO₂ um {co2_delta:.1f}kg/Jahr erhöhen"
            )

    stay_time, shift_time = entry.get("stay_annual_time_minutes"), shift.get("annual_time_minutes")
    if stay_time is not None and shift_time is not None:
        time_delta_hours = round((shift_time - stay_time) / 60)
        if time_delta_hours != 0:
            if en:
                parts.append(
                    f"take about {abs(time_delta_hours)}h/year less time" if time_delta_hours <= 0
                    else f"take about {time_delta_hours}h/year more time"
                )
            else:
                parts.append(
                    f"rund {abs(time_delta_hours)} Std/Jahr weniger Zeit brauchen" if time_delta_hours <= 0
                    else f"rund {time_delta_hours} Std/Jahr mehr Zeit brauchen"
                )

    if not parts:
        return None  # nothing quantifiable to say (shouldn't normally happen)
    delta_clause = _join_and(parts, lang)

    confidence = (shift.get("feasibility") or {}).get("confidence")
    if confidence == "low":
        caveat = (
            " This is a tentative idea — not yet checked against your personal circumstances."
            if en else
            " Das ist eine vorläufige Idee — noch nicht gegen deine persönliche Situation geprüft."
        )
    else:
        caveat = ""

    if en:
        return f"**{from_label} → {to_label}:** shifting these trips could {delta_clause}.{caveat}"
    return f"**{from_label} → {to_label}:** ein Wechsel dieser Fahrten könnte {delta_clause}.{caveat}"


def _preferences_intro(preferences: dict, lang: str) -> str:
    """One sentence naming the customer's own 0-100 onboarding priority scores —
    what ``suggested_shift`` in modal_shift_suggestions was actually weighted by
    (see engines/scoring.py) — so a shift that costs/emits more but was still
    suggested reads as intentional (their flexibility/time priority outweighed the
    others) rather than an unexplained inconsistency."""
    cost = preferences.get("cost_priority", 50)
    co2 = preferences.get("co2_priority", 50)
    time_ = preferences.get("convenience_priority", 50)
    if lang == "en":
        return (
            f"Weighted by how you told us you prioritize this — cost **{cost}/100**, "
            f"CO₂ **{co2}/100**, flexibility/time **{time_}/100** — here's where a "
            f"bigger change could pay off:"
        )
    return (
        f"Gewichtet nach deinen angegebenen Prioritäten — Kosten **{cost}/100**, "
        f"CO₂ **{co2}/100**, Flexibilität/Zeit **{time_}/100** — hier könnte sich eine "
        f"größere Veränderung lohnen:"
    )


def _modal_shift_section(analysis_result: dict, lang: str) -> str | None:
    """A "## Bigger changes worth considering" section built from
    ``modal_shift_suggestions`` — the cross-category comparison, distinct from the
    plan-level ``category_subscription_analysis`` covered above it in the memo body.
    Returns ``None`` (section omitted) when no category has a real suggested shift,
    rather than stating that nothing was found."""
    suggestions = analysis_result.get("modal_shift_suggestions") or []
    lines = [line for entry in suggestions if (line := _modal_shift_line(entry, lang))]
    if not lines:
        return None
    header = "## Bigger changes worth considering" if lang == "en" else "## Größere Veränderungen, die sich lohnen könnten"
    intro = _preferences_intro(analysis_result.get("preferences") or {}, lang)
    return f"{header}\n\n{intro}\n\n" + "\n\n".join(lines)


def _verdict_changed(entry: dict, projected_entry: dict | None) -> bool:
    """Whether a forecast scenario's projected verdict for this category is
    different enough from today's to be worth surfacing — a real, priced,
    different recommendation, not noise. Shared by the inline per-category caveat
    and the standalone "Looking ahead" section so both apply the exact same bar."""
    return bool(
        projected_entry
        and not projected_entry.get("incomplete_cost_basis")
        and projected_entry["recommendation"] != "insufficient_cost_data"
        and projected_entry["recommendation"] != entry["recommendation"]
    )


def _forecast_caveat_scenario(forecaster_out: dict | None) -> dict | None:
    """The forecast scenario worth comparing category verdicts against for a
    forward-looking caveat: the life-event scenario, when one was detected. Per
    forecasting.py's own rules, a baseline scenario is always first and a second
    scenario is only ever added when ``uncertainty_flags.life_event_detected`` is
    true, so the last scenario is that one. Returns ``None`` when there's nothing
    meaningfully different to flag (no life event, or no forecast data at all).
    """
    if not forecaster_out:
        return None
    if not (forecaster_out.get("uncertainty_flags") or {}).get("life_event_detected"):
        return None
    scenarios = forecaster_out.get("scenarios") or []
    return scenarios[-1] if len(scenarios) > 1 else None


def _forecast_caveat_line(projected_entry: dict, life_event_noun: str, lang: str) -> str:
    """A one-line forward-looking note for a category whose forecast-scenario verdict
    differs from today's. Reuses ``_category_line``'s own rendering — projected
    entries share the exact shape of ``category_subscription_analysis`` entries — so
    the phrasing/numbers can't drift out of sync with how the historical line is
    worded, and no new number-formatting logic has to be trusted separately.

    Named after the calendar-detected life event (e.g. "relocation") rather than the
    forecaster's raw scenario label (e.g. "post_relocation") — a customer reads the
    former, not internal scenario naming."""
    phrase, _ = _category_line(projected_entry, lang, include_label=False)
    if lang == "en":
        return f"*Your calendar shows an upcoming {life_event_noun} — here's what that could mean: {phrase}*"
    # life_event_noun is already the full "ein/eine <noun>" phrase for German (see
    # _life_event_article_noun_de) — no extra article to prepend here.
    return f"*Laut Ihrem Kalender steht {life_event_noun} bevor — das könnte bedeuten: {phrase}*"


def _demand_deltas(baseline_scenario: dict, event_scenario: dict, lang: str) -> list[str]:
    """One phrase per mode whose projected trip count under the life-event scenario
    differs from the baseline scenario by at least ``_DEMAND_CHANGE_THRESHOLD`` —
    the concrete "how will my travel behaviour actually shift" evidence behind the
    life event, not just its label. A mode present in only one scenario (newly
    picked up, or dropped entirely) always counts as a change. Sorted by size of
    the shift, capped to ``_MAX_BEHAVIOR_CHANGE_LINES`` so the section stays
    skimmable."""
    baseline_by_mode = {d["mode"]: d for d in baseline_scenario.get("predicted_demand", []) if d.get("mode")}
    event_by_mode = {d["mode"]: d for d in event_scenario.get("predicted_demand", []) if d.get("mode")}

    deltas = []
    for mode in set(baseline_by_mode) | set(event_by_mode):
        base_trips = (baseline_by_mode.get(mode) or {}).get("estimated_trips") or 0
        event_trips = (event_by_mode.get(mode) or {}).get("estimated_trips") or 0
        if base_trips == 0 and event_trips == 0:
            continue
        pct = (event_trips - base_trips) / base_trips if base_trips else 1.0
        if base_trips > 0 and abs(pct) < _DEMAND_CHANGE_THRESHOLD:
            continue
        deltas.append((mode, base_trips, event_trips, pct))
    deltas.sort(key=lambda d: abs(d[3]), reverse=True)

    lines = []
    for mode, base_trips, event_trips, pct in deltas[:_MAX_BEHAVIOR_CHANGE_LINES]:
        label = _mode_label(mode, lang)
        if lang == "en":
            direction = "up" if event_trips >= base_trips else "down"
            change = f" ({pct:+.0%})" if base_trips else ""
            lines.append(f"- **{label}:** {direction} from an estimated {base_trips:.0f} to {event_trips:.0f} trips/year{change}.")
        else:
            direction = "mehr" if event_trips >= base_trips else "weniger"
            change = f" ({pct:+.0%})" if base_trips else ""
            lines.append(f"- **{label}:** von geschätzt {base_trips:.0f} auf {event_trips:.0f} Fahrten/Jahr ({direction}){change}.")
    return lines


def _subscription_impact_line(entry: dict, projected_entry: dict, lang: str) -> str:
    """One bullet naming a category whose subscription advice would change under
    the life-event scenario — same phrasing engine as the inline caveat
    (``_category_line``), just formatted as a standalone list item instead of
    folded under the category's own paragraph."""
    label = (_CATEGORY_LABEL_EN if lang == "en" else _CATEGORY_LABEL_DE)[entry["category"]]
    phrase, _ = _category_line(projected_entry, lang, include_label=False)
    return f"- **{label}:** {phrase}"


def _forecast_outlook_section(forecaster_out: dict | None, categories: list[dict], lang: str) -> str | None:
    """A standalone, explicitly forward-looking section appended at the end of the
    memo — distinct from the inline per-category caveats above. Where those fold a
    single sentence into an already-written category paragraph, this section pulls
    everything forecast-related together: whether a life event was detected, what
    behaviour shift it implies (baseline vs. life-event scenario ``predicted_demand``),
    and whether that shift would change any subscription's recommendation.

    Always grounded in ``forecaster_out`` only — never lets a projected number
    change ``actions_required``/``total_estimated_savings_eur``, which stay derived
    from ``categories`` (today's historical verdict) elsewhere in this module.

    Returns ``None`` only when the forecaster produced no scenarios at all (e.g. it
    hasn't run yet) — a "nothing changes" outlook is still worth stating, so that
    case renders a (short) section rather than being suppressed.
    """
    scenarios = (forecaster_out or {}).get("scenarios") or []
    if not scenarios:
        return None

    uncertainty = forecaster_out.get("uncertainty_flags") or {}
    header = "## Looking ahead" if lang == "en" else "## Perspektivisch"

    if not uncertainty.get("life_event_detected"):
        body = (
            "Your forecasted travel demand over the next 12 months follows the same "
            "patterns as your history — no upcoming life events were flagged that "
            "would change these recommendations."
            if lang == "en" else
            "Ihr prognostizierter Reisebedarf über die nächsten 12 Monate folgt den "
            "gleichen Mustern wie bisher — es wurden keine bevorstehenden "
            "Lebensereignisse erkannt, die diese Empfehlungen ändern würden."
        )
        return f"{header}\n\n{body}"

    life_event_noun_en = _life_event_noun(uncertainty.get("life_event_type"), "en")
    life_event_noun_de = _life_event_noun(uncertainty.get("life_event_type"), "de")
    re_eval_days = uncertainty.get("recommend_re_evaluation_in_days")
    baseline = scenarios[0]
    event_scenario = scenarios[-1] if len(scenarios) > 1 else None

    if event_scenario is None:
        # Flagged but the forecaster didn't produce a comparable second scenario —
        # say so rather than inventing behaviour-change detail we don't have.
        body = (
            f"Your calendar shows a possible upcoming **{life_event_noun_en}**, but there "
            "wasn't enough detail yet to project how it would change your travel demand."
            if lang == "en" else
            f"In Ihrem Kalender deutet sich **{life_event_noun_de}** an, es gab aber noch "
            "nicht genug Details, um dessen Einfluss auf Ihr Reiseverhalten zu "
            "prognostizieren."
        )
        return f"{header}\n\n{body}"

    # Bilingual field (description_en/description_de) since forecasting.py's LLM/
    # fallback output is bilingual, same as this memo — never render the wrong
    # language's text. Falls back to description_en for older persisted rows from
    # before the split.
    description = event_scenario.get(f"description_{lang}") or event_scenario.get("description_en") or ""
    intro = (
        f"Your calendar shows an upcoming **{life_event_noun_en}** — here's what that "
        f"could mean: {description}"
        if lang == "en" else
        # life_event_noun_de is already the full "ein/eine <noun>" phrase (see
        # _life_event_article_noun_de) — "steht ... bevor" is the separable verb.
        f"In Ihrem Kalender steht **{life_event_noun_de}** bevor — folgende Auswirkungen "
        f"kann das haben: {description}"
    )

    behavior_lines = _demand_deltas(baseline, event_scenario, lang)
    behavior_intro = "Expected change in your travel behaviour:" if lang == "en" else "Erwartete Änderung Ihres Reiseverhaltens:"
    behavior_block = (
        f"{behavior_intro}\n" + "\n".join(behavior_lines)
        if behavior_lines else
        (
            "Projected trip volumes stay close to your current pattern overall."
            if lang == "en" else
            "Die prognostizierten Fahrtenzahlen bleiben insgesamt nahe am aktuellen Muster."
        )
    )

    projected_by_category = {
        e["category"]: e for e in event_scenario.get("projected_category_analysis", [])
    }
    impact_lines = [
        _subscription_impact_line(entry, projected_by_category.get(entry["category"]), lang)
        for entry in categories
        if _verdict_changed(entry, projected_by_category.get(entry["category"]))
    ]
    impact_intro = "What this could mean for your subscriptions:" if lang == "en" else "Was das für Ihre Abos bedeuten könnte:"
    impact_block = (
        f"{impact_intro}\n" + "\n".join(impact_lines)
        if impact_lines else
        (
            "None of your subscription recommendations change under this scenario yet "
            "— worth revisiting once the change actually takes effect."
            if lang == "en" else
            "Keine Ihrer Abo-Empfehlungen ändert sich in diesem Szenario bisher — es "
            "lohnt sich, dies erneut zu prüfen, sobald die Änderung eintritt."
        )
    )

    re_eval = ""
    if re_eval_days:
        re_eval = (
            f"\n\nWe'd recommend revisiting this analysis in about {re_eval_days} days."
            if lang == "en" else
            f"\n\nWir empfehlen, diese Analyse in etwa {re_eval_days} Tagen erneut zu prüfen."
        )

    return f"{header}\n\n{intro}\n\n{behavior_block}\n\n{impact_block}{re_eval}"


def template_memos(persona_name: str, analysis_result: dict, forecaster_out: dict | None = None) -> dict:
    """
    Drafts a context-aware, personalized mobility consultation memo in German and
    English purely from ``analysis_result["category_subscription_analysis"]`` —
    one verdict line per travel category, plus the actions that follow from it.

    ``forecaster_out`` (optional) adds a one-line forward-looking caveat under any
    category whose verdict would differ under the life-event forecast scenario (see
    ``_forecast_caveat_scenario``), plus a standalone "Looking ahead" section at the
    end (see ``_forecast_outlook_section``) naming any detected life event, the
    behaviour shift it implies, and whether it would change subscription advice —
    purely textual either way: ``actions_required`` and ``total_estimated_savings_eur``
    stay derived only from today's historical verdict, never from a speculative
    projection.
    """
    categories = analysis_result.get("category_subscription_analysis", [])
    scenario = _forecast_caveat_scenario(forecaster_out)
    projected_by_category = (
        {e["category"]: e for e in scenario.get("projected_category_analysis", [])}
        if scenario else {}
    )
    life_event_type = ((forecaster_out or {}).get("uncertainty_flags") or {}).get("life_event_type")

    actions_required = []
    total_savings = 0.0
    lines_en, lines_de = [], []

    for entry in categories:
        line_en, savings_en = _category_line(entry, "en")
        line_de, _ = _category_line(entry, "de")

        projected_entry = projected_by_category.get(entry["category"])
        if _verdict_changed(entry, projected_entry):
            line_en += "\n" + _forecast_caveat_line(projected_entry, _life_event_noun(life_event_type, "en"), "en")
            line_de += "\n" + _forecast_caveat_line(projected_entry, _life_event_noun(life_event_type, "de"), "de")

        lines_en.append(line_en)
        lines_de.append(line_de)
        total_savings += savings_en

        rec = entry["recommendation"]
        if rec in ("switch_to_alternative", "cancel_current_go_pay_as_you_go", "consider_subscribing"):
            # A cancel verdict means no alternative subscription is worth it — full
            # stop. Falling back to cheapest_alternative here (as the other two
            # verdicts legitimately do) would misreport "the least-bad of the
            # rejected alternatives" as a recommended switch, even though it's
            # provably worse than just cancelling (that's *why* it was rejected).
            to_plan = None
            if rec != "cancel_current_go_pay_as_you_go":
                alt = entry.get("recommended_alternative") or entry.get("cheapest_alternative")
                to_plan = alt["provider_plan_name"] if alt else None
            actions_required.append({
                "category": entry["category"],
                "action": rec,
                "from": _current_names(entry) if entry["current_subscriptions"] else None,
                "to": to_plan,
                "estimated_annual_savings_eur": savings_en,
            })

    total_savings = round(total_savings, 2)
    body_en = "\n\n".join(lines_en) if lines_en else "No travel history in a subscribable category was found."
    body_de = "\n\n".join(lines_de) if lines_de else "Es wurde kein Reiseverhalten in einer abonnierbaren Kategorie gefunden."

    savings_line_en = (
        f"Across all categories, following these suggestions could save an estimated total of "
        f"**€{total_savings:.2f}/year**."
        if total_savings > 0 else
        "Your current setup already looks cost-effective across the categories you use."
    )
    savings_line_de = (
        f"Insgesamt könnten diese Vorschläge geschätzt **€{total_savings:.2f}/Jahr** sparen."
        if total_savings > 0 else
        "Ihr aktuelles Setup ist in den von Ihnen genutzten Kategorien bereits kosteneffizient."
    )

    modal_shift_en = _modal_shift_section(analysis_result, "en")
    modal_shift_de = _modal_shift_section(analysis_result, "de")
    outlook_en = _forecast_outlook_section(forecaster_out, categories, "en")
    outlook_de = _forecast_outlook_section(forecaster_out, categories, "de")

    text_en = (
        f"Dear {persona_name},\n\n"
        f"I reviewed your travel history over the past year, category by category — comparing "
        f"what you're currently paying against paying as you go and any comparable subscription "
        f"alternative.\n\n"
        f"{body_en}\n\n"
        f"{savings_line_en}\n\n"
        + (f"{modal_shift_en}\n\n" if modal_shift_en else "")
        + (f"{outlook_en}\n\n" if outlook_en else "")
        + f"Best regards,\n"
        f"DB MoveOptimizer Strategy Advisor"
    )
    text_de = (
        f"Sehr geehrte(r) {persona_name},\n\n"
        f"ich habe Ihr Reiseverhalten des letzten Jahres kategorienweise überprüft — im Vergleich "
        f"zwischen Ihren aktuellen Kosten, Einzelfahrscheinen und vergleichbaren Abo-Alternativen.\n\n"
        f"{body_de}\n\n"
        f"{savings_line_de}\n\n"
        + (f"{modal_shift_de}\n\n" if modal_shift_de else "")
        + (f"{outlook_de}\n\n" if outlook_de else "")
        + f"Mit freundlichen Grüßen,\n"
        f"Ihr DB MoveOptimizer Strategieberater"
    )

    return {
        "total_estimated_savings_eur": total_savings,
        "actions_required": actions_required,
        "memo_english": text_en,
        "memo_german": text_de,
    }
