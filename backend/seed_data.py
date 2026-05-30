import uuid
import json
import random
from datetime import datetime, timedelta
from database import get_connection, init_db

# 1. Define Pricing Catalog
PRICING_CATALOG = [
    {
        "id": "pay_as_you_go",
        "name": "Pay-as-you-go (No Subscription)",
        "monthly_cost": 0.0,
        "discount_percent": 0.0,
        "unlimited_trips": 0,
        "coverage": "All transport (Standard rates)"
    },
    {
        "id": "deutschlandticket",
        "name": "Deutschlandticket",
        "monthly_cost": 49.0,
        "discount_percent": 100.0,  # Covers 100% of regional train, regional bus, and local transit
        "unlimited_trips": 1,
        "coverage": "Regional trains, buses, and local transit nationwide"
    },
    {
        "id": "bahncard_25_2nd",
        "name": "Bahncard 25 (2nd Class)",
        "monthly_cost": 5.24,  # €62.90/year
        "discount_percent": 25.0,
        "unlimited_trips": 0,
        "coverage": "25% discount on long-distance and regional trains (2nd class)"
    },
    {
        "id": "bahncard_50_2nd",
        "name": "Bahncard 50 (2nd Class)",
        "monthly_cost": 20.33,  # €244.00/year
        "discount_percent": 50.0,
        "unlimited_trips": 0,
        "coverage": "50% discount on long-distance flexpreis and 25% on saver rates (2nd class)"
    },
    {
        "id": "bahncard_100_2nd",
        "name": "Bahncard 100 (2nd Class)",
        "monthly_cost": 379.16,  # €4,550.00/year
        "discount_percent": 100.0,
        "unlimited_trips": 1,
        "coverage": "Unlimited travel on all DB trains and city-tickets nationwide (2nd class)"
    },
    {
        "id": "bahncard_25_1st",
        "name": "Bahncard 25 (1st Class)",
        "monthly_cost": 10.41,  # €125.00/year
        "discount_percent": 25.0,
        "unlimited_trips": 0,
        "coverage": "25% discount on long-distance and regional trains (1st class)"
    },
    {
        "id": "bahncard_50_1st",
        "name": "Bahncard 50 (1st Class)",
        "monthly_cost": 40.58,  # €487.00/year
        "discount_percent": 50.0,
        "unlimited_trips": 0,
        "coverage": "50% discount on long-distance flexpreis and 25% on saver rates (1st class)"
    },
    {
        "id": "bahncard_100_1st",
        "name": "Bahncard 100 (1st Class)",
        "monthly_cost": 642.83,  # €7,714.00/year
        "discount_percent": 100.0,
        "unlimited_trips": 1,
        "coverage": "Unlimited travel on all DB trains and city-tickets nationwide (1st class)"
    },
    {
        "id": "miles_sharing",
        "name": "Miles Car-Sharing Premium",
        "monthly_cost": 15.00,
        "discount_percent": 15.0,
        "unlimited_trips": 0,
        "coverage": "15% off car-sharing minutes and kilometers"
    }
]

