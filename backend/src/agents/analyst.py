from schema_map import simplify_mode

class AnalystAgent:
    def __init__(self):
        pass

    def run(self, travel_history: list, current_subscriptions: list) -> dict:
        """
        Ingests a customer's leg-level travel history (production ``trip_legs``)
        and active subscriptions. Returns a detailed audit of their mobility
        behavior and flags inefficiencies.
        """
        total_trips = len(travel_history)
        total_out_of_pocket = 0.0
        total_distance = 0.0
        total_co2 = 0.0

        mode_breakdown = {}

        # Process travel history (each record is a production trip leg)
        for trip in travel_history:
            cost = trip.get("estimated_cost_eur") or 0.0
            dist = trip.get("estimated_distance_km") or 0.0
            mode = simplify_mode(trip.get("transport_mode"))
            co2 = trip.get("estimated_co2_emissions") or 0.0

            total_out_of_pocket += cost
            total_distance += dist
            total_co2 += co2
            
            if mode not in mode_breakdown:
                mode_breakdown[mode] = {"trips": 0, "cost": 0.0, "distance_km": 0.0, "co2_kg": 0.0}
                
            mode_breakdown[mode]["trips"] += 1
            mode_breakdown[mode]["cost"] += cost
            mode_breakdown[mode]["distance_km"] += dist
            mode_breakdown[mode]["co2_kg"] += co2
            
        # Clean up numbers in mode breakdown
        for mode in mode_breakdown:
            mode_breakdown[mode]["cost"] = round(mode_breakdown[mode]["cost"], 2)
            mode_breakdown[mode]["distance_km"] = round(mode_breakdown[mode]["distance_km"], 2)
            mode_breakdown[mode]["co2_kg"] = round(mode_breakdown[mode]["co2_kg"], 2)

        # Calculate current annual subscription costs
        annual_sub_cost = 0.0
        active_subs = []
        for sub in current_subscriptions:
            if sub["subscription_status"] == "active":
                annual_sub_cost += sub["monthly_cost_eur"] * 12
                active_subs.append(sub["service"])
                
        total_annual_spend = total_out_of_pocket + annual_sub_cost
        
        # Detect Inefficiencies
        inefficiencies = []
        savings_potential = 0.0
        
        # Inefficiency 1: Unused subscriptions
        # If paying for a subscription but usage is extremely low (e.g. less than 5 trips in a year or 0 trips)
        for sub in current_subscriptions:
            if sub["subscription_status"] == "active":
                service = sub["service"]
                # Match service usage
                if service == "deutschlandticket":
                    # Deutschlandticket covers train trips. Let's see if she has train trips
                    train_trips = mode_breakdown.get("train", {}).get("trips", 0)
                    # If train trips are very low, she is losing money
                    # E.g. less than 15 trips in a year. Or she only makes cheap trips.
                    train_spend = mode_breakdown.get("train", {}).get("cost", 0.0)
                    if train_trips <= 5 or train_spend == 0.0:
                        waste = sub["monthly_cost_eur"] * 12
                        inefficiencies.append({
                            "type": "unused_subscription",
                            "service": "Deutschlandticket",
                            "annual_waste": round(waste, 2),
                            "details": f"You paid €{round(waste, 2)}/year for a Deutschlandticket, but had only {train_trips} train trips. It is highly inefficient."
                        })
                        savings_potential += waste
                elif service == "miles_sharing":
                    car_trips = mode_breakdown.get("car", {}).get("trips", 0)
                    if car_trips <= 3:
                        waste = sub["monthly_cost_eur"] * 12
                        inefficiencies.append({
                            "type": "unused_subscription",
                            "service": "Miles Car-Sharing Premium",
                            "annual_waste": round(waste, 2),
                            "details": f"You paid €{round(waste, 2)}/year for a Miles Car-Sharing Premium subscription, but made only {car_trips} car trips. The membership is unused."
                        })
                        savings_potential += waste
                        
        # Inefficiency 2: Overpaying for commute without subscription
        # E.g. High frequency train trips but NO subscriptions at all
        train_stats = mode_breakdown.get("train", {})
        train_trips = train_stats.get("trips", 0)
        train_cost = train_stats.get("cost", 0.0)
        
        if len(active_subs) == 0 and train_trips > 50:
            # Frequent traveler but has no card!
            # Could save with Deutschlandticket or a Bahncard
            inefficiencies.append({
                "type": "missing_subscription",
                "service": "None (No discount card)",
                "annual_waste": round(train_cost * 0.3, 2),  # Conservative estimate
                "details": f"You traveled {train_trips} times by train, spending €{round(train_cost, 2)} out-of-pocket, but have no Bahncard or Deutschlandticket. You are missing out on major discounts."
            })
            savings_potential += train_cost * 0.3

        # Inefficiency 3: Wrong Bahncard Tier
        # Clara: has BC25, spends €285 out-of-pocket on long distance. A BC50 would discount it by 50% instead of 25%.
        # Lukas: spends €700+/month on 1st class. A BC100 1st Class would cover everything.
        if "bahncard_25_2nd" in active_subs and train_cost > 300:
            # High spend on long-distance. Upgrading to BC50 might make sense.
            inefficiencies.append({
                "type": "suboptimal_subscription_tier",
                "service": "Bahncard 25 (2nd Class)",
                "annual_waste": round(train_cost * 0.15, 2),
                "details": "Your high volume of long-distance trips suggests that upgrading to a Bahncard 50 would yield significantly higher annual discounts."
            })
            savings_potential += train_cost * 0.15
            
        if "bahncard_50_1st" in active_subs and train_cost > 4000:
            # Extreme spend on 1st class. Bahncard 100 1st class is €7,714. If total spend is €9000+, they are wasting money!
            total_1st_class_spend = train_cost + 487.00
            if total_1st_class_spend > 8000:
                waste = total_1st_class_spend - 7714.00
                inefficiencies.append({
                    "type": "suboptimal_subscription_tier",
                    "service": "Bahncard 50 (1st Class)",
                    "annual_waste": round(waste, 2),
                    "details": f"You spent €{round(total_1st_class_spend, 2)} on 1st class travel (including tickets + Bahncard 50). A flat-rate Bahncard 100 (1st Class) would cost €7,714, saving you money and offering unlimited travel."
                })
                savings_potential += waste
        
        # Standardize outputs
        result = {
            "total_trips": total_trips,
            "total_out_of_pocket": round(total_out_of_pocket, 2),
            "total_distance_km": round(total_distance, 2),
            "co2_total_kg": round(total_co2, 2),
            "mode_breakdown": mode_breakdown,
            "current_annual_spend": round(total_annual_spend, 2),
            "subscription_costs_annual": round(annual_sub_cost, 2),
            "inefficiencies": inefficiencies,
            "savings_potential_estimate": round(savings_potential, 2)
        }
        
        return result

if __name__ == "__main__":
    # Test Analyst
    analyst = AnalystAgent()
    mock_history = [
        {"estimated_cost_eur": 14.20, "estimated_distance_km": 60, "transport_mode": "regional_train", "estimated_co2_emissions": 0.48},
        {"estimated_cost_eur": 14.20, "estimated_distance_km": 60, "transport_mode": "regional_train", "estimated_co2_emissions": 0.48}
    ]
    mock_subs = []
    print(analyst.run(mock_history, mock_subs))
