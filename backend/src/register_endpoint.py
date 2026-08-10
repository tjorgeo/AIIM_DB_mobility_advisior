"""Account registration followed by an optional mobility onboarding.

``POST /api/register`` creates the essential account plus an empty onboarding row.
``POST /api/onboarding/{user_id}/complete`` fills that row and records the user's
initial subscription holdings when the optional wizard is completed.
"""

import re
import time
import uuid
from collections import deque
from datetime import date
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple

# vorhandener Helper im Backend
from database import get_connection
from auth_utils import hash_password

# Fixed allowlist of tables _copy_user_table may touch — defence in depth so the
# dynamic table name can never be attacker-shaped even after a future refactor.
_COPYABLE_TABLES = {"user_trips", "trip_legs"}

# Minimal email format check (normalisation + a sane shape, not full RFC 5322).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Lightweight in-memory, per-IP fixed-window rate limit for /api/register. Single
# process only (fine for the demo container); a multi-process deploy would need
# shared state (e.g. Redis).
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_S = 600  # 10 minutes
_register_hits: Dict[str, deque] = {}


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    hits = _register_hits.setdefault(client_ip, deque())
    while hits and now - hits[0] > _RATE_LIMIT_WINDOW_S:
        hits.popleft()
    if len(hits) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Zu viele Registrierungen. Bitte später erneut versuchen.")
    hits.append(now)


# --- Request-Schemas (locker gehalten; Frontend liefert null für Skips) ---

