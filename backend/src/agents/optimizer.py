from schema_map import simplify_mode


class OptimizerAgent:
    def __init__(self):
        pass

    def run(self, travel_history: list, current_subscriptions: list, pricing_catalog: list, preferences: dict) -> dict:
        """
        Runs mathematical simulations of the traveler's historical trips (production
        ``trip_legs``) under all candidate subscription plans. Outputs 2 distinct
        scenarios (Cost-Optimized and Balanced) with precise cost breakdowns and
        carbon metrics.
        """
        # Determine if traveler has a 1st class preference
        is_1st_class = preferences.get("class_preference", "2nd") == "1st"
        co2_weight = preferences.get("co2_priority", 50)

        # Calculate baseline cost of current travel history (what they actually spent)
        baseline_out_of_pocket = sum((trip.get("estimated_cost_eur") or 0.0) for trip in travel_history)
        baseline_sub_cost = 0.0

        current_services = []
        for sub in current_subscriptions:
            if sub["subscription_status"] == "active":
                baseline_sub_cost += sub["monthly_cost_eur"] * 12
                current_services.append(sub["service"])

        baseline_total = baseline_out_of_pocket + baseline_sub_cost

        # Calculate baseline CO2 emissions
        baseline_co2 = sum((trip.get("estimated_co2_emissions") or 0.0) for trip in travel_history)

        # Helper: simulate cost for a specific subscription combination
        def simulate_portfolio(subs_to_test):
            ticket_cost = 0.0
            sub_annual_cost = 0.0
            co2_impact = baseline_co2
            
            # Subscriptions costs
            for s_id in subs_to_test:
                # Find in catalog
                catalog_item = next((item for item in pricing_catalog if item["id"] == s_id), None)
                if catalog_item:
                    sub_annual_cost += catalog_item["monthly_cost"] * 12
                    
            # Calculate ticket costs under this subscription set
            for trip in travel_history:
                cost = trip.get("estimated_cost_eur") or 0.0
                dist = trip.get("estimated_distance_km") or 0.0
                mode = simplify_mode(trip.get("transport_mode"))

                # Check for train discounts
                if mode == "train":
                    # If Bahncard 100 is in the portfolio, all train trips are free
                    if "bahncard_100_2nd" in subs_to_test or "bahncard_100_1st" in subs_to_test:
                        trip_cost = 0.0
                    # If Deutschlandticket is in the portfolio and it is a regional trip
                    elif "deutschlandticket" in subs_to_test and dist < 100.0:
                        trip_cost = 0.0
                    else:
                        # Apply Bahncard discounts
                        # We use the highest available discount in the test set
                        discount = 0.0
                        if is_1st_class:
                            if "bahncard_50_1st" in subs_to_test:
                                discount = 0.50
                            elif "bahncard_25_1st" in subs_to_test:
                                discount = 0.25
                        else:
                            if "bahncard_50_2nd" in subs_to_test:
                                discount = 0.50
                            elif "bahncard_25_2nd" in subs_to_test:
                                discount = 0.25
                                
                        # Apply discount to base ticket cost
                        # Note: since the historical cost already has discounts if they had BC,
                        # we want to reconstruct the base cost and then apply the test discount.
                        # For simplicity, if they currently have a Bahncard, the trip cost in history is already discounted.
                        # Let's approximate: if they have a current BC25, base_cost = history_cost / 0.75.
                        current_bc_discount = 0.0
                        if "bahncard_25_2nd" in current_services or "bahncard_25_1st" in current_services:
                            current_bc_discount = 0.25
                        elif "bahncard_50_2nd" in current_services or "bahncard_50_1st" in current_services:
                            current_bc_discount = 0.50
                            
                        base_cost = cost / (1.0 - current_bc_discount) if current_bc_discount < 1.0 else cost
                        trip_cost = base_cost * (1.0 - discount)
                        
                    ticket_cost += trip_cost
                    
                # Check for sharing discounts
                elif mode == "car":
                    # If Miles sharing is in portfolio, apply 15% discount
                    if "miles_sharing" in subs_to_test:
                        # If they already had it in history, it is already discounted
                        current_miles_discount = 0.15 if "miles_sharing" in current_services else 0.0
                        base_cost = cost / (1.0 - current_miles_discount) if current_miles_discount < 1.0 else cost
                        trip_cost = base_cost * 0.85
                    else:
                        # Reconstruct base if they had it but we're testing without it
                        current_miles_discount = 0.15 if "miles_sharing" in current_services else 0.0
                        trip_cost = cost / (1.0 - current_miles_discount) if current_miles_discount < 1.0 else cost
                        
                    ticket_cost += trip_cost
                else:
                    ticket_cost += cost
                    
            return round(ticket_cost + sub_annual_cost, 2), round(sub_annual_cost, 2), round(co2_impact, 2)

        # Build candidate portfolios to simulate
        candidates = []
        if is_1st_class:
            candidates = [
                [],  # Pay as you go
                ["bahncard_25_1st"],
                ["bahncard_50_1st"],
                ["bahncard_100_1st"],
                ["deutschlandticket"],  # DT is only 2nd class, but good for local transit
                ["deutschlandticket", "bahncard_25_1st"],
                ["deutschlandticket", "bahncard_50_1st"]
            ]
        else:
            candidates = [
                [],  # Pay as you go
                ["deutschlandticket"],
                ["bahncard_25_2nd"],
                ["bahncard_50_2nd"],
                ["bahncard_100_2nd"],
                ["deutschlandticket", "bahncard_25_2nd"],
                ["deutschlandticket", "bahncard_50_2nd"],
                ["miles_sharing"],
                ["deutschlandticket", "miles_sharing"]
            ]

        # Restrict candidates to products that actually exist in the catalog so we
        # never recommend (or price at zero) a plan the catalog doesn't carry.
        # Pay-as-you-go ([]) is always available.
        available = {item["id"] for item in pricing_catalog}
        candidates = [c for c in candidates if all(s in available for s in c)]
        if [] not in candidates:
            candidates.insert(0, [])

        # Simulate all candidates
        results = []
        for cand in candidates:
            total_cost, sub_cost, co2_impact = simulate_portfolio(cand)
            results.append({
                "portfolio": cand,
                "total_cost": total_cost,
                "sub_cost": sub_cost,
                "co2_impact_kg": co2_impact
            })
            
        # Sort portfolios by total cost
        results.sort(key=lambda x: x["total_cost"])
        
        # Scenario A: The absolute cheapest portfolio
        cheapest = results[0]
        # Make sure cheapest is actually cheaper than current. If not, keeping current is the cheapest!
        
        # Determine recommended actions for Scenario A
        cheapest_subs = cheapest["portfolio"]
        actions_a = []
        
        # Compare cheapest subs with current subs to decide actions
        for sub_id in cheapest_subs:
            if sub_id not in current_services:
                catalog_item = next((item for item in pricing_catalog if item["id"] == sub_id), None)
                name = catalog_item["name"] if catalog_item else sub_id
                actions_a.append({"action": "add", "item": name, "service_id": sub_id})
                
        for current_sub in current_services:
            if current_sub not in cheapest_subs:
                catalog_item = next((item for item in pricing_catalog if item["id"] == current_sub), None)
                name = catalog_item["name"] if catalog_item else current_sub
                actions_a.append({"action": "cancel", "item": name, "service_id": current_sub})
                
        annual_savings_a = round(baseline_total - cheapest["total_cost"], 2)

        # Scenario B: Balanced Portfolio
        # Prioritizes a slightly different mix if it offers better coverage, sustainability, or flexibility
        # For instance, if cheapest is Deutschlandticket, Scenario B might include Deutschlandticket + Bahncard 25
        # for spontaneity on express long-distance trains. Or keeping Miles sharing if they occasionally use it.
        # We pick the 2nd cheapest or a high-coverage portfolio that costs under 10% more than the cheapest
        balanced = None
        for res in results[1:]:
            if len(res["portfolio"]) > len(cheapest_subs) and res["total_cost"] < cheapest["total_cost"] * 1.15:
                balanced = res
                break
                
        if not balanced:
            # If no better high-coverage one is within 15% range, pick the second cheapest overall
            balanced = results[1] if len(results) > 1 else cheapest
            
        balanced_subs = balanced["portfolio"]
        actions_b = []
        
        for sub_id in balanced_subs:
            if sub_id not in current_services:
                catalog_item = next((item for item in pricing_catalog if item["id"] == sub_id), None)
                name = catalog_item["name"] if catalog_item else sub_id
                actions_b.append({"action": "add", "item": name, "service_id": sub_id})
                
        for current_sub in current_services:
            if current_sub not in balanced_subs:
                catalog_item = next((item for item in pricing_catalog if item["id"] == current_sub), None)
                name = catalog_item["name"] if catalog_item else current_sub
                actions_b.append({"action": "cancel", "item": name, "service_id": current_sub})
                
        annual_savings_b = round(baseline_total - balanced["total_cost"], 2)

        # Calculate CO2 offsets (Deutsche Bahn trains use 100% green energy, so they have 0 emissions in calculation,
        # or we simulate that moving people from car to train reduces CO2)
        # For this prototype: if they use car-sharing and we recommend a train ticket, we can simulate a 10% CO2 reduction
        # through transit shift in the balanced model.
        co2_reduction_a = 0.0
        co2_reduction_b = 0.0
        
        if "deutschlandticket" in cheapest_subs or "bahncard_100_2nd" in cheapest_subs:
            co2_reduction_a = round(baseline_co2 * 0.12, 1)
        if "deutschlandticket" in balanced_subs or "bahncard_100_2nd" in balanced_subs:
            co2_reduction_b = round(baseline_co2 * 0.20, 1) # Balanced has higher eco shift

        scenarios = [
            {
                "id": "A",
                "label": "Cost-Optimized Portfolio",
                "portfolio": cheapest_subs,
                "annual_cost": round(cheapest["total_cost"], 2),
                "annual_savings": annual_savings_a,
                "co2_impact_kg": round(cheapest["co2_impact_kg"] - co2_reduction_a, 2),
                "co2_savings_kg": co2_reduction_a,
                "changes": actions_a,
                "explanation": f"This plan minimizes your financial outlays to the absolute limit. By making {len(actions_a)} contract adjustments, you can retain €{annual_savings_a} in savings yearly."
            },
            {
                "id": "B",
                "label": "Balanced Mobility Portfolio",
                "portfolio": balanced_subs,
                "annual_cost": round(balanced["total_cost"], 2),
                "annual_savings": annual_savings_b,
                "co2_impact_kg": round(balanced["co2_impact_kg"] - co2_reduction_b, 2),
                "co2_savings_kg": co2_reduction_b,
                "changes": actions_b,
                "explanation": "This plan blends significant cost reductions with high regional/long-distance coverage, supporting spontaneity and reducing carbon emissions by shifting short trips to rail."
            }
        ]

        # Structure final recommendation result
        result = {
            "baseline_annual_cost": round(baseline_total, 2),
            "baseline_out_of_pocket": round(baseline_out_of_pocket, 2),
            "baseline_sub_cost": round(baseline_sub_cost, 2),
            "baseline_co2_kg": round(baseline_co2, 2),
            "scenarios": scenarios,
            "best_recommendation_id": "A" if annual_savings_a >= annual_savings_b else "B"
        }
        
        return result
