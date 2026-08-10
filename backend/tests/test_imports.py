"""Import/route smoke test — the safety net.

Catches the class of bug that hit this session: a FastAPI handler lazily imports a
symbol (e.g. ``from agent.advisor import run_turn``) that has silently
disappeared, so the endpoint 500s only when actually called. These tests import each
module and assert the exact symbols the handlers depend on still exist, and that
``main`` imports and registers the key routes.

Importing ``main`` is DB-safe: ``ping_db`` runs only inside the FastAPI lifespan, not
at import time.
"""

import importlib

import pytest

# (module, attribute) pairs the API handlers import — several are lazy in-handler
# imports, so a plain "import main" would NOT surface a missing one.
HANDLER_DEPS = [
    ("agent.advisor", "opening_briefing"),       # the chat handler's turn-0 import
    ("agent.advisor", "run_turn"),               # the chat handler's follow-up import
    ("agent.pipeline", "run_analysis"),
    ("agent.engines", "analyze_portfolio"),
    ("agent.llm_steps.forecast_reasoner", "forecast"),  # forecaster endpoints import it here now
    ("agent.engines", "template_memos"),
    ("agent.context", "load_context"),
    ("register_endpoint", "register"),
    ("register_endpoint", "complete_onboarding"),
    ("profile_endpoint", "get_profile"),
    ("profile_endpoint", "update_profile"),
    ("auth_utils", "verify_password"),
]

EXPECTED_ROUTES = {
    "/api/analyze",
    "/api/chat/{session_id}",
    "/api/login",
    "/api/register",
    "/api/onboarding/{user_id}/complete",
    "/api/personas",
    "/api/profile/{user_id}",
    "/api/recommendations/{rec_id}/approve",
}


@pytest.mark.parametrize("module_name, attr", HANDLER_DEPS)
def test_handler_dependency_importable(module_name, attr):
    module = importlib.import_module(module_name)
    assert hasattr(module, attr), f"{module_name}.{attr} is missing — a handler import would 500"


def test_app_imports_and_registers_routes():
    main = importlib.import_module("main")
    paths = {getattr(r, "path", None) for r in main.app.routes}
    missing = EXPECTED_ROUTES - paths
    assert not missing, f"routes not registered: {missing}"
