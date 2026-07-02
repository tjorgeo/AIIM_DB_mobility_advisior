import os
import json
import urllib.request

class CommunicatorAgent:
    def __init__(self):
        pass

    def run(self, persona_name: str, analysis_result: dict, optimizer_result: dict) -> dict:
        """
        Drafts a context-aware, personalized mobility consultation memo in German and English.
        Explains why the recommended scenarios make sense based on historical and predicted data.
        """
        # Determine the recommended scenario
        best_rec_id = optimizer_result["best_recommendation_id"]
        scenario = next((s for s in optimizer_result["scenarios"] if s["id"] == best_rec_id), optimizer_result["scenarios"][0])
        
        annual_savings = scenario["annual_savings"]
        co2_savings = scenario["co2_savings_kg"]
        changes = scenario["changes"]
        explanation_base = scenario["explanation"]
        
        # Prepare list of adjustments
        adds = [c["item"] for c in changes if c["action"] == "add"]
        cancels = [c["item"] for c in changes if c["action"] == "cancel"]
        
        adjustments_en = []
        adjustments_de = []
        
        if adds:
            adjustments_en.append(f"Add subscription(s): {', '.join(adds)}")
            adjustments_de.append(f"Abonnement(s) hinzufügen: {', '.join(adds)}")
        if cancels:
            adjustments_en.append(f"Cancel subscription(s): {', '.join(cancels)}")
            adjustments_de.append(f"Abonnement(s) kündigen: {', '.join(cancels)}")
            
        adjustments_str_en = "; ".join(adjustments_en) if adjustments_en else "No contract changes required."
        adjustments_str_de = "; ".join(adjustments_de) if adjustments_de else "Keine Vertragsänderungen erforderlich."

        # Reconstruct the dynamic templates
        text_en = (
            f"Dear {persona_name},\n\n"
            f"I have completed a thorough strategic audit of your mobility portfolio for DB MoveOptimizer. "
            f"Based on your past 12 months of travel behavior, we detected an inefficiency overhead of €{analysis_result['savings_potential_estimate_eur']}/year, "
            f"including under-utilized subscriptions and mismatched fare tiers.\n\n"
            f"### Recommended Strategy: {scenario['label']} (Scenario {scenario['id']})\n"
            f"* **Annual Net Cost:** €{scenario['annual_cost']} (representing **€{annual_savings} in savings** compared to your baseline of €{optimizer_result['baseline_annual_cost']}).\n"
            f"* **Sustainability Footprint:** Saved **{co2_savings} kg of CO₂** annually through optimized travel modes.\n"
            f"* **Required Operations:** {adjustments_str_en}\n\n"
            f"### Why This Works:\n"
            f"{explanation_base} "
            f"This recommendation directly aligns with your preferred cost priority of {analysis_result.get('preferences', {}).get('cost_priority', 80)}% "
            f"and carbon reduction threshold of {analysis_result.get('preferences', {}).get('co2_priority', 50)}%.\n\n"
            f"Would you like me to execute these changes and log them in your DB Account?\n\n"
            f"Best regards,\n"
            f"DB MoveOptimizer Strategy Advisor"
        )

        text_de = (
            f"Sehr geehrte(r) {persona_name},\n\n"
            f"ich habe eine detaillierte strategische Analyse Ihres Mobilitätsportfolios für den DB MoveOptimizer durchgeführt. "
            f"Auf Basis Ihres Reiseverhaltens der letzten 12 Monate haben wir ein Einsparpotenzial von €{analysis_result['savings_potential_estimate_eur']}/Jahr identifiziert, "
            f"hauptsächlich verursacht durch ungenutzte Abonnements und ungeeignete Tarifklassen.\n\n"
            f"### Empfohlene Strategie: {scenario['label']} (Szenario {scenario['id']})\n"
            f"* **Jährliche Gesamtkosten:** €{scenario['annual_cost']} (das bedeutet eine **Ersparnis von €{annual_savings}** im Vergleich zu Ihren aktuellen Kosten von €{optimizer_result['baseline_annual_cost']}).\n"
            f"* **CO₂-Reduktion:** Einsparung von **{co2_savings} kg CO₂** pro Jahr durch optimierte Verkehrsmittelwahl.\n"
            f"* **Notwendige Schritte:** {adjustments_str_de}\n\n"
            f"### Begründung:\n"
            f"{explanation_base.replace('This plan minimizes your financial outlays to the absolute limit. By making', 'Dieser Plan minimiert Ihre finanziellen Ausgaben auf das absolute Minimum. Durch').replace('contract adjustments, you can retain', 'Vertragsanpassungen sparen Sie jährlich').replace('in savings yearly.', 'ein.').replace('This plan blends significant cost reductions with high regional/long-distance coverage, supporting spontaneity and reducing carbon emissions by shifting short trips to rail.', 'Dieser Plan verbindet signifikante Kosteneinsparungen mit einer hohen regionalen und überregionalen Abdeckung. Er unterstützt Spontaneität und reduziert CO₂-Emissionen durch die Verkehrsverlagerung auf die Schiene.')}\n\n"
            f"Möchten Sie, dass ich diese Vertragsanpassungen direkt in Ihrem DB-Konto ausführe?\n\n"
            f"Mit freundlichen Grüßen,\n"
            f"Ihr DB MoveOptimizer Strategieberater"
        )

        # Return both English and German letters + structured JSON
        result = {
            "recommended_scenario_id": best_rec_id,
            "annual_savings_eur": annual_savings,
            "co2_savings_kg": co2_savings,
            "actions_required": changes,
            "memo_english": text_en,
            "memo_german": text_de
        }

        return result