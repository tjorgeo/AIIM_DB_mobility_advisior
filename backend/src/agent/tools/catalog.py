"""Catalogue tool. The agents call this to read live subscription products.

`lookup_subscriptions` reads the production `subscription_catalogs` table and
exposes each product keyed by its catalog id (the optimizer keys on the same id).
"""

import json

from langchain_core.tools import tool

from database import get_connection
from agent.schema_map import clean_row


@tool
def lookup_subscriptions(filter_type: str = "all") -> str:
    """Look up Deutsche Bahn mobility subscription products from the catalogue.

    Args:
        filter_type: 'all' to list everything, or a keyword to narrow the list
            (e.g. 'bahncard', 'deutschlandticket', 'car', 'public_transport').

    Returns:
        JSON string: list of products with id, name, category, monthly_cost,
        annual_cost and billing details.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscription_catalogs")
    rows = [clean_row(r) for r in cursor.fetchall()]
    conn.close()

    products = [
        {
            "id": r.get("subscription_id"),
            "name": r.get("provider_plan_name"),
            "provider": r.get("provider_name"),
            "category": r.get("subscription_category"),
            "monthly_cost": r.get("monthly_cost_eur"),
            "annual_cost": r.get("annual_cost_eur"),
            "billing_cycle": r.get("billing_cycle"),
            "pricing_model": r.get("pricing_model"),
        }
        for r in rows
    ]

    ft = (filter_type or "all").lower().strip()
    if ft and ft != "all":
        products = [
            p
            for p in products
            if ft in (p["id"] or "").lower()
            or ft in (p["name"] or "").lower()
            or ft in (p.get("category") or "").lower()
        ]

    if not products:
        return f"No products found for filter '{filter_type}'."
    return json.dumps(products, ensure_ascii=False, indent=2)