# 2. Define Traveler Personas
PERSONAS = [
    {
        "id": "persona_max_commuter",
        "db_customer_id": "DB-992-MAX",
        "name": "Max Commuter",
        "preferences": {
            "cost_priority": 90,
            "co2_priority": 60,
            "convenience_priority": 50,
            "class_preference": "2nd"
        },
        "consent_status": {
            "email_opted_in": True,
            "calendar_shared": False,
            "data_sharing_approved": True
        },
        "subscriptions": [
            # Max currently has no subscriptions, buying single tickets
        ],
        "travel_pattern": "commuter"  # Daily regional trains Munich -> Augsburg
    },
    {
        "id": "persona_clara_consultant",
        "db_customer_id": "DB-334-CLARA",
        "name": "Clara Eco-Consultant",
        "preferences": {
            "cost_priority": 60,
            "co2_priority": 100,
            "convenience_priority": 70,
            "class_preference": "2nd"
        },
        "consent_status": {
            "email_opted_in": True,
            "calendar_shared": True,
            "data_sharing_approved": True
        },
        "subscriptions": [
            {
                "id": "sub_clara_bc25",
                "service": "bahncard_25_2nd",
                "status": "active",
                "monthly_cost_eur": 5.24,
                "renewal_date": "2026-11-15"
            }
        ],
        "travel_pattern": "long_distance"  # Long-distance train trips Berlin -> Frankfurt/Cologne
    },
    {
        "id": "persona_anna_occasional",
        "db_customer_id": "DB-112-ANNA",
        "name": "Anna Occasional",
        "preferences": {
            "cost_priority": 80,
            "co2_priority": 40,
            "convenience_priority": 40,
            "class_preference": "2nd"
        },
        "consent_status": {
            "email_opted_in": False,
            "calendar_shared": False,
            "data_sharing_approved": True
        },
        "subscriptions": [
            {
                "id": "sub_anna_dt",
                "service": "deutschlandticket",
                "status": "active",
                "monthly_cost_eur": 49.0,
                "renewal_date": "2026-06-30"
            },
            {
                "id": "sub_anna_miles",
                "service": "miles_sharing",
                "status": "active",
                "monthly_cost_eur": 15.0,
                "renewal_date": "2026-06-15"
            }
        ],
        "travel_pattern": "rare"  # Almost no travel, but paying for subscriptions!
    },
    {
        "id": "persona_sophie_explorer",
        "db_customer_id": "DB-748-SOPHIE",
        "name": "Sophie Weekend Explorer",
        "preferences": {
            "cost_priority": 85,
            "co2_priority": 90,
            "convenience_priority": 50,
            "class_preference": "2nd"
        },
        "consent_status": {
            "email_opted_in": True,
            "calendar_shared": False,
            "data_sharing_approved": True
        },
        "subscriptions": [
            # No subscriptions, pays regional flex fares
        ],
        "travel_pattern": "regional_weekend"  # Extensive weekend trips around Bavaria/Austria
    },
    {
        "id": "persona_lukas_executive",
        "db_customer_id": "DB-881-LUKAS",
        "name": "Lukas Corporate Lead",
        "preferences": {
            "cost_priority": 40,
            "co2_priority": 70,
            "convenience_priority": 100,
            "class_preference": "1st"
        },
        "consent_status": {
            "email_opted_in": True,
            "calendar_shared": True,
            "data_sharing_approved": True
        },
        "subscriptions": [
            {
                "id": "sub_lukas_bc50",
                "service": "bahncard_50_1st",
                "status": "active",
                "monthly_cost_eur": 40.58,
                "renewal_date": "2026-10-01"
            }
        ],
        "travel_pattern": "heavy_long_distance"  # High-frequency long-distance 1st class (ICE)
    }
]

