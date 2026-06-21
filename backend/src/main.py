import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from database import init_db
from seed_data import seed_database
from orchestrator import Orchestrator

# Automate database creation and seeding on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist and the demo personas / pricing catalog are synced.
    # init_db() is idempotent (CREATE TABLE IF NOT EXISTS) and seed_database()
    # clears + re-inserts, so this is safe to run on every startup.
    print("Initializing Postgres schema and syncing pricing catalog + personas...")
    init_db()
    seed_database()
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

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "DB MoveOptimizer Agent Sandbox Backend",
        "version": "1.0.0"
    }

@app.get("/api/personas")
def get_personas():
    """
    Returns the list of seeded customer personas to let users switch profiles in the simulator.
    """
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, db_customer_id, name, preferences FROM users")
    rows = cursor.fetchall()
    
    personas = []
    for row in rows:
        r_dict = dict(row)
        r_dict["preferences"] = json.loads(r_dict["preferences"])
        
        # Fetch current subscriptions for this persona
        cursor.execute("SELECT service, monthly_cost_eur FROM subscriptions WHERE user_id = ?", (r_dict["id"],))
        subs = [dict(s) for s in cursor.fetchall()]
        r_dict["subscriptions"] = subs
        
        personas.append(r_dict)
        
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
