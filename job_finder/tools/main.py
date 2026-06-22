"""Tools for the agents"""

from typing import Any, Callable

CONFIDENCE_THRESHOLD = 0.95
EXPORT_COLUMNS = ["id", "title", "url", "snippet"]


def normalize_role(raw: str) -> str:
    """Collapse internal/edge whitespace and title-case a raw role string.

    ``"  software   engineer "`` -> ``"Software Engineer"``.
    """
    return " ".join(raw.split()).title()


def is_confident(confidence: float) -> bool:
    """True when ``confidence`` meets ``CONFIDENCE_THRESHOLD`` (0.95, inclusive).

    The boundary is inclusive by decision: exactly 0.95 is confident, 0.94 is not.
    """
    return confidence >= CONFIDENCE_THRESHOLD


def extract_text(node_input: Any) -> str | None:
    """Pull the user text out of a workflow node input.

    The input may be a plain ``str`` (``START`` hands a ``str`` in google-adk 2.2.0)
    or a ``types.Content`` (e.g. a HITL resume). Returns ``None`` for empty/blank
    input so callers can route to a re-prompt.

    ``google.genai`` is imported lazily so this module stays out of the heavy stack
    and the fast test tier stays warning-free.
    """
    from google.genai import types

    if isinstance(node_input, types.Content):
        raw = node_input.parts[0].text if node_input.parts else ""
    else:
        raw = node_input if node_input else ""
    return raw if raw else None


def extract_ashby_link(link: str) -> tuple[str, str] | None:
    """Extract ``(id, clean_url)`` from an Ashby job URL, or ``None`` to skip.

    Shape: ``jobs.ashbyhq.com/{company}/{uuid}`` -> id at ``parts[4]``. Company
    landing pages (no uuid segment) and short paths return ``None``. The id has any
    query string (``?source=...``) stripped; the url is rebuilt from ``parts[:5]``.
    """
    parts = link.split("/")
    if len(parts) < 5 or not parts[4]:
        return None
    job_post_id = parts[4].split("?")[0]
    return (job_post_id, "/".join(parts[:5]))


def extract_greenhouse_link(link: str) -> tuple[str, str] | None:
    """Extract ``(id, clean_url)`` from a Greenhouse job URL, or ``None`` to skip.

    Shape: ``boards.greenhouse.io/{company}/jobs/{numeric_id}`` -> id at
    ``parts[5]``. The query string is stripped *before* validating that the id is
    numeric (``.isdigit()``); non-numeric segments are skipped. The url is rebuilt
    from ``parts[:5]`` + the clean id.
    """
    parts = link.split("/")
    if len(parts) < 6:
        return None
    job_post_id = parts[5].split("?")[0]
    if not job_post_id.isdigit():
        return None

    return (job_post_id, "/".join(parts[:5]) + "/" + job_post_id)


def extract_lever_link(link: str) -> tuple[str, str] | None:
    """Extract ``(id, clean_url)`` from a Lever job URL, or ``None`` to skip.

    Shape: ``jobs.lever.co/{company}/{uuid}`` -> id at ``parts[4]``. This is the
    same path shape as Ashby *by coincidence, not contract* — kept deliberately
    duplicated so either vendor's URL scheme can change independently.

    Known open issue: this validates ``parts[4]`` *before* stripping the query
    string, so ``.../netflix/?lever-origin=x`` yields an id of ``""``. Consciously
    deferred; fix is to clean-then-check like ``extract_greenhouse_link``.
    """
    parts = link.split("/")
    if len(parts) < 5 or not parts[4]:
        return None
    job_post_id = parts[4].split("?")[0]
    return (job_post_id, "/".join(parts[:4]) + "/" + job_post_id)


def parse_page(
    organic_results: list[dict],
    extract_link: Callable[[str], tuple[str, str] | None],
) -> list[dict]:
    """Map SerpAPI ``organic_results`` to ``{title, url, snippet, id}`` dicts.

    ``extract_link`` is the per-ATS extractor (injected, not chosen here): it returns
    ``(id, clean_url)`` or ``None``. Entries the extractor rejects (landing pages,
    malformed URLs) are skipped. ``date_added``/``job_position`` are *not* stamped here
    — that keeps this pure and deterministic; the caller enriches as needed.
    """
    posts = []
    for job_post in organic_results:
        result = extract_link(job_post["link"])
        if result is None:
            continue
        job_post_id, url = result
        posts.append(
            {
                "title": job_post["title"],
                "url": url,
                "snippet": job_post["snippet"],
                "id": job_post_id,
            }
        )
    return posts


def dedupe_posts(posts: list[dict]) -> list[dict]:
    """Drop duplicate posts keyed on ``id``; the first copy wins.

    Insertion order is preserved (a dict with insert-if-absent). Dedup is
    **per-board only**: the same job cross-posted on two ATSes has two different ids
    and is intentionally kept as two entries. Used at the crawl aggregation point,
    where pagination overlap produces real duplicates.
    """
    deduped = {}
    for post in posts:
        if post["id"] not in deduped:
            deduped[post["id"]] = post
    return list(deduped.values())


def posts_to_rows(posts: list[dict]) -> list[list]:
    """Turn post dicts into the ``list[list]`` shape ``gspread`` writes to a sheet.

    Returns a header row followed by one row per post. ``EXPORT_COLUMNS`` is the
    single source of truth for both column order and header labels — each row is
    built by walking it, so reordering the constant reorders the data too. An empty
    ``posts`` yields header-only (a tab with columns, no rows). A missing key yields
    an empty cell (``p.get(e, "")``) so the row survives — degrades per-cell, not
    per-row. ``list[list]`` over CSV strings on purpose: gspread escapes each cell,
    so a comma inside a snippet stays in one column.
    """
    rows = [EXPORT_COLUMNS]
    for p in posts:
        row = [p.get(e, "") for e in EXPORT_COLUMNS]
        rows.append(row)
    return rows