class RegisterUser(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    gender: str = "not_specified"
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    home_city: Optional[str] = None
    home_postal_code: Optional[str] = None
    home_country_code: str = "DE"


class RegisterOnboarding(BaseModel):
    has_driving_license: Optional[bool] = None
    car_access: Optional[str] = None
    bike_access: List[str] = Field(default_factory=list)
    preferred_transport_modes: List[str] = Field(default_factory=list)
    avoided_transport_modes: List[str] = Field(default_factory=list)
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
    connected_mobility_accounts: List[str] = Field(default_factory=list, max_length=50)


class RegisterSubscription(BaseModel):
    service: str
    subscription_type: str = "subscription"
    billing_cycle: str = "monthly"


class RegisterCredentials(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    user: RegisterUser
    onboarding: RegisterOnboarding = Field(default_factory=RegisterOnboarding)
    subscriptions: List[RegisterSubscription] = Field(default_factory=list)
    credentials: RegisterCredentials


class OnboardingUserDetails(BaseModel):
    gender: str = "not_specified"
    date_of_birth: Optional[date] = None
    home_city: Optional[str] = None
    home_postal_code: Optional[str] = None
    home_country_code: str = "DE"


class OnboardingCompletionRequest(BaseModel):
    user: OnboardingUserDetails = Field(default_factory=OnboardingUserDetails)
    onboarding: RegisterOnboarding = Field(default_factory=RegisterOnboarding)
    subscriptions: List[RegisterSubscription] = Field(default_factory=list)


def _age_on(born: date | None) -> int | None:
    if born is None:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _has_onboarding_data(onboarding: RegisterOnboarding, subscriptions: list) -> bool:
    values = onboarding.model_dump()
    return bool(subscriptions) or any(
        value not in (None, "", [], {})
        for value in values.values()
    )


def _insert_subscriptions(cur, user_id: str, subscriptions: List[RegisterSubscription]) -> None:
    """Persist the subscriptions declared during the one-time onboarding setup."""
    for subscription in subscriptions:
        cur.execute(
            "SELECT subscription_id FROM subscription_catalogs "
            "WHERE provider_plan_id = ? OR provider_id = ? LIMIT 1",
            (subscription.service, subscription.service),
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


# --- Seed-Persona-Verknüpfung (Demo) ---

def _copy_user_table(cur, table: str, src_user: str, overrides: Dict[str, Tuple[str, tuple]]) -> None:
    """Kopiert alle Zeilen einer user-bezogenen Tabelle von src_user, wobei einzelne
    Spalten per SQL-Ausdruck überschrieben werden (z. B. user_id/PK-Remap). Die
    Spaltenliste kommt dynamisch aus information_schema, damit es schema-robust bleibt.

    ``overrides`` map jede zu überschreibende Spalte auf ``(expr, params)`` — ein
    SQL-Ausdruck mit ``%s``-Platzhaltern und den zugehörigen gebundenen Werten, damit
    keine Nutzer-/ID-Werte in den SQL-String interpoliert werden. Tabellen-/Spaltennamen
    stammen aus einer festen Allowlist bzw. information_schema (nie nutzergesteuert)."""
    if table not in _COPYABLE_TABLES:
        raise ValueError(f"table not allowed: {table}")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    cols = [r["column_name"] for r in cur.fetchall()]
    if not cols:
        return

    select_exprs = []
    override_params: list = []
    for c in cols:
        if c in overrides:
            expr, params = overrides[c]
            select_exprs.append(expr)
            override_params.extend(params)
        else:
            # identity copy — c comes from information_schema, not user input
            select_exprs.append(c)

    cur.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM {table} WHERE user_id = %s",
        (*override_params, src_user),
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
        # Werte werden als Query-Parameter gebunden (%s), nicht in SQL interpoliert.
        _copy_user_table(cur, "user_trips", src, {
            "trip_id": ("trip_id || '_' || %s", (suffix,)),
            "user_id": ("%s", (new_user_id,)),
        })
        _copy_user_table(cur, "trip_legs", src, {
            "leg_id": ("leg_id || '_' || %s", (suffix,)),
            "trip_id": ("trip_id || '_' || %s", (suffix,)),
            "user_id": ("%s", (new_user_id,)),
            "user_subscription_id": ("NULL", ()),  # Abo-Referenz der Quell-Persona nicht übernehmen
        })
        conn.commit()
        return src
    finally:
        conn.close()


# --- Handler ---

def register(req: RegisterRequest, request: Request):
    """Create the essential account and an initially empty onboarding record."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    u = req.user
    o = req.onboarding

    first_name = (u.first_name or "").strip()
    last_name = (u.last_name or "").strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=422, detail="Vor- und Nachname sind erforderlich.")

    # E-Mail normalisieren + validieren (email == username in diesem Flow).
    email = (u.email or "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Bitte eine gültige E-Mail-Adresse angeben.")

    if u.date_of_birth and u.date_of_birth > date.today():
        raise HTTPException(status_code=422, detail="Das Geburtsdatum darf nicht in der Zukunft liegen.")

    home_city = (u.home_city or "").strip() or None
    home_postal_code = (u.home_postal_code or "").strip() or None
    age = _age_on(u.date_of_birth)
    onboarding_status = "completed" if _has_onboarding_data(o, req.subscriptions) else "not_started"

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    onboarding_id = f"onb_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(req.credentials.password)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Duplikat-Prüfung (case-insensitiv). Die partiellen UNIQUE-Indizes auf
        # users(lower(email))/users(lower(username)) sind die harte Garantie; dieser
        # Vorab-Check liefert dem Frontend eine saubere 409 statt eines DB-Fehlers.
        cur.execute(
            "SELECT 1 FROM users WHERE lower(email) = ? OR lower(username) = ? LIMIT 1",
            (email, email),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Diese E-Mail ist bereits registriert.")

        cur.execute(
            """
            INSERT INTO users
              (user_id, email, username, first_name, last_name, date_of_birth,
               age, gender, home_city, home_postal_code, home_country_code, password_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (user_id, email, email, first_name, last_name, u.date_of_birth,
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
               travel_statement, activity_statement, connected_mobility_accounts,
               onboarding_status, onboarding_completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    CASE WHEN ? = 'completed' THEN NOW() ELSE NULL END)
            """,
            (onboarding_id, user_id, o.work_city, o.work_postal_code, o.work_arrangement,
             o.remote_work_share, o.household_size, o.income_band,
             o.mobility_budget_monthly_eur, o.has_driving_license, o.car_access, o.bike_access,
             o.preferred_transport_modes, o.avoided_transport_modes,
             o.score_emission, o.score_money, o.score_flexibility,
             o.typical_weekday_pattern, o.typical_weekend_pattern,
             o.travel_statement or "n/a", o.activity_statement or "n/a",
             list(dict.fromkeys(account for account in o.connected_mobility_accounts if account)),
             onboarding_status, onboarding_status),
        )

        # user_subscriptions: best-effort. Versucht, den service-Key auf einen
        # Katalogeintrag zu mappen. ACHTUNG zur Modellierung:
        #   subscription_type + billing_cycle liegen im Schema in
        #   subscription_catalogs (global), NICHT pro Nutzer. "employer_benefit" /
        #   "student_benefit" ist aber pro Nutzer. -> ggf. neue Spalte auf
        #   user_subscriptions (z. B. acquisition_channel) ergänzen. Bis dahin
        #   wird der Typ hier nicht persistiert.
        _insert_subscriptions(cur, user_id, req.subscriptions)

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        import traceback
        traceback.print_exc()
        # Keine rohe Exception an den Client leaken (interne Details / Schemainfos).
        raise HTTPException(status_code=500, detail="Registrierung fehlgeschlagen.")
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
            "name": f"{first_name} {last_name}".strip(),
            "firstName": first_name,
            "username": email,
            "email": email,
            "onboardingStatus": onboarding_status,
        },
        "linked_persona": linked_from,
    }


def complete_onboarding(user_id: str, req: OnboardingCompletionRequest):
    """Persist the optional onboarding after the essential account already exists.

    The endpoint is idempotent once completion succeeded: a repeated request returns
    the existing account state and does not duplicate subscriptions.
    """
    user = req.user
    onboarding = req.onboarding
    if user.date_of_birth and user.date_of_birth > date.today():
        raise HTTPException(status_code=422, detail="Das Geburtsdatum darf nicht in der Zukunft liegen.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.first_name, u.last_name, u.email, u.username,
                   o.onboarding_status
            FROM users u
            LEFT JOIN user_onboardings o ON o.user_id = u.user_id
            WHERE u.user_id = ?
            FOR UPDATE OF u
            """,
            (user_id,),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Profil nicht gefunden.")
        existing = dict(existing)

        if existing.get("onboarding_status") == "completed":
            conn.commit()
            return {
                "status": "success",
                "user": {
                    "id": user_id,
                    "name": f"{existing.get('first_name') or ''} {existing.get('last_name') or ''}".strip(),
                    "firstName": existing.get("first_name") or "",
                    "email": existing.get("email"),
                    "username": existing.get("username"),
                    "onboardingStatus": "completed",
                },
            }

        home_city = (user.home_city or "").strip() or None
        home_postal_code = (user.home_postal_code or "").strip() or None
        cur.execute(
            """
            UPDATE users
            SET date_of_birth = ?, age = ?, gender = ?, home_city = ?,
                home_postal_code = ?, home_country_code = ?
            WHERE user_id = ?
            """,
            (
                user.date_of_birth, _age_on(user.date_of_birth), user.gender,
                home_city, home_postal_code,
                (user.home_country_code or "DE").strip().upper(), user_id,
            ),
        )

        cur.execute(
            """
            UPDATE user_onboardings
            SET work_city = ?, work_postal_code = ?, work_arrangement = ?,
                remote_work_share = ?, household_size = ?, income_band = ?,
                mobility_budget_monthly_eur = ?, has_driving_license = ?, car_access = ?,
                bike_access = ?, preferred_transport_modes = ?, avoided_transport_modes = ?,
                score_emission = ?, score_money = ?, score_flexibility = ?,
                typical_weekday_pattern = ?, typical_weekend_pattern = ?,
                travel_statement = ?, activity_statement = ?,
                connected_mobility_accounts = ?, onboarding_status = 'completed',
                onboarding_completed_at = NOW()
            WHERE user_id = ?
            """,
            (
                onboarding.work_city, onboarding.work_postal_code, onboarding.work_arrangement,
                onboarding.remote_work_share, onboarding.household_size, onboarding.income_band,
                onboarding.mobility_budget_monthly_eur, onboarding.has_driving_license,
                onboarding.car_access, onboarding.bike_access,
                onboarding.preferred_transport_modes, onboarding.avoided_transport_modes,
                onboarding.score_emission, onboarding.score_money,
                onboarding.score_flexibility, onboarding.typical_weekday_pattern,
                onboarding.typical_weekend_pattern, onboarding.travel_statement or "n/a",
                onboarding.activity_statement or "n/a",
                list(dict.fromkeys(account for account in onboarding.connected_mobility_accounts if account)),
                user_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=409, detail="Onboarding-Profil fehlt.")

        _insert_subscriptions(cur, user_id, req.subscriptions)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "success",
        "user": {
            "id": user_id,
            "name": f"{existing.get('first_name') or ''} {existing.get('last_name') or ''}".strip(),
            "firstName": existing.get("first_name") or "",
            "email": existing.get("email"),
            "username": existing.get("username"),
            "onboardingStatus": "completed",
        },
    }
