"""Read the production schema for one user and shape the context the engines consume.

Records keep their production column names; the engines translate the transport-mode
and subscription vocabularies via ``schema_map``. Returns ``{"error": ...}`` when the
user is missing so callers can surface a clean 404.
"""

from database import get_connection
from agent.schema_map import clean_row, preferences_from_onboarding


def load_context(user_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return {"error": f"User with ID {user_id} not found in database."}

    user = clean_row(user_row)
    user["name"] = f"{user['first_name']} {user['last_name']}".strip()

    # Preferences live in user_onboardings (0-100 scores).
    cursor.execute(
        "SELECT * FROM user_onboardings WHERE user_id = ?", (user_id,)
    )
    onboarding_row = cursor.fetchone()
    preferences = preferences_from_onboarding(onboarding_row)

    # Subscriptions joined to the catalog. The engines key on the catalog PK
    # (subscription_id) and the subscription category, not on a service slug.
    cursor.execute(
        """
        SELECT s.user_subscription_id, s.subscription_status,
               s.is_primary_mobility_option, s.estimated_usage_frequency,
               c.subscription_id, c.provider_name, c.provider_plan_name,
               c.subscription_category, c.monthly_cost_eur, c.annual_cost_eur
        FROM user_subscriptions s
        LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
        WHERE s.user_id = ?
        """,
        (user_id,),
    )
    subscriptions = []
    for row in cursor.fetchall():
        sub = clean_row(row)
        sub["monthly_cost_eur"] = sub.get("monthly_cost_eur") or 0.0
        subscriptions.append(sub)

    # Travel history is leg-level (legs carry distance, cost, CO2 and mode),
    # ordered chronologically for the forecaster's monthly grouping.
    # reference_cost_eur is the pay-as-you-go price for a leg regardless of any
    # subscription held; the analysis engine uses it to compute discount-card
    # (e.g. BahnCard) realized savings, falling back to estimated_cost_eur when NULL.
    cursor.execute(
        """
        SELECT leg_id, trip_id, user_subscription_id, started_at, transport_mode, ticket_type, ticket_class,
               estimated_distance_km, estimated_cost_eur, reference_cost_eur, estimated_co2_emissions
        FROM trip_legs
        WHERE user_id = ?
        ORDER BY started_at ASC
        """,
        (user_id,),
    )
    travel_history = [clean_row(r) for r in cursor.fetchall()]

    # The optimizer's candidate catalog comes straight from subscription_catalogs,
    # keyed by the real PK.
    cursor.execute("SELECT * FROM subscription_catalogs")
    pricing_catalog = []
    for row in cursor.fetchall():
        item = clean_row(row)
        pricing_catalog.append(
            {
                "id": item.get("subscription_id"),
                "name": item.get("provider_plan_name"),
                "category": item.get("subscription_category"),
                "monthly_cost": item.get("monthly_cost_eur") or 0.0,
                "annual_cost": item.get("annual_cost_eur"),
                "subscription_type": item.get("subscription_type"),
            }
        )

    conn.close()
    return {
        "user": user,
        "user_preferences": preferences,
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": pricing_catalog,
    }
