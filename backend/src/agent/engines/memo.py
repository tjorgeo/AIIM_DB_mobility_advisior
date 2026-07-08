"""Deterministic consultation memo — the template fallback.

Pure function, no LLM. When an LLM is configured the pipeline replaces the prose
with an LLM-written version, but this template always produces a valid memo (and
the structured fields the frontend reads) so the app works without a key.

Built entirely from ``analyze_portfolio``'s ``category_subscription_analysis`` —
one line per travel category, saying whether the currently-held subscription (if
any) pays off, whether a cheaper alternative exists, or whether pay-as-you-go is
already the cheapest option. No portfolio scenarios, no combined recommendation:
each category stands on its own, since that's the level at which the underlying
numbers are actually comparable (see analysis.py's ``_pricing_basis``).
"""

_CATEGORY_LABEL_EN = {
    "public_transport": "Public transport",
    "bike_sharing": "Bike sharing",
    "car_sharing": "Car sharing",
    "e_scooter": "E-scooter",
}
_CATEGORY_LABEL_DE = {
    "public_transport": "Öffentlicher Nahverkehr",
    "bike_sharing": "Bike-Sharing",
    "car_sharing": "Car-Sharing",
    "e_scooter": "E-Scooter",
}


def _current_names(entry: dict) -> str:
    names = [c["provider_plan_name"] for c in entry["current_subscriptions"] if c.get("provider_plan_name")]
    return " + ".join(names) if names else "no subscription"


def _category_line(entry: dict, lang: str) -> tuple[str, float]:
    """One sentence describing the verdict for a single category, plus the
    estimated annual savings implied by that verdict (0.0 if the verdict is
    "nothing to change")."""
    en = lang == "en"
    label = (_CATEGORY_LABEL_EN if en else _CATEGORY_LABEL_DE)[entry["category"]]
    rec = entry["recommendation"]
    current = _current_names(entry)
    alt = entry.get("cheapest_alternative")
    alt_name = alt["provider_plan_name"] if alt else None

    if rec == "keep_current":
        savings = 0.0
        text = (
            f"**{label}:** {current} pays off — it's cheaper than paying as you go, so keep it."
            if en else
            f"**{label}:** {current} lohnt sich — günstiger als Einzelfahrscheine, also behalten."
        )
    elif rec == "switch_to_alternative":
        savings = round(entry["actual_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2)
        text = (
            f"**{label}:** switching from {current} to {alt_name} could save an estimated "
            f"€{savings:.2f}/year ({alt['pricing_basis']})."
            if en else
            f"**{label}:** ein Wechsel von {current} zu {alt_name} könnte geschätzt "
            f"€{savings:.2f}/Jahr sparen ({alt['pricing_basis']})."
        )
    elif rec == "cancel_current_go_pay_as_you_go":
        savings = round(entry["actual_annual_cost_eur"] - entry["no_subscription_annual_cost_eur"], 2)
        text = (
            f"**{label}:** {current} isn't paying off — cancelling and paying as you go would "
            f"save an estimated €{savings:.2f}/year."
            if en else
            f"**{label}:** {current} lohnt sich nicht — eine Kündigung zugunsten von Einzelfahrscheinen "
            f"würde geschätzt €{savings:.2f}/Jahr sparen."
        )
    elif rec == "consider_subscribing":
        savings = round(entry["no_subscription_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2)
        text = (
            f"**{label}:** a {alt_name} could save an estimated €{savings:.2f}/year compared to "
            f"paying as you go ({alt['pricing_basis']})."
            if en else
            f"**{label}:** ein {alt_name} könnte geschätzt €{savings:.2f}/Jahr im Vergleich zu "
            f"Einzelfahrscheinen sparen ({alt['pricing_basis']})."
        )
    else:  # no_subscription_needed
        savings = 0.0
        text = (
            f"**{label}:** paying as you go remains your cheapest option — no subscription needed."
            if en else
            f"**{label}:** Einzelfahrscheine bleiben die günstigste Option — kein Abo nötig."
        )
    return text, max(savings, 0.0)


def template_memos(persona_name: str, analysis_result: dict) -> dict:
    """
    Drafts a context-aware, personalized mobility consultation memo in German and
    English purely from ``analysis_result["category_subscription_analysis"]`` —
    one verdict line per travel category, plus the actions that follow from it.
    """
    categories = analysis_result.get("category_subscription_analysis", [])

    actions_required = []
    total_savings = 0.0
    lines_en, lines_de = [], []

    for entry in categories:
        line_en, savings_en = _category_line(entry, "en")
        line_de, _ = _category_line(entry, "de")
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
