"""Unit tests for agent.analyst_agent — the single-call grounded memo.

No DB, no real LLM call (mocked): the knowledge-base reads are plain disk I/O over the
committed tariff markdown corpus, same as agent.tools.knowledge itself.
"""

import json
from unittest.mock import patch, MagicMock

from agent.analyst_agent import _relevant_tariff_docs, run_briefing


def _catalog_entry(name, markdown_ref=None):
    return {"id": name, "name": name, "markdown_ref": markdown_ref}


def test_markdown_ref_resolves_exact_doc_no_fuzzy_search():
    """When the catalog gives an exact markdown_ref, the plan's doc must come from
    that file directly — not from a name-based list_tariff_docs search that could
    return the wrong fare-class/age variant."""
    catalog_by_name = {
        "BahnCard 25, 2. Klasse": _catalog_entry(
            "BahnCard 25, 2. Klasse",
            "ÖPNV_Bahncards/2. Klasse/Bahncard 25/bahncard25_2klasse.md",
        )
    }
    with patch("agent.analyst_agent.list_tariff_docs") as mock_search:
        docs = _relevant_tariff_docs(["BahnCard 25, 2. Klasse"], catalog_by_name)
        mock_search.invoke.assert_not_called()

    assert len(docs) == 1
    assert docs[0]["id"] == "bahncard25_2klasse"
    assert len(docs[0]["text"]) > 0


def test_plans_without_markdown_ref_fall_back_to_fuzzy_search():
    """A plan with no markdown_ref on file still gets a doc via the name-based search
    fallback, so older/incomplete catalog rows don't just lose tariff grounding."""
    catalog_by_name = {"Deutschlandticket": _catalog_entry("Deutschlandticket", markdown_ref=None)}
    docs = _relevant_tariff_docs(["Deutschlandticket"], catalog_by_name)
    assert docs, "expected the fuzzy fallback to find at least one doc"


def test_unknown_plan_name_yields_no_doc_without_crashing():
    docs = _relevant_tariff_docs(["Some Plan Not In Any Catalog"], {})
    assert docs == []


def test_run_briefing_grounds_multiple_recommended_plans():
    """Two plans named in category_subscription_analysis (a currently-held
    Deutschlandticket, and a BahnCard 25 as another category's cheapest alternative)
    must each get a doc via their own markdown_ref — one plan's variants must not
    crowd out the other (the bug the fuzzy-search-only version had before
    markdown_ref was wired in)."""
    analyst_out = {
        "total_trips": 10,
        "category_subscription_analysis": [
            {
                "category": "public_transport",
                "current_subscriptions": [{"provider_plan_name": "Deutschlandticket"}],
                "cheapest_alternative": None,
            },
            {
                "category": "bike_sharing",
                "current_subscriptions": [],
                "cheapest_alternative": {"provider_plan_name": "BahnCard 25, 2. Klasse"},
            },
        ],
    }
    forecaster_out = {"forecast_horizon_days": 90}
    pricing_catalog = [
        _catalog_entry(
            "Deutschlandticket",
            "ÖPNV_Bahncards/Deutschlandticket/deutschlandticket_tarifbestimmungen.md",
        ),
        _catalog_entry(
            "BahnCard 25, 2. Klasse",
            "ÖPNV_Bahncards/2. Klasse/Bahncard 25/bahncard25_2klasse.md",
        ),
    ]

    fake_response = MagicMock()
    fake_response.content = json.dumps({"english": "memo", "german": "Memo"})

    with patch("agent.analyst_agent.get_llm") as mock_get_llm:
        mock_get_llm.return_value.invoke.return_value = fake_response
        run_briefing("Jane Doe", analyst_out, forecaster_out, pricing_catalog)

        messages = mock_get_llm.return_value.invoke.call_args[0][0]
        payload = json.loads(messages[1].content.split("\n\n", 1)[1])

    doc_ids = {d["id"] for d in payload["tariff_documents"]}
    assert "deutschlandticket_tarifbestimmungen" in doc_ids
    assert "bahncard25_2klasse" in doc_ids


def _minimal_briefing_args():
    return (
        "Jane Doe",
        {"total_trips": 10},
        {"forecast_horizon_days": 90},
        {"scenarios": []},
        [],
    )


def test_run_briefing_retries_once_on_language_mix_then_succeeds():
    """Reproduces the backend-review bug: first reply concatenates english+german into
    one field (joined by '---') and duplicates it into the other. A single retry with
    a clean, separated reply must be accepted without raising."""
    bad = MagicMock()
    bad.content = json.dumps(
        {"english": "English memo\n---\nGerman memo", "german": "English memo\n---\nGerman memo"}
    )
    good = MagicMock()
    good.content = json.dumps({"english": "English memo", "german": "German memo"})

    with patch("agent.analyst_agent.get_llm") as mock_get_llm:
        mock_get_llm.return_value.invoke.side_effect = [bad, good]
        english, german = run_briefing(*_minimal_briefing_args())

    assert english == "English memo"
    assert german == "German memo"
    assert mock_get_llm.return_value.invoke.call_count == 2


def test_run_briefing_raises_after_second_language_mix():
    """If the retry also mixes languages, run_briefing must raise so the caller
    (pipeline.py) falls back to the deterministic template memo instead of shipping a
    broken memo."""
    bad = MagicMock()
    bad.content = json.dumps({"english": "Same text", "german": "Same text"})

    with patch("agent.analyst_agent.get_llm") as mock_get_llm:
        mock_get_llm.return_value.invoke.side_effect = [bad, bad]
        try:
            run_briefing(*_minimal_briefing_args())
            assert False, "expected ValueError"
        except ValueError:
            pass

    assert mock_get_llm.return_value.invoke.call_count == 2
