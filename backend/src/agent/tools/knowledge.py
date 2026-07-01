"""OpenKnowledgeFormat (OKF) tariff knowledge base — dependency-free agentic RAG.

The 61 tariff/AGB markdown files under ``data/Markdownfiles Abos`` are the corpus.
Retrieval is by *navigation*, not embeddings: the agent lists the documents (each
with a short description) via ``list_tariff_docs``, then reads the ones it needs via
``read_tariff_doc``.

The file tree is the source of truth. ``build_index()`` regenerates ``index.md`` —
an OKF index whose YAML front-matter describes every document — as a committed,
human/LLM-readable artifact. The tools themselves scan the tree, so they work even
if ``index.md`` is stale or missing.
"""

import json
import os
from pathlib import Path

from langchain_core.tools import tool

_INDEX_FILENAME = "index.md"
_MAX_DESC = 200

# Resolve the knowledge-base directory across docker (CWD=/app) and local layouts.
# knowledge.py lives at backend/src/agent/tools/ → parents[4] is the repo root.
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    os.getenv("KNOWLEDGE_DIR"),
    os.path.join(os.getcwd(), "data", "Markdownfiles Abos"),
    str(_HERE.parents[4] / "data" / "Markdownfiles Abos"),  # repo-root data
    str(_HERE.parents[3] / "data" / "Markdownfiles Abos"),  # backend/data
]


def _kb_dir() -> Path | None:
    for cand in _CANDIDATES:
        if cand and Path(cand).is_dir():
            return Path(cand)
    return None


def _is_meta_line(line: str) -> bool:
    """Frontmatter fences, horizontal rules, table rows and short italic metadata
    (e.g. ``*Stand: April 2024*``) — skipped when picking a description."""
    if line in ("---", "***", "___"):
        return True
    if line.startswith("|") or line.startswith("!["):
        return True
    if line.startswith("*") and line.endswith("*") and len(line) < 80:
        return True
    return False


def _title_and_description(text: str, fallback_name: str) -> tuple[str, str]:
    """Derive a title (first ``# `` heading, else humanised filename) and a one-line
    description (first substantive prose line) from a markdown document."""
    default_title = fallback_name.replace("_", " ").strip()
    title = default_title
    description = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if title == default_title:
                title = line.lstrip("#").strip() or title
            continue
        if _is_meta_line(line):
            continue
        description = line.lstrip("*_ ").rstrip("*_ ")
        break
    if len(description) > _MAX_DESC:
        description = description[: _MAX_DESC - 1].rstrip() + "…"
    return title, description


_docs_cache: list | None = None


def _scan_docs() -> list:
    """Scan the knowledge base into ``[{id, path, category, title, description}]``.
    Cached (the corpus is static)."""
    global _docs_cache
    if _docs_cache is not None:
        return _docs_cache

    base = _kb_dir()
    if base is None:
        _docs_cache = []
        return _docs_cache

    docs = []
    for path in sorted(base.rglob("*.md")):
        if path.name == _INDEX_FILENAME:
            continue
        rel = path.relative_to(base)
        category = rel.parts[0] if len(rel.parts) > 1 else "general"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        title, description = _title_and_description(text, path.stem)
        docs.append(
            {
                "id": path.stem,
                "path": str(rel),
                "category": category,
                "title": title,
                "description": description,
            }
        )
    _docs_cache = docs
    return docs


def build_index() -> str:
    """(Re)generate ``index.md`` — the OKF index with YAML front-matter describing
    every document. Returns the path written. Run once and commit; not needed at
    runtime (the tools scan the tree directly)."""
    base = _kb_dir()
    if base is None:
        raise FileNotFoundError("Knowledge base directory not found.")
    docs = _scan_docs()

    def _q(value: str) -> str:
        return '"' + value.replace('"', "'") + '"'

    lines = ["---", "knowledge_base: DB mobility tariff & AGB documents",
             f"document_count: {len(docs)}", "documents:"]
    for d in docs:
        lines.append(f"  - id: {d['id']}")
        lines.append(f"    path: {_q(d['path'])}")
        lines.append(f"    category: {_q(d['category'])}")
        lines.append(f"    title: {_q(d['title'])}")
        lines.append(f"    description: {_q(d['description'])}")
    lines += ["---", "", "# DB Mobility Knowledge Base",
              "",
              "Tariff conditions, prices and terms (AGB) for DB mobility subscriptions.",
              "Use `list_tariff_docs` to browse and `read_tariff_doc` to open a document.",
              ""]
    for d in docs:
        lines.append(f"- **{d['title']}** (`{d['id']}`, {d['category']}) — {d['description']}")

    out = base / _INDEX_FILENAME
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


@tool
def list_tariff_docs(query: str = "") -> str:
    """List available DB tariff / AGB knowledge documents (BahnCards, Deutschlandticket,
    car/bike/e-scooter sharing terms, CO₂ tables), each with a short description.

    Args:
        query: optional keyword to narrow the list (matched against title,
            description, category and id). Empty lists everything.

    Returns:
        JSON list of {id, title, category, description}. Pass an id to
        `read_tariff_doc` to read the full document.
    """
    docs = _scan_docs()
    if not docs:
        return "Knowledge base is unavailable (no tariff documents found)."

    q = (query or "").lower().strip()
    if q:
        docs = [
            d
            for d in docs
            if q in d["title"].lower()
            or q in d["description"].lower()
            or q in d["category"].lower()
            or q in d["id"].lower()
        ]
    if not docs:
        return f"No tariff documents match '{query}'."

    listing = [
        {"id": d["id"], "title": d["title"], "category": d["category"], "description": d["description"]}
        for d in docs
    ]
    return json.dumps(listing, ensure_ascii=False, indent=2)


@tool
def read_tariff_doc(doc_id: str) -> str:
    """Read the full text of one DB tariff / AGB document.

    Args:
        doc_id: the id (or path) returned by `list_tariff_docs`.

    Returns:
        The document's full markdown content, or an error message if not found.
    """
    docs = _scan_docs()
    base = _kb_dir()
    if base is None or not docs:
        return "Knowledge base is unavailable."

    key = (doc_id or "").strip().lower()
    match = next((d for d in docs if d["id"].lower() == key), None)
    if match is None:
        match = next((d for d in docs if d["path"].lower().endswith(key)), None)
    if match is None:
        return f"No tariff document with id '{doc_id}'. Use list_tariff_docs to find valid ids."

    try:
        return (base / match["path"]).read_text(encoding="utf-8")
    except OSError:
        return f"Could not read document '{doc_id}'."


if __name__ == "__main__":
    print("Knowledge base:", _kb_dir())
    print("Documents:", len(_scan_docs()))
    print("Wrote:", build_index())
