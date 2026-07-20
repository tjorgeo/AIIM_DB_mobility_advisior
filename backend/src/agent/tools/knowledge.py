"""OpenKnowledgeFormat (OKF) tariff knowledge base — dependency-free agentic RAG.

The tariff/AGB markdown files under ``data/Markdownfiles Abos`` are the corpus. Retrieval
is by *navigation*, not embeddings: the agent lists the documents (each with a ``type``,
``tags`` and a short description) via ``list_tariff_docs``, then reads the ones it needs
via ``read_tariff_doc``.

The corpus follows Google Cloud's **Open Knowledge Format** (OKF v0.1, Apache-2.0): each
concept document carries YAML front-matter whose only required field is ``type``, plus the
recommended ``title`` / ``description`` / ``tags`` / ``timestamp``. The reserved
``index.md`` (front-matter-free, per the spec) is a progressive-disclosure listing.

The front-matter is the source of truth for a document's metadata; ``build_index()``
*seeds* conformant front-matter into any doc that lacks it (inferring ``type``/``tags``
from the folder + filename) and regenerates ``index.md``. The tools scan the tree
directly and fall back to a prose heuristic for any doc still missing front-matter, so
they work even if ``index.md`` is stale or a document was hand-added without metadata.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

_INDEX_FILENAME = "index.md"
_LOG_FILENAME = "log.md"  # reserved by OKF (chronological history); not scanned as a concept
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


# --- OKF front-matter --------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Split an OKF document into ``(frontmatter_dict, body)``.

    Returns ``(None, text)`` when there is no leading ``---`` fenced block. The parser
    is intentionally minimal (no YAML dependency): it handles the flat ``key: value``
    and inline-list ``tags: [a, b]`` shapes this module emits, which is all OKF's
    front-matter needs.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, text

    fm: dict = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key] = val.strip("\"'")
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return fm, body


def _is_meta_line(line: str) -> bool:
    """Frontmatter fences, horizontal rules, table rows and short italic/bold metadata
    (e.g. ``*Stand: April 2024*``, ``**Quelle:** …``) — skipped when picking a description."""
    if line in ("---", "***", "___"):
        return True
    if line.startswith("|") or line.startswith("!["):
        return True
    if line.startswith("**") and ":" in line[:40]:
        return True
    if line.startswith("*") and line.endswith("*") and len(line) < 80:
        return True
    return False


def _title_and_description(body: str, fallback_name: str) -> tuple[str, str]:
    """Derive a title (first ``# `` heading, else humanised filename) and a one-line
    description (first substantive prose line) from a markdown body. The prose-heuristic
    fallback for documents without OKF front-matter."""
    default_title = fallback_name.replace("_", " ").strip()
    title = default_title
    description = ""
    for raw in body.splitlines():
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


# Canonical travel-category slugs, shared with the analysis pipeline / prompt.
_CATEGORY_SLUG = {
    "Bike Sharing": "bike_sharing",
    "Car Sharing": "car_sharing",
    "E-Scooter": "e_scooter",
    "ÖPNV_Bahncards": "long_distance_rail",  # Deutschlandticket special-cased below
}
_AGB_MARKERS = ("agb", "nutzungsbeding", "nutzungsbestimm", "mietbeding", "tarifbestimmung")
_PRICING_MARKERS = ("pricing", "preis", "tarif", "gebuehren", "kosten")


def _infer_type_and_tags(rel: Path) -> tuple[str, list[str]]:
    """Infer an OKF ``type`` and ``tags`` from a document's path — the seed values used
    when a doc has no front-matter yet. ``rel`` is relative to the KB root."""
    parts = rel.parts
    top = parts[0] if parts else "general"
    stem = rel.stem.lower()

    is_deutschlandticket = "deutschlandticket" in "/".join(parts).lower()
    category = "public_transport" if is_deutschlandticket else _CATEGORY_SLUG.get(top, "general")

    # provider: the sharing folder (parts[1]) or a rail label.
    if top == "ÖPNV_Bahncards":
        provider = "deutschlandticket" if is_deutschlandticket else "bahncard"
    else:
        provider = parts[1] if len(parts) > 2 else top.lower().replace(" ", "_")

    if any(m in stem for m in _AGB_MARKERS):
        doc_type = "AGB"
    elif "uebersicht" in stem:
        doc_type = "Overview"
    elif any(m in stem for m in _PRICING_MARKERS):
        doc_type = "Pricing"
    elif top == "ÖPNV_Bahncards":
        doc_type = "Tariff"
    else:
        doc_type = "Reference"

    tags = [category, provider]
    if "1klasse" in stem or "1. klasse" in "/".join(parts).lower():
        tags.append("first_class")
    if "2klasse" in stem or "2. klasse" in "/".join(parts).lower():
        tags.append("second_class")
    # de-dup, preserve order (set.add returns None, so the first occurrence is kept)
    seen: set = set()
    return doc_type, [t for t in tags if t and not (t in seen or seen.add(t))]


def _extract_resource(body: str) -> str:
    """Best-effort canonical URI from a ``**Quelle:** <url>`` line, else empty."""
    for raw in body.splitlines()[:15]:
        line = raw.strip()
        low = line.lower()
        if low.startswith("**quelle:**") or low.startswith("quelle:"):
            after = line.split(":", 1)[1] if ":" in line else ""
            for tok in after.replace("*", " ").split():
                if tok.startswith("http"):
                    return tok
    return ""


# --- Scan --------------------------------------------------------------------


_docs_cache: list | None = None


def _doc_metadata(text: str, rel: Path) -> dict:
    """Resolve one document's ``{type, title, description, tags, resource}`` — from OKF
    front-matter when present, otherwise from inferred type/tags + prose heuristic."""
    fm, body = _parse_frontmatter(text)
    inferred_type, inferred_tags = _infer_type_and_tags(rel)
    heur_title, heur_desc = _title_and_description(body, rel.stem)
    if fm:
        return {
            "type": fm.get("type") or inferred_type,
            "title": fm.get("title") or heur_title,
            "description": (fm.get("description") or heur_desc)[:_MAX_DESC],
            "tags": fm.get("tags") if isinstance(fm.get("tags"), list) else inferred_tags,
            "resource": fm.get("resource", ""),
        }
    return {
        "type": inferred_type,
        "title": heur_title,
        "description": heur_desc,
        "tags": inferred_tags,
        "resource": _extract_resource(body),
    }


def _scan_docs() -> list:
    """Scan the knowledge base into
    ``[{id, path, category, type, title, description, tags}]``. Cached (the corpus is
    static)."""
    global _docs_cache
    if _docs_cache is not None:
        return _docs_cache

    base = _kb_dir()
    if base is None:
        _docs_cache = []
        return _docs_cache

    docs = []
    for path in sorted(base.rglob("*.md")):
        if path.name in (_INDEX_FILENAME, _LOG_FILENAME):
            continue
        rel = path.relative_to(base)
        category = rel.parts[0] if len(rel.parts) > 1 else "general"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _doc_metadata(text, rel)
        docs.append({
            "id": path.stem,
            "path": str(rel),
            "category": category,
            "type": meta["type"],
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
        })
    _docs_cache = docs
    return docs


# --- Index / front-matter seeding (build step, not runtime) ------------------


def _fm_block(meta: dict, rel: Path) -> str:
    """Render an OKF front-matter block (required ``type`` + recommended fields)."""

    def _q(value: str) -> str:
        return '"' + str(value).replace('"', "'") + '"'

    lines = ["---", f"type: {meta['type']}", f"title: {_q(meta['title'])}"]
    if meta.get("description"):
        lines.append(f"description: {_q(meta['description'])}")
    if meta.get("tags"):
        lines.append("tags: [" + ", ".join(meta["tags"]) + "]")
    if meta.get("resource"):
        lines.append(f"resource: {meta['resource']}")
    lines.append(f"timestamp: {meta.get('timestamp')}")
    lines.append("---")
    return "\n".join(lines)


def seed_frontmatter() -> int:
    """Prepend OKF front-matter to every concept doc that lacks it. Idempotent — a doc
    that already opens with ``---`` is left untouched. Returns the number of files
    written. Run once and commit; not needed at runtime."""
    base = _kb_dir()
    if base is None:
        raise FileNotFoundError("Knowledge base directory not found.")

    written = 0
    for path in sorted(base.rglob("*.md")):
        if path.name in (_INDEX_FILENAME, _LOG_FILENAME):
            continue
        rel = path.relative_to(base)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _body = _parse_frontmatter(text)
        if fm is not None:
            continue  # already OKF-conformant
        meta = _doc_metadata(text, rel)
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()
        meta["timestamp"] = ts
        block = _fm_block(meta, rel)
        path.write_text(block + "\n\n" + text.lstrip("\n"), encoding="utf-8")
        written += 1

    global _docs_cache
    _docs_cache = None  # corpus changed on disk
    return written


def build_index() -> str:
    """(Re)generate the OKF-conformant reserved ``index.md`` — **no** front-matter, a
    progressive-disclosure listing grouped by category with
    ``* [Title](path) - description`` entries (OKF index convention). Seeds document
    front-matter first (see :func:`seed_frontmatter`). Returns the path written. Run once
    and commit; not needed at runtime (the tools scan the tree directly)."""
    base = _kb_dir()
    if base is None:
        raise FileNotFoundError("Knowledge base directory not found.")
    seed_frontmatter()
    docs = _scan_docs()

    lines = [
        "# DB Mobility Knowledge Base",
        "",
        "Tariff conditions, prices and terms (AGB) for DB mobility subscriptions, in "
        "[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog).",
        "Browse with `list_tariff_docs`, then open a document with `read_tariff_doc`.",
        "",
    ]
    by_category: dict = {}
    for d in docs:
        by_category.setdefault(d["category"], []).append(d)
    for category in sorted(by_category):
        lines.append(f"## {category}")
        lines.append("")
        for d in sorted(by_category[category], key=lambda x: x["title"].lower()):
            desc = f" - {d['description']}" if d["description"] else ""
            # Angle-bracket the destination so paths containing spaces are valid links.
            lines.append(f"* [{d['title']}](<{d['path']}>) ({d['type']}, `{d['id']}`){desc}")
        lines.append("")

    out = base / _INDEX_FILENAME
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


# --- Tools -------------------------------------------------------------------


@tool
def list_tariff_docs(query: str = "") -> str:
    """Browse the DB tariff / AGB knowledge base (BahnCards, Deutschlandticket, car / bike /
    e-scooter sharing terms, CO₂ tables). Returns each document's id, type, title, tags and
    a short description — the map you navigate before reading.

    Call this (then `read_tariff_doc`) for **any** question about tariff conditions,
    discounts, class tiers, deposits, cancellation or contract terms — and for **any
    comparison between two or more providers or services** (e.g. "which car-sharing is
    cheapest for me", "compare Sixt Share vs teilAuto vs Miles", "what's the difference
    between these bike plans"). The customer's analysis snapshot does NOT hold cross-
    provider conditions, so answer such questions from the docs, not from memory.

    Args:
        query: optional keyword to narrow the list (matched against title, description,
            type, tags, category and id). Empty lists everything.

    Returns:
        JSON list of {id, type, title, category, tags, description}. Pass an id to
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
            or q in d["type"].lower()
            or q in d["category"].lower()
            or q in d["id"].lower()
            or any(q in t.lower() for t in d.get("tags", []))
        ]
    if not docs:
        return f"No tariff documents match '{query}'."

    listing = [
        {
            "id": d["id"],
            "type": d["type"],
            "title": d["title"],
            "category": d["category"],
            "tags": d.get("tags", []),
            "description": d["description"],
        }
        for d in docs
    ]
    return json.dumps(listing, ensure_ascii=False, indent=2)


@tool
def read_tariff_doc(doc_id: str) -> str:
    """Read the full text of one DB tariff / AGB knowledge document (its OKF front-matter
    plus the tariff conditions, prices and terms). Use this after `list_tariff_docs` to
    ground any answer about a provider's conditions or any comparison between providers —
    quote the figures and terms you read rather than recalling them.

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
    print("Seeded front-matter into:", seed_frontmatter(), "docs")
    print("Wrote:", build_index())
