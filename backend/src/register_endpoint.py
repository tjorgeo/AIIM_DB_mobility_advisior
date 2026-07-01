"""
Strukturierter Onboarding-Submit — Vorschlag für das Backend-Team.

Das Frontend (frontend/src/api/client.js -> submitOnboarding) schickt das volle
Profil als JSON an  POST /api/register . Dieser Handler schreibt es in
users + user_onboardings (+ best-effort user_subscriptions).

Integration in backend/src/main.py:
  1. from register_endpoint import RegisterRequest, register   (oder Code inline kopieren)
  2. app.post("/api/register")(register)
  3. nichts am bestehenden /api/onboarding (LLM-Chat) ändern — das bleibt separat.

Hinweis zum API-Contract: /api/register ist ADDITIV (kein bestehender Payload
ändert sich), also Contract-konform.
"""

import uuid
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# vorhandener Helper im Backend
from database import get_connection
from auth_utils import hash_password


# --- Request-Schemas (locker gehalten; Frontend liefert null für Skips) ---

class RegisterUser(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    gender: str = "not_specified"
    date_of_birth: Optional[str] = None   # "YYYY-01-01" oder null
    age: Optional[int] = None
    home_city: Optional[str] = None
    home_postal_code: Optional[str] = None
    home_country_code: str = "DE"


class RegisterOnboarding(BaseModel):
    has_driving_license: Optional[bool] = None
    car_access: Optional[str] = None
    bike_access: Optional[str] = None
    preferred_transport_modes: List[str] = []
    avoided_transport_modes: List[str] = []
    score_money: Optional[int] = None
    score_emission: Optional[int] = None
    score_flexibility: Optional[int] = None
    work_arrangement: Optional[str] = None
    work_city: Optional[str] = None
    work_postal_code: Optional[str] = None
    remote_work_share: Optional[float] = None
    mobility_budget_monthly_eur: Optional[float] = None
    household_size: Optional[int] = None
    income_band: Optional[str] = None
    typical_weekday_pattern: Optional[str] = None
    typical_weekend_pattern: Optional[str] = None
    travel_statement: str = ""
    activity_statement: str = ""


class RegisterSubscription(BaseModel):
    service: str
    subscription_type: str = "subscription"
    billing_cycle: str = "monthly"


class RegisterCredentials(BaseModel):
    password: Optional[str] = None


class RegisterRequest(BaseModel):
    user: RegisterUser
    onboarding: RegisterOnboarding
    subscriptions: List[RegisterSubscription] = []
    credentials: RegisterCredentials = RegisterCredentials()


# --- Seed-Persona-Verknüpfung (Demo) ---

def _copy_user_table(cur, table: str, src_user: str, overrides: Dict[str, str]) -> None:
    """Kopiert alle Zeilen einer user-bezogenen Tabelle von src_user, wobei einzelne
    Spalten per SQL-Ausdruck überschrieben werden (z. B. user_id/PK-Remap). Die
    Spaltenliste kommt dynamisch aus information_schema, damit es schema-robust bleibt."""
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    cols = [r["column_name"] for r in cur.fetchall()]
    if not cols:
        return
    select_exprs = [overrides.get(c, c) for c in cols]
    cur.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM {table} WHERE user_id = %s",
        (src_user,),
    )


