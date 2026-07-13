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
    alt = entry.get("cheapest_alternative")
    alt_name = alt["provider_plan_name"] if alt else None

    if rec == "keep_current":
        savings = 0.0
        text = (
            f"{prefix_with_note}{current} pays off — it's cheaper than paying as you go, so keep it."
            if en else
            f"{prefix_with_note}{current} lohnt sich — günstiger als Einzelfahrscheine, also behalten."
        )
    elif rec == "switch_to_alternative":
        savings = round(entry["actual_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2)
        text = (
            f"{prefix_with_note}switching from {current} to {alt_name} could save an "
            f"estimated €{savings:.2f}/year ({alt['pricing_basis']})."
            if en else
            f"{prefix_with_note}ein Wechsel von {current} zu {alt_name} könnte geschätzt "
            f"€{savings:.2f}/Jahr sparen ({alt['pricing_basis']})."
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


def _forecast_caveat_line(projected_entry: dict, scenario_label: str, lang: str) -> str:
    """A one-line forward-looking note for a category whose forecast-scenario verdict
    differs from today's. Reuses ``_category_line``'s own rendering — projected
    entries share the exact shape of ``category_subscription_analysis`` entries — so
    the phrasing/numbers can't drift out of sync with how the historical line is
    worded, and no new number-formatting logic has to be trusted separately."""
    phrase, _ = _category_line(projected_entry, lang, include_label=False)
    if lang == "en":
        return f"*Looking ahead ({scenario_label}): {phrase}*"
    return f"*Perspektivisch ({scenario_label}): {phrase}*"


def template_memos(persona_name: str, analysis_result: dict, forecaster_out: dict | None = None) -> dict:
    """
    Drafts a context-aware, personalized mobility consultation memo in German and
    English purely from ``analysis_result["category_subscription_analysis"]`` —
    one verdict line per travel category, plus the actions that follow from it.

    ``forecaster_out`` (optional) adds a one-line forward-looking caveat under any
    category whose verdict would differ under the life-event forecast scenario (see
    ``_forecast_caveat_scenario``) — purely textual: ``actions_required`` and
    ``total_estimated_savings_eur`` stay derived only from today's historical
    verdict, never from a speculative projection.
    """
    categories = analysis_result.get("category_subscription_analysis", [])
    scenario = _forecast_caveat_scenario(forecaster_out)
    projected_by_category = (
        {e["category"]: e for e in scenario.get("projected_category_analysis", [])}
        if scenario else {}
    )

    actions_required = []
    total_savings = 0.0
    lines_en, lines_de = [], []

    for entry in categories:
        line_en, savings_en = _category_line(entry, "en")
        line_de, _ = _category_line(entry, "de")

        projected_entry = projected_by_category.get(entry["category"])
        if (
            projected_entry
            and not projected_entry.get("incomplete_cost_basis")
            and projected_entry["recommendation"] != "insufficient_cost_data"
            and projected_entry["recommendation"] != entry["recommendation"]
        ):
            scenario_label = scenario.get("label", "forecast")
            line_en += "\n" + _forecast_caveat_line(projected_entry, scenario_label, "en")
            line_de += "\n" + _forecast_caveat_line(projected_entry, scenario_label, "de")

        lines_en.append(line_en)
        lines_de.append(line_de)
        total_savings += savings_en

        rec = entry["recommendation"]
        if rec in ("switch_to_alternative", "cancel_current_go_pay_as_you_go", "consider_subscribing"):
            actions_required.append({
                "category": entry["category"],
                "action": rec,
                "from": _current_names(entry) if entry["current_subscriptions"] else None,
                "to": entry["cheapest_alternative"]["provider_plan_name"] if entry.get("cheapest_alternative") else None,
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

    text_en = (
        f"Dear {persona_name},\n\n"
        f"I reviewed your travel history over the past year, category by category — comparing "
        f"what you're currently paying against paying as you go and any comparable subscription "
        f"alternative.\n\n"
        f"{body_en}\n\n"
        f"{savings_line_en}\n\n"
        f"Best regards,\n"
        f"DB MoveOptimizer Strategy Advisor"
    )
    text_de = (
        f"Sehr geehrte(r) {persona_name},\n\n"
        f"ich habe Ihr Reiseverhalten des letzten Jahres kategorienweise überprüft — im Vergleich "
        f"zwischen Ihren aktuellen Kosten, Einzelfahrscheinen und vergleichbaren Abo-Alternativen.\n\n"
        f"{body_de}\n\n"
        f"{savings_line_de}\n\n"
        f"Mit freundlichen Grüßen,\n"
        f"Ihr DB MoveOptimizer Strategieberater"
    )

    return {
        "total_estimated_savings_eur": total_savings,
        "actions_required": actions_required,
        "memo_english": text_en,
        "memo_german": text_de,
    }
