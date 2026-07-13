"""Link-screening glue: follow each collected post to its ATS JSON API, read the
job's country + remote flag, and drop dead / wrong-locale posts via ``should_keep``.

This is **not** pure (it does network I/O) and is **not** in the fast unit-test
tier. It is kept out of ``agent.py`` / ``google.adk`` on purpose so it can be
exercised headlessly against the real APIs (``python -m job_finder.verify_screen``)
instead of only through ``adk web``. ``screen_node`` in ``agent.py`` is a thin
adapter over ``screen_posts``.

Per-vendor asymmetry (verified live, see the design amendment 2026-07-13):
- **Lever / Greenhouse** — single-job-by-id endpoints; HTTP 404 = dead.
- **Ashby** — board-level endpoint (all jobs for a company). We fetch each unique
  company's board once, then look each post's ``id`` up locally; ``id`` absent
  from the board = the posting is gone (dead).
"""

import asyncio

import httpx

from .main import (
    should_keep,
    extract_lever_fields,
    extract_ashby_fields,
    extract_greenhouse_fields,
)

CONCURRENCY = 10
TIMEOUT = 15
_HEADERS = {"User-Agent": "job_finder link screener"}

LEVER = "jobs.lever.co"
GREENHOUSE = "boards.greenhouse.io"
ASHBY = "jobs.ashbyhq.com"


def _split(url: str) -> tuple[str, str]:
    """``https://{domain}/{company}/...`` -> ``(domain, company)``."""
    parts = url.split("/")
    return parts[2], parts[3]


async def _get_json(client: httpx.AsyncClient, url: str) -> tuple[int, dict | None]:
    """GET ``url`` -> ``(status_code, parsed_json | None)``.

    Any network error/timeout maps to the ``0`` sentinel (``is_dead`` treats it as
    dead). A non-200 status returns ``(status, None)``; a 200 with unparseable body
    returns ``(200, None)`` (screened as unknown -> kept, per the keep-on-unknown
    rule).
    """
    try:
        resp = await client.get(url)
    except httpx.HTTPError:
        return 0, None
    if resp.status_code != 200:
        return resp.status_code, None
    try:
        return 200, resp.json()
    except ValueError:
        return 200, None


async def _fetch_ashby_board(client: httpx.AsyncClient, company: str) -> dict:
    """Return ``{job_id: job_dict}`` for an Ashby company board; ``{}`` on failure."""
    _, data = await _get_json(
        client, f"https://api.ashbyhq.com/posting-api/job-board/{company}"
    )
    if not data:
        return {}
    return {job["id"]: job for job in data.get("jobs", []) if job.get("id")}


async def _decide(client, post: dict, target: str, ashby_boards: dict) -> bool:
    """Screen one post -> keep (``True``) / drop (``False``)."""
    domain, company = _split(post["url"])
    job_id = post["id"]

    if domain == LEVER:
        status, data = await _get_json(
            client, f"https://api.lever.co/v0/postings/{company}/{job_id}"
        )
        country, is_remote = extract_lever_fields(data) if data else (None, False)
        return should_keep(status, country, is_remote, target)

    if domain == GREENHOUSE:
        status, data = await _get_json(
            client, f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
        )
        country, is_remote = extract_greenhouse_fields(data) if data else (None, False)
        return should_keep(status, country, is_remote, target)

    if domain == ASHBY:
        job = ashby_boards.get(company, {}).get(job_id)
        if job is None:
            return should_keep(404, None, False, target)  # id absent -> gone
        country, is_remote = extract_ashby_fields(job)
        return should_keep(200, country, is_remote, target)

    return True  # unknown domain -> keep (never drop what we can't classify)


async def screen_posts(posts: list[dict], target: str) -> list[dict]:
    """Follow each post's ATS API and return only live, in-locale (or remote) posts.

    Concurrency is bounded by a semaphore. Ashby company boards are pre-fetched
    once each. An unexpected error while screening a single post keeps that post
    (never silently drop a possibly-good one on a glue bug).
    """
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        ashby_companies = {
            _split(p["url"])[1] for p in posts if _split(p["url"])[0] == ASHBY
        }
        boards = {}
        if ashby_companies:
            fetched = await asyncio.gather(
                *(_fetch_ashby_board(client, c) for c in ashby_companies)
            )
            boards = dict(zip(ashby_companies, fetched))

        sem = asyncio.Semaphore(CONCURRENCY)

        async def screen(post):
            async with sem:
                try:
                    return post, await _decide(client, post, target, boards)
                except Exception:
                    return post, True

        decided = await asyncio.gather(*(screen(p) for p in posts))

    return [post for post, keep in decided if keep]
