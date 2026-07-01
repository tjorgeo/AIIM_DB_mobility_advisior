import os

from fastapi import FastAPI, HTTPException
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

app = FastAPI(
    title="DB MoveOptimizer — Strategy IT Consulting API Gateway",
    description="Synchronous multi-agent coordination API for mobility recommendation engine.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

# --- PYDANTIC SCHEMAS ---

class AnalyzeRequest(BaseModel):
    user_id: str

class ApproveRequest(BaseModel):
    scenario_id: str

class ChatRequest(BaseModel):
    user_id: str
    messages: list

class OnboardingRequest(BaseModel):
    messages: list
    user_id: str | None = None

class LoginRequest(BaseModel):
    identifier: str
    password: str

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
def analyze_portfolio(req: AnalyzeRequest):
    """
    Triggers the 4-Agent synchronous orchestration flow for a specific traveler persona.
    """
    try:
        pipeline_output = orchestrator.run_analysis(req.user_id)
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
    from graph.llm import llm_available
    if not llm_available():
        raise HTTPException(status_code=503, detail="Chat LLM not configured (UNI_GPT_API_KEY missing).")
    try:
        from graph.chat_agent import run_chat
        reply = run_chat(req.user_id, req.messages)
        return {"reply": reply}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/api/onboarding")
def onboarding(req: OnboardingRequest):
    """
    Conversational onboarding agent. Collects a new user's mobility profile and
    persists it on completion. Requires an LLM key (503 otherwise).
    """
    from graph.llm import llm_available
    if not llm_available():
        raise HTTPException(status_code=503, detail="Onboarding LLM not configured (UNI_GPT_API_KEY missing).")
    try:
        from graph.onboarding import run_onboarding
        return run_onboarding(req.messages, req.user_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Onboarding error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
