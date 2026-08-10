"""Read and update the structured onboarding profile for one user.

Profile updates are full-form replacements for ``users`` and the fields collected in
``user_onboardings``. Subscriptions are deliberately read-only in this endpoint; the
profile response includes active and historical holdings for display only.
"""

import re
import uuid
from datetime import date
from typing import Literal

import psycopg2
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from database import get_connection
from agent.schema_map import clean_row


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProfileUser(BaseModel):
    first_name: str
    last_name: str
    email: str
    gender: Literal["female", "male", "diverse", "not_specified"] = "not_specified"
    date_of_birth: date | None = None
    home_city: str | None = None
    home_postal_code: str | None = None
    home_country_code: str = Field(default="DE", min_length=2, max_length=2)


class ProfileOnboarding(BaseModel):
    has_driving_license: bool | None = None
    car_access: Literal["none", "occasional", "shared", "own"] | None = None
    bike_access: list[str] = Field(default_factory=list)
    preferred_transport_modes: list[str] = Field(default_factory=list)
    avoided_transport_modes: list[str] = Field(default_factory=list)
    score_money: int | None = Field(default=None, ge=0, le=100)
    score_emission: int | None = Field(default=None, ge=0, le=100)
    score_flexibility: int | None = Field(default=None, ge=0, le=100)
    work_arrangement: str | None = None
    work_city: str | None = None
    work_postal_code: str | None = None
    remote_work_share: float | None = Field(default=None, ge=0, le=1)
    mobility_budget_monthly_eur: float | None = Field(default=None, ge=0)
    household_size: int | None = Field(default=None, ge=1)
    income_band: str | None = None
    typical_weekday_pattern: str | None = None
    typical_weekend_pattern: str | None = None
    travel_statement: str = ""
    activity_statement: str = ""
    connected_mobility_accounts: list[str] = Field(default_factory=list, max_length=50)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: ProfileUser
    onboarding: ProfileOnboarding


def ensure_profile_schema() -> None:
    """Apply additive profile columns on existing Docker volumes.

    Postgres init scripts do not rerun for an existing volume, so these idempotent
    migrations keep profile editing usable after an ordinary container rebuild.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "ALTER TABLE user_subscriptions "
            "ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        )
        cursor.execute(
            "ALTER TABLE user_onboardings "
            "ADD COLUMN IF NOT EXISTS connected_mobility_accounts TEXT[] NOT NULL DEFAULT '{}'"
        )
        cursor.execute("ALTER TABLE users ALTER COLUMN date_of_birth DROP NOT NULL")
        cursor.execute("ALTER TABLE users ALTER COLUMN age DROP NOT NULL")
        cursor.execute("ALTER TABLE users ALTER COLUMN home_city DROP NOT NULL")
        cursor.execute("ALTER TABLE users ALTER COLUMN home_postal_code DROP NOT NULL")
        cursor.execute(
            "ALTER TABLE user_onboardings "
            "ADD COLUMN IF NOT EXISTS onboarding_status TEXT NOT NULL DEFAULT 'completed'"
        )
        cursor.execute(
            "ALTER TABLE user_onboardings "
            "ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ"
        )
        conn.commit()
    finally:
        conn.close()


def _age_on(born: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _unique_ids(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _compact_user(user: dict) -> dict:
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    return {
        "id": user["user_id"],
        "name": f"{first} {last}".strip(),
        "firstName": first,
        "email": user.get("email"),
        "username": user.get("username"),
        "initials": f"{first[:1]}{last[:1]}".upper(),
    }


def get_profile(user_id: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, email, username, first_name, last_name, date_of_birth, "
            "age, gender, home_city, home_postal_code, home_country_code "
            "FROM users WHERE user_id = ?",
            (user_id,),
        )
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Profil nicht gefunden.")

        cursor.execute("SELECT * FROM user_onboardings WHERE user_id = ?", (user_id,))
        onboarding_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT s.user_subscription_id, s.subscription_id, s.subscription_status,
                   s.valid_from, s.valid_until, s.status_changed_at,
                   c.provider_id, c.provider_plan_id, c.provider_name,
                   c.provider_plan_name, c.subscription_category,
                   c.subscription_type, c.billing_cycle, c.travel_class,
                   c.monthly_cost_eur, c.annual_cost_eur
            FROM user_subscriptions s
            LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
            WHERE s.user_id = ?
            ORDER BY (s.subscription_status = 'active') DESC, s.status_changed_at DESC
            """,
            (user_id,),
        )
        subscriptions = [clean_row(row) for row in cursor.fetchall()]

        user = clean_row(user_row)
        onboarding = clean_row(onboarding_row) if onboarding_row else {}
        return {
            "user": user,
            "onboarding": onboarding,
            "subscriptions": subscriptions,
        }
    finally:
        conn.close()


