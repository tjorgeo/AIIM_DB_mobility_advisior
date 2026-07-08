import os

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from register_endpoint import register 
from auth_utils import verify_password


from database import ping_db
from orchestrator import Orchestrator

# Shared demo password. The seed data has no per-user credentials, so login
# authenticates the identifier (username/email) against the real users and
# checks this single shared password. Override via the DEMO_LOGIN_PASSWORD env.
DEMO_LOGIN_PASSWORD = os.environ.get("DEMO_LOGIN_PASSWORD", "mobility")

# Verify the database is reachable on startup. The production schema and the
# dummy test user are provisioned by Postgres from database/init/*.sql, so the
# backend only confirms connectivity rather than creating/seeding tables itself.
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Verifying Postgres connectivity (schema provisioned by database/init)...")
    ping_db()
    yield
    print("Shutting down DB MoveOptimizer Backend...")
    # Flush any buffered Langfuse traces so nothing is lost on shutdown (no-op
    # when Langfuse is not configured).
    from agent.observability import flush as flush_langfuse
    flush_langfuse()

app = FastAPI(
    title="DB MoveOptimizer — Strategy IT Consulting API Gateway",
    description="Synchronous multi-agent coordination API for mobility recommendation engine.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration. Pin explicit origins (a wildcard combined
# with allow_credentials=True is an invalid/insecure combo browsers reject). Override
# for other environments via the comma-separated ALLOWED_ORIGINS env var.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

# --- PYDANTIC SCHEMAS ---

class AnalyzeRequest(BaseModel):
    user_id: str
    # Bypass the read-through cache and recompute (e.g. an explicit "Re-analyze").
    force: bool = False

class ApproveRequest(BaseModel):
    scenario_id: str

class ChatRequest(BaseModel):
    user_id: str
    messages: list

class LoginRequest(BaseModel):
    identifier: str
    password: str

class FeedbackRequest(BaseModel):
    trace_id: str
    value: int          # 1 = thumbs up, 0 = thumbs down
    comment: str | None = None

class ForecasterTestRequest(BaseModel):
    analyst_summary: dict
    calendar_events: list | None = None          # pre-structured CalendarEvent dicts
    ics_text: str | None = None                  # raw ICS — parsed and filtered by the LLM
    raw_calendar_entries: list | None = None     # pre-parsed raw entries (skips ICS parsing)
    forecast_horizon_days: int = 90
    as_of_date: str | None = None                # ISO date; overrides "today" for seasonal testing

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "DB MoveOptimizer Agent Sandbox Backend",
        "version": "1.0.0"
    }