# 3. Generate Travel History for past 12 months (May 2025 - April 2026)
def generate_travel_history(persona_id, pattern):
    trips = []
    start_date = datetime(2025, 5, 1)
    end_date = datetime(2026, 4, 30)
    
    # Standard emission factors (g CO2 per km)
    # Train: 8g, Car/Carsharing: 150g, Electric Scooter: 5g, Walk/Bike: 0g
    co2_factors = {
        "train": 0.008,     # kg/km
        "car": 0.150,       # kg/km
        "scooter": 0.005,   # kg/km
        "bus": 0.032        # kg/km
    }

    random.seed(42)  # For deterministic seeding
    
    current_date = start_date
    while current_date <= end_date:
        month = current_date.month
        year = current_date.year
        
        # Calculate seasonal multipliers (e.g. more travel in summer, holiday seasons)
        # Summer (July-August) and Winter Holidays (December) have slightly higher long-distance/weekend travel
        seasonal_mult = 1.0
        if month in [7, 8]:
            seasonal_mult = 1.3
        elif month == 12:
            seasonal_mult = 1.2
        elif month in [1, 2]:
            seasonal_mult = 0.8
            
        if pattern == "commuter":
            # Daily trips from Munich to Augsburg (Mon-Fri)
            # 20 workdays a month, 2 trips per day (round trip)
            # Distance: 60km each way
            # Regular regional single ticket: €14.20 each way
            if current_date.weekday() < 5:  # Mon-Fri
                # 90% chance of making the trip (account for sick days, home office)
                if random.random() < 0.90:
                    # Outward
                    dist = 61.2
                    cost = 14.20
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": current_date.strftime("%Y-%m-%d"),
                        "origin": "Munich Hbf",
                        "destination": "Augsburg Hbf",
                        "mode": "train",
                        "distance_km": dist,
                        "cost_eur": cost,
                        "co2_kg": dist * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })
                    # Return
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": current_date.strftime("%Y-%m-%d"),
                        "origin": "Augsburg Hbf",
                        "destination": "Munich Hbf",
                        "mode": "train",
                        "distance_km": dist,
                        "cost_eur": cost,
                        "co2_kg": dist * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })
            # Occasional weekend trip
            if current_date.weekday() >= 5 and random.random() < 0.05:
                dist = 12.0
                cost = 4.50
                trips.append({
                    "id": str(uuid.uuid4()),
                    "user_id": persona_id,
                    "trip_date": current_date.strftime("%Y-%m-%d"),
                    "origin": "Munich City Center",
                    "destination": "Nymphenburg",
                    "mode": "bus",
                    "distance_km": dist,
                    "cost_eur": cost,
                    "co2_kg": dist * co2_factors["bus"],
                    "created_at": datetime.now().isoformat()
                })

        elif pattern == "long_distance":
            # Clara long distance (Berlin -> Frankfurt, Cologne, Munich)
            # Long distance business travel, typically 2-3 round trips per month
            # Distance 500-600km. Average flex ticket is €95. With BC25 she gets 25% off -> €71.25.
            # We seed her cost with the *discounted* cost she actually paid!
            # Typically 2 trips per month, 3 in summer.
            num_trips = int(2 * seasonal_mult)
            if current_date.day == 5:  # Trigger once a month on specific days
                destinations = [
                    {"city": "Frankfurt Hbf", "dist": 545.0, "base_cost": 115.00},
                    {"city": "Köln Hbf", "dist": 575.0, "base_cost": 125.00},
                    {"city": "München Hbf", "dist": 620.0, "base_cost": 135.00}
                ]
                for _ in range(num_trips):
                    dest = random.choice(destinations)
                    # Outward (paid with BC25)
                    cost = dest["base_cost"] * 0.75  # 25% discount
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": (current_date + timedelta(days=random.randint(0, 15))).strftime("%Y-%m-%d"),
                        "origin": "Berlin Hbf",
                        "destination": dest["city"],
                        "mode": "train",
                        "distance_km": dest["dist"],
                        "cost_eur": round(cost, 2),
                        "co2_kg": dest["dist"] * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })
                    # Return
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": (current_date + timedelta(days=random.randint(16, 25))).strftime("%Y-%m-%d"),
                        "origin": dest["city"],
                        "destination": "Berlin Hbf",
                        "mode": "train",
                        "distance_km": dest["dist"],
                        "cost_eur": round(cost, 2),
                        "co2_kg": dest["dist"] * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })

        elif pattern == "rare":
            # Anna Occasional: Very few trips, but paying €49 DT + €15 Miles = €64/month!
            # Only 4 train trips in the entire year (regional).
            # Only 3 car-sharing trips in the entire year.
            if current_date.month in [6, 9, 12, 3] and current_date.day == 15:
                dist = 30.0
                cost = 0.00  # Covered by her Deutschlandticket (showed as €0 out of pocket)
                trips.append({
                    "id": str(uuid.uuid4()),
                    "user_id": persona_id,
                    "trip_date": current_date.strftime("%Y-%m-%d"),
                    "origin": "Hamburg Hbf",
                    "destination": "Lüneburg",
                    "mode": "train",
                    "distance_km": dist,
                    "cost_eur": cost,
                    "co2_kg": dist * co2_factors["train"],
                    "created_at": datetime.now().isoformat()
                })
            if current_date.month in [7, 10, 2] and current_date.day == 20:
                dist = 15.0
                cost = 18.00  # Paid for car sharing (after 15% discount)
                trips.append({
                    "id": str(uuid.uuid4()),
                    "user_id": persona_id,
                    "trip_date": current_date.strftime("%Y-%m-%d"),
                    "origin": "Hamburg Altona",
                    "destination": "Hamburg Airport",
                    "mode": "car",
                    "distance_km": dist,
                    "cost_eur": cost,
                    "co2_kg": dist * co2_factors["car"],
                    "created_at": datetime.now().isoformat()
                })

        elif pattern == "regional_weekend":
            # Sophie Weekend Explorer
            # Takes regional trains almost every weekend (6-8 trips a month).
            # e.g., Munich to Garmisch-Partenkirchen, Tegernsee, Salzburg.
            # Pays single fares (Bayern-Ticket or standard regional flex tickets).
            # Average cost per single weekend trip: €24.00.
            if current_date.weekday() == 5:  # Saturday
                if random.random() < 0.70 * seasonal_mult:
                    dest = random.choice([
                        {"name": "Garmisch-Partenkirchen", "dist": 90.0, "cost": 23.60},
                        {"name": "Tegernsee", "dist": 60.0, "cost": 17.50},
                        {"name": "Salzburg Hbf", "dist": 140.0, "cost": 34.00},
                        {"name": "Murnau", "dist": 75.0, "cost": 19.80}
                    ])
                    # Outward
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": current_date.strftime("%Y-%m-%d"),
                        "origin": "München Hbf",
                        "destination": dest["name"],
                        "mode": "train",
                        "distance_km": dest["dist"],
                        "cost_eur": dest["cost"],
                        "co2_kg": dest["dist"] * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })
                    # Return (same day or next)
                    trips.append({
                        "id": str(uuid.uuid4()),
                        "user_id": persona_id,
                        "trip_date": (current_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                        "origin": dest["name"],
                        "destination": "München Hbf",
                        "mode": "train",
                        "distance_km": dest["dist"],
                        "cost_eur": dest["cost"],
                        "co2_kg": dest["dist"] * co2_factors["train"],
                        "created_at": datetime.now().isoformat()
                    })

        elif pattern == "heavy_long_distance":
            # Lukas Executive
            # Heavy long distance 1st class travel (C-Level, constant commutes).
            # e.g. Frankfurt -> Berlin, Hamburg, Munich.
            # 6-8 trips a month in 1st class.
            # Currently has a Bahncard 50 1st Class (€487/year).
            # Average 1st Class ticket cost: €180. Flex ticket. With BC50, he gets 50% discount -> €90.
            if current_date.day in [4, 12, 18, 25]:
                dest = random.choice([
                    {"city": "Berlin Hbf", "dist": 545.0, "base_cost": 195.00},
                    {"city": "Hamburg Hbf", "dist": 490.0, "base_cost": 175.00},
                    {"city": "München Hbf", "dist": 395.0, "base_cost": 145.00},
                    {"city": "Stuttgart Hbf", "dist": 200.0, "base_cost": 95.00}
                ])
                # Outward (paid 50% off)
                cost = dest["base_cost"] * 0.50
                trips.append({
                    "id": str(uuid.uuid4()),
                    "user_id": persona_id,
                    "trip_date": current_date.strftime("%Y-%m-%d"),
                    "origin": "Frankfurt(Main)Hbf",
                    "destination": dest["city"],
                    "mode": "train",
                    "distance_km": dest["dist"],
                    "cost_eur": round(cost, 2),
                    "co2_kg": dest["dist"] * co2_factors["train"],
                    "created_at": datetime.now().isoformat()
                })
                # Return
                trips.append({
                    "id": str(uuid.uuid4()),
                    "user_id": persona_id,
                    "trip_date": (current_date + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "origin": dest["city"],
                    "destination": "Frankfurt(Main)Hbf",
                    "mode": "train",
                    "distance_km": dest["dist"],
                    "cost_eur": round(cost, 2),
                    "co2_kg": dest["dist"] * co2_factors["train"],
                    "created_at": datetime.now().isoformat()
                })

        current_date += timedelta(days=1)
        
    return trips

def seed_database():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear existing data to prevent primary key constraints
    cursor.execute("DELETE FROM pricing_catalog")
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM subscriptions")
    cursor.execute("DELETE FROM travel_history")
    cursor.execute("DELETE FROM recommendations")
    cursor.execute("DELETE FROM audit_log")

    # 1. Insert Pricing Catalog
    for item in PRICING_CATALOG:
        cursor.execute("""
        INSERT INTO pricing_catalog (id, name, monthly_cost, discount_percent, unlimited_trips, coverage)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (item["id"], item["name"], item["monthly_cost"], item["discount_percent"], item["unlimited_trips"], item["coverage"]))
        
    # 2. Insert Users, Subscriptions, and Travel History
    total_trips_seeded = 0
    for p in PERSONAS:
        # Insert user
        cursor.execute("""
        INSERT INTO users (id, db_customer_id, name, created_at, preferences, consent_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            p["id"],
            p["db_customer_id"],
            p["name"],
            datetime.now().isoformat(),
            json.dumps(p["preferences"]),
            json.dumps(p["consent_status"])
        ))
        
        # Insert current subscriptions
        for sub in p["subscriptions"]:
            cursor.execute("""
            INSERT INTO subscriptions (id, user_id, service, status, monthly_cost_eur, renewal_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (sub["id"], p["id"], sub["service"], sub["status"], sub["monthly_cost_eur"], sub["renewal_date"]))
            
        # Generate and insert travel history
        trips = generate_travel_history(p["id"], p["travel_pattern"])
        for trip in trips:
            cursor.execute("""
            INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur, co2_kg, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trip["id"],
                trip["user_id"],
                trip["trip_date"],
                trip["origin"],
                trip["destination"],
                trip["mode"],
                trip["distance_km"],
                trip["cost_eur"],
                trip["co2_kg"],
                trip["created_at"]
            ))
        total_trips_seeded += len(trips)
        print(f"Seeded {len(trips)} travel history records for {p['name']}.")
        
    conn.commit()
    conn.close()
    print("Database seeding completed successfully!")
    print(f"Total personas seeded: {len(PERSONAS)}")
    print(f"Total pricing models: {len(PRICING_CATALOG)}")
    print(f"Total trips seeded: {total_trips_seeded}")

if __name__ == "__main__":
    seed_database()
