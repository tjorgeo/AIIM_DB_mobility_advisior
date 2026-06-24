from schema_map import group_mode, category_covers_mode

# Friendly labels for the subscription categories the optimizer can cover. Used
# when suggesting a missing subscription, so the analyst stays product-agnostic.
_CATEGORY_LABEL = {
    "public_transport": "Public-transport pass",
    "car_sharing": "Car-sharing membership",
    "bike_sharing": "Bike-sharing pass",
    "e_scooter": "E-scooter pass",
}


class AnalystAgent:
    def __init__(self):
        pass

    def run(self, travel_history: list, current_subscriptions: list) -> dict:
        """
        Ingests a customer's leg-level travel history (production ``trip_legs``)
        and active subscriptions. Returns a detailed audit of their mobility
        behavior and flags inefficiencies generically, using the subscription
        category -> covered transport modes mapping (``category_covers_mode``)
        rather than hardcoded product names.

        Cost model: ``estimated_cost_eur`` on a leg is its intrinsic
        pay-as-you-go price. A leg actually costs the customer nothing when an
        active subscription already covers its mode.
        """
        # Current annual subscription costs + which categories are already covered.
        annual_sub_cost = 0.0
        active_subs = []
        active_categories = set()
        for sub in current_subscriptions:
            if sub.get("subscription_status") == "active":
                annual_sub_cost += (sub.get("monthly_cost_eur") or 0.0) * 12
                active_subs.append(sub)
                category = (sub.get("subscription_category") or "").lower()
                if category:
                    active_categories.add(category)

        total_trips = len(travel_history)
        total_out_of_pocket = 0.0
        total_distance = 0.0
        total_co2 = 0.0

        # Display breakdown (grouped modes) feeds the frontend; raw-mode stats
        # drive the coverage-based inefficiency checks. ``cost`` in raw_mode_stats
        # is the intrinsic price; mode_breakdown / total_out_of_pocket use the
        # actual cost after current coverage.
        mode_breakdown = {}
        raw_mode_stats = {}

        for leg in travel_history:
            intrinsic = leg.get("estimated_cost_eur") or 0.0
            dist = leg.get("estimated_distance_km") or 0.0
            co2 = leg.get("estimated_co2_emissions") or 0.0
            raw_mode = (leg.get("transport_mode") or "other").lower()
            disp = group_mode(raw_mode)

            covered = any(category_covers_mode(cat, raw_mode) for cat in active_categories)
            actual = 0.0 if covered else intrinsic

            total_out_of_pocket += actual
            total_distance += dist
            total_co2 += co2

            d = mode_breakdown.setdefault(
                disp, {"trips": 0, "cost": 0.0, "distance_km": 0.0, "co2_kg": 0.0}
            )
            d["trips"] += 1
            d["cost"] += actual
            d["distance_km"] += dist
            d["co2_kg"] += co2

            r = raw_mode_stats.setdefault(
                raw_mode, {"trips": 0, "cost": 0.0, "distance_km": 0.0}
            )
            r["trips"] += 1
            r["cost"] += intrinsic
            r["distance_km"] += dist

        for d in mode_breakdown.values():
            d["cost"] = round(d["cost"], 2)
            d["distance_km"] = round(d["distance_km"], 2)
            d["co2_kg"] = round(d["co2_kg"], 2)

        total_annual_spend = total_out_of_pocket + annual_sub_cost

        def covered_stats(category):
            """Aggregate trips / out-of-pocket spend / distance across all legs a
            subscription of ``category`` would cover."""
            trips = 0
            spend = distance = 0.0
            for raw_mode, st in raw_mode_stats.items():
                if category_covers_mode(category, raw_mode):
                    trips += st["trips"]
                    spend += st["cost"]
                    distance += st["distance_km"]
            return trips, round(spend, 2), round(distance, 2)

        inefficiencies = []
        savings_potential = 0.0

        # 1) Unused subscription — a flat plan barely used for the modes it covers.
        for sub in active_subs:
            category = (sub.get("subscription_category") or "").lower()
            annual = round((sub.get("monthly_cost_eur") or 0.0) * 12, 2)
            if annual <= 0:  # pay-as-you-go memberships carry no flat waste
                continue
            trips, _spend, _distance = covered_stats(category)
            if trips < 12:  # used less than ~once a month
                name = sub.get("provider_plan_name") or _CATEGORY_LABEL.get(
                    category, "Subscription"
                )
                inefficiencies.append(
                    {
                        "type": "unused_subscription",
                        "service": name,
                        "annual_waste": annual,
                        "details": (
                            f"You pay €{annual}/year for {name}, but only {trips} of "
                            f"your trips actually used it. Cancelling would free up "
                            f"most of that spend."
                        ),
                    }
                )
                savings_potential += annual

        # 2) Missing subscription — high out-of-pocket on a coverable category that
        #    no active subscription covers.
        for category, label in _CATEGORY_LABEL.items():
            if category in active_categories:
                continue
            trips, spend, _distance = covered_stats(category)
            if spend > 100.0 and trips >= 6:
                est = round(spend * 0.3, 2)
                inefficiencies.append(
                    {
                        "type": "missing_subscription",
                        "service": label,
                        "annual_waste": est,
                        "details": (
                            f"You spent €{spend} out-of-pocket across {trips} trips "
                            f"that a {label.lower()} would cover, but hold no such "
                            f"subscription. One could cut a large share of that cost."
                        ),
                    }
                )
                savings_potential += est

        return {
            "total_trips": total_trips,
            "total_out_of_pocket": round(total_out_of_pocket, 2),
            "total_distance_km": round(total_distance, 2),
            "co2_total_kg": round(total_co2, 2),
            "mode_breakdown": mode_breakdown,
            "current_annual_spend": round(total_annual_spend, 2),
            "subscription_costs_annual": round(annual_sub_cost, 2),
            "inefficiencies": inefficiencies,
            "savings_potential_estimate": round(savings_potential, 2),
        }


if __name__ == "__main__":
    analyst = AnalystAgent()
    mock_history = [
        {"estimated_cost_eur": 0.0, "estimated_distance_km": 8.5, "transport_mode": "public_transport", "estimated_co2_emissions": 0.5},
        {"estimated_cost_eur": 29.9, "estimated_distance_km": 120, "transport_mode": "long_distance_train", "estimated_co2_emissions": 6.0},
        {"estimated_cost_eur": 18.0, "estimated_distance_km": 12, "transport_mode": "car_sharing", "estimated_co2_emissions": 2.1},
    ]
    mock_subs = [
        {"subscription_status": "active", "subscription_category": "public_transport", "provider_plan_name": "Deutschlandticket", "monthly_cost_eur": 49.0},
    ]
    print(analyst.run(mock_history, mock_subs))