app.post("/api/register")(register)   
@app.post("/api/login")
def login(req: LoginRequest):
    """
    Authentifiziert per Username/E-Mail. Nutzt das eigene Passwort des Nutzers,
    falls eines gespeichert ist (via /api/register angelegt) — sonst Fallback auf
    das gemeinsame Demo-Passwort, damit die Seed-Personas weiter funktionieren.
    """
    from database import get_connection
 
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, first_name, last_name, email, username, password_hash
        FROM users
        WHERE username = ? OR email = ?
        ORDER BY (username = ?) DESC
        LIMIT 1
        """,
        (req.identifier, req.identifier, req.identifier),
    )
    row = cursor.fetchone()
    conn.close()
 
    if not row:
        raise HTTPException(
            status_code=401, detail="No account matches that username or email."
        )
 
    user = dict(row)
    stored = user.get("password_hash")
    if stored:
        # Registrierter Nutzer -> eigenes Passwort prüfen
        if not verify_password(req.password, stored):
            raise HTTPException(status_code=401, detail="Incorrect password.")
    else:
        # Seed-Persona ohne Hash -> gemeinsames Demo-Passwort
        if req.password != DEMO_LOGIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Incorrect password.")
 
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    initials = f"{first[:1]}{last[:1]}".upper()
    return {
        "id": user["user_id"],
        "name": f"{first} {last}".strip(),
        "firstName": first,
        "email": user.get("email"),
        "username": user.get("username"),
        "initials": initials,
    }


@app.get("/api/personas")
def get_personas():
    """
    Returns the users present in the production database (database/init schema),
    each enriched with onboarding preferences and current subscriptions. Lets the
    simulator confirm which mock users are accessible.
    """
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, first_name, last_name, email,
               home_city, home_postal_code, age, gender
        FROM users
        ORDER BY user_id
        """
    )
    rows = cursor.fetchall()

    personas = []
    for row in rows:
        r = dict(row)
        r["name"] = f"{r['first_name']} {r['last_name']}".strip()
        uid = r["user_id"]

        # Onboarding preferences (0-100 scores) for this user, if present.
        cursor.execute(
            """
            SELECT occupation, score_emission, score_money, score_flexibility,
                   preferred_transport_modes, mobility_budget_monthly_eur
            FROM user_onboardings
            WHERE user_id = ?
            """,
            (uid,),
        )
        onboarding = cursor.fetchone()
        r["preferences"] = dict(onboarding) if onboarding else None

        # Active subscriptions, joined to the catalog for human-readable names.
        cursor.execute(
            """
            SELECT c.provider_name, c.provider_plan_name, c.monthly_cost_eur,
                   s.subscription_status, s.is_primary_mobility_option
            FROM user_subscriptions s
            LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
            WHERE s.user_id = ?
            """,
            (uid,),
        )
        r["subscriptions"] = [dict(s) for s in cursor.fetchall()]

        personas.append(r)

    conn.close()
    return personas