def _link_random_persona(new_user_id: str) -> Optional[str]:
    """Kopiert die Trips (user_trips + trip_legs) einer zufälligen Seed-Persona auf
    den neuen User, damit die Analyse-Pipeline etwas zu rechnen hat. Seed-Personas
    erkennt man daran, dass sie kein Passwort haben (password_hash IS NULL) und Trips
    besitzen. Läuft in eigener Transaktion -> Fehler hier gefährden die Registrierung
    nicht. Gibt die Quell-user_id zurück (oder None)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tl.user_id
            FROM trip_legs tl
            JOIN users u ON u.user_id = tl.user_id
            WHERE u.password_hash IS NULL
            GROUP BY tl.user_id
            ORDER BY random()
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        src = row["user_id"]
        suffix = new_user_id  # bereits eindeutig

        # Reihenfolge wichtig: erst user_trips (Parent), dann trip_legs (FK auf trip_id).
        _copy_user_table(cur, "user_trips", src, {
            "trip_id": f"trip_id || '_' || '{suffix}'",
            "user_id": f"'{new_user_id}'",
        })
        _copy_user_table(cur, "trip_legs", src, {
            "leg_id": f"leg_id || '_' || '{suffix}'",
            "trip_id": f"trip_id || '_' || '{suffix}'",
            "user_id": f"'{new_user_id}'",
            "user_subscription_id": "NULL",  # Abo-Referenz der Quell-Persona nicht übernehmen
        })
        conn.commit()
        return src
    finally:
        conn.close()


# --- Handler ---

def register(req: RegisterRequest):
    """Legt einen neuen Nutzer samt Onboarding-Profil an."""
    u = req.user
    o = req.onboarding

    # NOT-NULL-Felder im Schema: first_name, last_name, date_of_birth, age,
    # home_city, home_postal_code. Bei übersprungenem Wohnort/Geburtsjahr hier
    # Fallbacks setzen, sonst schlägt der INSERT fehl.
    if not (u.first_name and u.last_name):
        raise HTTPException(status_code=422, detail="Vor- und Nachname sind erforderlich.")
    home_city = u.home_city or "unknown"
    home_postal_code = u.home_postal_code or "00000"
    date_of_birth = u.date_of_birth or "1970-01-01"
    age = u.age if u.age is not None else 0

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    onboarding_id = f"onb_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(req.credentials.password) if req.credentials.password else None

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users
              (user_id, email, username, first_name, last_name, date_of_birth,
               age, gender, home_city, home_postal_code, home_country_code, password_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (user_id, u.email, u.email, u.first_name, u.last_name, date_of_birth,
             age, u.gender, home_city, home_postal_code, u.home_country_code or "DE", password_hash),
        )

        cur.execute(
            """
            INSERT INTO user_onboardings
              (onboarding_id, user_id, work_city, work_postal_code, work_arrangement,
               remote_work_share, household_size, income_band,
               mobility_budget_monthly_eur, has_driving_license, car_access, bike_access,
               preferred_transport_modes, avoided_transport_modes,
               score_emission, score_money, score_flexibility,
               typical_weekday_pattern, typical_weekend_pattern,
               travel_statement, activity_statement)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (onboarding_id, user_id, o.work_city, o.work_postal_code, o.work_arrangement,
             o.remote_work_share, o.household_size, o.income_band,
             o.mobility_budget_monthly_eur, o.has_driving_license, o.car_access, o.bike_access,
             o.preferred_transport_modes, o.avoided_transport_modes,
             o.score_emission, o.score_money, o.score_flexibility,
             o.typical_weekday_pattern, o.typical_weekend_pattern,
             o.travel_statement or "n/a", o.activity_statement or "n/a"),
        )

        # user_subscriptions: best-effort. Versucht, den service-Key auf einen
        # Katalogeintrag zu mappen. ACHTUNG zur Modellierung:
        #   subscription_type + billing_cycle liegen im Schema in
        #   subscription_catalogs (global), NICHT pro Nutzer. "employer_benefit" /
        #   "student_benefit" ist aber pro Nutzer. -> ggf. neue Spalte auf
        #   user_subscriptions (z. B. acquisition_channel) ergänzen. Bis dahin
        #   wird der Typ hier nicht persistiert.
        for s in req.subscriptions:
            cur.execute(
                "SELECT subscription_id FROM subscription_catalogs "
                "WHERE provider_plan_id = ? OR provider_id = ? LIMIT 1",
                (s.service, s.service),
            )
            row = cur.fetchone()
            sub_catalog_id = row["subscription_id"] if row else None
            cur.execute(
                """
                INSERT INTO user_subscriptions
                  (user_subscription_id, user_id, subscription_id, subscription_status)
                VALUES (?,?,?,?)
                """,
                (f"usub_{uuid.uuid4().hex[:12]}", user_id, sub_catalog_id, "active"),
            )

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Registrierung fehlgeschlagen: {e}")
    finally:
        conn.close()

    # Neuen User mit einer zufälligen Seed-Persona "verbinden" (Trips kopieren), damit
    # die Analyse im Dashboard Daten hat. Best-effort: eigene Transaktion, Fehler hier
    # brechen die bereits erfolgreiche Registrierung nicht ab.
    linked_from = None
    try:
        linked_from = _link_random_persona(user_id)
    except Exception:
        import traceback
        traceback.print_exc()

    return {
        "status": "success",
        "user_id": user_id,
        # Gleiche kompakte Form wie /api/login, damit das Frontend die Session
        # direkt setzen kann (Auto-Login nach der Registrierung).
        "user": {
            "id": user_id,
            "name": f"{u.first_name} {u.last_name}".strip(),
            "firstName": u.first_name,
            "username": u.email,
            "email": u.email,
        },
        "linked_persona": linked_from,
    }