def update_profile(user_id: str, req: ProfileUpdateRequest):
    user = req.user
    onboarding = req.onboarding
    first_name = user.first_name.strip()
    last_name = user.last_name.strip()
    email = user.email.strip().lower()
    home_city = (user.home_city or "").strip() or None
    home_postal_code = (user.home_postal_code or "").strip() or None
    country = user.home_country_code.strip().upper()

    if not first_name or not last_name:
        raise HTTPException(status_code=422, detail="Vor- und Nachname sind erforderlich.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Bitte eine gültige E-Mail-Adresse angeben.")
    if user.date_of_birth and user.date_of_birth > date.today():
        raise HTTPException(status_code=422, detail="Das Geburtsdatum darf nicht in der Zukunft liegen.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT email, username FROM users WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Profil nicht gefunden.")
        existing = dict(existing)

        username = existing.get("username")
        if not username or (existing.get("email") and username.lower() == existing["email"].lower()):
            username = email

        cursor.execute(
            """
            UPDATE users
            SET email = ?, username = ?, first_name = ?, last_name = ?,
                date_of_birth = ?, age = ?, gender = ?, home_city = ?,
                home_postal_code = ?, home_country_code = ?
            WHERE user_id = ?
            """,
            (
                email, username, first_name, last_name, user.date_of_birth,
                _age_on(user.date_of_birth) if user.date_of_birth else None, user.gender, home_city,
                home_postal_code, country, user_id,
            ),
        )

        cursor.execute(
            """
            UPDATE user_onboardings
            SET work_city = ?, work_postal_code = ?, work_arrangement = ?,
                remote_work_share = ?, household_size = ?, income_band = ?,
                mobility_budget_monthly_eur = ?, has_driving_license = ?, car_access = ?,
                bike_access = ?, preferred_transport_modes = ?, avoided_transport_modes = ?,
                score_emission = ?, score_money = ?, score_flexibility = ?,
                typical_weekday_pattern = ?, typical_weekend_pattern = ?,
                travel_statement = ?, activity_statement = ?,
                connected_mobility_accounts = ?,
                onboarding_status = CASE
                    WHEN onboarding_status = 'completed' THEN 'completed'
                    ELSE 'in_progress'
                END
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
                _unique_ids(onboarding.connected_mobility_accounts), user_id,
            ),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO user_onboardings
                  (onboarding_id, user_id, work_city, work_postal_code, work_arrangement,
                   remote_work_share, household_size, income_band,
                   mobility_budget_monthly_eur, has_driving_license, car_access, bike_access,
                   preferred_transport_modes, avoided_transport_modes,
                   score_emission, score_money, score_flexibility,
                   typical_weekday_pattern, typical_weekend_pattern,
                   travel_statement, activity_statement, connected_mobility_accounts,
                   onboarding_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"onb_{uuid.uuid4().hex[:12]}", user_id,
                    onboarding.work_city, onboarding.work_postal_code,
                    onboarding.work_arrangement, onboarding.remote_work_share,
                    onboarding.household_size, onboarding.income_band,
                    onboarding.mobility_budget_monthly_eur,
                    onboarding.has_driving_license, onboarding.car_access,
                    onboarding.bike_access, onboarding.preferred_transport_modes,
                    onboarding.avoided_transport_modes, onboarding.score_emission,
                    onboarding.score_money, onboarding.score_flexibility,
                    onboarding.typical_weekday_pattern,
                    onboarding.typical_weekend_pattern,
                    onboarding.travel_statement or "n/a",
                    onboarding.activity_statement or "n/a",
                    _unique_ids(onboarding.connected_mobility_accounts), "in_progress",
                ),
            )
        cursor.execute(
            "SELECT onboarding_status FROM user_onboardings WHERE user_id = ?",
            (user_id,),
        )
        status_row = cursor.fetchone()
        onboarding_status = (
            dict(status_row).get("onboarding_status") if status_row else "in_progress"
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="E-Mail oder Benutzername wird bereits verwendet.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "success",
        "user": {
            **_compact_user({
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "username": username,
            }),
            "onboardingStatus": onboarding_status,
        },
    }
