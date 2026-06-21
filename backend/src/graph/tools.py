"""Agent tools. The optimizer/chat agents call these to read live data.

`lookup_subscriptions` reads the Postgres `pricing_catalog` (the current 9-product
demo catalogue). When Maike's 56-product catalogue is ported in Phase 3+, only this
query needs to point at the richer table — the agent interface stays the same.
"""

import json

from langchain_core.tools import tool

from database import get_connection


@tool
def lookup_subscriptions(filter_type: str = "all") -> str:
    """Look up Deutsche Bahn mobility subscription products from the pricing catalogue.

    Args:
        filter_type: 'all' to list everything, or a keyword to narrow the list
            (e.g. 'bahncard', 'deutschlandticket', 'car', '1st', '2nd').

    Returns:
        JSON string: list of products with id, name, monthly_cost,
        discount_percent, unlimited_trips and coverage.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pricing_catalog")
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()

    ft = (filter_type or "all").lower().strip()
    if ft and ft != "all":
        products = [
            p
            for p in products
            if ft in p["id"].lower()
            or ft in p["name"].lower()
            or ft in (p.get("coverage") or "").lower()
        ]

    if not products:
        return f"No products found for filter '{filter_type}'."
    return json.dumps(products, ensure_ascii=False, indent=2)
