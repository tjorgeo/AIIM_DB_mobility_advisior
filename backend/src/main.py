import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from register_endpoint import register 
from auth_utils import verify_password


from database import ping_db
from analysis_service import AnalysisService

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
    # Build the advisor's LangGraph checkpointer and create its tables up front, so a
    # misconfigured checkpointer fails loudly at boot rather than on the first chat turn.
    # Never fatal: the app still serves analysis + the template briefing without it.
    try:
        from agent.advisor.agent import setup_agent
        setup_agent()
        print("Advisor checkpointer ready.")
    except Exception:
        import traceback
        traceback.print_exc()
        print("Advisor checkpointer setup failed; chat memory will be limited.")
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

analysis = AnalysisService()

# --- PYDANTIC SCHEMAS ---

class AnalyzeRequest(BaseModel):
    user_id: str
    # Bypass the read-through cache and recompute (e.g. an explicit "Re-analyze").
    force: bool = False

class ApproveRequest(BaseModel):
    scenario_id: str

class SessionChatRequest(BaseModel):
    # The conversation so far (roles user/assistant). An empty list — or a list with no
    # user message yet — requests the opening briefing (turn 0). ``lang`` selects the
    # briefing language ("de"/"en").
    messages: list = []
    lang: str = "de"

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
    forecast_horizon_days: int = 365
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

    # Fetch onboardings and subscriptions in two bulk queries and group them in Python,
    # rather than issuing two extra queries per user (the old N+1). Constant query count
    # regardless of how many users exist.
    cursor.execute(
        """
        SELECT user_id, occupation, score_emission, score_money, score_flexibility,
               preferred_transport_modes, mobility_budget_monthly_eur
        FROM user_onboardings
        """
    )
    onboarding_by_user = {}
    for o in cursor.fetchall():
        o = dict(o)
        onboarding_by_user[o.pop("user_id")] = o

    cursor.execute(
        """
        SELECT s.user_id, c.provider_name, c.provider_plan_name, c.monthly_cost_eur,
               s.subscription_status, s.is_primary_mobility_option
        FROM user_subscriptions s
        LEFT JOIN subscription_catalogs c ON c.subscription_id = s.subscription_id
        """
    )
    subs_by_user = {}
    for s in cursor.fetchall():
        s = dict(s)
        subs_by_user.setdefault(s.pop("user_id"), []).append(s)

    conn.close()

    personas = []
    for row in rows:
        r = dict(row)
        r["name"] = f"{r['first_name']} {r['last_name']}".strip()
        uid = r["user_id"]
        r["preferences"] = onboarding_by_user.get(uid)
        r["subscriptions"] = subs_by_user.get(uid, [])
        personas.append(r)

    return personas

@app.post("/api/analyze")
def analyze_portfolio(req: AnalyzeRequest):
    """
    Triggers the 4-Agent orchestration flow for a specific traveler persona.

    Reuses the user's latest recommendation when available (unless ``force``); a fresh
    run is synchronous and waits for the LLM forecast + Analyst memo (when an LLM is
    configured), so the response already reflects the final result — no follow-up call
    needed to see calendar-driven life events or the upgraded memo prose.
    """
    try:
        return analysis.run_analysis(req.user_id, force=req.force)
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
    success = analysis.approve_recommendation(rec_id, req.scenario_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Recommendation session {rec_id} not found.")
    return {
        "status": "success",
        "message": f"Scenario {req.scenario_id} approved for recommendation {rec_id}.",
        "recommendation_id": rec_id,
        "scenario_id": req.scenario_id
    }

@app.post("/api/chat/{session_id}")
def chat_session(session_id: str, req: SessionChatRequest):
    """The single conversational surface — the Advisor agent grounded in one analysis
    session. With no user message yet it returns the opening briefing (turn 0, which
    replaces the old memo and works even without an LLM via the template fallback);
    otherwise it answers the follow-up (requires an LLM key, else 503).
    """
    from agent.session import get_session
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    from agent.advisor import opening_briefing, run_turn
    has_user_message = any(m.get("role") == "user" for m in (req.messages or []))
    if not has_user_message:
        reply, trace_id = opening_briefing(session_id, lang=req.lang)
        return {"reply": reply, "trace_id": trace_id, "session_id": session_id}

    from agent.llm import llm_available
    if not llm_available():
        raise HTTPException(status_code=503, detail="Chat LLM not configured (UNI_GPT_API_KEY missing).")
    try:
        reply, trace_id = run_turn(session_id, req.messages)
        return {"reply": reply, "trace_id": trace_id, "session_id": session_id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/api/chat/{session_id}/stream")
def chat_session_stream(session_id: str, req: SessionChatRequest):
    """Streaming variant of the follow-up chat — Server-Sent Events. Each event is a JSON
    line: ``{"type":"token","text":"…"}`` per token, then ``{"type":"done","trace_id":…}``.
    Requires an LLM key (503 otherwise); the opening briefing is served non-streamed via
    ``POST /api/chat/{session_id}``.
    """
    from agent.session import get_session
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    from agent.llm import llm_available
    if not llm_available():
        raise HTTPException(status_code=503, detail="Chat LLM not configured (UNI_GPT_API_KEY missing).")

    from agent.advisor import stream_turn

    def event_stream():
        try:
            for event in stream_turn(session_id, req.messages):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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

    Try one of the four personas with travel data (see database/seed/PERSONAS.md):
      - ce92d8e0-065e-589b-a60e-c692ef2d2ff9  (Julia Berger — BahnCard 25 should become BahnCard 50, Deutschlandticket pays off)
      - e1eb9483-d268-57cf-9b5f-0ef5e1a7fed2  (Jonas Keller — no subscription, should pick up a Deutschlandticket)
      - 725be174-ba53-516d-8beb-a4056cbac517  (Simone Wagner — three subscriptions, two should be cancelled)
      - 932d3626-708a-596b-a1fc-99c2fa1ce9b3  (Elif Yildiz — car-free, car-sharing-centric multi-modal freelancer)
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
def test_forecaster_for_user(user_id: str, forecast_horizon_days: int = 365, as_of_date: str | None = None):
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
    from agent.engines import analyze_portfolio, attach_projected_category_analysis
    from agent.llm_steps.forecast_reasoner import forecast

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
        attach_projected_category_analysis(
            result, analyst_out["mode_breakdown"], ctx["subscriptions"],
            ctx["pricing_catalog"], ctx["user"].get("age"),
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
    agent/llm_steps/forecast_reasoner.py MOCK_ANALYST_SUMMARY / MOCK_CALENDAR_EVENTS for
    the expected shape of each field.
    """
    from agent.llm_steps.forecast_reasoner import forecast
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
