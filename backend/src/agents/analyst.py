"""Deterministic mobility analyst agent.

Ingests leg-level travel history and active subscription records, computes
factual usage statistics, detects temporal patterns, and produces a structured
summary. No LLM, no hardcoded thresholds — inefficiencies are flagged only
when the math is unambiguous (e.g. a subscription cost more than it saved).
"""

from collections import defaultdict
from datetime import datetime

from schema_map import group_mode, category_covers_mode


_MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

_ALL_CATEGORIES = {"public_transport", "bike_sharing", "car_sharing", "e_scooter"}

_CATEGORY_LABEL = {
    "public_transport": "Public-transport pass",
    "bike_sharing": "Bike-sharing pass",
    "car_sharing": "Car-sharing membership",
    "e_scooter": "E-scooter pass",
}


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class AnalystAgent:
    def run(self, travel_history: list, current_subscriptions: list) -> dict:
        """
        Parameters
        ----------
        travel_history:
            List of trip_leg dicts from the DB (production column names, values
            already coerced by ``clean_row``).
        current_subscriptions:
            List of user_subscriptions rows joined to subscription_catalogs
            (production column names).

        Returns a dict with two logical sections:
        - Full output consumed by the Optimizer and stored in recommendations.
        - ``forecaster_summary`` — a nested dict already shaped to the
          AnalystSummary schema that ForecasterAgent.run() expects.
        """

        # ------------------------------------------------------------------ #
        # 1. Data window                                                       #
        # ------------------------------------------------------------------ #
        dates = [dt for leg in travel_history if (dt := _parse_dt(leg.get("started_at")))]

        if dates:
            date_min, date_max = min(dates), max(dates)
            data_window_days = max((date_max - date_min).days, 1)
            analysis_period_start = date_min.date().isoformat()
            analysis_period_end = date_max.date().isoformat()
        else:
            data_window_days = 0
            analysis_period_start = analysis_period_end = ""

        months_of_data = max(data_window_days, 1) / 30.44
        data_warning = "too little data for reliable annualization" if data_window_days < 14 else None

        # ------------------------------------------------------------------ #
        # 2. Active subscriptions                                              #
        # ------------------------------------------------------------------ #
        annual_sub_cost = 0.0
        active_subs_by_id: dict[str, dict] = {}
        active_categories: set[str] = set()
        current_contracts: list[str] = []

        for sub in current_subscriptions:
            if sub.get("subscription_status") != "active":
                continue
            monthly = float(sub.get("monthly_cost_eur") or 0.0)
            annual = float(sub.get("annual_cost_eur") or 0.0) or monthly * 12
            annual_sub_cost += annual
            sub_id = sub.get("user_subscription_id")
            if sub_id:
                active_subs_by_id[sub_id] = {**sub, "_annual_cost": annual}
            category = (sub.get("subscription_category") or "").lower()
            if category:
                active_categories.add(category)
            name = sub.get("provider_plan_name") or sub.get("provider_name") or "Subscription"
            cost_label = f"€{monthly:.0f}/mo" if monthly else (f"€{annual:.0f}/yr" if annual else "")
            current_contracts.append(f"{name} ({cost_label})" if cost_label else name)

        # ------------------------------------------------------------------ #
        # 3. Per-leg aggregation                                               #
        # ------------------------------------------------------------------ #
        total_intrinsic = 0.0
        total_effective = 0.0
        total_distance = 0.0
        total_co2 = 0.0

        # raw_mode_stats: production transport_mode (for uncovered-category checks)
        raw_mode_stats: dict[str, dict] = defaultdict(
            lambda: {"trips": 0, "intrinsic": 0.0, "distance": 0.0, "co2": 0.0}
        )
        # disp_mode_stats: grouped display mode (for mode_breakdown output)
        disp_mode_stats: dict[str, dict] = defaultdict(
            lambda: {"trips": 0, "intrinsic": 0.0, "effective": 0.0, "distance": 0.0, "co2": 0.0}
        )
        # sub_stats: per-subscription attribution, keyed by user_subscription_id.
        # Drives subscription_coverage directly from what each leg actually used,
        # rather than inferring coverage from category+mode. This correctly
        # distinguishes flat passes (paid €0) from discount cards like a BahnCard
        # (paid a reduced price) — both report a real "realized_savings" figure.
        sub_stats: dict[str, dict] = defaultdict(
            lambda: {"trips": 0, "reference": 0.0, "paid": 0.0, "distance": 0.0}
        )
        # monthly_total[(year, month)] = trip count (for seasonality)
        monthly_total: dict[tuple, int] = defaultdict(int)

        for leg in travel_history:
            # reference_cost_eur is the pay-as-you-go price for this leg regardless
            # of any subscription held. Falls back to estimated_cost_eur for legs
            # that predate the field or where no subscription applies.
            intrinsic = float(
                leg.get("reference_cost_eur") or leg.get("estimated_cost_eur") or 0.0
            )
            paid = float(leg.get("estimated_cost_eur") or 0.0)
            dist = float(leg.get("estimated_distance_km") or 0.0)
            co2 = float(leg.get("estimated_co2_emissions") or 0.0)
            raw_mode = (leg.get("transport_mode") or "other").lower()
            disp = group_mode(raw_mode)

            leg_sub_id = leg.get("user_subscription_id")
            attributed = leg_sub_id in active_subs_by_id
            effective = paid if attributed else intrinsic

            if attributed:
                st = sub_stats[leg_sub_id]
                st["trips"] += 1
                st["reference"] += intrinsic
                st["paid"] += paid
                st["distance"] += dist

            total_intrinsic += intrinsic
            total_effective += effective
            total_distance += dist
            total_co2 += co2

            raw_mode_stats[raw_mode]["trips"] += 1
            raw_mode_stats[raw_mode]["intrinsic"] += intrinsic
            raw_mode_stats[raw_mode]["distance"] += dist
            raw_mode_stats[raw_mode]["co2"] += co2

            disp_mode_stats[disp]["trips"] += 1
            disp_mode_stats[disp]["intrinsic"] += intrinsic
            disp_mode_stats[disp]["effective"] += effective
            disp_mode_stats[disp]["distance"] += dist
            disp_mode_stats[disp]["co2"] += co2

            dt = _parse_dt(leg.get("started_at"))
            if dt:
                monthly_total[(dt.year, dt.month)] += 1

        total_trips = len(travel_history)

        # ------------------------------------------------------------------ #
        # 4. Mode breakdown (annualized, backward-compatible keys kept)        #
        # ------------------------------------------------------------------ #
        mode_breakdown: dict[str, dict] = {}
        for mode, st in disp_mode_stats.items():
            n = st["trips"]
            trips_pm = round(n / months_of_data, 2)
            dist_pm = round(st["distance"] / months_of_data, 2)
            co2_pm = round(st["co2"] / months_of_data, 2)
            avg_dist_per_trip = round(st["distance"] / max(n, 1), 2)
            mode_breakdown[mode] = {
                # New keys
                "trips_total": n,
                "trips_per_month": trips_pm,
                "trips_per_year": round(trips_pm * 12, 1),
                "distance_km_total": round(st["distance"], 2),
                "distance_km_per_month": dist_pm,
                "avg_distance_km_per_trip": avg_dist_per_trip,
                "co2_kg_total": round(st["co2"], 2),
                "co2_kg_per_month": co2_pm,
                "intrinsic_cost_eur_total": round(st["intrinsic"], 2),
                "effective_cost_eur_total": round(st["effective"], 2),
                # Backward-compatible aliases (used by pipeline.py and communicator)
                "trips": n,
                "cost": round(st["effective"], 2),
                "distance_km": round(st["distance"], 2),
                "co2_kg": round(st["co2"], 2),
            }

        # ------------------------------------------------------------------ #
        # 5. Dominant patterns (sorted by trips/month desc)                   #
        # ------------------------------------------------------------------ #
        dominant_patterns = sorted(
            [
                {
                    "mode": mode,
                    "avg_trips_per_month": st["trips_per_month"],
                    "avg_distance_km": st["avg_distance_km_per_trip"],
                }
                for mode, st in mode_breakdown.items()
                if st["trips_total"] > 0
            ],
            key=lambda x: -x["avg_trips_per_month"],
        )

        # ------------------------------------------------------------------ #
        # 6. Seasonality detection (purely statistical)                        #
        # ------------------------------------------------------------------ #
        detected_seasonality = self._detect_seasonality(monthly_total)

        # ------------------------------------------------------------------ #
        # 7. Subscription coverage vs. actual value (threshold-free math)     #
        #                                                                       #
        # Attribution is per-leg via user_subscription_id (set when a leg was   #
        # actually used with that subscription), not inferred from category+    #
        # mode. This means a flat pass (paid €0) and a discount card like a     #
        # BahnCard (paid a reduced price) both produce a correct                #
        # realized_savings_eur = reference_cost - amount_paid, annualized.      #
        # ------------------------------------------------------------------ #
        def _covered_stats(category: str) -> dict:
            trips, intrinsic, distance = 0, 0.0, 0.0
            for raw_mode, st in raw_mode_stats.items():
                if category_covers_mode(category, raw_mode):
                    trips += st["trips"]
                    intrinsic += st["intrinsic"]
                    distance += st["distance"]
            annualized_value = round(intrinsic / months_of_data * 12, 2)
            return {
                "trips_total": trips,
                "trips_annualized": round(trips / months_of_data * 12, 1),
                "intrinsic_total_eur": round(intrinsic, 2),
                "intrinsic_annualized_eur": annualized_value,
                "distance_km_total": round(distance, 2),
            }

        subscription_coverage = []
        for sub_id, sub in active_subs_by_id.items():
            category = (sub.get("subscription_category") or "").lower()
            annual_cost = sub["_annual_cost"]
            if annual_cost <= 0:
                continue
            st = sub_stats.get(sub_id, {"trips": 0, "reference": 0.0, "paid": 0.0, "distance": 0.0})
            covered_value = round(st["reference"] / months_of_data * 12, 2)
            realized_savings = round((st["reference"] - st["paid"]) / months_of_data * 12, 2)
            net_savings = round(realized_savings - annual_cost, 2)
            subscription_coverage.append({
                "provider_plan_name": sub.get("provider_plan_name") or sub.get("provider_name", ""),
                "subscription_category": category,
                "annual_cost_eur": round(annual_cost, 2),
                "covered_value_eur": covered_value,
                "realized_savings_eur": realized_savings,
                "net_savings_eur": net_savings,
                "trips_total": st["trips"],
                "trips_annualized": round(st["trips"] / months_of_data * 12, 1),
                "distance_km_total": round(st["distance"], 2),
            })

        # ------------------------------------------------------------------ #
        # 8. Uncovered spend (raw fact for the Optimizer, not a rec)          #
        # ------------------------------------------------------------------ #
        uncovered_spend_by_category: dict[str, float] = {}
        for cat in _ALL_CATEGORIES:
            if cat not in active_categories:
                cs = _covered_stats(cat)
                if cs["intrinsic_annualized_eur"] > 0:
                    uncovered_spend_by_category[cat] = cs["intrinsic_annualized_eur"]

        # ------------------------------------------------------------------ #
        # 9. Inefficiencies — only when math is unambiguous                   #
        # ------------------------------------------------------------------ #
        inefficiencies = []
        savings_potential = 0.0

        for cov in subscription_coverage:
            if cov["net_savings_eur"] < 0:
                waste = abs(cov["net_savings_eur"])
                inefficiencies.append({
                    "type": "overpaid_subscription",
                    "service": cov["provider_plan_name"],
                    "annual_waste_eur": round(waste, 2),
                    # kept for backward compat (communicator reads "annual_waste")
                    "annual_waste": round(waste, 2),
                    "details": (
                        f"{cov['provider_plan_name']} costs €{cov['annual_cost_eur']:.2f}/year "
                        f"but only saved €{cov['realized_savings_eur']:.2f}/year versus paying "
                        f"pay-as-you-go on the trips it was used for — a net overpayment of "
                        f"€{waste:.2f}/year."
                    ),
                })
                savings_potential += waste

        # ------------------------------------------------------------------ #
        # 10. Forecaster summary (matches AnalystSummary in forecaster.py)    #
        # ------------------------------------------------------------------ #
        forecaster_summary = {
            "dominant_patterns": dominant_patterns,
            "detected_seasonality": detected_seasonality,
            "current_contracts": current_contracts,
            "detected_inefficiencies": [i["details"] for i in inefficiencies],
        }

        current_annual_spend = round(total_effective + annual_sub_cost, 2)

        return {
            # Data window
            "data_window_days": data_window_days,
            "months_of_data": round(months_of_data, 2),
            "analysis_period_start": analysis_period_start,
            "analysis_period_end": analysis_period_end,
            "data_warning": data_warning,
            # Aggregates
            "total_trips": total_trips,
            "total_distance_km": round(total_distance, 2),
            "co2_total_kg": round(total_co2, 2),
            "total_intrinsic_spend_eur": round(total_intrinsic, 2),
            "total_effective_spend_eur": round(total_effective, 2),
            "subscription_costs_annual_eur": round(annual_sub_cost, 2),
            "current_annual_spend_eur": current_annual_spend,
            # Breakdowns
            "mode_breakdown": mode_breakdown,
            "subscription_coverage": subscription_coverage,
            "uncovered_spend_by_category": uncovered_spend_by_category,
            # Patterns
            "dominant_patterns": dominant_patterns,
            "detected_seasonality": detected_seasonality,
            # Inefficiencies
            "inefficiencies": inefficiencies,
            "savings_potential_estimate_eur": round(savings_potential, 2),
            # Backward-compatible aliases (communicator / pipeline use these keys)
            "total_out_of_pocket": round(total_effective, 2),
            "current_annual_spend": current_annual_spend,
            "subscription_costs_annual": round(annual_sub_cost, 2),
            "savings_potential_estimate": round(savings_potential, 2),
            # Forecaster-ready summary (used by forecaster_node in pipeline.py)
            "forecaster_summary": forecaster_summary,
        }

    def _detect_seasonality(self, monthly_total: dict[tuple, int]) -> str:
        if len(monthly_total) < 3:
            return "insufficient data for seasonality detection"

        # Average trips per calendar month across all years in the data
        by_cal_month: dict[int, list[int]] = defaultdict(list)
        for (_, month), count in monthly_total.items():
            by_cal_month[month].append(count)

        avg_by_cal_month = {m: sum(v) / len(v) for m, v in by_cal_month.items()}
        overall_avg = sum(avg_by_cal_month.values()) / len(avg_by_cal_month)

        if overall_avg == 0:
            return "no trips recorded"

        peak_month = max(avg_by_cal_month, key=avg_by_cal_month.get)
        trough_month = min(avg_by_cal_month, key=avg_by_cal_month.get)
        peak_ratio = avg_by_cal_month[peak_month] / overall_avg
        trough_ratio = avg_by_cal_month[trough_month] / overall_avg

        if peak_ratio < 1.2 and trough_ratio > 0.8:
            return "no significant seasonal variation detected"

        parts = []
        if peak_ratio >= 1.2:
            parts.append(
                f"peak travel in {_MONTH_NAMES[peak_month]} ({peak_ratio:.1f}× monthly average)"
            )
        if trough_ratio <= 0.8:
            parts.append(
                f"lowest activity in {_MONTH_NAMES[trough_month]} ({trough_ratio:.1f}× monthly average)"
            )
        return "; ".join(parts)