@app.post("/api/analyze")
def analyze_portfolio(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Triggers the 4-Agent orchestration flow for a specific traveler persona.

    Reuses the user's latest recommendation when available (unless ``force``); a fresh
    run returns the deterministic numbers with the template memo immediately and
    schedules the slow LLM memo as a background task, so the next mount serves the
    upgraded prose from cache.
    """
    try:
        pipeline_output = orchestrator.run_analysis(req.user_id, force=req.force)
        if pipeline_output.pop("_fresh", False):
            background_tasks.add_task(
                orchestrator.generate_memo, pipeline_output["session_id"], req.user_id
            )
        return pipeline_output
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline Orchestration Error: {str(e)}")

@app.post("/api/recommendations/{rec_id}/approve")
def approve_recommendation(rec_id: str, req: ApproveRequest):
    """
    Records customer approval for a recommended scenario in the database audit trail.
    """
    success = orchestrator.approve_recommendation(rec_id, req.scenario_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Recommendation session {rec_id} not found.")
    return {
        "status": "success",
        "message": f"Scenario {req.scenario_id} approved for recommendation {rec_id}.",
        "recommendation_id": rec_id,
        "scenario_id": req.scenario_id
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    """
    Conversational mobility advisor (agentic ReAct loop with catalogue tool use).
    Requires an LLM key; without one we return 503 and the frontend falls back to
    its scripted assistant.
    """
    from agent.llm import llm_available
    if not llm_available():
        raise HTTPException(status_code=503, detail="Chat LLM not configured (UNI_GPT_API_KEY missing).")
    try:
        from agent.communicator_agent import run_chat
        reply, trace_id = run_chat(req.user_id, req.messages)
        # trace_id lets the frontend attach a thumbs up/down score to this reply
        # (null when Langfuse tracing is disabled).
        return {"reply": reply, "trace_id": trace_id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    """
    Records end-user feedback (chat thumbs up/down) as a `user-thumbs` BOOLEAN
    score on the given Langfuse trace. No-op (still 200) when Langfuse tracing is
    disabled, so the frontend can call it unconditionally.
    """
    from agent.observability import create_score
    create_score(
        trace_id=req.trace_id,
        name="user-thumbs",
        value=1 if req.value else 0,
        data_type="BOOLEAN",
        comment=req.comment,
    )
    return {"status": "ok"}


@app.get("/api/analyst/{user_id}")
def test_analyst(user_id: str):
    """
    Run the analyst agent for a specific user and return the full output.
    Useful for inspecting usage statistics, dominant patterns, seasonality,
    subscription coverage, and detected inefficiencies without going through
    the full pipeline.

    Try one of the six personas with travel data:
      - 38bb9fdb-7d90-55a0-98d8-f9935f1aec70  (Mara Vogel — flat-pass commuter, well covered)
      - be6f3d9a-713a-5a56-bd77-5b27feea6827  (Tobias Hahn — BahnCard 50, frequent business traveler)
      - d90794d2-efac-5b8d-b1cd-01244a890cb2  (Nina Schröder — pure pay-as-you-go, no subscriptions)
      - 671fbc5b-99f1-505f-aaaa-1c682f552803  (Lukas Weber — over-subscribed, barely uses any of it)
      - b31247a7-eb90-533a-bff7-1f0d37d28adc  (Petra Sommer — thin data, joined ~6 weeks ago)
      - 99cb2bd6-228b-566d-a250-16290da30521  (Sandra Hoffmann — family, car-sharing + flat pass)
    """
    from agent.context import load_context
    from agent.engines import analyze_portfolio

    ctx = load_context(user_id)
    if ctx.get("error"):
        raise HTTPException(status_code=404, detail=ctx["error"])

    try:
        result = analyze_portfolio(
            ctx["travel_history"],
            ctx["subscriptions"],
            ctx["pricing_catalog"],
            user_age=ctx["user"].get("age"),
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analyst error: {str(e)}")


@app.get("/api/forecaster/{user_id}")
def test_forecaster_for_user(user_id: str, forecast_horizon_days: int = 90, as_of_date: str | None = None):
    """
    Run load_context -> analyze_portfolio -> forecast for a real seeded persona,
    stopping before the optimize/communicate steps of the full /api/analyze
    pipeline. Useful for inspecting the forecaster's output (LLM demand scenarios,
    or the deterministic fallback) on its own, against real travel history and
    calendar entries.

    Optional ``as_of_date`` (ISO "YYYY-MM-DD") overrides "today" — handy for
    checking the deterministic fallback's seasonal-month override against a
    persona's historical data without waiting for the real calendar to reach the
    relevant months (e.g. ``?as_of_date=2025-11-15`` to test a winter forecast now).

    Same six personas as /api/analyst/{user_id} work here.
    """
    from agent.context import load_context
    from agent.engines import analyze_portfolio, forecast

    ctx = load_context(user_id)
    if ctx.get("error"):
        raise HTTPException(status_code=404, detail=ctx["error"])

    try:
        analyst_out = analyze_portfolio(ctx["travel_history"], ctx["subscriptions"])
        result = forecast(
            analyst_out["forecaster_summary"],
            raw_calendar_entries=ctx["raw_calendar_entries"],
            forecast_horizon_days=forecast_horizon_days,
            as_of_date=as_of_date,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Forecaster error: {str(e)}")


@app.post("/api/forecaster/test")
def test_forecaster(req: ForecasterTestRequest):
    """
    Run the forecaster agent directly with supplied test data.
    Useful for experimenting with different analyst summaries and calendar events
    without going through the full analysis pipeline.

    Pass any analyst_summary and calendar_events you like — see
    agent/engines/forecasting.py MOCK_ANALYST_SUMMARY / MOCK_CALENDAR_EVENTS for
    the expected shape of each field.
    """
    from agent.engines import forecast
    try:
        result = forecast(
            req.analyst_summary,
            calendar_events=req.calendar_events,
            ics_text=req.ics_text,
            raw_calendar_entries=req.raw_calendar_entries,
            forecast_horizon_days=req.forecast_horizon_days,
            as_of_date=req.as_of_date,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Forecaster error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
